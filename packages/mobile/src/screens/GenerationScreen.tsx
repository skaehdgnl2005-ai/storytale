/**
 * 생성 중 로딩 UX (S32).
 *
 * 흐름: Preview → Generation → (S33) Library/Viewer
 *
 * - PreviewScreen 의 확정 CTA 가 이 화면으로 네비게이트한다.
 * - 마운트 시 `getProfile(childId)` 로 child 전체 정보를 재조회한 뒤
 *   `POST /stories/generate` (S19) 를 호출해 백그라운드 생성 잡을 시작한다.
 * - 잡이 시작되면 `GET /stories/jobs/{job_id}` 를 `JOB_POLL_INTERVAL_MS`(1.5s)
 *   간격으로 폴링하여 `scenes` 배열이 늘어나는 과정을 UI 에 반영한다.
 * - 새 장면 카드가 추가될 때마다 `LayoutAnimation.spring` 으로 부드럽게 등장.
 *
 * SSE vs 폴링 선택:
 *   React Native 기본 `fetch` 는 SSE 파서가 없고, Expo managed 에서 추가
 *   네이티브 모듈(react-native-sse) 도입은 MVP 범위를 넘음. 백엔드는
 *   `/jobs/{id}/stream` 과 `/jobs/{id}` 둘 다 지원하므로, MVP 에서는 폴링만
 *   사용한다. SSE 전환은 S35/E2E 이후 성능 검토에서 재결정 (TODO(post-S32)).
 *
 * child 재조회 이유:
 *   Preview 화면은 route params 에 `{childId, childName}` 만 보유. `/stories/generate`
 *   백엔드 라우터는 `ChildInput {child_id, name, age, gender, comfort_object,
 *   friend_name, favorite_animal}` 전체를 요구하므로 getProfile 한 번 더.
 *   (현재 라우터는 요청 바디의 child 를 그대로 사용하므로 DB 일관성 보장 목적도 있음.)
 *
 * 디자인: docs/visual-identity-guide-rn.md Section 12
 *   - warm pastel, borderRadius 14/20, Pretendard, shadowColor "#3E3225"
 *   - 최소 터치 타겟 52px, accessibilityLabel 필수
 *   - 생성 상태 카피는 CLAUDE.md 톤 가이드(로딩: "이야기가 자라고 있어요 🌱")
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  LayoutAnimation,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  UIManager,
  View,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { theme } from "../theme";
import { ApiClientError } from "../api/client";
import { getProfile, type ChildProfile } from "../api/profiles";
import {
  JOB_POLL_INTERVAL_MS,
  generateStory,
  getJobStatus,
  type GeneratedScene,
  type JobStatusValue,
} from "../api/stories";

type Props = NativeStackScreenProps<RootStackParamList, "Generation">;

// Android 에서 LayoutAnimation 을 쓰려면 experimental 플래그를 켜야 한다
// (iOS 는 기본 활성). Expo SDK 54 기준으로도 여전히 필요한 가드.
if (
  Platform.OS === "android" &&
  UIManager.setLayoutAnimationEnabledExperimental
) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

// ---------------------------------------------------------------------------
// helper: ChildProfile → /stories/generate 의 ChildInput 매핑
// ---------------------------------------------------------------------------

const toChildInput = (profile: ChildProfile) => ({
  child_id: profile.id,
  name: profile.name,
  age: profile.age,
  gender: profile.gender,
  comfort_object: profile.comfort_object ?? null,
  friend_name: profile.friend_name ?? null,
  favorite_animal: profile.favorite_animal ?? null,
});

// ---------------------------------------------------------------------------
// 컴포넌트
// ---------------------------------------------------------------------------

export const GenerationScreen: React.FC<Props> = ({ route, navigation }) => {
  const { plan, childId, childName, style } = route.params;

  const [status, setStatus] = useState<JobStatusValue>("pending");
  const [totalScenes, setTotalScenes] = useState(plan.scenes.length);
  const [completedScenes, setCompletedScenes] = useState(0);
  const [scenes, setScenes] = useState<GeneratedScene[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // S33: 완료 시 snapshot.story_id 를 받아 Viewer 로 넘긴다.
  // 백엔드 `_run_generation` 은 `job.status = COMPLETED` 직전에 `job.story_id` 를
  // 채우므로, status === "completed" 스냅샷에서 story_id 는 항상 채워져 있다.
  const [storyId, setStoryId] = useState<string | null>(null);

  // 직전 렌더에서 본 scenes.length — 변화 감지용.
  // state 로 두면 비교가 한 박자 늦어 LayoutAnimation 호출이 어긋난다.
  const lastSceneCountRef = useRef(0);

  // -------------------------------------------------------------------------
  // 에러 매핑 — 기존 스크린 패턴(S30b/S31) 재사용
  // -------------------------------------------------------------------------

  const handleApiError = useCallback(
    (err: unknown, stage: "start" | "poll"): void => {
      if (!(err instanceof ApiClientError)) {
        setErrorMessage("예상치 못한 오류가 생겼어요.");
        return;
      }

      if (err.status === 401) {
        // TODO(post-S27): 로그인 화면이 마련되면 navigation.replace("Login") 로 교체.
        setErrorMessage("다시 로그인해주세요. 로그인 정보가 만료됐어요.");
        return;
      }

      if (err.status === 404 && stage === "poll") {
        // 폴링 중 404 = 서버 재시작 등으로 잡 상태 소실(MVP 인메모리 잡매니저).
        setErrorMessage(
          "서버가 잠시 쉬어가고 있어요. 이야기를 다시 만들어볼까요?",
        );
        return;
      }

      if (err.status === 404) {
        setErrorMessage("선택한 아이를 찾을 수 없어요.");
        return;
      }

      if (err.status === 422) {
        setErrorMessage("이야기 설계가 조금 어긋났어요. 미리보기로 돌아가 주세요.");
        return;
      }

      setErrorMessage("잠깐, 다시 한번 해볼게요 😊");
    },
    [],
  );

  // -------------------------------------------------------------------------
  // 생성 시작 + 폴링 루프 — 언마운트 시 안전하게 취소
  // -------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;
    let pollTimeout: ReturnType<typeof setTimeout> | null = null;

    const applySceneUpdate = (next: GeneratedScene[]): void => {
      if (next.length !== lastSceneCountRef.current) {
        // 장면 카드가 새로 등장할 때만 스프링 애니메이션 트리거.
        LayoutAnimation.configureNext(LayoutAnimation.Presets.spring);
        lastSceneCountRef.current = next.length;
      }
      setScenes(next);
    };

    const pollOnce = async (jobId: string): Promise<void> => {
      if (cancelled) return;
      try {
        const snapshot = await getJobStatus(jobId);
        if (cancelled) return;

        setStatus(snapshot.status);
        setTotalScenes(snapshot.total_scenes);
        setCompletedScenes(snapshot.completed_scenes);
        applySceneUpdate(snapshot.scenes);
        // S33: DB 저장이 끝나면 story_id 가 먼저 채워지고 그 다음 status 가 completed.
        // 같은 스냅샷에서 둘 다 받으므로 단일 렌더에 함께 커밋된다.
        if (snapshot.story_id) {
          setStoryId(snapshot.story_id);
        }

        if (snapshot.status === "completed") {
          return;
        }
        if (snapshot.status === "failed") {
          setErrorMessage(
            snapshot.error ?? "이야기를 만드는 중 문제가 생겼어요.",
          );
          return;
        }

        pollTimeout = setTimeout(
          () => void pollOnce(jobId),
          JOB_POLL_INTERVAL_MS,
        );
      } catch (err) {
        if (!cancelled) handleApiError(err, "poll");
      }
    };

    const start = async (): Promise<void> => {
      try {
        const profile = await getProfile(childId);
        if (cancelled) return;

        const { job_id } = await generateStory({
          confirmed_plan: plan,
          child: toChildInput(profile),
          style,
        });
        if (cancelled) return;

        setStatus("in_progress");
        // 첫 폴링은 즉시 — 짧은 장면은 이미 1장이 생성되었을 수 있음.
        await pollOnce(job_id);
      } catch (err) {
        if (!cancelled) handleApiError(err, "start");
      }
    };

    void start();

    return () => {
      cancelled = true;
      if (pollTimeout) clearTimeout(pollTimeout);
    };
    // route params 는 네비게이션 1회용이라 불변. 의존성은 childId/style/plan 로
    // 충분하지만, plan 객체 참조가 바뀌면 재시작된다(의도된 동작).
  }, [childId, plan, style, handleApiError]);

  // -------------------------------------------------------------------------
  // 핸들러
  // -------------------------------------------------------------------------

  const handleBackToHome = (): void => {
    navigation.popToTop();
  };

  const handleOpenBook = (): void => {
    // 방어 코드: 원칙상 status === "completed" + story_id 동시 수신이지만,
    // 만약 story_id 가 누락된 완료 스냅샷이 왔다면 Home 으로 복귀시켜 상한 흐름 방지.
    if (!storyId) {
      handleBackToHome();
      return;
    }
    // Generation 스택은 뒤로가기 차단 화면이므로, Viewer 에서 back 할 때
    // 사용자가 이 화면으로 돌아오지 않도록 스택을 [Home, Viewer] 로 재구성한다.
    navigation.reset({
      index: 1,
      routes: [{ name: "Home" }, { name: "Viewer", params: { storyId } }],
    });
  };

  // -------------------------------------------------------------------------
  // 렌더
  // -------------------------------------------------------------------------

  const isDone = status === "completed";
  const isFailed = status === "failed" || errorMessage !== null;
  const isBusy = !isDone && !isFailed;

  const progressRatio =
    totalScenes > 0
      ? Math.min(1, Math.max(0, completedScenes / totalScenes))
      : 0;
  const progressPercent = Math.round(progressRatio * 100);

  const headerLine = isFailed
    ? "잠깐, 다시 한번 해볼게요 😊"
    : isDone
      ? "이야기가 완성됐어요! 📖"
      : "이야기가 자라고 있어요 🌱";

  return (
    <View style={styles.flex}>
      <ScrollView
        style={styles.flex}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        {/* 상단 헤더 */}
        <Text style={styles.childChip}>{childName}를 위한 이야기</Text>
        <Text style={styles.title}>{plan.title}</Text>
        <Text style={styles.headerLine}>{headerLine}</Text>

        {/* 진행 상태 */}
        <View
          style={styles.progressCard}
          accessibilityLiveRegion="polite"
          accessibilityLabel={`${totalScenes}장 중 ${completedScenes}장 완성`}
        >
          <View style={styles.progressRow}>
            {isBusy && (
              <ActivityIndicator
                color={theme.colors.primary}
                accessibilityLabel="생성 중"
              />
            )}
            <Text style={styles.progressText}>
              {isFailed
                ? (errorMessage ?? "잠시 후 다시 시도해주세요.")
                : isDone
                  ? `${totalScenes}장의 이야기가 모두 완성됐어요.`
                  : `${completedScenes}/${totalScenes}장을 쓰고 있어요`}
            </Text>
          </View>
          <View style={styles.progressBarTrack}>
            <View
              style={[
                styles.progressBarFill,
                { width: `${progressPercent}%` },
                isFailed && styles.progressBarFailed,
              ]}
            />
          </View>
        </View>

        {/* 완성된 장면 카드 (LayoutAnimation.spring 으로 등장) */}
        {scenes.length > 0 && (
          <Text style={styles.sectionTitle}>지금까지 만들어진 이야기</Text>
        )}
        <View style={styles.scenesBlock}>
          {scenes.map((scene) => (
            <View key={scene.scene_id} style={styles.sceneCard}>
              <Text style={styles.sceneNumber}>{scene.page_number}</Text>
              <Text style={styles.sceneText} numberOfLines={3}>
                {scene.text}
              </Text>
            </View>
          ))}
        </View>

        {/* 아직 빈 상태 안내 */}
        {isBusy && scenes.length === 0 && (
          <View style={styles.emptyCard}>
            <Text style={styles.emptyText}>
              잠시만 기다려주세요. 첫 장면이 곧 도착해요.
            </Text>
          </View>
        )}
      </ScrollView>

      {/* 하단 고정 CTA */}
      <View style={styles.footer}>
        {isFailed ? (
          <Pressable
            style={styles.primaryButton}
            onPress={handleBackToHome}
            accessibilityRole="button"
            accessibilityLabel="처음으로"
          >
            <Text style={styles.primaryButtonText}>처음으로</Text>
          </Pressable>
        ) : isDone ? (
          <Pressable
            style={styles.primaryButton}
            onPress={handleOpenBook}
            accessibilityRole="button"
            accessibilityLabel="그림책 열어보기"
          >
            <Text style={styles.primaryButtonText}>그림책 열어보기</Text>
          </Pressable>
        ) : (
          <Pressable
            style={[styles.primaryButton, styles.primaryDisabled]}
            disabled
            accessibilityRole="button"
            accessibilityLabel="이야기 만드는 중"
            accessibilityState={{ disabled: true, busy: true }}
          >
            <Text style={styles.primaryButtonText}>이야기를 만들고 있어요…</Text>
          </Pressable>
        )}
      </View>
    </View>
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
    marginBottom: 6,
  },
  headerLine: {
    fontFamily: "Pretendard-Medium",
    fontSize: 15,
    color: theme.colors.textSecondary,
    marginBottom: 20,
  },
  progressCard: {
    backgroundColor: theme.colors.white,
    borderRadius: 20,
    padding: 20,
    marginBottom: 24,
    ...cardShadow,
  },
  progressRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginBottom: 14,
  },
  progressText: {
    flex: 1,
    fontFamily: "Pretendard-SemiBold",
    fontSize: 15,
    color: theme.colors.text,
    lineHeight: 22,
  },
  progressBarTrack: {
    height: 8,
    borderRadius: 999,
    backgroundColor: theme.colors.border,
    overflow: "hidden",
  },
  progressBarFill: {
    height: "100%",
    backgroundColor: theme.colors.primary,
    borderRadius: 999,
  },
  progressBarFailed: {
    backgroundColor: theme.colors.error,
  },
  sectionTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: 17,
    color: theme.colors.text,
    marginBottom: 12,
  },
  scenesBlock: {
    gap: 10,
  },
  sceneCard: {
    flexDirection: "row",
    alignItems: "flex-start",
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
  emptyCard: {
    backgroundColor: theme.colors.white,
    borderRadius: 14,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: theme.colors.border,
    padding: 16,
    alignItems: "center",
  },
  emptyText: {
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
});
