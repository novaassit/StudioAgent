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
    """중괄호 쌍을 맞춰 유효한 JSON 블록을 추출합니다."""
    if not text: return None
    text = text.replace("```json", "").replace("```", "").strip()
    start_idx = text.find('{')
    if start_idx == -1: return None
    brace_count = 0
    for i in range(start_idx, len(text)):
        if text[i] == '{': brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0: return text[start_idx:i+1]
    return None

class StudioAgent:
    def __init__(self):
        print(f"\n🚀 StudioAgent 기동 완료 | 모델: {MODEL_NAME}")
        print("-" * 50)
        self.history = [
            {"role": "system", "content": """너는 최고의 시니어 소프트웨어 엔지니어다.
            [필수 규칙]
            1. 반드시 JSON으로 응답하라: {"thought": "...", "action": {"name": "...", "args": {...}}}
            2. 파일 목록 확인: list_files / 파일 읽기: read_file / 전체 쓰기: write_file
            3. 특정 부분 수정: replace_in_file (args: file_path, old_text, new_text)
            4. `edit_file`이나 `patch_file`이 필요하면 `replace_in_file`을 사용하라.
            5. 한 번에 한 단계씩만 진행하라.
            """}
        ]
        self.last_action_count = 0
        self.last_action_key = ""

    def call_llm(self, retry_count=3):
        for attempt in range(retry_count):
            try:
                # 컨텍스트 관리: 너무 긴 히스토리 방지
                if len(self.history) > 20:
                    print("\n💡 대화가 너무 깁니다. 핵심 맥락만 유지합니다.")
                    self.history = [self.history[0], self.history[-3], self.history[-2], self.history[-1]]
                
                payload = {"model": MODEL_NAME, "messages": self.history, "temperature": 0.3}
                response = requests.post(f"{LM_STUDIO_API_BASE}/chat/completions", json=payload, timeout=120)
                
                if response.status_code == 200:
                    content = response.json()['choices'][0]['message']['content']
                    if content and content.strip(): return content
                    print(f"\n⚠️ 빈 응답 수신. 힌트 주입 중... ({attempt + 1}/{retry_count})")
                    self.history.append({"role": "user", "content": "응답이 비어 있습니다. 생각과 행동을 JSON으로 답해 주세요."})
                else:
                    print(f"\n❌ 서버 오류 ({response.status_code})")
                
                time.sleep(1)
            except Exception as e:
                print(f"\n❌ 에러: {e}. 재시도...")
                time.sleep(1)
        return None

    def run(self, user_prompt):
        print(f"\n👤 User: {user_prompt}")
        self.history.append({"role": "user", "content": user_prompt})
        
        while True:
            print("\n⏳ 에이전트 생각 중...", end="\r")
            raw_response = self.call_llm()
            
            if not raw_response:
                print("\n❌ 작업을 중단합니다. 서버를 확인하세요.")
                break
                
            json_str = extract_json_robustly(raw_response)
            try:
                if not json_str: raise ValueError("JSON missing")
                llm_response = json.loads(json_str)
            except:
                print(f"\n⚠️ 형식 오류 재교정 중...")
                self.history.append({"role": "user", "content": "오류: 반드시 JSON 형식으로만 응답하세요."})
                continue
            
            thought = llm_response.get('thought', '분석 중...')
            print(f"\r🤔 생각: {thought}")
            
            if "final_answer" in llm_response:
                print(f"\n🏁 완료: {llm_response['final_answer']}")
                break
                
            action = llm_response.get("action")
            if action:
                if isinstance(action, str): name, args = action, {}
                else: name, args = action.get("name"), action.get("args", {})
                
                # 에일리어스 및 정규화
                if name in ["edit_file", "patch_file", "replace", "replace_text"]: name = "replace_in_file"
                if name in ["create_file", "update_file", "save_file"]: name = "write_file"
                if name in ["read_code", "get_code"]: name = "read_file"
                
                # 중복 방지 로직 개선
                action_key = f"{name}:{json.dumps(args, sort_keys=True)}"
                if self.last_action_key == action_key:
                    self.last_action_count += 1
                else:
                    self.last_action_count = 0
                
                if self.last_action_count >= 2:
                    print(f"⚠️ 경고: 동일 행동[{name}] 반복 감지. 대안 제시 중...")
                    self.history.append({"role": "user", "content": f"이미 {name}을 여러 번 시도했지만 결과가 같거나 실패했습니다. 다른 파일이나 다른 도구를 사용해 보세요."})
                    self.last_action_count = 0
                    continue

                self.last_action_key = action_key
                print(f"🛠️ 실행: [{name}]")
                
                # 도구 실행
                result = ""
                path = args.get('file_path') or args.get('filepath') or args.get('path')
                
                if name == "list_files": result = list_files(**args)
                elif name == "read_file":
                    result = read_file(file_path=path) if path else "Error: path missing"
                    if not result.startswith("Error"): print(f"   📖 읽기 완료: {path}")
                elif name == "write_file":
                    content = args.get('content') or args.get('code')
                    result = write_file(file_path=path, content=content) if path and content else "Error: args missing"
                    if not result.startswith("Error"): print(f"   📝 작성 완료: {path}")
                elif name == "replace_in_file":
                    old_text = args.get('old_text') or args.get('old_code') or args.get('search')
                    new_text = args.get('new_text') or args.get('new_code') or args.get('replace')
                    result = replace_in_file(file_path=path, old_text=old_text, new_text=new_text) if path and old_text and new_text else "Error: args missing"
                    if not result.startswith("Error"): print(f"   ✂️ 수정 완료: {path}")
                elif name == "execute_command": result = execute_command(**args)
                else: result = f"Unknown tool: {name}"
                
                print(f"📊 결과: {str(result)[:60]}...")
                self.history.append({"role": "assistant", "content": json.dumps(llm_response)})
                self.history.append({"role": "system", "content": f"Tool Result: {result}"})
            else:
                self.history.append({"role": "assistant", "content": json.dumps(llm_response)})

if __name__ == "__main__":
    agent = StudioAgent()
    try:
        user_input = input("\n명령 입력 > ")
        if user_input: agent.run(user_input)
    except KeyboardInterrupt:
        print("\n👋 종료")
