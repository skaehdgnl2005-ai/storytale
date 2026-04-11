# StoryTale 상세 아키텍처

## 시스템 전체 흐름

```
부모 앱
  │
  ├─ [1] 아이 프로필 등록 (이름, 나이, 사진, 위안물건, 친구, 동물)
  │
  ├─ [2] 목적 선택 (가치 / 관심사 / 문제해결 / 기념일)
  │
  ├─ [3] 서술형 입력 (1~2문장)
  │        │
  │        ▼
  │   ┌─────────────────────────────────────────────┐
  │   │ AI 인터프리터 (1층)                          │
  │   │                                             │
  │   │  의도 분석 ──→ 아크 선택 ──→ 장면 설계       │
  │   │     │              │             │          │
  │   │     │         0층 가드레일        │          │
  │   │     │    (감정흐름 + 문체 + 안전규칙)        │
  │   └─────┼─────────────────────────┼─────────────┘
  │         │                         │
  │         ▼                         ▼
  ├─ [4] 미리보기 확인 (수정 최대 3회)
  │        │
  │        ▼ (확정)
  │   ┌─────────────────────────────────────────────┐
  │   │ 스토리 생성 엔진 (3층)                       │
  │   │                                             │
  │   │  scene_plan + child_profile                 │
  │   │     → 장면별 텍스트 생성 (Claude API)        │
  │   │     → 장면별 일러스트 프롬프트 생성           │
  │   └─────────────────────────┬───────────────────┘
  │                             │
  │                             ▼
  │   ┌──────────────────────────────────────────────────┐
  │   │ 일러스트 파이프라인 (4층)                          │
  │   │                                                  │
  │   │  [Step 1] 아이 사진 → PuLID 얼굴 앵커 생성        │
  │   │  [Step 2] 얼굴 앵커 + 스타일 → 멀티뷰 캐릭터 시트  │
  │   │  [Step 3] 캐릭터 시트 → Identity Prompt Block 추출 │
  │   │  [Step 4] 장면 프롬프트(Identity Block 포함)       │
  │   │           + 캐릭터 시트(PuLID) → 일러스트 생성     │
  │   │  [Step 5] CLIP+DINOv2 하이브리드 일관성 검증       │
  │   │           → 통과 / 재생성(2회) / 인페인팅 폴백     │
  │   └──────────────────────────┬─────────────────────────┘
  │                             │
  │                             ▼
  └─ [5] 완성된 그림책 열람 / 서재 저장
```

## 데이터 모델

### User
| 필드 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| email | str | 소셜 로그인 이메일 |
| provider | str | "google", "kakao", "apple" |
| created_at | datetime | |

### ChildProfile
| 필드 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| user_id | UUID | FK → User |
| name | str (암호화) | 아이 이름 |
| age | int | 나이 |
| gender | str | 성별 |
| comfort_object | str? (암호화) | 위안 물건 |
| friend_name | str? (암호화) | 친구 이름 |
| favorite_animal | str? | 좋아하는 동물 |
| character_sheet_url | str? | 생성된 캐릭터 시트 S3 URL |
| photo_hash | str? | 원본 사진 해시 (사진 자체는 미저장) |

### EmotionalArcTemplate (0층)
| 필드 | 타입 | 설명 |
|------|------|------|
| id | str | "gentle_resolution" 등 |
| description | str | 설명 |
| target_ages | str[] | 대상 연령대 |
| stages | JSONB | ArcStage 배열 |
| rules | str[] | 이 아크의 규칙 |

### AgeStyleGuide (0층)
| 필드 | 타입 | 설명 |
|------|------|------|
| age_group | str | "3-4", "5-6", "7-8" |
| sentence_rules | JSONB | 문장 규칙 |
| emotional_expression | JSONB | 감정 표현 규칙 |
| page_guidelines | JSONB | 페이지 가이드 |

### SafetyRails (0층)
| 필드 | 타입 | 설명 |
|------|------|------|
| id | int | PK |
| prohibitions | str[] | 금지 규칙 |
| required_elements | str[] | 필수 요소 |

### Story
| 필드 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| user_id | UUID | FK → User |
| child_id | UUID | FK → ChildProfile |
| intent_analysis | JSONB | 의도 분석 결과 |
| scene_plan | JSONB | 확정된 장면 설계 |
| status | str | "planning", "confirmed", "generating", "completed", "failed" |
| style | str | "watercolor", "pastel_crayon", "clean_digital" |
| created_at | datetime | |

