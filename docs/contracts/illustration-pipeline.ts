// docs/contracts/illustration-pipeline.ts
// 일러스트 파이프라인 인터페이스 계약
// v2: 캐릭터 동일성 강화 (PuLID + 멀티뷰 + CLIP+DINOv2 하이브리드 검증)

import type { Gender, IllustrationStyle, PersonalizedScene } from "./story-engine";

// ============================================================
// 캐릭터 시트 (v2: 멀티뷰 + Identity Prompt Block)
// ============================================================

interface CharacterReferenceImages {
  front: string;                         // 정면 (필수) — PuLID 얼굴 앵커 기반
  threeQuarter?: string;                 // 3/4 각도 — 자연스러운 포즈 생성에 활용
  side?: string;                         // 측면 — 프로필 뷰 일관성 확보
}

interface CharacterSheet {
  characterId: string;
  referenceImages: CharacterReferenceImages;   // v2: 단일 URL → 멀티뷰 구조
  faceAnchorUrl: string;                       // PuLID용 얼굴 앵커 이미지 (스타일 무관, 순수 얼굴 특징)
  identityPromptBlock: string;                 // 고정 외형 묘사 텍스트 (영문, 모든 장면 프롬프트에 주입)
                                               // 예: "a young girl with round face, short black hair with red hairpin,
                                               //      wearing yellow sweater with star pattern, rosy cheeks, big brown eyes"
  style: IllustrationStyle;
  createdAt: string;                           // ISO datetime
}

// ============================================================
// 캐릭터 시트 생성 서비스 (v2: 3단계 프로세스)
// ============================================================

interface CharacterSheetService {
  // ── Phase 1: 얼굴 앵커 생성 ──
  // 아이 사진 → PuLID 모델(bytedance/flux-pulid)로 얼굴 특징 추출
  // 스타일에 무관한 순수 얼굴 앵커 생성 (1회만 생성, 모든 스타일에서 재사용)
  // 사진은 처리 후 즉시 삭제됨 (보안 규칙)
  //
  // ⚠️ Python 구현 deviation: createFaceAnchor는 별도의 FaceAnchorService로 분리.
  //   이유: 얼굴 앵커는 스타일과 무관하게 1회만 생성되므로, 캐릭터 시트 생성과
  //   생명주기가 다르다. 보안 민감 로직(EXIF 제거, 사진 즉시 폐기)을 격리하기 위해 분리.
  //   Python 경로: packages/backend/src/storytale/illustration/face_anchor_service.py::FaceAnchorService
  //   반환 타입도 { faceAnchorUrl, photoHash } 로 확장됨 (photo_hash 보안 정책).
  createFaceAnchor(
    childPhoto: Buffer,
    gender: Gender,
    ageApprox: number
  ): Promise<{ faceAnchorUrl: string; photoHash: string }>;

  // ── Phase 2: 스타일화된 멀티뷰 캐릭터 시트 생성 ──
  // 얼굴 앵커 + 선택된 스타일 → 정면/3/4/측면 참조 이미지 생성
  // PuLID id_weight: 0.8~1.0 (얼굴 동일성 최우선)
  createCharacterSheet(
    faceAnchorUrl: string,
    style: IllustrationStyle,
    gender: Gender,
    ageApprox: number
  ): Promise<CharacterSheet>;

  // ── Phase 3: Identity Prompt Block 추출 ──
  // 캐릭터 시트 이미지를 LLM(Claude)에 분석시켜
  // 영문 외형 묘사 텍스트를 생성 (모든 장면 프롬프트에 동일하게 주입)
  generateIdentityPromptBlock(
    characterSheet: CharacterSheet
  ): Promise<string>;

  // 기존 캐릭터 시트 조회 (같은 아이 + 같은 스타일이면 재사용)
  getExistingSheet(
    photoHash: string,
    style: IllustrationStyle
  ): Promise<CharacterSheet | null>;
}

// ============================================================
// 장면 일러스트
// ============================================================

interface SceneIllustration {
  sceneId: string;
  imageUrl: string;                      // S3 URL
  consistencyScore: ConsistencyScore;    // v2: 단일 숫자 → 상세 점수
  generationAttempts: number;            // 몇 회 만에 생성되었는지
  usedInpainting: boolean;              // 인페인팅 폴백 사용 여부
  width: number;
  height: number;
}

