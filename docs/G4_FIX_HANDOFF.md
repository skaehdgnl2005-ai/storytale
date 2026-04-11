# G4 품질 게이트 수정 인수인계

> 생성일: 2026-04-10
> 상태: 세션 1 미시작 → P0 + P1 일부 수정 필요

## 배경

Phase 5 일러스트 파이프라인(S21~S26) 품질 게이트 G4 검증 결과 **불통과**.
테스트 95/95 통과하지만, 런타임 버그 3건 + 계약 불일치 5건 + 아트 디렉션 위반 4건 + 보안 미준수 2건 발견.

## 시작 시 필수 읽기

1. `docs/SESSION_LOG.md` — "품질 게이트 G4" 섹션 (발견된 이슈 전체 목록)
2. `docs/contracts/illustration-pipeline.ts` — 계약 원본
3. `docs/guardrail-seeds/art-direction.json` — 아트 디렉션 원본

## 세션 1: P0 + P1 핵심 (파일 5개 제한 준수)

### 수정 대상 파일
1. `packages/backend/src/storytale/illustration/illustration_orchestrator.py`
2. `packages/backend/src/storytale/illustration/scene_illustration_service.py`
3. `packages/backend/src/storytale/illustration/consistency_validator.py`
4. `packages/backend/src/storytale/illustration/face_anchor_service.py`
5. `packages/backend/tests/test_s24_consistency_validator.py`

### 수정 항목 (TDD: 테스트 먼저 → 구현)

#### Fix 1: B1 — 오케스트레이터 S3 업로드 URL/bytes 혼동 [Critical]
- **파일**: `illustration_orchestrator.py:187`
- **현재**: `await self._storage.upload(best_image_url, s3_key)` — URL 문자열 전달
- **수정**:
  ```python
  # 이미지 다운로드 후 bytes로 전달
  async with httpx.AsyncClient() as http:
      resp = await http.get(best_image_url)
      resp.raise_for_status()
      image_bytes = resp.content
  s3_url = await self._storage.upload(image_bytes, s3_key)
  ```
- **테스트**: `test_s26_illustration_orchestrator.py`에서 `storage.upload` mock의 첫 번째 인자가 `bytes`인지 검증 추가
- **주의**: `ReplicateClient`가 이미 `httpx`를 사용하므로 의존성 추가 불필요. 오케스트레이터에 httpx import 추가만 하면 됨.

#### Fix 2: B2 — ID_WEIGHT_BOOST 미적용 [Major]
- **파일 2개**: `scene_illustration_service.py` + `illustration_orchestrator.py`
- **현재**: `ID_WEIGHT_BOOST = 0.1` 선언만 있고 미사용. `generate_illustration()`에 id_weight 파라미터 없음.
- **수정**:
  1. `SceneIllustrationService.generate_illustration()`에 `id_weight: float | None = None` 옵셔널 파라미터 추가
     - `None`이면 기존 `DEFAULT_ID_WEIGHT`(0.85) 사용
     - 값이 있으면 해당 값으로 PuLID 호출
  2. `IllustrationOrchestrator._process_scene()`에서:
     - attempt 1: `id_weight=None` (기본값)
     - attempt 2+: `id_weight=DEFAULT_ID_WEIGHT + ID_WEIGHT_BOOST` (0.95)
- **테스트**: `test_s26`의 `test_retry_with_id_weight_increase_on_second_failure`가 실제로 id_weight 값을 assert하도록 수정

#### Fix 3: B3 — face_drift 분류 오류 [Major]
- **파일**: `consistency_validator.py:154`
- **현재**: `if dino_score <= clip_score:` → 동점이면 face_drift로 잘못 분류
- **수정**: `if dino_score < clip_score:`
- **테스트 추가** (`test_s24_consistency_validator.py`):
  - `test_equal_scores_above_low_threshold` — clip=0.70, dino=0.70 → composite=0.70 → 실패, `style_mismatch` (not face_drift)
  - `test_only_clip_below_low_threshold` — clip=0.60, dino=0.70 → `style_mismatch` (dino > clip이므로)

