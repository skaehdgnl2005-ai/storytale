/**
 * 서술형 입력 화면 (S30b).
 *
 * 흐름: PurposeSelect → DescriptiveInput → (S31) Preview
 *
 * - 목적별로 다른 질문/예시 가이드 제공.
 * - 부모는 1~500자의 자유 서술 입력 (security.md 부모 입력 제한).
 * - `POST /stories/plan` 호출 → ScenePlan + StoryPreview 수신.
 * - 응답을 받으면 S31 미리보기 화면으로 넘겨야 하나, S31 미구현 상태이므로
 *   임시로 Alert 으로 결과 요약을 표시한다 (TODO(S31)).
 *
 * child_id 처리:
 *   - 현재 mobile 에 "선택된 child" 상태 관리가 없음 (SESSION_LOG S30a 메모).
 *   - 마운트 시 listProfiles() → 첫 프로필 자동 사용 + 화면 상단에 이름 노출.
 *   - 다중 자녀 가구는 S31 picker 도입 후 해소 (SESSION_LOG에 기록).
 *
 * 디자인: docs/visual-identity-guide-rn.md v3.1
 *   - StyledInput (multiline) + 프로그레스 바 문자 카운트
 *   - PremiumCreateButton 으로 Primary CTA
 *   - 새 theme tokens (colors, shadows, radius, typography, spacing)
 */

import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { CommonActions } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { HomeTabParamList } from "../navigation/AppNavigator";
import type { PurposeId } from "../data/purposes";
import { colors, radius, shadows, spacing, typography } from "../theme";
import { ApiClientError } from "../api/client";
import { forceLogoutToLogin } from "../auth/bootstrap";
import { listProfiles, type ChildProfile } from "../api/profiles";
import {
  PARENT_TEXT_MAX_LENGTH,
  REJECTED_INTENT_CODE,
  createStoryPlan,
} from "../api/stories";
import { StyledInput } from "../components/StyledInput";
import { PremiumCreateButton } from "../components/PremiumCreateButton";
import { Card } from "../components/Card";

type Props = NativeStackScreenProps<HomeTabParamList, "DescriptiveInput">;

// ---------------------------------------------------------------------------
// 목적별 가이드 카피 — `Record<PurposeId, ...>` 가 컴파일 타임에 4종 모두 강제.
// (S29 의 PURPOSE_CARDS 와 동일하게, 백엔드 IntentCategory 와 1:1 매핑.)
// ---------------------------------------------------------------------------

interface PurposeGuide {
  /** 입력 영역 위 큰 글씨. 부모 친근 톤. */
  prompt: string;
  /** TextInput placeholder. */
  placeholder: string;
  /** 부모가 막막할 때 참고할 짧은 예시. 1~2개. */
  examples: readonly string[];
}

const PURPOSE_GUIDES: Record<PurposeId, PurposeGuide> = {
  value_teaching: {
    prompt: "어떤 마음을 알려주고 싶으세요?",
    placeholder: "예: 거짓말하지 않는 용기를 알려주고 싶어요",
    examples: [
      "혼자 잘 수 있는 용기를 길러주고 싶어요",
      "친구에게 양보하는 마음을 함께 배웠으면 해요",
    ],
  },
  interest_story: {
    prompt: "아이가 푹 빠진 게 뭐예요?",
    placeholder: "예: 공룡을 너무 좋아해요, 특히 트리케라톱스",
    examples: [
      "우주랑 별자리에 매일 빠져 있어요",
      "공룡 중에서도 티라노사우루스를 제일 좋아해요",
    ],
  },
  problem_solving: {
    prompt: "지금 어떤 일을 함께 풀어보고 싶으세요?",
    placeholder: "예: 동생이 태어났는데 자꾸 동생을 밀쳐요",
    examples: [
      "어린이집 가는 걸 너무 무서워해요",
      "동생이 생긴 뒤로 떼를 자주 써요",
    ],
  },
  celebration: {
    prompt: "어떤 날을 기념하고 싶으세요?",
    placeholder: "예: 다음 주가 생일인데 특별한 책을 만들어주고 싶어요",
    examples: [
      "다음 달 어린이집 입학을 응원하고 싶어요",
      "할머니 댁에 처음 혼자 다녀온 날을 기억해주고 싶어요",
    ],
  },
};

// ---------------------------------------------------------------------------
// 컴포넌트
// ---------------------------------------------------------------------------

type ProfileState =
  | { kind: "loading" }
  | { kind: "ready"; child: ChildProfile }
  | { kind: "empty" } // 프로필 없음 → 등록 유도
  | { kind: "error"; message: string };

