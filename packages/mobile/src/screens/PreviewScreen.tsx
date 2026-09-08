/**
 * 미리보기 & 수정 화면 (S31).
 *
 * 흐름: DescriptiveInput → Preview → (S32) Generation
 *
 * - S30b에서 `createStoryPlan` 응답(plan + preview)을 route params로 받는다.
 * - 부모는 미리보기를 보고 최대 3회까지 자유 서술로 수정 요청을 보낼 수 있다.
 * - 수정은 `POST /stories/plan/revise` (S31a) 호출. 서버가 revision_count 한도 검증.
 * - "이 이야기로 만들기" CTA 는 S32(생성 중 로딩 UX) 에서 구현. 현재는 임시 Alert.
 *
 * 설계 메모:
 * - `plan` / `preview` / `revisionCount` 는 로컬 state. route params는 초기값만 제공.
 * - `revisionCount` 는 **클라이언트 카운터** — 서버가 응답으로 갱신값을 돌려주면 그대로 덮어씀.
 *   악의적 조작 방지는 서버가 한 번 더 검증하므로 이중 안전망.
 * - `MAX_REVISIONS` 상수는 `packages/mobile/src/api/stories.ts` 에서 백엔드와 동기화.
 *
 * 디자인: docs/visual-identity-guide-rn.md v3.1
 *   - Card 컴포넌트로 장면 하이라이트
 *   - PremiumCreateButton + SecondaryButton
 *   - StyledInput for revision feedback
 *   - 새 theme tokens (colors, shadows, radius, typography, spacing)
 */

import React, { useCallback, useMemo, useState } from "react";
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
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { HomeTabParamList } from "../navigation/AppNavigator";
import { colors, radius, shadows, spacing, typography } from "../theme";
import { ApiClientError } from "../api/client";
import { forceLogoutToLogin } from "../auth/bootstrap";
import {
  MAX_REVISIONS,
  MAX_REVISIONS_EXCEEDED_CODE,
  PARENT_TEXT_MAX_LENGTH,
  REJECTED_INTENT_CODE,
  revisePlan,
  type ScenePlan,
  type StoryPreview,
} from "../api/stories";
import { Card } from "../components/Card";
import { StyledInput } from "../components/StyledInput";
import { PremiumCreateButton } from "../components/PremiumCreateButton";
import { SecondaryButton } from "../components/SecondaryButton";

type Props = NativeStackScreenProps<HomeTabParamList, "Preview">;

// ---------------------------------------------------------------------------
// 컴포넌트
// ---------------------------------------------------------------------------

