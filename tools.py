import os
import subprocess

MAX_READ_CHARS = 3000  # LM Studio 컨텍스트 초과 방지

def list_files(directory="."):
    """디렉토리 내 파일 목록을 반환합니다."""
    try:
        files = os.listdir(directory)
        return "\n".join(files)
    except Exception as e:
        return f"Error: {str(e)}"

def read_file(file_path):
    """파일 내용을 읽습니다. 너무 길면 잘라서 반환합니다."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > MAX_READ_CHARS:
            return content[:MAX_READ_CHARS] + f"\n\n... (파일이 너무 길어 {MAX_READ_CHARS}자까지만 표시. 총 {len(content)}자)"
        return content
    except Exception as e:
        return f"Error: {str(e)}"

def write_file(file_path, content):
    """파일 전체를 새로 작성합니다."""
    try:
        dir_name = os.path.dirname(file_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"

def replace_in_file(file_path, old_text, new_text):
    """파일 내 특정 텍스트를 찾아 교체합니다."""
    try:
        if not os.path.exists(file_path):
            return f"Error: File {file_path} not found. Use write_file to create it first."
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_text not in content:
            preview = content[:200] if len(content) > 200 else content
            return f"Error: old_text not found in {file_path}. Use read_file to check current content. File preview:\n{preview}"
        new_content = content.replace(old_text, new_text)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"Successfully updated {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"

def execute_command(command):
    """쉘 명령어를 실행합니다."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        output = f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        if len(output) > MAX_READ_CHARS:
            output = output[:MAX_READ_CHARS] + "\n... (출력이 잘렸습니다)"
        return output
    except Exception as e:
        return f"Error: {str(e)}"
