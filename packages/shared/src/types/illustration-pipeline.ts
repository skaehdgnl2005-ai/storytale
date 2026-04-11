// packages/shared/src/types/illustration-pipeline.ts

import type { Gender, IllustrationStyle, PersonalizedScene } from "./story-engine";

// React Native에서도 사용 가능하도록 Buffer 대신 Uint8Array 지원하는 타입 정의 추가
type ImageBuffer = Uint8Array; // Node.js의 Buffer도 Uint8Array이므로 호환 가능함

// ============================================================
// 캐릭터 시트
// ============================================================

interface CharacterReferenceImages {
  front: string;
  threeQuarter?: string;
  side?: string;
}

interface CharacterSheet {
  characterId: string;
  referenceImages: CharacterReferenceImages;
  faceAnchorUrl: string;
  identityPromptBlock: string;
  style: IllustrationStyle;
  createdAt: string;
}

// ============================================================
// 캐릭터 시트 생성 서비스
// ============================================================

interface CharacterSheetService {
  createFaceAnchor(
    childPhoto: ImageBuffer,
    gender: Gender,
    ageApprox: number
  ): Promise<{ faceAnchorUrl: string }>;

  createCharacterSheet(
    faceAnchorUrl: string,
    style: IllustrationStyle,
    gender: Gender,
    ageApprox: number
  ): Promise<CharacterSheet>;

  generateIdentityPromptBlock(
    characterSheet: CharacterSheet
  ): Promise<string>;

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
  imageUrl: string;
  consistencyScore: ConsistencyScore;
  generationAttempts: number;
  usedInpainting: boolean;
  width: number;
  height: number;
}

interface SceneIllustrationService {
  generateIllustration(
    illustrationPrompt: string,
    character: CharacterSheet,
    style: IllustrationStyle,
    sceneEmotion: string
  ): Promise<SceneIllustration>;
}

// ============================================================
// 일관성 검증
// ============================================================

type ConsistencyFailureReason =
  | "face_drift"
  | "style_mismatch"
  | "proportion_error";

interface ConsistencyScore {
  clipScore: number;
  dinoScore: number;
  compositeScore: number;
  passed: boolean;
  failureReason?: ConsistencyFailureReason;
}

interface ConsistencyValidator {
  validate(
    generatedImageUrl: string,
    characterSheet: CharacterSheet
  ): Promise<ConsistencyScore>;
}

// ============================================================
// 인페인팅 폴백
// ============================================================

interface InpaintingService {
  correctCharacterRegion(
    sceneImageUrl: string,
    characterSheet: CharacterSheet,
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
    imageBuffer: ImageBuffer,
    key: string
  ): Promise<string>;

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
  generateAllIllustrations(
    storyId: string,
    scenes: PersonalizedScene[],
    character: CharacterSheet,
    style: IllustrationStyle
  ): AsyncGenerator<SceneIllustration>;
}

export type {
  ImageBuffer,
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
