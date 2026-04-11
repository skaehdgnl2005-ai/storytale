# @storytale/shared

StoryTale 프로젝트의 프론트엔드와 백엔드 간에 공유되는 도메인 타입 및 계약(Contract)을 정의하는 모듈입니다.

## 주요 타입 및 역할
- **`story-engine.ts`**: 가드레일, AI 인터프리터, 부모 확인, 스토리 생성 등에 대한 도메인 모델과 서비스 인터페이스를 제공합니다.
- **`illustration-pipeline.ts`**: 멀티뷰 캐릭터 시트, 장면 일러스트 생성, 일관성 검증 등에 필요한 타입들을 제공합니다.
- **`user-service.ts`**: 사용자 인증, 아이 프로필, 스토리 히스토리 관리를 위한 타입들을 제공합니다.

## 사용 예시

```typescript
import { 
  AgeGroup, 
  IllustrationStyle, 
  ScenePlan 
} from '@storytale/shared/types';

// 또는 빌드 후 직접 import 할 수도 있습니다.
// import { ... } from '@storytale/shared';

const style: IllustrationStyle = "watercolor";
```

## 타입 검사 실행 방법

```bash
cd packages/shared
npm run typecheck
# 또는
npm run build
```
