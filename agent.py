# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
# ]
# ///

import json
import requests
import os
import sys
import time

# 경로 설정
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

from tools import list_files, read_file, write_file, replace_in_file, execute_command

LM_STUDIO_API_BASE = "http://localhost:1234/v1"
MODEL_NAME = "qwen/qwen3-coder-next"

def extract_json_robustly(text):
    """중괄호 쌍을 맞춰 유효한 JSON 블록을 추출합니다. 문자열 내부 중괄호는 무시."""
    if not text: return None
    text = text.replace("```json", "").replace("```", "").strip()
    start_idx = text.find('{')
    if start_idx == -1: return None
    brace_count = 0
    in_string = False
    escape = False
    for i in range(start_idx, len(text)):
        c = text[i]
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == '{': brace_count += 1
        elif c == '}':
            brace_count -= 1
            if brace_count == 0: return text[start_idx:i+1]
    return None

# 알려진 도구 이름 집합
KNOWN_TOOLS = {"list_files", "read_file", "write_file", "replace_in_file", "execute_command", "final_answer"}
TOOL_ALIASES = {
    "list_directory": "list_files", "ls": "list_files",
    "edit_file": "replace_in_file", "patch": "replace_in_file",
    "create_file": "write_file", "save_file": "write_file", "update_file": "write_file",
    "run": "execute_command", "shell": "execute_command", "run_command": "execute_command", "exec": "execute_command",
}

def normalize_action(action):
    """LLM이 잘못된 형식으로 보낸 action을 정규화합니다.

    정상: {"name": "replace_in_file", "args": {"file_path": "..."}}
    비정상1: {"replace_in_file": {"file_path": "..."}}  → name이 key로 들어감
    비정상2: {"name": "replace_in_file", "file_path": "..."}  → args 없이 flat
    """
    if not isinstance(action, dict):
        return None, {}

    name = action.get("name", "")
    args = action.get("args", {})

    # 정상 형식
    if name and name in KNOWN_TOOLS or name in TOOL_ALIASES:
        if not args:
            # args가 없으면 name과 알려진 키를 제외한 나머지를 args로
            args = {k: v for k, v in action.items() if k not in ("name", "thought")}
        resolved = TOOL_ALIASES.get(name, name)
        return resolved, args

    # 비정상1: {"replace_in_file": {"file_path": "..."}} — 도구이름이 key로 들어온 경우
    for key in action:
        resolved = TOOL_ALIASES.get(key, key)
        if resolved in KNOWN_TOOLS:
            val = action[key]
            if isinstance(val, dict):
                return resolved, val
            else:
                return resolved, {}

    # name이 alias인 경우
    if name:
        resolved = TOOL_ALIASES.get(name, name)
        return resolved, args

    return name, args


