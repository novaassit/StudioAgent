import json
import requests
from tools import list_files, read_file, write_file, execute_command

# LM Studio 기본 설정 (필요에 따라 변경 가능)
LM_STUDIO_API_BASE = "http://localhost:1234/v1"
MODEL_NAME = "qwen/qwen3-coder-next" # 요청하신 모델명으로 업데이트 완료

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
            
            응답 형식:
            반드시 JSON 형식으로 응답하라. (생각과 행동을 분리)
            예: {"thought": "파일 목록을 먼저 확인해야겠어.", "action": {"name": "list_files", "args": {"directory": "."}}}
            만약 작업이 완료되었다면: {"thought": "작업을 완료했습니다.", "final_answer": "코드 작성을 마쳤습니다."}
            """}
        ]

    def call_llm(self):
        try:
            payload = {
                "model": MODEL_NAME,
                "messages": self.history,
                # 일부 이전 모델이나 특정 설정에서 400 에러를 유발할 수 있어 일단 주석 처리하거나 확인 필요
                # "response_format": {"type": "json_object"} 
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
            if llm_response_str is None:
                break # 에러 발생 시 루프 종료
                
            try:
                llm_response = json.loads(llm_response_str)
            except json.JSONDecodeError:
                print(f"❌ 에러: LLM이 유효한 JSON을 응답하지 않았습니다: {llm_response_str}")
                break
            
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
                self.history.append({"role": "assistant", "content": llm_response_str})
                self.history.append({"role": "system", "content": f"Tool Result: {result}"})

if __name__ == "__main__":
    agent = StudioAgent()
    # 테스트용 프롬프트
    agent.run("현재 폴더의 파일을 확인하고 hello.py 파일을 만들어서 'print(\"hello world\")'를 작성해줘.")
