import json
from http.server import BaseHTTPRequestHandler, HTTPServer

state_counter = 0

class MockLMStudioHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global state_counter
        state_counter += 1
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        if state_counter == 1:
            content = json.dumps({
                "thought": "파일 목록을 확인합니다.",
                "action": {"name": "list_files", "args": {"directory": "."}}
            })
        elif state_counter == 2:
            content = json.dumps({
                "thought": "hello_test.py 파일을 생성합니다.",
                "action": {"name": "write_file", "args": {"file_path": "hello_test.py", "content": "print('Test Success')"}}
            })
        else:
            content = json.dumps({
                "thought": "완료했습니다.",
                "final_answer": "테스트가 성공적으로 끝났습니다!"
            })
            
        response = {
            "choices": [{"message": {"content": content}}]
        }
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def log_message(self, format, *args):
        return # 로그 출력 방지

if __name__ == "__main__":
    print("Mock Server starting on port 1234...")
    server = HTTPServer(('localhost', 1234), MockLMStudioHandler)
    server.serve_forever()
