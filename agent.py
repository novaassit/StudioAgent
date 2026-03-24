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
            2. 수정은 `replace_in_file`을 우선 사용하라.
            3. 수정이 성공했다면 더 이상 파일을 읽지 말고 즉시 {"final_answer": "..."}를 출력하여 종료하라.
            """}
        ]
        self.last_action_key = ""
        self.last_action_count = 0

    def call_llm(self, retry_count=3):
        for attempt in range(retry_count):
            try:
                # 컨텍스트 압축: 히스토리가 길어지면 최신 10개만 유지
                if len(self.history) > 20:
                    print("\n💡 컨텍스트 압축 중...")
                    self.history = [self.history[0]] + self.history[-10:]
                
                payload = {"model": MODEL_NAME, "messages": self.history, "temperature": 0.2}
                response = requests.post(f"{LM_STUDIO_API_BASE}/chat/completions", json=payload, timeout=120)
                
                if response.status_code == 200:
                    content = response.json()['choices'][0]['message']['content']
                    if content and content.strip(): return content
                    print(f"\n⚠️ 빈 응답 수신... ({attempt + 1}/{retry_count})")
                    self.history.append({"role": "user", "content": "작업이 완료되었다면 final_answer를, 아니라면 다음 단계를 JSON으로 답하세요."})
                else:
                    print(f"\n❌ 서버 오류 ({response.status_code})")
                
                time.sleep(1)
            except Exception as e:
                print(f"\n❌ 에러: {e}")
                time.sleep(1)
        return None

    def run(self, user_prompt):
        print(f"\n👤 User: {user_prompt}")
        self.history.append({"role": "user", "content": user_prompt})
        
        while True:
            print("\n⏳ 에이전트 생각 중...", end="\r")
            raw_response = self.call_llm()
            if not raw_response: break
                
            json_str = extract_json_robustly(raw_response)
            try:
                if not json_str: raise ValueError("JSON missing")
                llm_response = json.loads(json_str)
            except:
                self.history.append({"role": "user", "content": "오류: 반드시 JSON 형식으로만 응답하세요."})
                continue
            
            thought = llm_response.get('thought', '진행 중...')
            print(f"\r🤔 생각: {thought}")
            
            if "final_answer" in llm_response:
                print(f"\n🏁 최종 보고: {llm_response['final_answer']}")
                break
                
            action = llm_response.get("action")
            if action:
                name, args = action.get("name"), action.get("args", {})
                if name in ["edit_file", "patch_file", "replace"]: name = "replace_in_file"
                if name in ["read_code", "get_code"]: name = "read_file"
                
                # 중복 방지
                action_key = f"{name}:{json.dumps(args, sort_keys=True)}"
                if self.last_action_key == action_key:
                    self.history.append({"role": "user", "content": "이미 수행한 동작입니다. 결과가 만족스럽다면 final_answer를 출력하세요."})
                    continue
                self.last_action_key = action_key

                print(f"🛠️ 실행: [{name}]")
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
                    result = replace_in_file(file_path=path, old_text=old_text, new_text=new_text)
                    if not result.startswith("Error"): print(f"   ✂️ 수정 완료: {path}")
                elif name == "execute_command": result = execute_command(**args)
                
                # 가시화
                display_result = (str(result)[:100] + "...") if len(str(result)) > 100 else result
                print(f"📊 결과: {display_result}")
                
                # 히스토리에는 요약본만 저장 (중요: 컨텍스트 절약)
                history_result = (str(result)[:500] + "\n...(중략)...") if len(str(result)) > 500 else result
                self.history.append({"role": "assistant", "content": json.dumps(llm_response)})
                self.history.append({"role": "system", "content": f"Tool Result: {history_result}"})
                
                # 수정 성공 시 모델에게 칭찬(?)과 함께 종료 유도
                if name == "replace_in_file" and not result.startswith("Error"):
                    self.history.append({"role": "system", "content": "수정이 성공했습니다! 이제 변경된 내용을 요약하여 final_answer를 출력하고 종료하세요."})

if __name__ == "__main__":
    agent = StudioAgent()
    try:
        user_input = input("\n무엇을 도와드릴까요? > ")
        if user_input: agent.run(user_input)
    except KeyboardInterrupt:
        print("\n👋 종료")
