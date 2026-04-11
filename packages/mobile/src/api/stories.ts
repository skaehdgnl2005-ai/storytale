/**
 * 스토리 API 함수 (S30b + S31 + S32).
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
 * ScenePlan 최대 수정 횟수. 백엔드 `MAX_REVISIONS`와 반드시 일치.
 *
 * 백엔드(`POST /stories/plan/revise`)는 요청의 `revision_count`가 이 값 이상이면
 * 400 + `MAX_REVISIONS_EXCEEDED`로 거부한다. 클라이언트는 UI에서도 동일한
 * 한도를 적용해 수정 입력을 disable 처리한다(이중 안전망).
 */
export const MAX_REVISIONS = 3 as const;

/**
 * 백엔드가 RejectedIntentError를 400으로 매핑할 때 사용하는 코드.
 * 클라이언트는 `ApiClientError.code === REJECTED_INTENT_CODE` 로 분기한다.
 */
export const REJECTED_INTENT_CODE = "REJECTED_INTENT" as const;

/**
 * 백엔드가 수정 한도 초과를 400으로 매핑할 때 사용하는 코드 (S31a).
 */
export const MAX_REVISIONS_EXCEEDED_CODE = "MAX_REVISIONS_EXCEEDED" as const;

/**
 * 생성 잡 폴링 간격 (ms). S32에서 `GET /stories/jobs/{jobId}` 를 반복 호출한다.
 *
 * 근거:
 * - 너무 짧으면(≤500ms) 백엔드/네트워크 부담 + 배터리 소모.
 * - 너무 길면(≥3s) 장면 카드가 뭉쳐서 등장해 애니메이션이 체감되지 않음.
 * - 1.5초는 Claude API 가 한 장면(4~6문장)을 생성하는 체감 시간과 근접하여
 *   장면 카드가 리듬감 있게 등장한다.
 */
export const JOB_POLL_INTERVAL_MS = 1500 as const;

/**
 * 백엔드 `JobStatus` Enum 과 1:1 매칭. 와이어 포맷이 문자열이므로 유니온으로 표현.
 */
export type JobStatusValue = "pending" | "in_progress" | "completed" | "failed";

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

export interface PlanRevisionRequest {
  current_plan: ScenePlan;
  feedback: string;
  /**
   * 이번 호출 이전까지 이미 적용된 수정 횟수 (0-based).
   * 백엔드는 `revision_count < MAX_REVISIONS` 일 때만 처리한다.
   */
  revision_count: number;
  child_id: string;
}

export interface PlanRevisionResponse {
  plan: ScenePlan;
  preview: StoryPreview;
  /** 이번 호출이 끝난 후의 누적 카운트 (= 요청 revision_count + 1). */
  revision_count: number;
}

// ---------------------------------------------------------------------------
// 생성 요청/응답 (S32) — 백엔드 POST /stories/generate + GET /stories/jobs/{id}
// ---------------------------------------------------------------------------

/**
 * 스토리 생성 요청 body. 백엔드 `GenerateStoryRequest` 와 1:1 매칭.
 *
 * child 는 백엔드 `ChildInput` 구조로, mobile `profiles.ts::ChildProfile` 을
 * GenerationScreen 에서 매핑해 전달한다 (id → child_id 이름 차이만 있음).
 */
export interface ChildInput {
  child_id: string;
  name: string;
  age: number;
  gender: string;
  comfort_object?: string | null;
  friend_name?: string | null;
  favorite_animal?: string | null;
}

export interface GenerateStoryRequest {
  confirmed_plan: ScenePlan;
  child: ChildInput;
  /** 백엔드 VALID_STYLES: "watercolor" | "pastel_crayon" | "clean_digital". */
  style: string;
}

export interface GenerateStoryResponse {
  job_id: string;
}

/**
 * 폴링 시 수신하는 생성된 장면 1건의 모양.
 *
 * 백엔드 `_run_generation` 이 `scene.model_dump()` 를 그대로 `job.scenes` 에
 * 추가하므로, `GeneratedScene` 는 `StoryOrchestrator.generate_story()` 의
 * `PersonalizedScene` 필드와 동일하다 (snake_case).
 * illustration_url 은 S26(일러스트 파이프라인) 완료 후 채워진다.
 */
