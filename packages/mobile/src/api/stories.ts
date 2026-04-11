/**
 * 스토리 API 함수 (S30b).
 *
 * 백엔드 라우터: `packages/backend/src/storytale/api/stories/router.py`
 * 계약: `docs/contracts/story-engine.ts` (StoryOrchestrator.interpretAndPlan)
 *
 * 와이어 포맷은 백엔드 Pydantic 직렬화(snake_case)와 1:1 매칭한다.
 * camelCase로 별명을 두지 않는다 — `profiles.ts` 와 동일한 규약.
 */

import { apiFetch } from "./client";
import type { PurposeId } from "../data/purposes";

// ---------------------------------------------------------------------------
// 상수
// ---------------------------------------------------------------------------

/**
 * 부모 서술형 입력의 최대 길이.
 *
 * 백엔드 `PARENT_TEXT_MAX_LENGTH`(stories/router.py)와 반드시 일치해야 한다.
 * security.md: "부모 서술형 입력: 최대 500자 제한".
 */
export const PARENT_TEXT_MAX_LENGTH = 500 as const;

/**
 * 백엔드가 RejectedIntentError를 400으로 매핑할 때 사용하는 코드.
 * 클라이언트는 `ApiClientError.code === REJECTED_INTENT_CODE` 로 분기한다.
 */
export const REJECTED_INTENT_CODE = "REJECTED_INTENT" as const;

// ---------------------------------------------------------------------------
// 와이어 타입 — 백엔드 Pydantic 모델과 1:1 매칭 (snake_case)
// ---------------------------------------------------------------------------

export interface PlannedScene {
  scene_id: string;
  emotion: string;
  purpose: string;
  description: string;
  child_elements: string[];
}

export interface StyleNotes {
  tone: string;
  avoid: string[];
  repetition_motif?: string | null;
}

export interface ScenePlan {
  title: string;
  scenes: PlannedScene[];
  style_notes: StyleNotes;
}

export interface StoryPreview {
  title: string;
  summary: string;
  scene_highlights: string[];
  page_count: number;
  /** 백엔드 기본값 "watercolor". S31에서 부모가 변경 가능. */
  style: string;
}

// ---------------------------------------------------------------------------
// 요청/응답
// ---------------------------------------------------------------------------

export interface PlanStoryRequest {
  parent_text: string;
  /**
   * 백엔드 `IntentCategory` 와 1:1 매핑.
   * `PurposeId` 를 사용하므로 mobile 측 카드 식별자와 컴파일 타임 일치한다.
   */
  purpose_category: PurposeId;
  child_id: string;
}

export interface PlanStoryResponse {
  plan: ScenePlan;
  preview: StoryPreview;
}

// ---------------------------------------------------------------------------
// API 함수
// ---------------------------------------------------------------------------

/**
 * 부모 서술형 텍스트 + 목적 + 아이 → ScenePlan + StoryPreview.
 *
 * 백엔드: `POST /api/v1/stories/plan` (S30a).
 * 비동기/SSE 아닌 동기 응답. LLM 호출 1~2회로 보통 5~15초 내 완료.
 *
 * 에러 매핑:
 * - 400 + `code === "REJECTED_INTENT"`: 가드레일이 거부 → 부드러운 안내.
 * - 401: JWT 만료 → 재로그인 유도.
 * - 404: child_id 소유자 불일치/존재하지 않음.
 * - 500: 일반 LLM 실패 → 잠시 후 재시도 안내.
 */
export async function createStoryPlan(
  input: PlanStoryRequest,
): Promise<PlanStoryResponse> {
  return apiFetch<PlanStoryResponse>("/stories/plan", {
    method: "POST",
    body: input,
  });
}
