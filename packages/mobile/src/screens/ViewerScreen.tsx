/**
 * 그림책 뷰어 (S33 — v3.1 디자인).
 *
 * 흐름: Generation(완료) → Viewer → (back) Home
 *
 * - Generation 완료 시 `navigation.reset({ routes: [Home, Viewer] })` 로 진입.
 *   뒤로가기/팝은 바로 Home 으로 이동하게 되어, 사용자가 "생성 진행 화면"으로
 *   돌아가는 어색한 흐름을 피한다.
 * - 마운트 시 `getStory(storyId)` 1회 호출 → StoryDetailResponse 로 페이지 렌더.
 * - 페이지 넘기기: 가로 FlatList + `pagingEnabled`. 스와이프 한 번에 한 페이지.
 * - 각 페이지: 일러스트 영역(4:3) + 텍스트 카드. S26 이 채우기 전에는 placeholder.
 *
 * 디자인: storyViewer 전용 색상 적용.
 *   - bg: #FFF9EE, text: #3D3225, accent: #E88D5A
 *   - 스토리 텍스트: Cafe24Ssurround, 22px, lineHeight 44
 *   - 페이지 인디케이터: 도트 형식
 *   - 커스텀 헤더: "지우기" 좌측 + "X" 닫기 우측
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
  useWindowDimensions,
  type ListRenderItemInfo,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { colors, shadows, radius, typography, spacing, storyViewer } from "../theme";
import { ApiClientError } from "../api/client";
import { forceLogoutToLogin } from "../auth/bootstrap";
import {
  deleteStory,
  getStory,
  type StoryDetailResponse,
  type StoryPageDetail,
} from "../api/stories";

type Props = NativeStackScreenProps<RootStackParamList, "Viewer">;

// ---------------------------------------------------------------------------
// 컴포넌트
// ---------------------------------------------------------------------------

export const ViewerScreen: React.FC<Props> = ({ route, navigation }) => {
  const { storyId } = route.params;
  const { width: screenWidth } = useWindowDimensions();

  const [story, setStory] = useState<StoryDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [currentPageIndex, setCurrentPageIndex] = useState(0);

  // -------------------------------------------------------------------------
  // 스토리 로드 — 마운트 시 1회
  // -------------------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    const load = async (): Promise<void> => {
      try {
        const result = await getStory(storyId);
        if (cancelled) return;
        setStory(result);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiClientError) {
          if (err.status === 401) {
            // S27b — 토큰 만료/폐기 감지 시 저장소 비우고 Login 으로 강제 이동.
            void forceLogoutToLogin(navigation);
            return;
          } else if (err.status === 404) {
            setErrorMessage("이야기를 찾을 수 없어요.");
          } else {
            setErrorMessage("잠깐, 다시 한번 해볼게요 😊");
          }
        } else {
          setErrorMessage("예상치 못한 오류가 생겼어요.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [storyId]);

  // -------------------------------------------------------------------------
  // 페이지 추적 — 스와이프 완료 시 현재 페이지 index 갱신
  // -------------------------------------------------------------------------

  const handleMomentumScrollEnd = useCallback(
    (event: NativeSyntheticEvent<NativeScrollEvent>): void => {
      if (screenWidth <= 0) return;
      const nextIndex = Math.round(
        event.nativeEvent.contentOffset.x / screenWidth,
      );
      setCurrentPageIndex((prev) => (prev === nextIndex ? prev : nextIndex));
    },
    [screenWidth],
  );

  // FlatList 성능 힌트 — 항목 폭이 고정되어 있으므로 getItemLayout 제공 가능.
  const getItemLayout = useCallback(
    (_: ArrayLike<StoryPageDetail> | null | undefined, index: number) => ({
      length: screenWidth,
      offset: screenWidth * index,
      index,
    }),
    [screenWidth],
  );

  const handleClose = useCallback((): void => {
    navigation.goBack();
  }, [navigation]);

  // -------------------------------------------------------------------------
  // 삭제 CTA (S34) — 커스텀 헤더의 "지우기" 텍스트가 호출.
  //
  // 진입 경로 두 가지:
  //   A) Generation → reset([Home, Viewer]): 이 경우 stack 깊이 = 2.
  //      삭제 후 `navigation.popToTop()` 으로 Home 복귀.
  //   B) Library → Viewer (push): stack 깊이 = 3 (Home / Library / Viewer).
  //      삭제 후 `navigation.goBack()` 으로 Library 복귀하여 사라진 카드 확인.
  //
  // 두 경로 모두 `goBack()` 으로 충분하다 — A 에서는 reset 의 Home 으로,
  // B 에서는 Library 로 자연스럽게 돌아간다.
  // -------------------------------------------------------------------------

  const handleDelete = useCallback((): void => {
    if (story === null) return;
    Alert.alert(
      "이야기를 지울까요?",
      `"${story.title}" 을(를) 서재에서 영영 지워요. 이 동작은 되돌릴 수 없어요.`,
      [
        { text: "취소", style: "cancel" },
        {
          text: "지우기",
          style: "destructive",
          onPress: async () => {
            try {
              await deleteStory(storyId);
              navigation.goBack();
            } catch (err) {
              if (err instanceof ApiClientError) {
                if (err.status === 404) {
                  // 이미 서버에서 삭제된 상태 → 동일하게 뒤로.
                  navigation.goBack();
                  return;
                }
                if (err.status === 401) {
                  // S27b — 401 일관 정책: 저장소 비우고 Login 으로 강제 이동.
                  void forceLogoutToLogin(navigation);
                  return;
                }
              }
              Alert.alert(
                "잠깐, 다시 한번 해볼게요 😊",
                "이야기를 지우지 못했어요. 잠시 후 다시 시도해주세요.",
              );
            }
          },
        },
      ],
    );
  }, [navigation, story, storyId]);

  // -------------------------------------------------------------------------
  // 페이지 렌더 — 가로 스와이프 1칸씩
  // -------------------------------------------------------------------------

  const renderPage = useCallback(
    ({ item }: ListRenderItemInfo<StoryPageDetail>) => (
      <View style={[styles.page, { width: screenWidth }]}>
        <ScrollView
          style={styles.pageScrollContainer}
          contentContainerStyle={styles.pageScroll}
          showsVerticalScrollIndicator={false}
        >
          <View style={styles.illustrationWrap}>
            {item.illustration_url ? (
              <Image
                source={{ uri: item.illustration_url }}
                style={styles.illustration}
                resizeMode="cover"
                accessibilityLabel={`${item.page_number}페이지 그림`}
              />
            ) : (
              <View style={styles.illustrationPlaceholder}>
                <Text style={styles.placeholderEmoji}>🎨</Text>
                <Text style={styles.placeholderText}>
                  그림은 곧 도착해요
                </Text>
              </View>
            )}
          </View>

          <View style={styles.textCard}>
            <Text style={styles.pageNumberLabel}>{item.page_number}페이지</Text>
            <Text style={styles.pageText}>{item.text}</Text>
          </View>
        </ScrollView>
      </View>
    ),
    [screenWidth],
  );

  // -------------------------------------------------------------------------
  // 상태별 렌더
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={storyViewer.accent} size="large" />
        <Text style={styles.loadingText}>이야기를 펼치고 있어요 📖</Text>
      </View>
    );
  }

  if (errorMessage !== null || story === null) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>
          {errorMessage ?? "이야기를 불러올 수 없어요."}
        </Text>
        <Pressable
          style={styles.errorButton}
          onPress={handleClose}
          accessibilityRole="button"
          accessibilityLabel="처음으로 돌아가기"
        >
          <Text style={styles.errorButtonText}>처음으로</Text>
        </Pressable>
      </View>
    );
  }

  return <ViewerReady
    story={story}
    screenWidth={screenWidth}
    currentPageIndex={currentPageIndex}
    renderPage={renderPage}
    getItemLayout={getItemLayout}
    handleMomentumScrollEnd={handleMomentumScrollEnd}
    handleClose={handleClose}
    handleDelete={handleDelete}
  />;
};

// ---------------------------------------------------------------------------
// 성공 상태 하위 컴포넌트 — useMemo 훅을 조건부 렌더 이후로 빼내기 위해 분리
// ---------------------------------------------------------------------------

interface ViewerReadyProps {
  story: StoryDetailResponse;
  screenWidth: number;
  currentPageIndex: number;
  renderPage: (info: ListRenderItemInfo<StoryPageDetail>) => React.ReactElement;
  getItemLayout: (
    data: ArrayLike<StoryPageDetail> | null | undefined,
    index: number,
  ) => { length: number; offset: number; index: number };
  handleMomentumScrollEnd: (
    event: NativeSyntheticEvent<NativeScrollEvent>,
  ) => void;
  handleClose: () => void;
  handleDelete: () => void;
}

const ViewerReady: React.FC<ViewerReadyProps> = ({
  story,
  screenWidth,
  currentPageIndex,
  renderPage,
  getItemLayout,
  handleMomentumScrollEnd,
  handleClose,
  handleDelete,
}) => {
  const totalPages = story.pages.length;
  const clampedIndex = useMemo(
    () =>
      totalPages === 0
        ? 0
        : Math.min(Math.max(currentPageIndex, 0), totalPages - 1),
    [currentPageIndex, totalPages],
  );

  return (
    <View style={styles.viewerRoot}>
      {/* 커스텀 헤더: "지우기" 좌측 + "X" 닫기 우측 */}
      <View style={styles.customHeader}>
        <Pressable
          onPress={handleDelete}
          accessibilityRole="button"
          accessibilityLabel="이야기 지우기"
          hitSlop={8}
          style={styles.headerAction}
        >
          <Text style={styles.headerDeleteText}>지우기</Text>
        </Pressable>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {story.title}
        </Text>
        <Pressable
          onPress={handleClose}
          accessibilityRole="button"
          accessibilityLabel="닫기"
          hitSlop={8}
          style={styles.headerAction}
        >
          <Text style={styles.headerCloseText}>X</Text>
        </Pressable>
      </View>

      {/* 본문 — 가로 스와이프 페이지 */}
      <FlatList
        style={styles.pageList}
        data={story.pages}
        keyExtractor={(item) => item.id}
        renderItem={renderPage}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={handleMomentumScrollEnd}
        getItemLayout={getItemLayout}
        // 빠른 스와이프 시 끝까지 튀는 것을 방지.
        decelerationRate="fast"
        // 첫 렌더 시 0번째 페이지가 화면에 꽉 차도록 명시(가로 flex 이슈 가드).
        initialNumToRender={1}
        maxToRenderPerBatch={2}
        windowSize={3}
        extraData={screenWidth}
      />

      {/* 하단 도트 인디케이터 */}
      <View style={styles.footer}>
        <View
          style={styles.dotContainer}
          accessibilityLabel={`${clampedIndex + 1}페이지 / 전체 ${totalPages}페이지`}
        >
          {story.pages.map((_, idx) => (
            <View
              key={idx}
              style={[
                styles.dot,
                idx === clampedIndex ? styles.dotActive : styles.dotInactive,
              ]}
            />
          ))}
        </View>
      </View>
    </View>
  );
};