export interface GeneratedScene {
  scene_id: string;
  page_number: number;
  text: string;
  illustration_prompt: string;
  illustration_url?: string | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatusValue;
  total_scenes: number;
  completed_scenes: number;
  scenes: GeneratedScene[];
  error: string | null;
  story_id: string | null;
}

// ---------------------------------------------------------------------------
// 스토리 조회 (S33) — 백엔드 GET /stories/{story_id}
// ---------------------------------------------------------------------------

/**
 * 저장된 스토리의 단일 페이지. 백엔드 `StoryPageResponse` 와 1:1 매칭.
 *
 * `GeneratedScene`(잡 폴링용)과 분리한 이유:
 * - `GeneratedScene` 은 "생성 진행 중" 스냅샷 용도로 `scene_id` 기반.
 * - `StoryPageDetail` 은 DB 저장 후 조회용으로 `id`(페이지 row PK) + `scene_id` 를
 *   모두 가짐. 뷰어는 `id` 를 FlatList key 로 사용한다(재마운트 안정성).
 */
export interface StoryPageDetail {
  id: string;
  page_number: number;
  scene_id: string;
  text: string;
  illustration_prompt: string;
  illustration_url: string | null;
}

/**
 * 스토리 상세 응답. 백엔드 `StoryDetailResponse` 와 1:1 매칭.
 *
 * 페이지는 `page_number` 오름차순으로 서버가 정렬해서 내려준다.
 */
export interface StoryDetailResponse {
  id: string;
  title: string;
  status: string;
  style: string;
  /** ISO 8601 문자열. 백엔드 `datetime.isoformat()`. */
  created_at: string;
  page_count: number;
  pages: StoryPageDetail[];
}

/**
 * 저장된 스토리 단건 조회. ViewerScreen(S33) 이 마운트 시 1회 호출.
 *
 * 백엔드: `GET /api/v1/stories/{story_id}` (S20).
 * 소유자 검증은 서버에서 JWT 기준으로 수행되며, 남의 스토리는 404 로 동일 처리된다.
 *
 * 에러 매핑 (ViewerScreen 에서 사용):
 * - 401: JWT 만료 → 재로그인 유도.
 * - 404: 존재하지 않음 또는 소유자 불일치 → "이야기를 찾을 수 없어요" 안내.
 * - 그 외: "잠깐, 다시 한번 해볼게요 😊".
 */
export async function getStory(storyId: string): Promise<StoryDetailResponse> {
  return apiFetch<StoryDetailResponse>(`/stories/${storyId}`);
}

// ---------------------------------------------------------------------------
// 내 서재 — 목록/삭제 (S34)
// ---------------------------------------------------------------------------

/**
 * 스토리 목록 한 행. 백엔드 `StoryListItem` 와 1:1 매칭 (snake_case).
 *
 * `StoryDetailResponse` 와 달리 `pages` 가 없다 — 목록은 카드만 그릴 정보만 포함.
 * 카드 탭 → `getStory(id)` 로 전체 페이지를 받아오는 흐름.
 */
export interface StoryListItem {
  id: string;
  title: string;
  status: string;
  style: string;
  /** ISO 8601 문자열. 백엔드 `datetime.isoformat()`. */
  created_at: string;
  page_count: number;
}

/**
 * 스토리 목록 응답. 백엔드 `StoryListResponse` 와 1:1 매칭.
 *
 * 페이지네이션은 limit/offset 기반(api-conventions.md). 응답에 `total` 포함되어
 * 무한 스크롤 종료 시점을 클라이언트가 알 수 있다.
 */
export interface StoryListResponse {
  items: StoryListItem[];
  total: number;
  limit: number;
  offset: number;
}

/** 내 서재 기본 페이지 크기. 한 화면에 카드 ~6개 + 여유분. */
export const STORIES_PAGE_SIZE = 20 as const;

