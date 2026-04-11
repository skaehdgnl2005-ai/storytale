# storytale.db

데이터베이스 스키마(SQLAlchemy Models)와 세션 관리를 담당하는 모듈입니다.

## 주요 클래스/함수
- `Base`: 모든 모델의 부모 클래스. (`storytale.db.base`)
- `User`: 사용자 모델 (소셜 로그인 연동)
- `ChildProfile`: 아이 프로필 모델 정보
- `EmotionalArcTemplate`, `AgeStyleGuide`, `SafetyRails`: 0층 가드레일 역할을 하는 고정 모델 (JSONB 필드 포함)
- `Story`, `StoryPage`: 스토리 엔진이 생성한 결과물을 담는 모델

## 사용 예시

```python
from storytale.db.models import User, Story
from sqlalchemy.orm import Session

def get_user_stories(db: Session, user_id: str):
    return db.query(Story).filter(Story.user_id == user_id).all()
```

## 테스트 실행 방법
```bash
cd packages/backend
pytest tests/test_s3_db_models.py
```
