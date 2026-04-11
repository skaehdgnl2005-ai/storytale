# 코드 스타일 규칙

## Python (백엔드)
- Python 3.12+, 타입 힌트 필수 (모든 함수 시그니처).
- Pydantic v2 모델 사용. dataclass 대신 BaseModel.
- 비동기: `async/await` 기본. 동기 I/O 금지.
- 포매터: ruff format. 린터: ruff check. 설정은 pyproject.toml.
- 함수 하나는 30줄 이하. 넘으면 분리.
- 변수/함수: snake_case. 클래스: PascalCase. 상수: UPPER_SNAKE.
- import 순서: stdlib → 외부 패키지 → 내부 모듈. 각 그룹 사이 빈 줄.

## TypeScript (shared, mobile)
- strict mode 필수. any 사용 금지.
- interface 우선 (type은 유니온/교차에만).
- 함수형 컴포넌트 + hooks. class 컴포넌트 금지.
- 네이밍: camelCase (변수/함수), PascalCase (타입/컴포넌트).

## 공통
- 매직 넘버 금지. 상수로 추출.
- 주석은 "왜(why)"만 쓸 것. "무엇(what)"은 코드가 말하게.
- TODO 남길 때: `# TODO(S세션번호): 설명` 형식.