/**
 * 본인 스토리 목록을 페이지네이션으로 조회한다 (LibraryScreen).
 *
 * 백엔드: `GET /api/v1/stories?limit=&offset=` (S20).
 * 정렬은 서버가 `created_at desc` 로 내려준다 (최신 스토리가 위).
 *
 * 에러 매핑:
 * - 401: JWT 만료 → 재로그인 유도.
 * - 그 외: "잠깐, 다시 한번 해볼게요 😊".
 */
export async function listStories(
  options: { limit?: number; offset?: number } = {},
): Promise<StoryListResponse> {
  const limit = options.limit ?? STORIES_PAGE_SIZE;
  const offset = options.offset ?? 0;
  const query = `?limit=${limit}&offset=${offset}`;
  return apiFetch<StoryListResponse>(`/stories${query}`);
}

/**
 * 본인 스토리를 삭제한다. LibraryScreen 의 카드 long-press 또는 ViewerScreen
 * 의 삭제 CTA 가 호출한다.
 *
 * 백엔드: `DELETE /api/v1/stories/{story_id}` (S34) → 204 No Content.
 * `apiFetch` 가 204 일 때 `undefined` 를 반환하므로 본 함수는 void 를 돌려준다.
 *
 * 에러 매핑:
 * - 401: JWT 만료 → 재로그인 유도.
 * - 404: 이미 삭제됨 또는 소유자 불일치(서버에서 동일 처리) → "이야기를 찾을 수 없어요".
 * - 그 외: "잠깐, 다시 한번 해볼게요 😊".
 */
export async function deleteStory(storyId: string): Promise<void> {
  await apiFetch<void>(`/stories/${storyId}`, { method: "DELETE" });
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

/**
 * ScenePlan + 부모 피드백 → 수정된 ScenePlan + 새 StoryPreview + 갱신된 카운트.
 *
 * 백엔드: `POST /api/v1/stories/plan/revise` (S31a).
 * 응답의 `revision_count`를 다음 호출에 그대로 넘긴다 (stateless flow).
 *
 * 에러 매핑:
 * - 400 + `code === "MAX_REVISIONS_EXCEEDED"`: 한도 초과 → 안내만 표시.
 * - 400 + `code === "REJECTED_INTENT"`: 가드레일 거부 → 부드러운 안내.
 * - 401/404/422/500: createStoryPlan 과 동일.
 */
export async function revisePlan(
  input: PlanRevisionRequest,
): Promise<PlanRevisionResponse> {
  return apiFetch<PlanRevisionResponse>("/stories/plan/revise", {
    method: "POST",
    body: input,
  });
}

/**
 * 확정된 ScenePlan + child + style → 백그라운드 생성 시작.
 *
 * 백엔드: `POST /api/v1/stories/generate` (S19) → 202 + `{job_id}`.
 * 실제 장면 생성은 백그라운드 태스크에서 진행되므로 이 호출은 즉시 반환된다.
 * 클라이언트는 `getJobStatus(job_id)` 를 `JOB_POLL_INTERVAL_MS` 간격으로 폴링
 * 하여 장면이 하나씩 채워지는 과정을 UI에 반영한다.
 *
 * 에러 매핑:
 * - 401: JWT 만료 → 재로그인 유도.
 * - 422: ScenePlan/style 검증 실패 → 잠시 후 다시 시도.
 * - 500: LLM 호출 실패 → 잠시 후 다시 시도.
 */
export async function generateStory(
  input: GenerateStoryRequest,
): Promise<GenerateStoryResponse> {
  return apiFetch<GenerateStoryResponse>("/stories/generate", {
    method: "POST",
    body: input,
  });
}

/**
 * 생성 잡 상태 조회. GenerationScreen 이 `JOB_POLL_INTERVAL_MS` 간격으로 호출.
 *
 * 백엔드: `GET /api/v1/stories/jobs/{job_id}`.
 * 완료 시 `status === "completed"` + `story_id` 채워짐.
 * 실패 시 `status === "failed"` + `error` 채워짐.
 *
 * 404: job_id 유효하지 않음 (MVP 인메모리 잡 매니저 — 서버 재시작 후 소실).
 */
export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return apiFetch<JobStatusResponse>(`/stories/jobs/${jobId}`);
}
