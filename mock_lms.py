from flask import Flask, request, jsonify
import json

app = Flask(__name__)

# 테스트용 시나리오 상태 카운터
state_counter = 0

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    global state_counter
    state_counter += 1
    
    if state_counter == 1:
        # 첫 번째 생각: 파일 목록 확인
        content = json.dumps({
            "thought": "현재 폴더의 파일을 먼저 확인해야겠습니다.",
            "action": {"name": "list_files", "args": {"directory": "."}}
        })
    elif state_counter == 2:
        # 두 번째 생각: 파일 생성
        content = json.dumps({
            "thought": "파일 목록을 확인했습니다. 이제 hello_test.py 파일을 만들겠습니다.",
            "action": {"name": "write_file", "args": {"file_path": "hello_test.py", "content": "print('Agent Test Success')"}}
        })
    else:
        # 최종 답변
        content = json.dumps({
            "thought": "모든 작업을 완료했습니다.",
            "final_answer": "hello_test.py 파일을 성공적으로 생성했습니다!"
        })
        
    return jsonify({
        "choices": [{
            "message": {
                "content": content
            }
        }]
    })

if __name__ == "__main__":
    app.run(port=1234)
