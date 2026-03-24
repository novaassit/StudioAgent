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
        self.system_prompt = """너는 최고의 시니어 소프트웨어 엔지니어다.
        [응답 규칙 - 절대 준수]
        항상 아래 JSON 형식 하나만 출력하라:
        {
          "thought": "현재 상황 분석 및 계획",
          "action": {
            "name": "도구명", 
            "args": {"인자": "값"}
          }
        }
        
        [도구 목록]
        - list_files: 폴더 목록 확인 (args: {"directory": "."})
        - read_file: 파일 내용 읽기 (args: {"file_path": "파일명"})
        - replace_in_file: 코드 수정 (args: {"file_path": "파일명", "old_text": "기존코드", "new_text": "새코드"})
        - final_answer: 모든 작업 완료 보고
        """
        self.history = [{"role": "system", "content": self.system_prompt}]
        self.last_raw_response = ""
        self.repeat_count = 0

    def call_llm(self, retry_count=3):
        for attempt in range(retry_count):
            try:
                # 컨텍스트가 꼬이면 과감하게 압축
                if len(self.history) > 12:
                    self.history = [self.history[0]] + self.history[-6:]
                
                payload = {"model": MODEL_NAME, "messages": self.history, "temperature": 0.4}
                response = requests.post(f"{LM_STUDIO_API_BASE}/chat/completions", json=payload, timeout=120)
                
                if response.status_code == 200:
                    content = response.json()['choices'][0]['message']['content']
                    if content and content.strip(): return content
                
                print(f"\n⚠️ 응답 부재. 재시도 중... ({attempt + 1})")
                time.sleep(1)
            except Exception as e:
                print(f"\n❌ 에러: {e}")
                time.sleep(1)
        return None

    def run(self, user_prompt):
        print(f"\n👤 User: {user_prompt}")
        self.history.append({"role": "user", "content": user_prompt})
        
        turn = 0
        while turn < 15:
            turn += 1
            print(f"\n⏳ [턴 {turn}] 에이전트 생각 중...", end="\r")
            raw_response = self.call_llm()
            if not raw_response: break
            
            # 지능 붕괴 복구: 동일한 이상 응답 반복 감지
            if raw_response == self.last_raw_response:
                self.repeat_count += 1
                if self.repeat_count >= 2:
                    print("\n🚨 모델 고착 상태 감지! 히스토리를 강제 초기화합니다.")
                    self.history = [{"role": "system", "content": self.system_prompt}, {"role": "user", "content": user_prompt}]
                    self.repeat_count = 0
                    continue
            else:
                self.repeat_count = 0
            self.last_raw_response = raw_response

            json_str = extract_json_robustly(raw_response)
            try:
                if not json_str: raise ValueError("No JSON")
                llm_response = json.loads(json_str)
                
                # 자가 치유 (Self-Healing): 인자만 뱉었을 경우 구조 복구
                if "action" not in llm_response:
                    if "directory" in llm_response:
                        llm_response = {"thought": "폴더 목록을 확인합니다.", "action": {"name": "list_files", "args": llm_response}}
                    elif "file_path" in llm_response:
                        llm_response = {"thought": "파일을 읽습니다.", "action": {"name": "read_file", "args": llm_response}}
            except:
                self.history.append({"role": "user", "content": "오류: JSON 형식을 지키세요. 예: {\"thought\": \"...\", \"action\": {\"name\": \"list_files\", \"args\": {\"directory\": \".\"}}}"})
                continue
            
            thought = llm_response.get('thought', '진행 중...')
            print(f"\r🤔 생각: {thought}")
            
            if "final_answer" in llm_response:
                print(f"\n🏁 최종 보고: {llm_response['final_answer']}")
                break
                
            action = llm_response.get("action")
            if action:
                name = action.get("name")
                args = action.get("args", {})
                
                # 정규화
                if name in ["list_directory", "ls"]: name = "list_files"
                if name in ["edit_file", "patch"]: name = "replace_in_file"
                
                print(f"🛠️ 실행: [{name}]")
                path = args.get('file_path') or args.get('filepath') or args.get('path')
                
                if name == "list_files": result = list_files(directory=args.get('directory', '.'))
                elif name == "read_file": result = read_file(file_path=path)
                elif name == "write_file": result = write_file(file_path=path, content=args.get('content', ''))
                elif name == "replace_in_file":
                    result = replace_in_file(file_path=path, old_text=args.get('old_text', ''), new_text=args.get('new_text', ''))
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
