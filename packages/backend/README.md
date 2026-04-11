# StoryTale Backend

개인화 아동 그림책 생성 API 서버 (FastAPI + Python 3.12).

## 주요 모듈

| 모듈 | 역할 |
|------|------|
| `storytale.app` | FastAPI 앱 엔트리포인트, 헬스체크 |

> 추가 모듈은 S3~S20 태스크에서 순차적으로 구현됩니다.

## 설치 및 실행

```bash
# 의존성 설치 (개발 모드)
cd packages/backend
pip install -e ".[dev]"

# 개발 서버 실행
uvicorn storytale.app:app --reload

# 테스트
pytest

# 린트 & 포맷
ruff check src tests
ruff format src tests
```

## 프로젝트 구조

```
packages/backend/
├── pyproject.toml        # Python 패키지 설정
├── src/
│   └── storytale/
│       ├── __init__.py   # 패키지 (버전 정보)
│       └── app.py        # FastAPI 앱
└── tests/
    └── test_s1_monorepo_structure.py
```
