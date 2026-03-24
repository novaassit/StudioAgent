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
        print(f"\n🚀 StudioAgent 기동 완료")
        print(f"🤖 모델: {MODEL_NAME}")
        print("-" * 50)
        self.history = [
            {"role": "system", "content": """너는 시니어 코딩 에이전트다. 
            - 반드시 JSON으로 응답하라.
            - 한 번에 하나의 Action만 수행하라.
            - 코드 수정 시 먼저 코드를 읽고(read_file), 분석 후 수정(write_file)하라.
            """}
        ]

    def call_llm(self):
        try:
            payload = {"model": MODEL_NAME, "messages": self.history}
            response = requests.post(f"{LM_STUDIO_API_BASE}/chat/completions", json=payload, timeout=120)
            if response.status_code != 200:
                print(f"\n❌ 서버 에러 ({response.status_code}): {response.text}")
                return None
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
            if not raw_response:
                print("\n⚠️ 서버에서 응답이 없습니다. 종료합니다.")
                break
                
            json_str = extract_json_robustly(raw_response)
            try:
                if not json_str: raise ValueError("JSON 블록을 찾을 수 없습니다.")
                llm_response = json.loads(json_str)
            except Exception as e:
                print(f"\n⚠️ 파싱 실패: {e}")
                print(f"--- 원문 ---\n{raw_response[:200]}...\n------------")
                self.history.append({"role": "system", "content": "오류: JSON 형식을 지켜주세요."})
                continue
            
            thought = llm_response.get('thought', '진행 중...')
            print(f"\r🤔 생각: {thought}")
            
            if "final_answer" in llm_response:
                print(f"\n🏁 완료: {llm_response['final_answer']}")
                break
                
            action = llm_response.get("action")
            if action:
                # action이 문자열인 경우와 딕셔너리인 경우 모두 대응
                if isinstance(action, str):
                    name = action
                    args = {}
                else:
                    name = action.get("name")
                    args = action.get("args", {})
                
                if not name:
                    print("⚠️ 도구 이름이 명시되지 않았습니다.")
                    continue
                    
                # 에일리어스 처리
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
                        print(f"   📖 파일 읽기 성공: {path}")
                    else:
                        result = "Error: Missing path"
                elif name == "write_file":
                    path = args.get('file_path') or args.get('filepath') or args.get('path') or args.get('filename') or args.get('file')
                    content = args.get('content') or args.get('code') or args.get('text')
                    if path:
                        result = write_file(file_path=path, content=content)
                        print(f"   📝 파일 작성 성공: {path}")
                    else:
                        result = "Error: Missing path or content"
                elif name == "execute_command":
                    result = execute_command(**args)
                else:
                    result = f"Unknown tool: {name}"
                
                # 결과 가시화 (중요)
                display_result = (str(result)[:100] + "...") if len(str(result)) > 100 else result
                print(f"📊 결과: {display_result}")
                
                # 히스토리에 기록하여 다음 루프 유도
                self.history.append({"role": "assistant", "content": json.dumps(llm_response)})
                self.history.append({"role": "system", "content": f"Tool Result: {result}"})
            else:
                # 행동이 없는 경우 루프가 돌지 않으므로 히스토리에 추가 후 재시도
                self.history.append({"role": "assistant", "content": json.dumps(llm_response)})

if __name__ == "__main__":
    agent = StudioAgent()
    try:
        user_input = input("\n명령을 입력하세요 > ")
        agent.run(user_input)
    except KeyboardInterrupt:
        print("\n👋 종료")
