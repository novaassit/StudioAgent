# StudioAgent: Local LLM-Based Coding Agent 🚀

**StudioAgent**는 LM Studio와 연동하여 내 로컬 환경에서 코드를 분석, 작성, 실행하는 똑똑한 코딩 에이전트입니다.

## 🌟 주요 기능
- **파일 관리**: 파일 목록 조회, 코드 읽기, 코드 생성/쓰기.
- **코드 분석**: 로컬 모델을 이용한 코드 리뷰 및 버그 수정.
- **쉘 실행**: 터미널 명령어를 실행하여 코드를 직접 테스트.
- **자율 행동**: 생각하고 도구를 골라 실행하는 ReAct 구조.

## 🛠️ 시작하기

### 1. LM Studio 설정
- [LM Studio](https://lmstudio.ai/)를 다운로드하여 설치합니다.
- 원하는 모델(예: `Qwen2.5-7B-Instruct`, `Llama-3.1-8B`)을 다운로드하고 로드합니다.
- **Local Server** 탭에서 서버를 시작합니다 (기본값: `http://localhost:1234`).

### 2. 에이전트 설치 및 실행
```bash
# 레포지토리 클론 (또는 다운로드)
git clone <repository_url>
cd studio_agent

# 필수 라이브러리 설치
pip install requests

# 에이전트 실행
python agent.py
```

### 3. 사용 예시
에이전트가 실행되면 프롬프트를 입력하세요:
- "현재 폴더의 파일을 확인하고 hello.py 파일을 만들어서 'print(\"hello world\")'를 작성해줘."
- "기존 파일을 읽고 에러가 있는지 분석해줘."
- "이 코드를 실행하고 결과를 알려줘."

## 📁 프로젝트 구조
- `agent.py`: 에이전트의 두뇌 및 메인 루프.
- `tools.py`: 파일 조작 및 쉘 실행 도구 모음.
- `PRD.md`: 제품 요구 사양 및 향후 로드맵.

## ⚖️ 라이선스
MIT License
