/**
 * 그림책 뷰어 (S33).
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
 * 디자인: docs/visual-identity-guide-rn.md Section 12
 *   - warm pastel, borderRadius 14/20, Pretendard, shadowColor "#3E3225"
 *   - 최소 터치 타겟 52px, accessibilityLabel 필수
 *   - 로딩: "이야기가 자라고 있어요 🌱"
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Image,
  Platform,
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
import { theme } from "../theme";
import { ApiClientError } from "../api/client";
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
            // TODO(post-S27): 로그인 화면 마련되면 navigation.replace("Login").
            setErrorMessage("다시 로그인해주세요. 로그인 정보가 만료됐어요.");
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

  const handleBackToHome = useCallback((): void => {
    navigation.popToTop();
  }, [navigation]);

  // -------------------------------------------------------------------------
  // 삭제 CTA (S34) — headerRight 의 "지우기" 버튼이 호출.
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
                  Alert.alert(
                    "로그인이 필요해요",
                    "로그인 정보가 만료됐어요. 다시 로그인해주세요.",
                  );
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

  // 스토리 로드 후 headerRight 에 "지우기" 버튼을 노출.
  // 로딩/에러 상태에서는 헤더 액션을 보여주지 않는다(잘못 누름 방지).
  useEffect(() => {
    if (story === null) {
      navigation.setOptions({ headerRight: undefined });
      return;
    }
    navigation.setOptions({
      headerRight: () => (
        <Pressable
          onPress={handleDelete}
          accessibilityRole="button"
          accessibilityLabel="이야기 지우기"
          hitSlop={8}
          style={styles.headerDeleteButton}
        >
          <Text style={styles.headerDeleteText}>지우기</Text>
        </Pressable>
      ),
    });
  }, [navigation, story, handleDelete]);

  // -------------------------------------------------------------------------
  // 페이지 렌더 — 가로 스와이프 1칸씩
  // -------------------------------------------------------------------------

  const renderPage = useCallback(
    ({ item }: ListRenderItemInfo<StoryPageDetail>) => (
      <View style={[styles.page, { width: screenWidth }]}>
        <ScrollView
          style={styles.flex}
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
        <ActivityIndicator color={theme.colors.primary} size="large" />
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
          style={styles.primaryButton}
          onPress={handleBackToHome}
          accessibilityRole="button"
          accessibilityLabel="처음으로 돌아가기"
        >
          <Text style={styles.primaryButtonText}>처음으로</Text>
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
    handleBackToHome={handleBackToHome}
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
  handleBackToHome: () => void;
}

const ViewerReady: React.FC<ViewerReadyProps> = ({
  story,
  screenWidth,
  currentPageIndex,
  renderPage,
  getItemLayout,
  handleMomentumScrollEnd,
  handleBackToHome,
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
    <View style={styles.flex}>
      {/* 상단 제목 */}
      <View style={styles.headerCard}>
        <Text style={styles.title} numberOfLines={2}>
          {story.title}
        </Text>
      </View>

      {/* 본문 — 가로 스와이프 페이지 */}
      <FlatList
        style={styles.flex}
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

      {/* 하단 페이지 표시 + Home 복귀 */}
      <View style={styles.footer}>
        <Text
          style={styles.pageIndicator}
          accessibilityLabel={`${clampedIndex + 1}페이지 / 전체 ${totalPages}페이지`}
        >
          {clampedIndex + 1} / {totalPages}
        </Text>
        <Pressable
          style={styles.homeButton}
          onPress={handleBackToHome}
          accessibilityRole="button"
          accessibilityLabel="처음으로 돌아가기"
        >
          <Text style={styles.homeButtonText}>처음으로</Text>
        </Pressable>
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
  centered: {
    flex: 1,
    backgroundColor: theme.colors.background,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
    gap: 16,
  },
  loadingText: {
    fontFamily: "Pretendard-Medium",
    fontSize: 15,
    color: theme.colors.textSecondary,
    textAlign: "center",
  },
  errorText: {
    fontFamily: "Pretendard-Medium",
    fontSize: 15,
    color: theme.colors.text,
    textAlign: "center",
    lineHeight: 22,
  },
  headerCard: {
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 12,
    backgroundColor: theme.colors.background,
  },
  title: {
    fontFamily: "Pretendard-Bold",
    fontSize: 22,
    color: theme.colors.text,
    lineHeight: 30,
  },
  page: {
    flex: 1,
  },
  pageScroll: {
    paddingHorizontal: 24,
    paddingTop: 8,
    paddingBottom: 24,
  },
  illustrationWrap: {
    width: "100%",
    aspectRatio: 4 / 3,
    borderRadius: 20,
    overflow: "hidden",
    marginBottom: 16,
    backgroundColor: theme.colors.primaryLight,
    ...cardShadow,
  },
  illustration: {
    width: "100%",
    height: "100%",
  },
  illustrationPlaceholder: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
  },
  placeholderEmoji: {
    fontSize: 40,
  },
  placeholderText: {
    fontFamily: "Pretendard-Medium",
    fontSize: 13,
    color: theme.colors.textSecondary,
  },
  textCard: {
    backgroundColor: theme.colors.white,
    borderRadius: 20,
    paddingVertical: 18,
    paddingHorizontal: 20,
    ...cardShadow,
  },
  pageNumberLabel: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: 12,
    color: theme.colors.primary,
    backgroundColor: theme.colors.primaryLight,
    alignSelf: "flex-start",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    overflow: "hidden",
    marginBottom: 10,
  },
  pageText: {
    fontFamily: "Pretendard-Medium",
    fontSize: 16,
    color: theme.colors.text,
    lineHeight: 26,
  },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 24,
    paddingTop: 12,
    paddingBottom: 24,
    backgroundColor: theme.colors.background,
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
    gap: 12,
  },
  pageIndicator: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: 14,
    color: theme.colors.textSecondary,
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: theme.colors.white,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: theme.colors.border,
    overflow: "hidden",
  },
  homeButton: {
    flex: 1,
    backgroundColor: theme.colors.primary,
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 20,
    minHeight: 52,
    alignItems: "center",
    justifyContent: "center",
    ...buttonShadow,
  },
  homeButtonText: {
    fontFamily: "Pretendard-Bold",
    fontSize: 16,
    color: theme.colors.white,
  },
  primaryButton: {
    backgroundColor: theme.colors.primary,
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 32,
    minHeight: 52,
    alignItems: "center",
    justifyContent: "center",
    ...buttonShadow,
  },
  primaryButtonText: {
    fontFamily: "Pretendard-Bold",
    fontSize: 17,
    color: theme.colors.white,
  },
  headerDeleteButton: {
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  headerDeleteText: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: 15,
    color: theme.colors.error,
  },
});