class StudioAgent:
    def __init__(self):
        print(f"\n🚀 StudioAgent 기동 완료 | 모델: {MODEL_NAME}")
        print("-" * 50)
        self.system_prompt = """너는 최고의 시니어 소프트웨어 엔지니어다.

[응답 규칙]
반드시 아래 JSON 형식으로만 응답하라:
{"thought": "생각", "action": {"name": "도구명", "args": {"key": "value"}}}

작업이 완료되면 반드시 아래 형식으로 보고하라:
{"thought": "완료", "final_answer": "결과 요약"}

[사용 가능 도구]
1. list_files: 디렉토리 파일 목록 조회. args: {"directory": "."}
2. read_file: 파일 내용 읽기. args: {"file_path": "경로"}
3. write_file: 새 파일 생성 또는 전체 덮어쓰기. args: {"file_path": "경로", "content": "내용"}
4. replace_in_file: 기존 파일의 특정 텍스트 교체. args: {"file_path": "경로", "old_text": "원본", "new_text": "변경"}
5. execute_command: 쉘 명령어 실행. args: {"command": "명령어"}

[도구 선택 규칙]
- 새 파일 생성: write_file 사용
- 기존 파일 수정: replace_in_file 사용 (실패 시 read_file로 정확한 내용 확인 후 재시도)
- replace_in_file 실패 시: read_file로 현재 파일 내용을 먼저 확인하라

[완료 규칙]
- 파일 생성/수정 후 성공 메시지를 받으면 final_answer로 보고하라
- 불필요하게 같은 작업을 반복하지 마라
"""
        self.history = [{"role": "system", "content": self.system_prompt}]
        self.last_action = None
        self.last_result = None
        self.action_log = []
        self.consecutive_errors = 0  # 연속 오류 카운터

    def call_llm(self):
        """LLM을 한 번 호출합니다. 히스토리를 오염시키지 않습니다."""
        try:
            # 컨텍스트 압축
            if len(self.history) > 20:
                self.history = [self.history[0]] + self.history[-8:]

            payload = {"model": MODEL_NAME, "messages": self.history, "temperature": 0.5}
            response = requests.post(f"{LM_STUDIO_API_BASE}/chat/completions", json=payload, timeout=120)

            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                if content and content.strip():
                    # LLM 응답이 너무 길면 유효 JSON만 추출 (반복 생성 방지)
                    if len(content) > 4000:
                        extracted = extract_json_robustly(content)
                        if extracted:
                            content = extracted
                        else:
                            content = content[:4000]
                    return content
            return None
        except Exception as e:
            print(f"\n❌ LLM 호출 에러: {e}")
            return None

    def call_llm_with_retry(self):
        """LLM 호출. 빈 응답 시 힌트를 임시로 추가하여 재시도 (히스토리 오염 없음)."""
        result = self.call_llm()
        if result:
            return result

        print(f"\n⚠️ 빈 응답, 힌트와 함께 재시도...")
        if self.last_action and self.last_action[0] == "list_files":
            hint = '위 도구 결과를 바탕으로 다음 단계를 진행하세요. 파일 내용을 읽어야 합니다. JSON으로 응답하세요.'
        elif self.last_action and self.last_action[0] == "read_file":
            hint = '위 파일 내용을 바탕으로 수정하세요. JSON으로 응답하세요.'
        else:
            hint = '반드시 JSON 형식으로 응답하세요: {"thought": "생각", "action": {"name": "도구명", "args": {...}}}'

        self.history.append({"role": "user", "content": hint})
        result = self.call_llm()
        self.history.pop()

        if result:
            return result

        print(f"\n⚠️ 재시도 2...")
        if self.last_action and self.last_action[0] == "list_files":
            strong_hint = f'반드시 JSON으로 응답하라: {{"thought": "파일을 읽겠습니다", "action": {{"name": "read_file", "args": {{"file_path": "index.html"}}}}}}'
        elif self.last_action and self.last_action[0] == "read_file":
            strong_hint = '반드시 JSON으로 응답하라: {"thought": "코드를 수정하겠습니다", "action": {"name": "replace_in_file", "args": {"file_path": "파일명", "old_text": "원본", "new_text": "변경"}}}'
        else:
            strong_hint = '반드시 JSON으로 응답하라: {"thought": "파일을 확인하겠습니다", "action": {"name": "list_files", "args": {"directory": "."}}}'

        self.history.append({"role": "user", "content": strong_hint})
        result = self.call_llm()
        self.history.pop()

        return result

    def execute_tool(self, name, args):
        """도구를 실행하고 결과를 반환합니다."""
        path = args.get('file_path') or args.get('filepath') or args.get('path')

        if name == "list_files":
            return list_files(directory=args.get('directory', '.'))
        elif name == "read_file":
            return read_file(file_path=path)
        elif name == "write_file":
            return write_file(file_path=path, content=args.get('content', ''))
        elif name == "replace_in_file":
            return replace_in_file(file_path=path, old_text=args.get('old_text', ''), new_text=args.get('new_text', ''))
        elif name == "execute_command":
            return execute_command(command=args.get('command', ''))
        else:
            return f"Unknown tool: {name}. Available: list_files, read_file, write_file, replace_in_file, execute_command"

    def run(self, user_prompt):
        print(f"\n👤 User: {user_prompt}")
        self.history.append({"role": "user", "content": user_prompt})

        turn = 0
        empty_count = 0  # 연속 빈 응답 카운터
        while turn < 15:
            turn += 1
            print(f"\n⏳ [턴 {turn}] 에이전트 생각 중...", end="\r")
            raw_response = self.call_llm_with_retry()

            if not raw_response:
                empty_count += 1
                # LLM 무응답 → 마지막 도구 결과 기반 자동 진행
                if self.last_action and self.last_action[0] == "list_files" and self.last_result:
                    first_file = self.last_result.strip().split('\n')[0].strip()
                    if first_file:
                        print(f"\n🤖 자동 진행: LLM 무응답 → read_file({first_file}) 자동 실행")
                        result = read_file(file_path=first_file)
                        print(f"📊 결과: {str(result)[:60]}...")
                        self.last_action = ("read_file", first_file)
                        self.last_result = result
                        self.action_log.append(f"read_file({first_file}): OK")
                        auto_response = {"thought": f"{first_file} 파일을 읽어 내용을 확인합니다.", "action": {"name": "read_file", "args": {"file_path": first_file}}}
                        self.history.append({"role": "assistant", "content": json.dumps(auto_response, ensure_ascii=False)})
                        self.history.append({"role": "user", "content": f"도구 실행 결과:\n{result}\n\n위 결과를 바탕으로 수정이 필요한 부분을 찾아 replace_in_file로 수정하세요. JSON으로 응답하세요."})
                        empty_count = 0
                        continue
                if empty_count >= 3:
                    print(f"\n⚠️ LLM 연속 무응답 ({empty_count}회). 지금까지의 작업을 보고합니다.")
                    summary = "\n".join(self.action_log[-5:]) if self.action_log else "작업 없음"
                    print(f"📋 수행된 작업:\n{summary}")
                    break
                print(f"\n⚠️ LLM 무응답 ({empty_count}/3). 재시도...")
                continue

            # JSON 파싱
            json_str = extract_json_robustly(raw_response)
            try:
                if not json_str: raise ValueError("No JSON")
                llm_response = json.loads(json_str)
            except:
                self.consecutive_errors += 1
                # 연속 오류 3회 이상이면 이전 오류 메시지를 정리하고 하나만 유지
                if self.consecutive_errors >= 3:
                    # 히스토리에서 연속 오류 메시지 제거
                    while len(self.history) > 2 and self.history[-1].get("role") == "user" and "오류" in self.history[-1].get("content", ""):
                        self.history.pop()
                self.history.append({"role": "user", "content": 'JSON 형식 오류. 반드시 이 형식으로 응답: {"thought": "생각", "action": {"name": "도구명", "args": {...}}}'})
                continue

            self.consecutive_errors = 0  # 성공적으로 파싱되면 리셋
            empty_count = 0  # 빈 응답 카운터도 리셋

            thought = llm_response.get('thought', '진행 중...')
            print(f"\r🤔 생각: {thought}")

            # final_answer 처리 (top-level)
            if "final_answer" in llm_response:
                print(f"\n🏁 최종 보고: {llm_response['final_answer']}")
                break

            action = llm_response.get("action")
            if not action:
                # action이 없지만 self-healing 시도
                if "directory" in llm_response:
                    action = {"name": "list_files", "args": llm_response}
                elif "file_path" in llm_response:
                    action = {"name": "read_file", "args": llm_response}
                else:
                    self.history.append({"role": "assistant", "content": json.dumps(llm_response, ensure_ascii=False)})
                    continue

            # action 형식 정규화 (잘못된 형식 자동 복구)
            name, args = normalize_action(action)

            if not name:
                self.history.append({"role": "assistant", "content": json.dumps(llm_response, ensure_ascii=False)})
                self.history.append({"role": "user", "content": 'action 형식 오류. 올바른 형식: {"name": "도구명", "args": {"key": "value"}}'})
                continue

            # final_answer를 action으로 보낸 경우
            if name == "final_answer":
                answer = args.get("answer") or args.get("message") or args.get("result") or str(args)
                print(f"\n🏁 최종 보고: {answer}")
                break

            # 동일 도구+인자 반복 호출 감지 → 자동 실행
            path = args.get('file_path') or args.get('filepath') or args.get('path')
            # execute_command는 command 값으로 비교, 나머지는 path로 비교
            if name == "execute_command":
                action_key = args.get('command', '')
            else:
                action_key = path or args.get('directory', '')
            current_action = (name, action_key)
            if current_action == self.last_action:
                print(f"⚠️ 동일 도구 반복 감지: [{name}] → 자동 진행")
                if name == "list_files" and self.last_result:
                    first_file = self.last_result.strip().split('\n')[0].strip()
                    if first_file:
                        print(f"🤖 자동 진행: read_file({first_file})")
                        result = read_file(file_path=first_file)
                        print(f"📊 결과: {str(result)[:60]}...")
                        self.last_action = ("read_file", first_file)
                        self.last_result = result
                        self.action_log.append(f"read_file({first_file}): OK")
                        auto_response = {"thought": f"{first_file} 파일 내용을 확인합니다.", "action": {"name": "read_file", "args": {"file_path": first_file}}}
                        self.history.append({"role": "assistant", "content": json.dumps(auto_response, ensure_ascii=False)})
                        result_trimmed = str(result)[:1500] if len(str(result)) > 1500 else str(result)
                        self.history.append({"role": "user", "content": f"도구 실행 결과:\n{result_trimmed}\n\n위 결과를 바탕으로 수정할 부분을 찾아 replace_in_file로 수정하세요. JSON으로 응답하세요."})
                        continue
                elif name == "read_file":
                    # 파일이 잘렸던 경우, execute_command로 특정 라인 범위를 읽도록 안내
                    if self.last_result and "파일이 너무 길어" in str(self.last_result):
                        self.history.append({"role": "assistant", "content": json.dumps(llm_response, ensure_ascii=False)})
                        self.history.append({"role": "user", "content": f"파일이 길어서 잘렸습니다. execute_command로 특정 부분을 읽으세요. 예: grep -n 'dropInterval' {path} 또는 sed -n '200,300p' {path}"})
                        continue
                    self.history.append({"role": "assistant", "content": json.dumps(llm_response, ensure_ascii=False)})
                    self.history.append({"role": "user", "content": f"이미 {path} 파일을 읽었습니다. 이제 replace_in_file로 수정하거나 write_file로 덮어쓰세요. JSON으로 응답하세요."})
                    continue
                else:
                    self.history.append({"role": "assistant", "content": json.dumps(llm_response, ensure_ascii=False)})
                    self.history.append({"role": "user", "content": "같은 작업을 반복하고 있습니다. 다른 도구를 사용하거나 final_answer로 보고하세요."})
                    continue

            # 도구 실행
            print(f"🛠️ 실행: [{name}]")
            result = self.execute_tool(name, args)
            print(f"📊 결과: {str(result)[:60]}...")

            self.last_action = current_action
            self.last_result = result
            self.action_log.append(f"{name}({path or args.get('directory', '.')}): {str(result)[:50]}")
            self.history.append({"role": "assistant", "content": json.dumps(llm_response, ensure_ascii=False)})

            # 히스토리에 넣을 결과는 토큰 절약을 위해 길이 제한
            result_str = str(result)
            if len(result_str) > 1500:
                # 앞 800자 + ... + 뒤 500자 (핵심 코드는 보통 앞뒤에 있음)
                result_for_history = result_str[:800] + f"\n\n... (중략, 총 {len(result_str)}자) ...\n\n" + result_str[-500:]
            else:
                result_for_history = result_str

            if name == "replace_in_file" or name == "write_file":
                self.history.append({"role": "user", "content": f"도구 실행 결과:\n{result_for_history}\n\n수정이 완료되었으면 final_answer로 보고하세요. 추가 수정이 필요하면 계속하세요."})
            else:
                self.history.append({"role": "user", "content": f"도구 실행 결과:\n{result_for_history}\n\n위 결과를 바탕으로 다음 action을 JSON으로 응답하세요."})

if __name__ == "__main__":
    agent = StudioAgent()
    try:
        user_input = input("\n명령 입력 > ")
        if user_input: agent.run(user_input)
    except KeyboardInterrupt:
        print("\n👋 종료")