#### Fix 4: P2 — photo_hash 미계산 [보안]
- **파일**: `face_anchor_service.py`
- **현재**: `FaceAnchorResult`에 `face_anchor_url`만 존재
- **수정**:
  1. `FaceAnchorResult`를 Pydantic `BaseModel`로 변경 (현재 TypedDict)
  2. `photo_hash: str` 필드 추가
  3. `create_face_anchor()` 내에서 `hashlib.sha256(child_photo).hexdigest()` 계산
  4. 결과에 `photo_hash` 포함
- **테스트**: `test_s22a`에 `test_returns_photo_hash` 추가 — 동일 입력 시 동일 해시

### 검증

모든 수정 후:
```bash
cd packages/backend
python -m pytest tests/test_s21_replicate_client.py tests/test_s22a_face_anchor.py tests/test_s22b_character_sheet.py tests/test_s23_scene_illustration.py tests/test_s24_consistency_validator.py tests/test_s24_inpainting_service.py tests/test_s25_image_storage.py tests/test_s26_illustration_orchestrator.py -v
```
전체 통과 확인 후, `ruff check src tests && ruff format src tests` 실행.

---

## 세션 2: P1 나머지 + P2

### 수정 대상 파일
1. `packages/backend/src/storytale/illustration/scene_illustration_service.py`
2. `packages/backend/src/storytale/illustration/face_anchor_service.py`
3. `packages/backend/src/storytale/illustration/replicate_client.py`
4. `packages/backend/tests/test_s23_scene_illustration.py`
5. `packages/backend/tests/test_s22a_face_anchor.py`

### 수정 항목

#### Fix 5: A2 — composition_rules 프롬프트 반영
- `_build_prompt()`에서 `composition_rules` 읽어 영어 토큰 추가:
  - `"character fills 40-60% of frame"`
  - `"maximum 3 props, simple environment"`
  - `"centered or rule-of-thirds framing"`

#### Fix 6: A4 — 프롬프트 5단계 순서 정리
- `illustration_prompt`는 Identity + Action + Environment만 포함하도록 역할 정의
- `_build_prompt()`가 Emotion → Style 순서로 추가
- `story-personalizer-v1.md`의 일러스트 프롬프트 생성 로직도 확인 필요

#### Fix 7: P1 — PNG EXIF 제거
- `_strip_exif()`에 PNG 경로 추가: Pillow로 `eXIf`, `tEXt`, `zTXt`, `iTXt` 청크 제거
- Pillow가 이미 의존성에 있는지 확인 필요 (없으면 추가)

#### Fix 8: A1/A3 — 테스트 픽스처 보강
- `test_s23`의 `_ART_DIRECTION`에 6개 감정 전부 + 8개 금지어 전부 추가
- 각 감정별 테스트 케이스 추가 (fear, anger, comfort)
- `clean_digital` 스타일 테스트 추가

#### Fix 9: P3 — 폴링 에러 처리
- `replicate_client.py` `_poll_until_complete`에 `resp.raise_for_status()` 추가

### P2 잔여 (문서/타입 정리, 별도 세션 가능)
- C2: `createFaceAnchor` 위치 — 계약에 deviation 문서화 또는 코드 이동
- C3: `reference_images` 구조화 모델로 변경
- C4: Pydantic camelCase alias 설정
- C5: `docs/prompts/identity-prompt-block-v1.md` 생성
- N1: `failure_reason is None` 방어 코드 추가

---

## 주의사항

- **TDD 필수**: 테스트 먼저 작성 → 실패 확인 → 구현 → 통과 확인
- **파일 5개 제한**: 한 세션에서 5개 이상 동시 수정 금지 (CLAUDE.md 규칙)
- **SESSION_LOG 기록**: 세션 완료 시 "G4 Fix 세션 N" 항목 추가
- **G4 재검증**: 세션 2 완료 후 G4 품질 게이트 재실행하여 통과 확인