export const PreviewScreen: React.FC<Props> = ({ route, navigation }) => {
  const { childId, childName } = route.params;

  // plan / preview / revisionCount 는 서버 응답으로 갱신되는 로컬 state.
  const [plan, setPlan] = useState<ScenePlan>(route.params.plan);
  const [preview, setPreview] = useState<StoryPreview>(route.params.preview);
  const [revisionCount, setRevisionCount] = useState(0);

  const [feedback, setFeedback] = useState("");
  const [revising, setRevising] = useState(false);

  const revisionsRemaining = MAX_REVISIONS - revisionCount;
  const canRevise = revisionsRemaining > 0;

  const trimmedLength = useMemo(() => feedback.trim().length, [feedback]);
  const overLimit = feedback.length > PARENT_TEXT_MAX_LENGTH;
  const canSubmitRevision =
    canRevise && trimmedLength > 0 && !overLimit && !revising;

  // -------------------------------------------------------------------------
  // 에러 매핑 — S30b 패턴 + MAX_REVISIONS_EXCEEDED 분기 추가
  // -------------------------------------------------------------------------

  const handleApiError = useCallback((err: unknown): void => {
    if (!(err instanceof ApiClientError)) {
      Alert.alert(
        "잠깐, 다시 한번 해볼게요 😊",
        "예상치 못한 오류가 생겼어요.",
      );
      return;
    }

    if (err.status === 400 && err.code === MAX_REVISIONS_EXCEEDED_CODE) {
      Alert.alert(
        "수정은 여기까지예요",
        `수정은 최대 ${MAX_REVISIONS}회까지 가능해요. 지금 이야기를 그대로 만들어볼까요?`,
      );
      return;
    }

    if (err.status === 400 && err.code === REJECTED_INTENT_CODE) {
      Alert.alert(
        "이 수정은 함께 만들기 어려워요",
        err.detail || "조금 다른 표현으로 다시 들려주실래요?",
      );
      return;
    }

    if (err.status === 401) {
      // S27b — 토큰 만료/폐기 감지 시 저장소 비우고 Login 으로 강제 이동.
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
      Alert.alert("잠깐, 입력을 확인해 주세요", "1~500자 사이로 적어주세요.");
      return;
    }

    Alert.alert("잠깐, 다시 한번 해볼게요 😊", "잠시 후 다시 시도해주세요.");
    // navigation 은 stable ref 이지만 exhaustive-deps 일관성을 위해 명시.
  }, [navigation]);

  // -------------------------------------------------------------------------
  // 수정 요청
  // -------------------------------------------------------------------------

  const handleRevise = async (): Promise<void> => {
    if (!canSubmitRevision) return;

    setRevising(true);
    try {
      const result = await revisePlan({
        current_plan: plan,
        feedback: feedback.trim(),
        revision_count: revisionCount,
        child_id: childId,
      });

      setPlan(result.plan);
      setPreview(result.preview);
      setRevisionCount(result.revision_count);
      setFeedback("");
    } catch (err) {
      handleApiError(err);
    } finally {
      setRevising(false);
    }
  };

  // -------------------------------------------------------------------------
  // 확정 → 생성 (S32 로 네비게이트)
  // -------------------------------------------------------------------------

  const handleConfirm = (): void => {
    // S32: GenerationScreen 에서 POST /stories/generate + 폴링 루프.
    // plan 은 최신 revise 결과를 그대로 넘긴다. style 은 preview 가 보유.
    navigation.navigate("Generation", {
      plan,
      childId,
      childName,
      style: preview.style,
    });
  };

  // -------------------------------------------------------------------------
  // 렌더
  // -------------------------------------------------------------------------

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
        {/* 상단 헤더 */}
        <Text style={styles.childChip}>{childName}에게 들려줄 이야기</Text>
        <Text style={styles.title}>{preview.title}</Text>
        <View style={styles.metaRow}>
          <Text style={styles.metaBadge}>{preview.page_count}장의 이야기</Text>
        </View>

        {/* 요약 카드 */}
        <Card style={styles.summaryCard}>
          <Text style={styles.summaryText}>{preview.summary}</Text>
        </Card>

        {/* 장면 하이라이트 */}
        <Text style={styles.sectionTitle}>이런 장면들이 펼쳐져요</Text>
        <View style={styles.scenesBlock}>
          {preview.scene_highlights.map((highlight, idx) => (
            <Card key={`${idx}-${highlight}`} style={styles.sceneCard}>
              <View style={styles.sceneRow}>
                <Text style={styles.sceneNumber}>{idx + 1}</Text>
                <Text style={styles.sceneText}>{highlight}</Text>
              </View>
            </Card>
          ))}
        </View>

        {/* 수정 섹션 */}
        <View style={styles.reviseSection}>
          <View style={styles.reviseHeaderRow}>
            <Text style={styles.sectionTitle}>마음에 들지 않는 부분이 있나요?</Text>
            <View
              style={[
                styles.revisionBadge,
                !canRevise && styles.revisionBadgeLocked,
              ]}
            >
              <Text
                style={[
                  styles.revisionBadgeText,
                  !canRevise && styles.revisionBadgeTextLocked,
                ]}
                accessibilityLabel={`수정 ${revisionCount} 회 사용, ${revisionsRemaining} 회 남음`}
              >
                수정 {revisionCount}/{MAX_REVISIONS}
              </Text>
            </View>
          </View>

          {canRevise ? (
            <>
              <StyledInput
                style={[styles.reviseInput, overLimit && styles.inputError]}
                value={feedback}
                onChangeText={setFeedback}
                placeholder="예: 토끼 친구 대신 서준이가 나왔으면 좋겠어요"
                multiline
                textAlignVertical="top"
                maxLength={PARENT_TEXT_MAX_LENGTH + 50}
                accessibilityLabel="수정 요청 입력"
                accessibilityHint={`최대 ${PARENT_TEXT_MAX_LENGTH}자까지 적을 수 있어요`}
                editable={!revising}
              />

              <View style={styles.counterRow}>
                <Text style={[styles.counter, counterTone]}>
                  {feedback.length}/{PARENT_TEXT_MAX_LENGTH}
                </Text>
                {overLimit && (
                  <Text style={styles.counterWarning}>
                    {PARENT_TEXT_MAX_LENGTH}자 이내로 줄여주세요
                  </Text>
                )}
              </View>

              <SecondaryButton
                label={revising ? "이야기를 다듬고 있어요 ✨" : "이렇게 바꿔주세요"}
                onPress={handleRevise}
                disabled={!canSubmitRevision}
                accessibilityLabel="이렇게 바꿔주세요"
                style={styles.reviseButton}
              />
            </>
          ) : (
            <View style={styles.lockedCard}>
              <Text style={styles.lockedText}>
                수정은 {MAX_REVISIONS}회까지 가능해요. 이제 이야기를 만들어볼까요?
              </Text>
            </View>
          )}
        </View>
      </ScrollView>

      {/* 고정 확정 CTA */}
      <View style={styles.footer}>
        <PremiumCreateButton
          label="이 이야기로 만들기"
          onPress={handleConfirm}
          disabled={revising}
          accessibilityLabel="이 이야기로 만들기"
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
    marginBottom: spacing.md,
    overflow: "hidden",
  },
  title: {
    fontFamily: "Pretendard-Bold",
    fontSize: 26,
    color: colors.neutral[800],
    lineHeight: 34,
    marginBottom: spacing.sm,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.lg - 4,
  },
  metaBadge: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs,
    color: colors.neutral[300],
    backgroundColor: colors.neutral[0],
    borderWidth: 1,
    borderColor: colors.neutral[100],
    paddingHorizontal: 10,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
    overflow: "hidden",
  },
  summaryCard: {
    marginBottom: spacing.xl - 4,
  },
  summaryText: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm + 1,
    color: colors.neutral[800],
    lineHeight: 24,
  },
  sectionTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.base,
    color: colors.neutral[800],
    marginBottom: spacing.md,
  },
  scenesBlock: {
    marginBottom: spacing.xl - 4,
    gap: 10,
  },
  sceneCard: {
    paddingVertical: spacing.md + 2,
    paddingHorizontal: spacing.base,
  },
  sceneRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  sceneNumber: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.sm,
    color: colors.primary[400],
    backgroundColor: colors.primary[50],
    width: 28,
    height: 28,
    borderRadius: 14,
    textAlign: "center",
    lineHeight: 28,
    overflow: "hidden",
  },
  sceneText: {
    flex: 1,
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[800],
    lineHeight: 20,
  },
  reviseSection: {
    marginTop: spacing.xs,
  },
  reviseHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  revisionBadge: {
    backgroundColor: colors.primary[50],
    paddingHorizontal: 10,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
  },
  revisionBadgeLocked: {
    backgroundColor: colors.neutral[100],
  },
  revisionBadgeText: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.xs,
    color: colors.primary[500],
  },
  revisionBadgeTextLocked: {
    color: colors.neutral[300],
  },
  reviseInput: {
    minHeight: 110,
    lineHeight: 22,
    borderRadius: radius.md,
    textAlignVertical: "top",
  },
  inputError: {
    borderColor: colors.semantic.error,
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
  reviseButton: {
    marginTop: spacing.md,
  },
  lockedCard: {
    backgroundColor: colors.neutral[0],
    borderRadius: radius.md,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: colors.neutral[100],
    padding: spacing.base,
  },
  lockedText: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs,
    color: colors.neutral[300],
    lineHeight: 20,
    textAlign: "center",
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
