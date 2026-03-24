import os
import subprocess

def list_files(directory="."):
    """디렉토리 내 파일 목록을 반환합니다."""
    try:
        files = os.listdir(directory)
        return "\n".join(files)
    except Exception as e:
        return f"Error: {str(e)}"

def read_file(file_path):
    """파일 내용을 읽습니다."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
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
            return f"Error: File {file_path} not found"
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_text not in content:
            return f"Error: Original text not found in {file_path}"
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
        return f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    except Exception as e:
        return f"Error: {str(e)}"
