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
            {"role": "system", "content": """너는 정직하고 유능한 시니어 소프트웨어 엔지니어다.
            [엄격한 행동 지침]
            1. **현실 직시**: 도구 실행 결과가 'Error'라면 절대로 성공했다고 거짓말하지 마라. 에러 원인을 분석하고 다시 시도하라.
            2. **경로 제한**: 오직 현재 디렉토리('.') 내의 파일만 다루어라. 외부 경로(예: /mnt/data)를 추측하지 마라.
            3. **도구 사용**: 
               - 폴더 목록은 `list_files`를 사용하라. (args: {"directory": "."})
               - 파일 수정은 `replace_in_file`을 사용하라.
            4. **정직한 보고**: 모든 작업이 실제로 성공했을 때만 `final_answer`를 출력하라.
            """}
        ]
        self.last_action_key = ""
        self.last_action_count = 0

    def call_llm(self, retry_count=3):
        for attempt in range(retry_count):
            try:
                if len(self.history) > 20:
                    self.history = [self.history[0]] + self.history[-10:]
                
                payload = {"model": MODEL_NAME, "messages": self.history, "temperature": 0.1} # 더 낮은 온도로 환각 방지
                response = requests.post(f"{LM_STUDIO_API_BASE}/chat/completions", json=payload, timeout=120)
                
                if response.status_code == 200:
                    content = response.json()['choices'][0]['message']['content']
                    if content and content.strip(): return content
                    self.history.append({"role": "user", "content": "응답이 비어 있습니다. 현재 상황에서 필요한 도구를 JSON으로 호출하세요."})
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
                if isinstance(action, str): name, args = action, {}
                else: name, args = action.get("name"), action.get("args", {})
                
                # 에일리어스 확장
                if name in ["list_directory", "ls", "dir"]: name = "list_files"
                if name in ["edit_file", "patch_file", "replace"]: name = "replace_in_file"
                if name in ["read_code", "get_code"]: name = "read_file"
                
                # 중복 방지
                action_key = f"{name}:{json.dumps(args, sort_keys=True)}"
                if self.last_action_key == action_key:
                    self.history.append({"role": "user", "content": "방금 한 행동을 반복하지 마세요. 결과가 에러라면 다른 방법을 찾으세요."})
                    continue
                self.last_action_key = action_key

                print(f"🛠️ 실행: [{name}]")
                result = ""
                path = args.get('file_path') or args.get('filepath') or args.get('path') or args.get('filename')
                
                if name == "list_files": 
                    dir_path = args.get('directory') or "."
                    result = list_files(directory=dir_path)
                elif name == "read_file":
                    result = read_file(file_path=path) if path else "Error: path missing"
                    if not result.startswith("Error"): print(f"   📖 읽기 완료: {path}")
                elif name == "write_file":
                    content = args.get('content') or args.get('code')
                    result = write_file(file_path=path, content=content) if path and content else "Error: args missing"
                elif name == "replace_in_file":
                    old_text = args.get('old_text') or args.get('old_code') or args.get('search')
                    new_text = args.get('new_text') or args.get('new_code') or args.get('replace')
                    result = replace_in_file(file_path=path, old_text=old_text, new_text=new_text)
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