// ---------------------------------------------------------------------------
// 스타일
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  // ── 공통 ────────────────────────────────────────────
  centered: {
    flex: 1,
    backgroundColor: storyViewer.bg,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
    gap: spacing.base,
  },
  loadingText: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: storyViewer.text,
    textAlign: "center",
  },
  errorText: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: storyViewer.text,
    textAlign: "center",
    lineHeight: 22,
  },
  errorButton: {
    backgroundColor: storyViewer.accent,
    borderRadius: radius.md,
    paddingVertical: spacing.base,
    paddingHorizontal: spacing.xl,
    minHeight: 52,
    alignItems: "center",
    justifyContent: "center",
    ...shadows.accentGlow,
  },
  errorButtonText: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.base,
    color: colors.neutral[0],
  },

  // ── 뷰어 루트 ──────────────────────────────────────
  viewerRoot: {
    flex: 1,
    backgroundColor: storyViewer.bg,
  },

  // ── 커스텀 헤더 ─────────────────────────────────────
  customHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingTop: spacing["2xl"],
    paddingBottom: spacing.md,
    backgroundColor: storyViewer.bg,
  },
  headerAction: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    minWidth: 44,
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  headerDeleteText: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.sm,
    color: colors.semantic.error,
  },
  headerTitle: {
    flex: 1,
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.base,
    color: storyViewer.text,
    textAlign: "center",
    marginHorizontal: spacing.sm,
  },
  headerCloseText: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.lg,
    color: storyViewer.text,
  },

  // ── 페이지 ──────────────────────────────────────────
  pageList: {
    flex: 1,
    backgroundColor: storyViewer.bg,
  },
  page: {
    flex: 1,
  },
  pageScrollContainer: {
    flex: 1,
    backgroundColor: storyViewer.bg,
  },
  pageScroll: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.lg,
  },
  illustrationWrap: {
    width: "100%",
    aspectRatio: 4 / 3,
    borderRadius: radius.lg,
    overflow: "hidden",
    marginBottom: spacing.base,
    backgroundColor: colors.primary[50],
    ...shadows.softBase,
  },
  illustration: {
    width: "100%",
    height: "100%",
  },
  illustrationPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
  },
  placeholderEmoji: {
    fontSize: 40,
  },
  placeholderText: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs,
    color: colors.neutral[300],
  },
  textCard: {
    backgroundColor: colors.neutral[0],
    borderRadius: radius.lg,
    paddingVertical: spacing.lg,
    paddingHorizontal: spacing.lg,
    ...shadows.softBase,
  },
  pageNumberLabel: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.xs,
    color: storyViewer.accent,
    backgroundColor: colors.primary[50],
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
    overflow: "hidden",
    marginBottom: spacing.md,
  },
  pageText: {
    fontFamily: "Cafe24Ssurround",
    fontSize: typography.size.xl,
    color: storyViewer.text,
    lineHeight: 44,
  },

  // ── 하단 도트 인디케이터 ────────────────────────────
  footer: {
    alignItems: "center",
    paddingTop: spacing.md,
    paddingBottom: spacing.lg,
    backgroundColor: storyViewer.bg,
  },
  dotContainer: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: radius.full,
  },
  dotActive: {
    backgroundColor: colors.primary[400],
  },
  dotInactive: {
    backgroundColor: colors.neutral[300],
  },
});
