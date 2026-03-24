import json
import requests
from tools import list_files, read_file, write_file, execute_command

# LM Studio 기본 설정
LM_STUDIO_API_BASE = "http://localhost:1234/v1"
MODEL_NAME = "qwen/qwen3-coder-next"

def extract_first_json(text):
    """텍스트에서 첫 번째로 완성된 JSON 객체 하나만 추출합니다."""
    if not text: return None
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
        print(f"\n🚀 StudioAgent: 로컬 코딩 엔진 기동 완료")
        print(f"🤖 모델: {MODEL_NAME} | 📡 서버: {LM_STUDIO_API_BASE}")
        print("-" * 50)
        
        self.history = [
            {"role": "system", "content": """너는 세계 최고의 시니어 소프트웨어 엔지니어 에이전트다. 
            너의 목표는 사용자의 요청을 완벽하게 분석하여 실제로 작동하는 코드를 구현하는 것이다.
            
            [핵심 행동 강령]
            1. **현황 파악**: 필요한 경우 파일 목록을 확인하라.
            2. **계획 수립**: 복잡한 요청(예: 게임 만들기)은 어떤 파일들이 필요한지 먼저 사용자에게 브리핑하라.
            3. **즉각 실행**: 계획이 서면 `write_file` 도구를 사용하여 지체 없이 코드를 작성하기 시작하라.
            4. **완결성**: 코드는 생략 없이 전체 내용을 작성하라.
            
            [사용 가능한 도구]
            1. list_files(directory="."): 파일 목록 확인
            2. read_file(file_path): 코드 읽기
            3. write_file(file_path, content): 코드 작성/수정
            4. execute_command(command): 쉘 명령 실행 (테스트 등)
            
            [응답 규칙]
            - 반드시 한 번에 하나의 Action만 수행하라.
            - 반드시 JSON 형식으로만 응답하라.
            - 형식: {"thought": "당신의 전략적 사고", "action": {"name": "도구명", "args": {...}}}
            - 완료 시: {"thought": "분석 결과", "final_answer": "최종 결과 보고"}
            """}
        ]

    def call_llm(self):
        try:
            payload = {"model": MODEL_NAME, "messages": self.history}
            response = requests.post(f"{LM_STUDIO_API_BASE}/chat/completions", json=payload, timeout=90)
            if response.status_code != 200:
                print(f"\n❌ 서버 에러: {response.text}")
                return None
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"\n❌ 연결 실패: {str(e)}")
            return None

    def run(self, user_prompt):
        print(f"\n👤 User: {user_prompt}")
        self.history.append({"role": "user", "content": user_prompt})
        
        while True:
            llm_response_str = self.call_llm()
            if not llm_response_str: break
                
            json_str = extract_first_json(llm_response_str)
            try:
                if not json_str: raise ValueError("No JSON found")
                llm_response = json.loads(json_str)
            except:
                print(f"\n⚠️ 응답 형식 재조정 중...")
                self.history.append({"role": "system", "content": "오류: JSON 형식으로만 응답하세요."})
                continue
            
            thought = llm_response.get('thought', '생각 중...')
            print(f"\n🤔 에이전트 생각: {thought}")
            
            if "final_answer" in llm_response:
                print(f"🏁 최종 답변: {llm_response['final_answer']}")
                break
                
            action = llm_response.get("action")
            if action:
                tool_name = action["name"]
                args = action.get("args", {})
                
                print(f"🛠️ 도구 실행: [{tool_name}]")
                
                if tool_name == "list_files": result = list_files(**args)
                elif tool_name == "read_file": result = read_file(**args)
                elif tool_name == "write_file": 
                    result = write_file(**args)
                    print(f"   📝 파일 작성 완료: {args.get('file_path')}")
                elif tool_name == "execute_command": result = execute_command(**args)
                else: result = "Unknown tool"
                
                self.history.append({"role": "assistant", "content": json.dumps(llm_response)})
                self.history.append({"role": "system", "content": f"Tool Result: {result}"})

if __name__ == "__main__":
    agent = StudioAgent()
    try:
        user_input = input("\n무엇을 도와드릴까요? > ")
        agent.run(user_input)
    except KeyboardInterrupt:
        print("\n👋 종료합니다.")