interface SceneIllustrationService {
  generateIllustration(
    illustrationPrompt: string,          // 영문 프롬프트 (Identity Block이 이미 포함된 상태)
    character: CharacterSheet,           // faceAnchorUrl + referenceImages로 PuLID/IP-Adapter 주입
    style: IllustrationStyle,
    sceneEmotion: string                 // 장면 감정 (아트 디렉션의 emotion_to_visual 참조)
  ): Promise<SceneIllustration>;
}

// ============================================================
// 일관성 검증 (v2: CLIP + DINOv2 하이브리드)
// ============================================================

// CLIP: 글로벌 의미론적 유사도 (스타일, 전체 분위기 일관성)
// DINOv2: 구조적 시각 유사도 (얼굴 구조, 비율, 세부 특징)
// 합산: compositeScore = 0.4 × clipScore + 0.6 × dinoScore

type ConsistencyFailureReason =
  | "face_drift"           // 얼굴 구조 불일치 (DINOv2 low)
  | "style_mismatch"       // 화풍 불일치 (CLIP low)
  | "proportion_error";    // 캐릭터 비율 이상

interface ConsistencyScore {
  clipScore: number;                     // 0~1, 글로벌 의미 유사도
  dinoScore: number;                     // 0~1, 구조적 시각 유사도
  compositeScore: number;                // 0~1, 가중 합산
  passed: boolean;                       // compositeScore >= 0.80
  failureReason?: ConsistencyFailureReason;
}

interface ConsistencyValidator {
  // 생성된 일러스트와 캐릭터 시트의 유사도 검증
  // 비교 대상: 생성 이미지의 캐릭터 영역 vs 캐릭터 시트 정면 이미지
  validate(
    generatedImageUrl: string,
    characterSheet: CharacterSheet
  ): Promise<ConsistencyScore>;
}

// compositeScore threshold: 0.80 (기존 CLIP 단독 0.75보다 엄격)
// 재생성 전략:
//   1차 실패 → 프롬프트 미세 조정 후 재생성
//   2차 실패 → PuLID id_weight 상향(+0.1) 후 재생성
//   3차 실패 → 인페인팅 폴백 (캐릭터 영역만 faceAnchor 기반 보정)

// ============================================================
// 인페인팅 폴백 (v2 신규)
// ============================================================

interface InpaintingService {
  // 캐릭터 얼굴/상체 영역만 인페인팅으로 보정
  // 배경과 포즈는 유지하면서 캐릭터 동일성만 복구
  correctCharacterRegion(
    sceneImageUrl: string,               // 원본 장면 이미지
    characterSheet: CharacterSheet,      // 얼굴 앵커 + Identity Block 참조
    failureReason: ConsistencyFailureReason
  ): Promise<{
    correctedImageUrl: string;
    finalScore: ConsistencyScore;
  }>;
}

// ============================================================
// 이미지 저장
// ============================================================

interface ImageStorageService {
  upload(
    imageBuffer: Buffer,
    key: string                          // S3 key. 예: "stories/{storyId}/scenes/{sceneId}.png"
  ): Promise<string>;                    // 반환: public URL

  delete(key: string): Promise<void>;

  generatePresignedUrl(
    key: string,
    expiresInSeconds: number
  ): Promise<string>;
}

// ============================================================
// 오케스트레이터
// ============================================================

interface IllustrationOrchestrator {
  // 전체 일러스트 생성 플로우 (v2 강화)
  // 1. 캐릭터 시트 준비 (createFaceAnchor → createCharacterSheet → generateIdentityPromptBlock)
  // 2. 장면별 일러스트 생성 (Identity Block 주입 + PuLID 얼굴 앵커 참조)
  // 3. CLIP+DINOv2 하이브리드 검증
  // 4. 실패 시: 재생성(2회) → 인페인팅 폴백(1회)
  generateAllIllustrations(
    storyId: string,
    scenes: PersonalizedScene[],
    character: CharacterSheet,
    style: IllustrationStyle
  ): AsyncGenerator<SceneIllustration>;
  // 장면별로 yield하므로 SSE로 진행률 전달 가능
}

export type {
  CharacterReferenceImages,
  CharacterSheet,
  CharacterSheetService,
  SceneIllustration,
  SceneIllustrationService,
  ConsistencyScore,
  ConsistencyFailureReason,
  ConsistencyValidator,
  InpaintingService,
  ImageStorageService,
  IllustrationOrchestrator,
};