### StoryPage
| 필드 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| story_id | UUID | FK → Story |
| page_number | int | 페이지 번호 |
| scene_id | str | 장면 ID |
| text | str | 생성된 텍스트 |
| illustration_prompt | str | 일러스트 생성에 사용된 프롬프트 |
| illustration_url | str? | S3 일러스트 URL |
| consistency_score | float? | CLIP 일관성 점수 |

## 외부 서비스 의존성

| 서비스 | 용도 | 호출 시점 | 예상 지연 |
|--------|------|----------|----------|
| Claude API (Sonnet) | 의도분석, 장면설계, 텍스트생성, Identity Prompt Block 추출 | 스토리 생성 전 과정 | 1~3초/호출 |
| Replicate (Flux.1 + PuLID) | 얼굴 앵커, 캐릭터 시트, 장면 일러스트 | 텍스트 생성 완료 후 | 10~30초/장 |
| Replicate (bytedance/flux-pulid) | PuLID 기반 얼굴 동일성 보존 | 캐릭터 시트 + 장면 일러스트 | 10~20초/장 |
| DINOv2 (ViT-L/14) | 캐릭터 구조적 유사도 검증 | 일러스트 생성 후 | 1~2초/장 |
| S3 | 이미지 저장 | 일러스트 생성 후 | <1초 |
| Redis | 작업 큐, 캐싱, Rate limiting | 상시 | <10ms |

## 비동기 작업 처리

스토리 생성은 총 2~5분 소요. 동기 처리 불가.

1. 클라이언트가 `POST /stories/generate` → 202 + jobId.
2. API 레이어에서 `StoryOrchestrator` → `IllustrationOrchestrator`를 순차 호출.
3. 백그라운드 워커가 장면별로 순차 생성.
4. 각 장면 완료 시 SSE로 클라이언트에 통합 스트리밍 (텍스트 완료 → 일러스트 완료 순).
5. 클라이언트는 장면 완료될 때마다 프리뷰 갱신.
6. 전체 완료 시 SSE로 완료 이벤트 + Story 상태 "completed".

워커: MVP는 FastAPI BackgroundTasks로 충분. Celery + Redis 전환은 동시 생성 요청 50건/분 초과 시 검토.

## 1편당 비용 추정

| 항목 | 호출 수 | 단가 (예상) | 소계 |
|------|:-------:|------------|:----:|
| Claude API (의도분석) | 1회 | ~$0.01 | $0.01 |
| Claude API (장면설계) | 1회 | ~$0.02 | $0.02 |
| Claude API (미리보기) | 1회 | ~$0.005 | $0.005 |
| Claude API (텍스트 생성) | 8~16장면 | ~$0.02/회 | $0.16~$0.32 |
| Claude API (Identity Block 추출) | 1회 | ~$0.01 | $0.01 |
| Replicate (PuLID 얼굴 앵커) | 1회 | ~$0.05 | $0.05 |
| Replicate (멀티뷰 캐릭터 시트) | 3뷰 | ~$0.05/뷰 | $0.15 |
| Replicate (장면 일러스트+PuLID) | 8~16장면 | ~$0.07/회 | $0.56~$1.12 |
| DINOv2 검증 | 8~16장면 | ~$0.005/회 | $0.04~$0.08 |
| 인페인팅 폴백 (평균 10% 장면) | 1~2회 | ~$0.05/회 | $0.05~$0.10 |
| **1편 합계** | | | **$1.05~$1.83** |

> 수정 루프(최대 3회)는 장면설계 + 미리보기 재호출이므로 최대 +$0.075 추가.
> 캐릭터 동일성 강화로 기존 대비 $0.40~$0.63 증가. 재생성 횟수 감소로 일부 상쇄 기대.

## 캐싱 전략

| 대상 | 캐시 키 | TTL | 비고 |
|------|---------|:---:|------|
| 가드레일 데이터 (아크, 문체, 안전규칙) | `guardrails:{age_group}` | 1시간 | 변경 빈도 낮음 |
| 캐릭터 시트 | `character:{photo_hash}:{style}` | 90일 | 같은 아이+스타일이면 재사용 |

> 나머지 캐싱 대상(의도분석 결과 등)은 구현 과정에서 필요 시 추가.
