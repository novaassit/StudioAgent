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

from tools import list_files, read_file, write_file, execute_command

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
            [필수 원칙]
            1. 반드시 JSON으로 응답하라: {"thought": "...", "action": {"name": "...", "args": {...}}}
            2. 파일 목록에 `index.html`만 있다면, 모든 JS/CSS 코드가 그 안에 포함되어 있다고 간주하고 즉시 `read_file`하라.
            3. 동일한 도구를 반복 호출하지 마라. 한 번 확인했다면 바로 다음 단계(분석 또는 수정)로 넘어가라.
            4. `tetris.py` 같은 존재하지 않는 파일을 추측해서 읽지 마라. 오직 `list_files`로 확인된 파일만 읽어라.
            """}
        ]
        self.last_action = None

    def call_llm(self, retry_count=3):
        for attempt in range(retry_count):
            try:
                payload = {"model": MODEL_NAME, "messages": self.history, "temperature": 0.2}
                response = requests.post(f"{LM_STUDIO_API_BASE}/chat/completions", json=payload, timeout=120)
                
                if response.status_code == 200:
                    content = response.json()['choices'][0]['message']['content']
                    if content and content.strip(): return content
                    
                    # 빈 응답 시 강제 유도
                    print(f"\n⚠️ 빈 응답 수신. 행동 지침 주입 중... ({attempt + 1}/{retry_count})")
                    self.history.append({"role": "user", "content": "응답이 없습니다. 방금 얻은 파일 목록을 바탕으로 바로 코드를 읽거나 수정하는 단계를 진행하세요. 생각과 행동을 JSON으로 답하세요."})
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
                self.history.append({"role": "user", "content": "오류: 반드시 유효한 JSON 형식으로만 응답하세요."})
                continue
            
            thought = llm_response.get('thought', '다음 단계 진행 중...')
            print(f"\r🤔 생각: {thought}")
            
            if "final_answer" in llm_response:
                print(f"\n🏁 완료: {llm_response['final_answer']}")
                break
                
            action = llm_response.get("action")
            if action:
                if isinstance(action, str): name, args = action, {}
                else: name, args = action.get("name"), action.get("args", {})
                
                # 무한 루프 방지: 동일 도구 연속 호출 감지
                current_action_key = f"{name}:{json.dumps(args, sort_keys=True)}"
                if self.last_action == current_action_key:
                    print(f"⚠️ 경고: 동일한 행동[{name}] 반복 감지. 대안 제시 중...")
                    self.history.append({"role": "user", "content": f"방금 {name}을(를) 이미 수행했습니다. 결과를 다시 확인하고, 이제는 실제로 코드를 읽거나 수정하는 Action을 취하세요."})
                    continue
                
                self.last_action = current_action_key

                # 에일리어스 처리
                if name in ["create_file", "update_file", "save_file"]: name = "write_file"
                if name in ["read_code", "get_code", "view_file"]: name = "read_file"
                
                print(f"🛠️ 실행: [{name}]")
                
                if name == "list_files": result = list_files(**args)
                elif name == "read_file":
                    path = args.get('file_path') or args.get('filepath') or args.get('path') or args.get('filename') or args.get('file')
                    if path:
                        if os.path.isdir(path): result = f"Error: '{path}'는 폴더입니다. 파일명을 입력하세요."
                        else:
                            result = read_file(file_path=path)
                            if result.startswith("Error"): print(f"   ❌ 읽기 실패: {path}")
                            else: print(f"   📖 읽기 완료: {path}")
                    else: result = "Error: file_path 누락"
                elif name == "write_file":
                    path = args.get('file_path') or args.get('filepath') or args.get('path') or args.get('filename') or args.get('file')
                    content = args.get('content') or args.get('code') or args.get('text')
                    if path and content:
                        result = write_file(file_path=path, content=content)
                        if result.startswith("Error"): print(f"   ❌ 작성 실패: {path}")
                        else: print(f"   📝 작성 완료: {path}")
                    else: result = "Error: 인자 누락"
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