export const DescriptiveInputScreen: React.FC<Props> = ({
  route,
  navigation,
}) => {
  const { purpose } = route.params;
  const guide = PURPOSE_GUIDES[purpose];

  const [text, setText] = useState("");
  const [profileState, setProfileState] = useState<ProfileState>({
    kind: "loading",
  });
  const [submitting, setSubmitting] = useState(false);

  // 마운트 시 첫 프로필 자동 선택. (SESSION_LOG S30b: 임시 — S31 picker 예정)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const profiles = await listProfiles();
        if (cancelled) return;
        if (profiles.length === 0) {
          setProfileState({ kind: "empty" });
        } else {
          setProfileState({ kind: "ready", child: profiles[0] });
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiClientError && err.status === 401) {
          // S27b — 401 일관 정책: 저장소 비우고 Login 으로 강제 이동.
          void forceLogoutToLogin(navigation);
          return;
        }
        setProfileState({
          kind: "error",
          message: "프로필을 불러오지 못했어요. 잠시 후 다시 시도해주세요.",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
    // navigation 은 React Navigation 이 보장하는 stable ref. 한 번만 실행된다.
  }, [navigation]);

  const trimmedLength = useMemo(() => text.trim().length, [text]);
  const overLimit = text.length > PARENT_TEXT_MAX_LENGTH;
  const canSubmit =
    profileState.kind === "ready" &&
    trimmedLength > 0 &&
    !overLimit &&
    !submitting;

  const handleApiError = (err: unknown): void => {
    if (!(err instanceof ApiClientError)) {
      Alert.alert(
        "잠깐, 다시 한번 해볼게요 😊",
        "예상치 못한 오류가 생겼어요.",
      );
      return;
    }

    if (err.status === 400 && err.code === REJECTED_INTENT_CODE) {
      Alert.alert(
        "이 이야기는 함께 만들기 어려워요",
        err.detail || "조금 다른 표현으로 다시 들려주실래요?",
      );
      return;
    }

    if (err.status === 401) {
      // S27b — 토큰 만료/폐기 감지 시 저장소 비우고 Login 으로 강제 이동.
      // fire-and-forget: handleApiError 는 void 반환이므로 await 하지 않음.
      void forceLogoutToLogin(navigation);
      return;
    }

    if (err.status === 404) {
      Alert.alert(
        "선택한 아이를 찾을 수 없어요",
        "프로필이 사라졌거나 권한이 없어요.",
      );
      return;
    }

    if (err.status === 422) {
      Alert.alert(
        "잠깐, 입력을 확인해 주세요",
        "1~500자 사이로 적어주세요.",
      );
      return;
    }

    Alert.alert("잠깐, 다시 한번 해볼게요 😊", "잠시 후 다시 시도해주세요.");
  };

  const handleSubmit = async (): Promise<void> => {
    if (profileState.kind !== "ready" || !canSubmit) return;

    setSubmitting(true);
    try {
      const result = await createStoryPlan({
        parent_text: text.trim(),
        purpose_category: purpose,
        child_id: profileState.child.id,
      });

      // S31: Preview 화면으로 plan + preview 전달.
      navigation.navigate("Preview", {
        plan: result.plan,
        preview: result.preview,
        childId: profileState.child.id,
        childName: profileState.child.name,
      });
    } catch (err) {
      handleApiError(err);
    } finally {
      setSubmitting(false);
    }
  };

  // -------------------------------------------------------------------------
  // 진행률 계산 (문자 카운트 프로그레스 바)
  // -------------------------------------------------------------------------

  const progressPercent = Math.min(
    100,
    Math.round((text.length / PARENT_TEXT_MAX_LENGTH) * 100),
  );

  // -------------------------------------------------------------------------
  // 렌더
  // -------------------------------------------------------------------------

  if (profileState.kind === "loading") {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.primary[400]} />
      </View>
    );
  }

  if (profileState.kind === "empty") {
    return (
      <View style={styles.centered}>
        <Text style={styles.emptyTitle}>먼저 아이 프로필을 만들어주세요</Text>
        <Text style={styles.emptyBody}>
          이야기 속 주인공이 될 아이의 이름과 좋아하는 것들을 알려주세요.
        </Text>
        <PremiumCreateButton
          label="프로필 만들기"
          onPress={() => navigation.dispatch(CommonActions.navigate("MyPageTab", { screen: "ProfileForm" }))}
          accessibilityLabel="아이 프로필 만들기"
        />
      </View>
    );
  }

  if (profileState.kind === "error") {
    return (
      <View style={styles.centered}>
        <Text style={styles.emptyTitle}>잠깐, 다시 한번 해볼게요 😊</Text>
        <Text style={styles.emptyBody}>{profileState.message}</Text>
      </View>
    );
  }

  const counterTone = overLimit
    ? styles.counterOver
    : trimmedLength > 0
      ? styles.counterActive
      : styles.counterMuted;

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        style={styles.flex}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.childChip}>
          {profileState.child.name}에게 들려줄 이야기
        </Text>
        <Text style={styles.title}>{guide.prompt}</Text>
        <Text style={styles.subtitle}>
          1~2문장이면 충분해요. 당신이 아이를 가장 잘 아니까요.
        </Text>

        <StyledInput
          style={[styles.input, overLimit && styles.inputError]}
          value={text}
          onChangeText={setText}
          placeholder={guide.placeholder}
          multiline
          textAlignVertical="top"
          maxLength={PARENT_TEXT_MAX_LENGTH + 50}
          accessibilityLabel="이야기 내용 입력"
          accessibilityHint={`최대 ${PARENT_TEXT_MAX_LENGTH}자까지 적을 수 있어요`}
        />

        {/* 문자 카운트 프로그레스 바 */}
        <View style={styles.progressBarTrack}>
          <View
            style={[
              styles.progressBarFill,
              { width: `${progressPercent}%` },
              overLimit && styles.progressBarOver,
            ]}
          />
        </View>

        <View style={styles.counterRow}>
          <Text style={[styles.counter, counterTone]}>
            {text.length}/{PARENT_TEXT_MAX_LENGTH}
          </Text>
          {overLimit && (
            <Text style={styles.counterWarning}>
              {PARENT_TEXT_MAX_LENGTH}자 이내로 줄여주세요
            </Text>
          )}
        </View>

        <Card style={styles.examplesBlock}>
          <Text style={styles.examplesTitle}>이렇게 적어도 좋아요</Text>
          {guide.examples.map((example) => (
            <Text key={example} style={styles.exampleItem}>
              · {example}
            </Text>
          ))}
        </Card>
      </ScrollView>

      <View style={styles.footer}>
        <PremiumCreateButton
          label={submitting ? "이야기가 자라고 있어요 🌱" : "이야기 만들기"}
          onPress={handleSubmit}
          disabled={!canSubmit}
          loading={submitting}
          accessibilityLabel="이야기 만들기"
        />
      </View>
    </KeyboardAvoidingView>
  );
};

