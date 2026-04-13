/**
 * 토큰 영구 저장소 (S27b).
 *
 * AsyncStorage 래퍼. access/refresh 토큰 쌍을 디바이스에 보관하여
 * 앱 재시작 후에도 로그인 상태를 유지한다.
 *
 * 보안 참고:
 * AsyncStorage 는 평문 저장소다 (iOS 는 sandbox 내부,
 * Android 는 shared_prefs XML). jailbreak/root 된 디바이스에서는
 * 토큰 탈취 위험이 있다. S38 배포 전 `expo-secure-store`
 * (iOS Keychain / Android Keystore) 로 마이그레이션 권장.
 * 자세한 내용은 docs/SESSION_LOG.md 의 S27b 세션 2 기술 부채 섹션 참조.
 */

import AsyncStorage from "@react-native-async-storage/async-storage";

// key 는 "storytale.auth." 네임스페이스로 묶어서 향후 마이그레이션 시 일괄 삭제가 쉽도록.
const ACCESS_TOKEN_KEY = "storytale.auth.accessToken";
const REFRESH_TOKEN_KEY = "storytale.auth.refreshToken";

export interface StoredTokens {
  accessToken: string;
  refreshToken: string;
}

export async function saveTokens(tokens: StoredTokens): Promise<void> {
  // multiSet 은 atomic 이 아니지만 개별 setItem 을 순차 실행하는 것보단 빠르다.
  // 중간 실패 시 loadTokens 가 둘 중 하나만 반환할 수 있으므로 null 체크로 방어.
  await AsyncStorage.multiSet([
    [ACCESS_TOKEN_KEY, tokens.accessToken],
    [REFRESH_TOKEN_KEY, tokens.refreshToken],
  ]);
}

export async function loadTokens(): Promise<StoredTokens | null> {
  const pairs = await AsyncStorage.multiGet([ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY]);
  const accessToken = pairs[0][1];
  const refreshToken = pairs[1][1];
  if (!accessToken || !refreshToken) {
    return null;
  }
  return { accessToken, refreshToken };
}

export async function clearTokens(): Promise<void> {
  await AsyncStorage.multiRemove([ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY]);
}
