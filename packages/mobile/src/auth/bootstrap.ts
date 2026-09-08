/**
 * 앱 시작 시 인증 부트스트랩 (S27b).
 *
 * 저장된 토큰을 로드 → `setAccessToken` 으로 메모리 주입 →
 * `GET /auth/me` 로 서버 측 유효성 검증 → 결과에 따라 초기 라우트 결정.
 *
 * 토큰이 없거나 검증 실패 시 저장소를 비우고 Login 으로 진입.
 * 네트워크 오류(서버 꺼짐 등)는 "유효" 로 간주하지 않는다 — 로그인 화면으로
 * 보내 사용자가 재시도할 기회를 제공한다.
 */

import { CommonActions } from "@react-navigation/native";
import { ApiClientError, getCurrentUser, setAccessToken } from "../api/client";
import { clearTokens, loadTokens } from "../storage/tokenStore";

export type BootstrapRoute = "MainTabs" | "Login";

/**
 * 앱 진입 시 초기 라우트를 결정한다.
 *
 * - 토큰 없음 → Login
 * - 토큰 있음 + /auth/me 200 → Home
 * - 토큰 있음 + /auth/me 401 → 토큰 폐기 + Login
 * - 토큰 있음 + 네트워크/서버 오류 → Login (사용자 재시도 유도)
 */
export async function bootstrapAuth(): Promise<BootstrapRoute> {
  const tokens = await loadTokens();
  if (!tokens) {
    return "Login";
  }

  setAccessToken(tokens.accessToken);

  try {
    await getCurrentUser();
    return "MainTabs";
  } catch (err) {
    // 401 은 "서버가 명시적으로 토큰을 거부" — 저장소를 비운다.
    // 나머지는 일시적 오류 가능성이 있으므로 토큰은 남겨두되 메모리는 비운다.
    if (err instanceof ApiClientError && err.status === 401) {
      await clearTokens();
    }
    setAccessToken(null);
    return "Login";
  }
}

/**
 * 화면 내에서 401 을 감지했을 때 Login 으로 강제 이동한다 (S27b).
 *
 * 1. 메모리 토큰 비움 → 이후 apiFetch 호출은 Authorization 헤더 없음.
 * 2. 영구 저장소 비움 → 앱 재시작 시 bootstrapAuth 가 토큰을 찾지 못해 Login 경로.
 * 3. navigation.reset 으로 Login 하나만 남은 stack 으로 교체 → back 으로 authed
 *    화면에 복귀 불가.
 *
 * 주의: `/auth/logout` 은 현재 no-op 버그 상태(SESSION_LOG S27b 세션 1 참조)
 * 이므로 서버 호출은 일부러 하지 않는다. S27d 에서 logout 버그 수정 후
 * 여기서도 서버 무효화를 병행하도록 재검토.
 */
export async function forceLogoutToLogin(
  navigation: { dispatch: (action: ReturnType<typeof CommonActions.reset>) => void },
): Promise<void> {
  setAccessToken(null);
  await clearTokens();
  navigation.dispatch(
    CommonActions.reset({ index: 0, routes: [{ name: "Login" }] }),
  );
}
