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
 * 디자인: docs/visual-identity-guide-rn.md Section 12
 *   - warm pastel, borderRadius 14/20, Pretendard, shadowColor "#3E3225"
 *   - 최소 터치 타겟 52px, accessibilityLabel 필수
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
  TextInput,
  View,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { theme } from "../theme";
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

type Props = NativeStackScreenProps<RootStackParamList, "Preview">;

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
        <View style={styles.summaryCard}>
          <Text style={styles.summaryText}>{preview.summary}</Text>
        </View>

        {/* 장면 하이라이트 */}
        <Text style={styles.sectionTitle}>이런 장면들이 펼쳐져요</Text>
        <View style={styles.scenesBlock}>
          {preview.scene_highlights.map((highlight, idx) => (
            <View key={`${idx}-${highlight}`} style={styles.sceneCard}>
              <Text style={styles.sceneNumber}>{idx + 1}</Text>
              <Text style={styles.sceneText}>{highlight}</Text>
            </View>
          ))}
        </View>

        {/* 수정 섹션 */}
        <View style={styles.reviseSection}>
          <View style={styles.reviseHeaderRow}>
            <Text style={styles.sectionTitle}>마음에 들지 않는 부분이 있나요?</Text>
            <Text
              style={[
                styles.revisionBadge,
                !canRevise && styles.revisionBadgeLocked,
              ]}
              accessibilityLabel={`수정 ${revisionCount} 회 사용, ${revisionsRemaining} 회 남음`}
            >
              수정 {revisionCount}/{MAX_REVISIONS}
            </Text>
          </View>

          {canRevise ? (
            <>
              <TextInput
                style={[styles.input, overLimit && styles.inputError]}
                value={feedback}
                onChangeText={setFeedback}
                placeholder="예: 토끼 친구 대신 서준이가 나왔으면 좋겠어요"
                placeholderTextColor={theme.colors.textSecondary}
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

              <Pressable
                style={[
                  styles.secondaryButton,
                  !canSubmitRevision && styles.secondaryDisabled,
                ]}
                onPress={handleRevise}
                disabled={!canSubmitRevision}
                accessibilityRole="button"
                accessibilityLabel="이렇게 바꿔주세요"
                accessibilityState={{
                  disabled: !canSubmitRevision,
                  busy: revising,
                }}
              >
                {revising ? (
                  <View style={styles.buttonRow}>
                    <ActivityIndicator color={theme.colors.primary} />
                    <Text style={styles.secondaryButtonText}>
                      이야기를 다듬고 있어요 ✨
                    </Text>
                  </View>
                ) : (
                  <Text style={styles.secondaryButtonText}>
                    이렇게 바꿔주세요
                  </Text>
                )}
              </Pressable>
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
        <Pressable
          style={[styles.primaryButton, revising && styles.primaryDisabled]}
          onPress={handleConfirm}
          disabled={revising}
          accessibilityRole="button"
          accessibilityLabel="이 이야기로 만들기"
        >
          <Text style={styles.primaryButtonText}>이 이야기로 만들기</Text>
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
};

// ---------------------------------------------------------------------------
// 스타일
// ---------------------------------------------------------------------------

const buttonShadow = Platform.select({
  ios: {
    shadowColor: "#3E3225",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
  },
  android: {
    elevation: 4,
  },
});

const cardShadow = Platform.select({
  ios: {
    shadowColor: "#3E3225",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 6,
  },
  android: {
    elevation: 2,
  },
});

const styles = StyleSheet.create({
  flex: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 24,
  },
  childChip: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: 13,
    color: theme.colors.primary,
    backgroundColor: theme.colors.primaryLight,
    alignSelf: "flex-start",
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
    marginBottom: 12,
    overflow: "hidden",
  },
  title: {
    fontFamily: "Pretendard-Bold",
    fontSize: 26,
    color: theme.colors.text,
    lineHeight: 34,
    marginBottom: 8,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 20,
  },
  metaBadge: {
    fontFamily: "Pretendard-Medium",
    fontSize: 12,
    color: theme.colors.textSecondary,
    backgroundColor: theme.colors.white,
    borderWidth: 1,
    borderColor: theme.colors.border,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    overflow: "hidden",
  },
  summaryCard: {
    backgroundColor: theme.colors.white,
    borderRadius: 20,
    padding: 20,
    marginBottom: 28,
    ...cardShadow,
  },
  summaryText: {
    fontFamily: "Pretendard-Medium",
    fontSize: 15,
    color: theme.colors.text,
    lineHeight: 24,
  },
  sectionTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: 17,
    color: theme.colors.text,
    marginBottom: 12,
  },
  scenesBlock: {
    marginBottom: 28,
    gap: 10,
  },
  sceneCard: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: theme.colors.white,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: theme.colors.border,
    paddingVertical: 14,
    paddingHorizontal: 16,
    gap: 12,
  },
  sceneNumber: {
    fontFamily: "Pretendard-Bold",
    fontSize: 14,
    color: theme.colors.primary,
    backgroundColor: theme.colors.primaryLight,
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
    fontSize: 14,
    color: theme.colors.text,
    lineHeight: 20,
  },
  reviseSection: {
    marginTop: 4,
  },
  reviseHeaderRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  revisionBadge: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: 12,
    color: theme.colors.primary,
    backgroundColor: theme.colors.primaryLight,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    overflow: "hidden",
  },
  revisionBadgeLocked: {
    color: theme.colors.textSecondary,
    backgroundColor: theme.colors.border,
  },
  input: {
    backgroundColor: theme.colors.white,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: theme.colors.border,
    paddingHorizontal: 16,
    paddingVertical: 14,
    minHeight: 110,
    fontFamily: "Pretendard-Medium",
    fontSize: 15,
    color: theme.colors.text,
    lineHeight: 22,
  },
  inputError: {
    borderColor: "#D9534F",
  },
  counterRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 8,
    minHeight: 18,
  },
  counter: {
    fontFamily: "Pretendard-Medium",
    fontSize: 12,
  },
  counterMuted: {
    color: theme.colors.textSecondary,
  },
  counterActive: {
    color: theme.colors.text,
  },
  counterOver: {
    color: "#D9534F",
  },
  counterWarning: {
    fontFamily: "Pretendard-Medium",
    fontSize: 12,
    color: "#D9534F",
  },
  secondaryButton: {
    marginTop: 12,
    backgroundColor: theme.colors.primaryLight,
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 20,
    minHeight: 52,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: theme.colors.primary,
  },
  secondaryDisabled: {
    opacity: 0.5,
  },
  secondaryButtonText: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: 15,
    color: theme.colors.primary,
  },
  lockedCard: {
    backgroundColor: theme.colors.white,
    borderRadius: 14,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: theme.colors.border,
    padding: 16,
  },
  lockedText: {
    fontFamily: "Pretendard-Medium",
    fontSize: 13,
    color: theme.colors.textSecondary,
    lineHeight: 20,
    textAlign: "center",
  },
  footer: {
    paddingHorizontal: 24,
    paddingTop: 12,
    paddingBottom: 24,
    backgroundColor: theme.colors.background,
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
  },
  primaryButton: {
    backgroundColor: theme.colors.primary,
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 24,
    minHeight: 52,
    alignItems: "center",
    justifyContent: "center",
    ...buttonShadow,
  },
  primaryDisabled: {
    opacity: 0.5,
  },
  primaryButtonText: {
    fontFamily: "Pretendard-Bold",
    fontSize: 17,
    color: theme.colors.white,
  },
  buttonRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
});
