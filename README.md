# StoryTale — 아동발달 가드레일 안에서 만드는 개인화 그림책 생성 앱

> A parent writes one or two sentences ("my kid is struggling with a new sibling"); StoryTale turns it into a picture book where *this* child is the hero — text by Claude, illustrations with a consistent character (PuLID + CLIP/DINOv2 identity check) — all inside child-development guardrails. FastAPI + React Native monorepo, 51 test files, CI.

**한 줄로**: 부모가 전문가가 아니어도 1~2문장이면 충분하다. AI가 아동발달 가드레일(0층) 안에서 아이의 이름·특성·세계가 녹아든 한 권을 설계하고, 부모가 확정한 뒤에만 생성한다.

## 무엇을 만들었나
- **4층 파이프라인**: 0층 가드레일(감정 흐름·연령별 문체·안전 규칙) → 1층 인터프리터(의도 분석 → 아크 선택 → 장면 설계) → 2층 부모 확인 루프(수정 최대 3회, 확정 전 생성 금지) → 3층 개인화 생성(Claude) → 4층 일러스트(얼굴 앵커 → 멀티뷰 캐릭터 시트 → Identity Prompt Block → 장면 생성 → CLIP+DINOv2 일관성 검증 → 재생성/인페인팅 폴백).
- **프롬프트를 버전 관리되는 자산으로**: `docs/prompts/*-v1.md` 8종(intent-analyzer, scene-planner, plan-reviser, story-personalizer, identity-prompt-block, preview-generator, tag-generator, book-recommender).
- **가드레일 시드 데이터** `docs/guardrail-seeds/` 4종(emotional-arcs, age-style-guides, safety-rails, art-direction).
- 모노레포 `packages/{backend(FastAPI), mobile(Expo RN), shared, admin-web}` + 이메일/소셜 인증, 서재, 추천 플로우.

## 왜 이렇게 만들었나 (설계 결정)
- **가장 어려웠던 문제**: 같은 아이가 모든 페이지에서 같은 얼굴로 나오게 하는 것(character consistency). 장면마다 독립 생성하면 얼굴이 흔들리므로, 아이 사진에서 얼굴 앵커를 만들고 캐릭터 시트를 먼저 확정한 뒤 모든 장면 프롬프트에 Identity Block을 주입하고, 생성 후 CLIP+DINOv2 하이브리드 점수로 통과/재생성(2회)/인페인팅을 결정한다.
- **부모가 확정하기 전에는 생성하지 않는다.** 비용과 신뢰 모두의 문제다. 미리보기(장면 설계)는 싸고, 일러스트는 비싸다.
- **품질 게이트를 계획/결과 문서 쌍으로 운영**: `docs/quality-gates/G1-*-plan.md` ↔ `-result.md`. 가드레일 데이터 리뷰(G1), 인터프리터 검증(G2), 추천(G3.5) 각각 사전에 통과 기준을 못 박고 결과를 기록했다.

## 어떻게 검증했나
- pytest 테스트 파일 50개(`packages/backend/tests/`, S10 가드레일 결합 ~ S27 인증까지) + 모바일 프론트 계약 테스트.
- GitHub Actions `test.yml`: ruff lint + pytest + 프론트 typecheck.
- 품질 게이트 결과: G3.5 PASS 9/10. G2는 API 부하로 1차 실패 후 재검증 항목으로 남아 있다(`docs/PROGRESS.md`).
- Phase 진행: 1~6 완료, 7(통합/운영) 2/4, 8(테스트 인프라) 0/2.

## 기술 스택
FastAPI · Python 3.12 · SQLAlchemy/Alembic · PostgreSQL · Redis · Anthropic SDK (Claude) · google-genai · Replicate (Flux.1 Dev + PuLID + IP-Adapter) · CLIP + DINOv2 · React Native (Expo) · TypeScript · Docker Compose

## 실행 방법
```bash
# backend
cd packages/backend
python -m venv .venv && . .venv/bin/activate     # Windows: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp ../../.env.example .env                        # 키 채우기
uvicorn storytale.main:app --reload
pytest                                            # 테스트

# mobile
cd packages/mobile && npm install && npx expo start
```

## 프로젝트 구조
```
packages/backend/   FastAPI 서비스 (guardrails, interpreter, story, illustration, auth, recommend)
packages/mobile/    Expo RN 앱 (프로필 → 목적 → 서술 입력 → 미리보기 → 생성 → 뷰어 → 서재)
packages/shared/    타입 계약
docs/prompts/       버전 관리되는 프롬프트 8종
docs/guardrail-seeds/  가드레일 시드 JSON 4종
docs/quality-gates/    G1~G3.5 계획/결과
docs/ARCHITECTURE.md   4층 파이프라인 상세
```

## 상태
Phase 6(프론트엔드)까지 완료, 배포(S38) 착수 가능 상태. 현재 브랜치에는 모바일 리디자인과 추천 플로우 화면 작업이 진행 중이다. 실제 배포 URL은 아직 없다.
