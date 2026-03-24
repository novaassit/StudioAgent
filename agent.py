import json
import requests
from tools import list_files, read_file, write_file, execute_command

# LM Studio 기본 설정 (필요에 따라 변경 가능)
LM_STUDIO_API_BASE = "http://localhost:1234/v1"
MODEL_NAME = "qwen/qwen3-coder-next" # 요청하신 모델명으로 업데이트 완료

def extract_first_json(text):
    """텍스트에서 첫 번째로 완성된 JSON 객체 하나만 추출합니다."""
    if not text:
        return None
    start_idx = text.find('{')
    if start_idx == -1:
        return None
    
    brace_count = 0
    for i in range(start_idx, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                return text[start_idx:i+1]
    return None

class StudioAgent:
    def __init__(self):
        print(f"\n🚀 StudioAgent 기동 중...")
        print(f"📡 서버 주소: {LM_STUDIO_API_BASE}")
        print(f"🤖 사용 모델: {MODEL_NAME}")
        print("-" * 30)
        
        self.history = [
            {"role": "system", "content": """너는 숙련된 소프트웨어 엔지니어링 에이전트다. 
            파일을 분석하고, 코드를 작성하며, 명령을 실행하여 프로젝트를 관리한다.
            
            사용 가능한 도구:
            1. list_files(directory="."): 디렉토리 내 파일 목록 확인
            2. read_file(file_path): 파일 내용 읽기
            3. write_file(file_path, content): 파일 생성 및 수정
            4. execute_command(command): 쉘 명령어 실행
            
            ⚠️ 규정:
            - 반드시 한 번에 **단 하나의 행동(Action)**만 수행하라.
            - 응답은 반드시 JSON 형식으로만 하라.
            - 여러 단계의 작업이 필요하다면, 현재 단계만 수행하고 결과를 기다려라.
            
            응답 형식:
            {"thought": "생각 내용", "action": {"name": "도구이름", "args": {...}}}
            만약 작업이 완료되었다면: {"thought": "완료", "final_answer": "최종결과"}
            """}
        ]

    def call_llm(self):
        try:
            payload = {
                "model": MODEL_NAME,
                "messages": self.history,
            }
            response = requests.post(
                f"{LM_STUDIO_API_BASE}/chat/completions",
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                print(f"\n❌ 서버 응답 에러 ({response.status_code}): {response.text}")
                return None
                
            return response.json()['choices'][0]['message']['content']
        except requests.exceptions.ConnectionError:
            print(f"\n❌ 에러: LM Studio 서버({LM_STUDIO_API_BASE})에 연결할 수 없습니다.")
            print("💡 LM Studio가 실행 중인지, 'Local Server'가 활성화되어 있는지 확인해 주세요.")
            return None
        except Exception as e:
            print(f"\n❌ 에러 발생: {str(e)}")
            return None

    def run(self, user_prompt):
        print(f"User: {user_prompt}")
        self.history.append({"role": "user", "content": user_prompt})
        
        while True:
            # LLM에게 생각과 행동 물어보기
            llm_response_str = self.call_llm()
            if not llm_response_str:
                break
                
            # 개선된 JSON 파싱: 첫 번째 완성된 { } 블록만 추출
            json_str = extract_first_json(llm_response_str)
            try:
                if json_str:
                    llm_response = json.loads(json_str)
                else:
                    raise ValueError("No JSON object found")
            except (json.JSONDecodeError, ValueError):
                print(f"\n❌ 에러: LLM이 유효한 JSON을 응답하지 않았습니다.")
                print(f"--- LLM 원문 응답 ---\n{llm_response_str}\n--------------------")
                self.history.append({"role": "system", "content": "오류: JSON 형식이 올바르지 않습니다. 반드시 하나의 JSON 객체만 응답하세요."})
                continue
            
            print(f"Agent Thought: {llm_response.get('thought')}")
            
            # 최종 답변인 경우
            if "final_answer" in llm_response:
                print(f"Final Answer: {llm_response['final_answer']}")
                break
                
            # 행동(도구 실행)이 있는 경우
            action = llm_response.get("action")
            if action:
                tool_name = action["name"]
                args = action.get("args", {})
                
                print(f"Executing Tool: {tool_name} with {args}")
                
                # 도구 실행
                if tool_name == "list_files": result = list_files(**args)
                elif tool_name == "read_file": result = read_file(**args)
                elif tool_name == "write_file": result = write_file(**args)
                elif tool_name == "execute_command": result = execute_command(**args)
                else: result = "Unknown tool"
                
                # 결과 기록
                self.history.append({"role": "assistant", "content": json.dumps(llm_response)})
                self.history.append({"role": "system", "content": f"Tool Result: {result}"})

if __name__ == "__main__":
    agent = StudioAgent()
    # 터미널 입력을 받을 수 있도록 변경
    try:
        user_input = input("수행할 작업을 입력하세요: ")
        agent.run(user_input)
    except KeyboardInterrupt:
        print("\n종료합니다.")
