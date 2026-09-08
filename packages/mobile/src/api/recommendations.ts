/**
 * 동화책 추천 API 함수 (R-UI Step 1).
 *
 * 백엔드 라우터: `packages/backend/src/storytale/api/recommendations/router.py`
 * 계약: `docs/contracts/book-recommendation.ts`
 *
 * 와이어 포맷은 백엔드 Pydantic 직렬화(snake_case)와 1:1 매칭한다.
 */

import { apiFetch } from "./client";
import type { PurposeId } from "../data/purposes";

// ---------------------------------------------------------------------------
// 와이어 타입 — 백엔드 Pydantic 모델과 1:1 매칭 (snake_case)
// ---------------------------------------------------------------------------

export interface BookMetadata {
  id: string;
  isbn: string;
  title: string;
  author: string;
  publisher: string;
  cover_image_url: string | null;
  synopsis: string | null;
  target_age_min: number;
  target_age_max: number;
  source: "nlcy" | "aladin" | "kyobo" | "manual";
}

export interface SituationTag {
  tag_category: string;
  situation_description: string;
  emotional_keywords: string[];
  recommended_arc_id: string | null;
  confidence_score: number;
}

export interface BookRecommendation {
  book: BookMetadata;
  match_score: number;
  matched_tags: SituationTag[];
  why_this_book: string;
  reading_questions: string[];
  conversation_guide: string[];
}

export interface IntentAnalysis {
  intent_category: string;
  emotional_keywords: string[];
  child_elements: string[];
  recommended_arc_id: string;
  confidence: number;
}

export interface RecommendationResult {
  intent_analysis: IntentAnalysis;
  recommendations: BookRecommendation[];
  has_custom_story_option: boolean;
  custom_story_prompt: string;
}

// ---------------------------------------------------------------------------
// 요청
// ---------------------------------------------------------------------------

export interface CreateRecommendationRequest {
  parent_text: string;
  child_age: number;
  purpose_category: PurposeId;
  child_id?: string;
}

// ---------------------------------------------------------------------------
// API 함수
// ---------------------------------------------------------------------------

/**
 * 부모 서술 텍스트 + 아이 나이 + 목적 → 동화책 추천 결과.
 *
 * 백엔드: `POST /api/v1/recommendations` (R7).
 * LLM 호출 포함으로 5~15초 소요될 수 있음.
 *
 * 에러 매핑:
 * - 400: 입력 검증 실패 (parent_text 길이 등).
 * - 401: JWT 만료 → 재로그인 유도.
 * - 500: LLM/외부 API 실패 → "잠깐, 다시 한번 해볼게요".
 */
export async function createRecommendation(
  input: CreateRecommendationRequest,
): Promise<RecommendationResult> {
  return apiFetch<RecommendationResult>("/recommendations", {
    method: "POST",
    body: input,
  });
}
