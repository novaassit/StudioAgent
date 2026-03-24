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
            반드시 다음 JSON 형식을 엄격히 지켜 응답하라:
            {"thought": "생각", "action": {"name": "도구명", "args": {"인자": "값"}}}
            
            [규정]
            1. `read_file`이나 `write_file`을 쓸 때는 반드시 `args` 안에 `file_path`를 명시하라.
               예: {"action": {"name": "read_file", "args": {"file_path": "index.html"}}}
            2. 한 번에 한 단계씩만 진행하라.
            3. 코드를 수정하기 전에는 반드시 `read_file`로 내용을 먼저 확인하라.
            """}
        ]

    def call_llm(self):
        try:
            payload = {"model": MODEL_NAME, "messages": self.history}
            response = requests.post(f"{LM_STUDIO_API_BASE}/chat/completions", json=payload, timeout=120)
            if response.status_code != 200:
                print(f"\n❌ 서버 에러: {response.status_code}")
                return None
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"\n❌ 연결 에러: {e}")
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
                print(f"\n⚠️ 형식 재요청 중...")
                self.history.append({"role": "system", "content": "오류: 반드시 JSON 형식으로 응답하고, 도구 사용 시 args를 포함하세요."})
                continue
            
            thought = llm_response.get('thought', '분석 중...')
            print(f"\r🤔 생각: {thought}")
            
            if "final_answer" in llm_response:
                print(f"\n🏁 완료: {llm_response['final_answer']}")
                break
                
            action = llm_response.get("action")
            if action:
                if isinstance(action, str):
                    name, args = action, {}
                else:
                    name, args = action.get("name"), action.get("args", {})
                
                if name in ["create_file", "update_file", "save_file"]: name = "write_file"
                if name in ["read_code", "get_code", "view_file"]: name = "read_file"
                
                print(f"🛠️ 실행: [{name}]")
                result = ""
                
                if name == "list_files":
                    result = list_files(**args)
                elif name == "read_file":
                    path = args.get('file_path') or args.get('filepath') or args.get('path') or args.get('filename') or args.get('file')
                    if path:
                        result = read_file(file_path=path)
                        print(f"   📖 읽기 완료: {path}")
                    else:
                        result = "Error: 파일 경로(file_path)가 누락되었습니다. 어떤 파일을 읽을지 'args'에 명시하세요."
                elif name == "write_file":
                    path = args.get('file_path') or args.get('filepath') or args.get('path') or args.get('filename') or args.get('file')
                    content = args.get('content') or args.get('code') or args.get('text')
                    if path and content:
                        result = write_file(file_path=path, content=content)
                        print(f"   📝 작성 완료: {path}")
                    else:
                        result = "Error: file_path 또는 content가 누락되었습니다."
                elif name == "execute_command":
                    result = execute_command(**args)
                else:
                    result = f"Unknown tool: {name}"
                
                print(f"📊 결과: {str(result)[:50]}...")
                
                self.history.append({"role": "assistant", "content": json.dumps(llm_response)})
                self.history.append({"role": "system", "content": f"Tool Result: {result}"})
            else:
                self.history.append({"role": "assistant", "content": json.dumps(llm_response)})

if __name__ == "__main__":
    agent = StudioAgent()
    try:
        user_input = input("\n명령 입력 > ")
        agent.run(user_input)
    except KeyboardInterrupt:
        print("\n👋 종료")
