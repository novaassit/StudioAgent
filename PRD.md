# PRD: StudioAgent (Local LLM Coding Agent)

## 1. 프로젝트 개요
**StudioAgent**는 LM Studio(로컬 LLM)를 두뇌로 사용하여 사용자의 로컬 환경에서 코드를 분석, 작성, 실행 및 테스트하는 자율형 코딩 에이전트입니다. Claude Code와 유사한 사용자 경험을 로컬 환경에서 제공하는 것을 목표로 합니다.

## 2. 핵심 가치
- **Privacy First**: 모든 코드 분석과 생성이 로컬 서버(LM Studio)에서 이루어집니다.
- **Autonomy**: 단순 코드 생성을 넘어, 파일을 읽고 쓰고 실행하며 스스로 결과를 검증합니다.
- **Extensibility**: Python 기반의 도구 시스템으로 새로운 기능을 쉽게 추가할 수 있습니다.

## 3. 주요 기능 (Phase 1 - 완료)
- **File Management**: 파일 목록 조회, 파일 읽기, 파일 쓰기/생성.
- **Code Execution**: 터미널 명령어를 통한 코드 실행 및 결과 확인.
- **ReAct Loop**: [생합(Thought) -> 행동(Action) -> 결과(Observation)] 루프를 통한 자율적 문제 해결.
- **Structured Response**: JSON 기반의 응답 체계를 통해 도구 호출의 안정성 확보.

## 4. 로드맵 (Phase 2 & 3)
### Phase 2: 고도화된 코드 편집
- **Surgical Edit**: 파일 전체를 덮어쓰지 않고 특정 줄만 수정하는 기능.
- **Global Search (Grep)**: 프로젝트 전체에서 특정 심볼이나 텍스트 검색.
- **History Summarization**: 긴 대화 시 컨텍스트 최적화를 위한 요약 기능.

### Phase 3: 에코시스템 통합
- **Git Integration**: 브랜치 생성, 커밋, diff 분석 자동화.
- **Multi-file Planning**: 여러 파일에 걸친 복잡한 리팩토링 계획 수립 및 실행.
- **IDE Plugin**: VS Code 등과의 연동.

## 5. 기술 스택
- **Language**: Python 3.10+
- **LLM Engine**: LM Studio (OpenAI Compatible API)
- **Libraries**: Requests (HTTP Client)
