# storytale.interpreter

StoryTale AI 인터프리터 모듈 (1층). 부모 텍스트 → 의도 분석 → 장면 설계 파이프라인을 담당한다.

## 주요 클래스/함수

| 클래스/함수 | 역할 |
|------------|------|
| `LLMClient` | Claude API 호출 공통 래퍼 (재시도, 타임아웃, JSON 파싱, 로깅) |
| `LLMClientError` | LLM 오류 예외 (`code`, `retryable` 속성 포함) |

## 사용 예시

```python
from storytale.interpreter.llm_client import LLMClient, LLMClientError

# 기본 텍스트 완성
client = LLMClient(api_key="sk-ant-...")
text = await client.complete(
    system="당신은 친절한 어시스턴트입니다.",
    user="안녕하세요!",
)

# JSON 응답 (마크다운 블록 자동 처리)
data = await client.complete_json(
    system="JSON으로만 응답하세요.",
    user='{"key": "value"}를 그대로 반환하세요.',
    temperature=0.3,
)

# 에러 처리
try:
    result = await client.complete("sys", "usr")
except LLMClientError as e:
    print(e.code)      # MAX_RETRIES_EXCEEDED | LLM_PARSE_ERROR | LLM_TIMEOUT
    print(e.retryable) # bool
```

## 테스트 실행

```bash
cd packages/backend
.venv/Scripts/activate   # Windows
pytest tests/test_s11_llm_client.py -v -m "not integration"

# 실제 API 호출 통합 테스트 (CLAUDE_API_KEY 필요)
CLAUDE_API_KEY=sk-ant-... pytest tests/test_s11_llm_client.py -v -m integration
```
