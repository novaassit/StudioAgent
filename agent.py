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
    """중첩된 중괄호가 포함된 텍스트에서 가장 바깥쪽의 완성된 JSON 객체를 추출합니다."""
    if not text: return None
    
    # 마크다운 코드 블록 제거 시도 (있다면)
    text = text.replace("```json", "").replace("```", "").strip()
    
    start_idx = text.find('{')
    if start_idx == -1: return None
    
    brace_count = 0
    for i in range(start_idx, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                # 가장 바깥쪽 중괄호가 닫히는 지점까지 반환
                return text[start_idx:i+1]
    return None

class StudioAgent:
    def __init__(self):
        print(f"\n🚀 StudioAgent 기동 완료")
        print(f"🤖 모델: {MODEL_NAME}")
        print("-" * 50)
        
        self.history = [
            {"role": "system", "content": """너는 시니어 코딩 에이전트다. 
            [지침]
            - 반드시 JSON으로만 응답하라.
            - 한 번에 하나의 Action만 수행하라.
            - 코드 작성 시 index.html, style.css, script.js 순서로 하나씩 완성하라.
            
            [응답 형식]
            {"thought": "계획", "action": {"name": "도구명", "args": {...}}}
            """}
        ]

    def call_llm(self):
        try:
            payload = {"model": MODEL_NAME, "messages": self.history}
            response = requests.post(f"{LM_STUDIO_API_BASE}/chat/completions", json=payload, timeout=120)
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"\n❌ 서버 연결 실패: {e}")
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
                if not json_str: raise ValueError("No JSON found")
                llm_response = json.loads(json_str)
            except Exception as e:
                print(f"\n⚠️ 파싱 실패. 원인: {e}")
                print(f"--- 원문 일부 ---\n{raw_response[:300]}...\n----------------")
                self.history.append({"role": "system", "content": "오류: JSON 형식이 올바르지 않습니다. 중괄호 쌍을 확인하고 유효한 JSON만 응답하세요."})
                continue
            
            thought = llm_response.get('thought', '진행 중...')
            print(f"\r🤔 생각: {thought}")
            
            if "final_answer" in llm_response:
                print(f"\n🏁 완료: {llm_response['final_answer']}")
                break
                
            action = llm_response.get("action")
            if action:
                name, args = action["name"], action.get("args", {})
                
                # 도구 에일리어스 및 인자 호환성 처리
                if name in ["create_file", "update_file", "save_file"]: name = "write_file"
                if name in ["read_code", "get_code", "view_file"]: name = "read_file"
                
                print(f"🛠️ 실행: [{name}]")
                
                if name == "list_files": result = list_files(**args)
                elif name == "read_file": 
                    path = args.get('file_path') or args.get('filepath') or args.get('path') or args.get('filename') or args.get('file')
                    if path:
                        result = read_file(file_path=path)
                        print(f"   📖 파일 읽기 완료: {path}")
                    else:
                        result = "Error: Missing path for read_file"
                elif name == "write_file": 
                    path = args.get('file_path') or args.get('filepath') or args.get('path') or args.get('filename') or args.get('file')
                    content = args.get('content', '') or args.get('code', '') or args.get('text', '')
                    if path:
                        result = write_file(file_path=path, content=content)
                        print(f"   📝 파일 작성됨: {path}")
                    else:
                        result = "Error: Missing path"
                elif name == "execute_command": result = execute_command(**args)
                else: result = f"Unknown tool: {name}"
                
                self.history.append({"role": "assistant", "content": json.dumps(llm_response)})
                self.history.append({"role": "system", "content": f"Tool Result: {result}"})

if __name__ == "__main__":
    agent = StudioAgent()
    try:
        user_input = input("\n명령을 입력하세요 > ")
        agent.run(user_input)
    except KeyboardInterrupt:
        print("\n👋 종료")