// ---------------------------------------------------------------------------
// 스타일
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  flex: {
    flex: 1,
    backgroundColor: colors.neutral[50],
  },
  centered: {
    flex: 1,
    backgroundColor: colors.neutral[50],
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
    gap: spacing.md,
  },
  emptyTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.lg,
    color: colors.neutral[800],
    textAlign: "center",
  },
  emptyBody: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[300],
    textAlign: "center",
    marginBottom: spacing.base,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.lg,
  },
  childChip: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.xs,
    color: colors.primary[500],
    backgroundColor: colors.primary[50],
    alignSelf: "flex-start",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: radius.full,
    marginBottom: spacing.base,
    overflow: "hidden",
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
    marginBottom: spacing.lg - 4,
    lineHeight: 20,
  },
  input: {
    minHeight: 140,
    lineHeight: 24,
    borderRadius: radius.md,
    textAlignVertical: "top",
  },
  inputError: {
    borderColor: colors.semantic.error,
  },
  progressBarTrack: {
    height: 4,
    borderRadius: radius.full,
    backgroundColor: colors.neutral[200],
    overflow: "hidden",
    marginTop: spacing.sm,
  },
  progressBarFill: {
    height: "100%",
    backgroundColor: colors.primary[400],
    borderRadius: radius.full,
  },
  progressBarOver: {
    backgroundColor: colors.semantic.error,
  },
  counterRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: spacing.sm,
    minHeight: 18,
  },
  counter: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs,
  },
  counterMuted: {
    color: colors.neutral[300],
  },
  counterActive: {
    color: colors.neutral[800],
  },
  counterOver: {
    color: colors.semantic.error,
  },
  counterWarning: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs,
    color: colors.semantic.error,
  },
  examplesBlock: {
    marginTop: spacing.lg,
  },
  examplesTitle: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.sm,
    color: colors.neutral[800],
    marginBottom: spacing.sm,
  },
  exampleItem: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs,
    color: colors.neutral[300],
    lineHeight: 20,
  },
  footer: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.lg,
    backgroundColor: colors.neutral[50],
    borderTopWidth: 1,
    borderTopColor: colors.neutral[100],
  },
});
