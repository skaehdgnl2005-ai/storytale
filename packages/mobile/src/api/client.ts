/**
 * API 클라이언트 — fetch 기반, JWT 토큰 자동 첨부.
 *
 * S28: 프로필 API 연동을 위한 최소 인프라.
 * S27b: 이메일+비밀번호 로그인 API 함수 + AuthTokens 타입 추가.
 */

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
}

export class ApiClientError extends Error {
  constructor(
    public status: number,
    public detail: string,
    public code?: string,
  ) {
    super(detail);
    this.name = "ApiClientError";
  }
}

/**
 * 백엔드 에러 응답 본문을 파싱한다.
 *
 * 백엔드(`storytale/app.py::custom_http_exception_handler`)는 모든 HTTPException을
 * `{"error": {"code": <status>, "message": <string|dict>}}` 형식으로 래핑한다.
 *
 * S30a에서 도입된 RejectedIntentError 패턴은 detail 자리에 dict를 넘긴다:
 *   `{"error": {"code": 400, "message": {"code": "REJECTED_INTENT", "message": "..."}}}`
 *
 * 레거시 `{"detail": "..."}` 형식도 호환한다 (S20 이전 일부 라우터).
 */
function parseErrorBody(body: unknown): { detail?: string; code?: string } {
  if (typeof body !== "object" || body === null) return {};

  // 1) 래핑 형식: {error: {code, message}}
  const errObj = (body as { error?: unknown }).error;
  if (typeof errObj === "object" && errObj !== null) {
    const message = (errObj as { message?: unknown }).message;
    if (typeof message === "string") {
      return { detail: message };
    }
    if (typeof message === "object" && message !== null) {
      // detail에 dict가 들어간 케이스 (REJECTED_INTENT 등)
      const innerMessage = (message as { message?: unknown }).message;
      const innerCode = (message as { code?: unknown }).code;
      return {
        detail: typeof innerMessage === "string" ? innerMessage : undefined,
        code: typeof innerCode === "string" ? innerCode : undefined,
      };
    }
  }

  // 2) 레거시 형식: {detail: "..."}
  const legacyDetail = (body as { detail?: unknown }).detail;
  if (typeof legacyDetail === "string") {
    return { detail: legacyDetail };
  }

  return {};
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, headers: customHeaders, ...rest } = options;

  const headers: Record<string, string> = {
    ...(customHeaders as Record<string, string>),
  };

  if (accessToken) {
    headers["Authorization"] = `Bearer ${accessToken}`;
  }

  if (body !== undefined && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers,
    body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    let detail = "알 수 없는 오류가 발생했어요";
    let code: string | undefined;
    try {
      const errorBody: unknown = await response.json();
      const parsed = parseErrorBody(errorBody);
      if (parsed.detail) detail = parsed.detail;
      code = parsed.code;
    } catch {
      // JSON 파싱 실패 시 기본 메시지 사용
    }
    throw new ApiClientError(response.status, detail, code);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// S27b — 이메일+비밀번호 인증 API
// ---------------------------------------------------------------------------

/**
 * 백엔드 AuthTokens 응답 형식. S27/S27b 공통.
 * 계약: packages/backend/src/storytale/auth/schemas.py::AuthTokens
 */
export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  expires_in: number;
}

/**
 * 현재 로그인한 사용자 정보. `GET /auth/me` 응답.
 * 계약: packages/backend/src/storytale/api/auth_router.py::get_me
 */
export interface CurrentUser {
  user_id: string;
  email: string | null;
  provider: string;
  consent_given: boolean;
}

/**
 * 이메일+비밀번호 회원가입.
 *
 * - 성공: AuthTokens (access + refresh + expires_in).
 * - 409 + code "EMAIL_ALREADY_EXISTS": 이미 가입된 이메일.
 * - 422: Pydantic 검증 실패 (이메일 형식 / 비번 길이 / UTF-8 72바이트 초과).
 */
export function registerWithEmail(email: string, password: string): Promise<AuthTokens> {
  return apiFetch<AuthTokens>("/auth/register/email", {
    method: "POST",
    body: { email, password },
  });
}

/**
 * 이메일+비밀번호 로그인.
 *
 * - 성공: AuthTokens.
 * - 401: 로그인 실패. 백엔드는 3가지 케이스(이메일 없음 / 비번 틀림 /
 *   소셜 전용 유저)를 동일 응답으로 처리 — 이메일 존재 여부 노출 방지.
 *   UI 는 "이메일 또는 비밀번호를 다시 확인해주세요" 로 통일.
 * - 422: 이메일 형식 검증 실패.
 */
export function loginWithEmail(email: string, password: string): Promise<AuthTokens> {
  return apiFetch<AuthTokens>("/auth/login/email", {
    method: "POST",
    body: { email, password },
  });
}

/**
 * 현재 토큰의 유효성 검증 + 사용자 정보 조회.
 * bootstrap 단계에서 저장된 토큰이 만료/폐기되었는지 확인한다.
 */
export function getCurrentUser(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/auth/me", { method: "GET" });
}
