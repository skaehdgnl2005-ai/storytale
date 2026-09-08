/**
 * 이메일+비밀번호 로그인 / 회원가입 화면 (S27b — v3.1 디자인).
 *
 * 세션 1(백엔드) 계약:
 *  POST /auth/register/email  → 200 AuthTokens / 409 EMAIL_ALREADY_EXISTS / 422
 *  POST /auth/login/email     → 200 AuthTokens / 401 (3케이스 통일) / 422
 *
 * 본 화면은 "개발용 최소 로그인" 이다 — 소셜 OAuth 는 S27c 로 분리.
 * 과투자 금지: 비번 찾기/이메일 재발송/약관 동의 플로우는 S27c 또는 S38 이후로 미룸.
 */

import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { colors, shadows, radius, typography, spacing } from "../theme";
import {
  ApiClientError,
  loginWithEmail,
  registerWithEmail,
  setAccessToken,
} from "../api/client";
import { saveTokens } from "../storage/tokenStore";
import { StyledInput } from "../components/StyledInput";
import { PremiumCreateButton } from "../components/PremiumCreateButton";
import { SecondaryButton } from "../components/SecondaryButton";

type Props = NativeStackScreenProps<RootStackParamList, "Login">;

type Mode = "login" | "signup";

// 백엔드 MIN_PASSWORD_LENGTH 와 일치. 422 를 서버까지 왕복시키지 않고 클라이언트에서 안내.
const MIN_PASSWORD_LENGTH = 8;

const EMAIL_ALREADY_EXISTS_CODE = "EMAIL_ALREADY_EXISTS";

export const LoginScreen: React.FC<Props> = ({ navigation }) => {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // 서버가 최종 검증하지만, 명백한 빈값/짧은 비번은 미리 막아서 422 왕복을 줄인다.
  const isValid =
    email.trim().length > 0 && password.length >= MIN_PASSWORD_LENGTH;

  const toggleMode = () => {
    setMode((m) => (m === "login" ? "signup" : "login"));
    setErrorMessage(null);
  };

  const handleSubmit = async () => {
    if (!isValid || loading) return;

    setLoading(true);
    setErrorMessage(null);

    try {
      const normalizedEmail = email.trim();
      const tokens =
        mode === "signup"
          ? await registerWithEmail(normalizedEmail, password)
          : await loginWithEmail(normalizedEmail, password);

      // 메모리 + 영구 저장소 순서로 주입. 영구 저장소가 실패해도 현재 세션은
      // 사용 가능하므로 catch 하지 않고 throw 를 전파 (상위 catch 에서 에러 배너).
      setAccessToken(tokens.access_token);
      await saveTokens({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      });

      // Login 스택 완전 제거. Home 으로 진입 후 back 해도 LoginScreen 재진입 못함.
      navigation.reset({ index: 0, routes: [{ name: "MainTabs" }] });
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  };

  const handleError = (err: unknown) => {
    if (!(err instanceof ApiClientError)) {
      setErrorMessage("잠깐, 다시 한번 해볼게요");
      return;
    }

    if (mode === "signup" && err.status === 409 && err.code === EMAIL_ALREADY_EXISTS_CODE) {
      // 모드 자동 전환으로 UX 개선 — 사용자는 회원가입 시도했는데 이미 있으면
      // 같은 입력값 그대로 로그인 탭으로 넘어가도록.
      setMode("login");
      setErrorMessage("이미 가입된 이메일이에요. 로그인으로 바꿔드렸어요 😊");
      return;
    }

    if (err.status === 401) {
      // 백엔드가 3가지 케이스를 통일해서 돌려주므로 힌트 없이 일반 메시지만.
      setErrorMessage("이메일이나 비밀번호를 다시 확인해주세요");
      return;
    }

    if (err.status === 422) {
      setErrorMessage(err.detail || "입력 형식이 올바르지 않아요");
      return;
    }

    setErrorMessage(err.detail || "잠깐, 다시 한번 해볼게요");
  };

  const submitLabel = mode === "signup" ? "가입하기" : "로그인";
  const toggleLabel =
    mode === "signup" ? "이미 계정이 있어요" : "처음이에요, 가입할래요";

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        {/* StoryTale 텍스트 로고 */}
        <Text style={styles.logo}>StoryTale</Text>

        {/* 마스코트 앵커 영역 */}
        <View style={styles.mascotAnchor} />

        <Text style={styles.title}>
          {mode === "signup" ? "첫 이야기를 시작해볼까요" : "다시 만나서 반가워요"}
        </Text>
        <Text style={styles.subtitle}>
          {mode === "signup"
            ? "이메일과 비밀번호로 가입할 수 있어요"
            : "가입했던 이메일로 로그인해주세요"}
        </Text>

        {errorMessage ? (
          <View style={styles.errorBanner} accessibilityLiveRegion="polite">
            <Text style={styles.errorText}>{errorMessage}</Text>
          </View>
        ) : null}

        <Text style={styles.label}>이메일</Text>
        <StyledInput
          value={email}
          onChangeText={setEmail}
          placeholder="예: parent@example.com"
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="email"
          textContentType="emailAddress"
          maxLength={254}
          accessibilityLabel="이메일 입력"
        />

        <Text style={styles.label}>비밀번호</Text>
        <StyledInput
          value={password}
          onChangeText={setPassword}
          placeholder="8자 이상"
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          textContentType={mode === "signup" ? "newPassword" : "password"}
          accessibilityLabel="비밀번호 입력"
        />

        <View style={styles.submitWrap}>
          <PremiumCreateButton
            label={submitLabel}
            onPress={handleSubmit}
            disabled={!isValid}
            loading={loading}
            accessibilityLabel={submitLabel}
          />
        </View>

        <SecondaryButton
          label={toggleLabel}
          onPress={toggleMode}
          disabled={loading}
          variant="text"
          accessibilityLabel={toggleLabel}
          style={styles.toggleButton}
        />
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  container: {
    flex: 1,
    backgroundColor: colors.neutral[50],
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl,
    paddingBottom: spacing["2xl"],
  },
  logo: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size["2xl"],
    color: colors.neutral[800],
    textAlign: "center",
    marginBottom: spacing.base,
  },
  mascotAnchor: {
    height: 120,
    marginBottom: spacing.lg,
  },
  title: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.xl,
    color: colors.neutral[800],
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[300],
    marginBottom: spacing.xl,
  },
  errorBanner: {
    backgroundColor: "#FDECEC",
    borderColor: colors.semantic.error,
    borderWidth: 1,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginBottom: spacing.base,
  },
  errorText: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.semantic.error,
  },
  label: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.sm,
    color: colors.neutral[800],
    marginBottom: spacing.sm,
    marginTop: spacing.base,
  },
  submitWrap: {
    marginTop: spacing.xl,
  },
  toggleButton: {
    alignSelf: "center",
    marginTop: spacing.base,
  },
});
