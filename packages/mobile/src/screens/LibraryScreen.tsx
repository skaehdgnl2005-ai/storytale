/**
 * 내 서재 (S34).
 *
 * 흐름: Home → Library → (카드 탭) Viewer → (back) Library → (back) Home
 *
 * - 마운트 시 `listStories()` 1회 호출 → 카드 그리드 렌더.
 * - Pull-to-refresh 로 다시 불러올 수 있음.
 * - 카드 탭 → `navigation.navigate("Viewer", { storyId })` (Library back 가능).
 * - 카드 long-press → 삭제 확인 Alert → `deleteStory(id)` + 로컬 state 제거.
 *
 * 상태 분기 (4종):
 *   1) loading — 첫 로드 중. ActivityIndicator + "이야기를 펼치고 있어요 📖".
 *   2) error — 401/그 외. CTA "다시 시도" 로 재호출.
 *   3) empty — items.length === 0. "첫 번째 이야기를 만들어볼까요?" 카드 + 만들기 CTA.
 *   4) list — 카드 그리드. created_at 내림차순(서버 정렬).
 *
 * S33 의 `ViewerReady` 분리 패턴을 의도적으로 따르지 않았다 — 본 화면은 list 상태에서
 * 추가 훅이 필요하지 않아 단일 컴포넌트로 충분하며, 4상태 모두 early return 으로 처리.
 *
 * 디자인: docs/visual-identity-guide-rn.md Section 12
 *   - warm pastel, borderRadius 14/20, Pretendard, shadowColor "#3E3225"
 *   - 최소 터치 타겟 52px, accessibilityLabel 필수
 *   - 톤: "이야기가 자라고 있어요 🌱" 등 CLAUDE.md 카피 패턴
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Platform,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
  type ListRenderItemInfo,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { theme } from "../theme";
import { ApiClientError } from "../api/client";
import {
  deleteStory,
  listStories,
  type StoryListItem,
} from "../api/stories";

type Props = NativeStackScreenProps<RootStackParamList, "Library">;

// ---------------------------------------------------------------------------
// 헬퍼
// ---------------------------------------------------------------------------

/**
 * "2026-04-11T05:23:01+00:00" → "2026.04.11"
 *
 * 백엔드는 `datetime.isoformat()` 결과를 그대로 내려준다(timezone 포함).
 * 카드 부제목으로 노출할 사람-친화 포맷으로 변환.
 *
 * Date 파싱 실패 시 원본 문자열을 반환해 카드가 깨지지 않게 한다.
 */
function formatCreatedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const yyyy = date.getFullYear();
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  return `${yyyy}.${mm}.${dd}`;
}

/**
 * 백엔드 status 문자열을 사람-친화 라벨로 변환.
 * 현재는 "completed" 만 저장되므로 단순하지만, draft/failed 도입 시 확장 지점.
 */
function statusLabel(status: string): string {
  switch (status) {
    case "completed":
      return "완성";
    case "draft":
      return "초안";
    case "failed":
      return "실패";
    default:
      return status;
  }
}

// ---------------------------------------------------------------------------
// 컴포넌트
// ---------------------------------------------------------------------------

export const LibraryScreen: React.FC<Props> = ({ navigation }) => {
  const [items, setItems] = useState<StoryListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // 로드 — 마운트 + pull-to-refresh
  // -------------------------------------------------------------------------

  const load = useCallback(async (): Promise<void> => {
    try {
      const result = await listStories();
      setItems(result.items);
      setErrorMessage(null);
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.status === 401) {
          // TODO(post-S27): 로그인 화면 마련되면 navigation.replace("Login").
          setErrorMessage("다시 로그인해주세요. 로그인 정보가 만료됐어요.");
        } else {
          setErrorMessage("잠깐, 다시 한번 해볼게요 😊");
        }
      } else {
        setErrorMessage("예상치 못한 오류가 생겼어요.");
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await load();
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [load]);

  const handleRefresh = useCallback(async (): Promise<void> => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  // -------------------------------------------------------------------------
  // 액션 — 카드 탭/삭제
  // -------------------------------------------------------------------------

  const handleOpenStory = useCallback(
    (storyId: string): void => {
      navigation.navigate("Viewer", { storyId });
    },
    [navigation],
  );

  /**
   * 카드 long-press 시 삭제 확인 Alert.
   * 확인 → DELETE 호출 → 성공 시 로컬 state 에서 제거(낙관적이지 않은 보수 처리).
   * 404 는 이미 삭제된 것으로 간주하고 동일하게 로컬에서 제거.
   */
  const handleDeleteStory = useCallback(
    (story: StoryListItem): void => {
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
                await deleteStory(story.id);
                setItems((prev) => prev.filter((s) => s.id !== story.id));
              } catch (err) {
                if (err instanceof ApiClientError) {
                  if (err.status === 404) {
                    // 이미 삭제된 상태로 간주.
                    setItems((prev) => prev.filter((s) => s.id !== story.id));
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
    },
    [],
  );

  const handleStartCreate = useCallback((): void => {
    navigation.navigate("PurposeSelect");
  }, [navigation]);

  // -------------------------------------------------------------------------
  // 렌더 — 카드 1장
  // -------------------------------------------------------------------------

  const renderCard = useCallback(
    ({ item }: ListRenderItemInfo<StoryListItem>) => {
      const subtitle = `${formatCreatedAt(item.created_at)} · ${item.page_count}페이지 · ${statusLabel(item.status)}`;
      return (
        <Pressable
          style={({ pressed }) => [styles.card, pressed && styles.cardPressed]}
          onPress={() => handleOpenStory(item.id)}
          onLongPress={() => handleDeleteStory(item)}
          delayLongPress={400}
          accessibilityRole="button"
          accessibilityLabel={`${item.title} 열기`}
          accessibilityHint="길게 누르면 지울 수 있어요"
        >
          <View style={styles.cardCover}>
            <Text style={styles.cardCoverEmoji}>📖</Text>
          </View>
          <View style={styles.cardBody}>
            <Text style={styles.cardTitle} numberOfLines={2}>
              {item.title || "제목 없는 이야기"}
            </Text>
            <Text style={styles.cardSubtitle} numberOfLines={1}>
              {subtitle}
            </Text>
          </View>
        </Pressable>
      );
    },
    [handleOpenStory, handleDeleteStory],
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

  if (errorMessage !== null) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{errorMessage}</Text>
        <Pressable
          style={styles.primaryButton}
          onPress={async () => {
            setLoading(true);
            await load();
            setLoading(false);
          }}
          accessibilityRole="button"
          accessibilityLabel="다시 시도"
        >
          <Text style={styles.primaryButtonText}>다시 시도</Text>
        </Pressable>
      </View>
    );
  }

  if (items.length === 0) {
    return (
      <View style={styles.centered}>
        <Text style={styles.emptyEmoji}>🌱</Text>
        <Text style={styles.emptyTitle}>첫 번째 이야기를 만들어볼까요?</Text>
        <Text style={styles.emptyHint}>
          만든 이야기들이 여기 모일 거예요.
        </Text>
        <Pressable
          style={styles.primaryButton}
          onPress={handleStartCreate}
          accessibilityRole="button"
          accessibilityLabel="이야기 만들기 시작"
        >
          <Text style={styles.primaryButtonText}>이야기 만들기</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <FlatList
      style={styles.list}
      contentContainerStyle={styles.listContent}
      data={items}
      keyExtractor={(item) => item.id}
      renderItem={renderCard}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={handleRefresh}
          tintColor={theme.colors.primary}
        />
      }
      ItemSeparatorComponent={() => <View style={styles.separator} />}
    />
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
  centered: {
    flex: 1,
    backgroundColor: theme.colors.background,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 24,
    gap: 12,
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
  emptyEmoji: {
    fontSize: 48,
    marginBottom: 4,
  },
  emptyTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: 20,
    color: theme.colors.text,
    textAlign: "center",
  },
  emptyHint: {
    fontFamily: "Pretendard-Medium",
    fontSize: 14,
    color: theme.colors.textSecondary,
    textAlign: "center",
    marginBottom: 12,
  },
  list: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  listContent: {
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  separator: {
    height: 12,
  },
  card: {
    flexDirection: "row",
    backgroundColor: theme.colors.white,
    borderRadius: 20,
    padding: 14,
    minHeight: 96,
    alignItems: "center",
    gap: 14,
    ...cardShadow,
  },
  cardPressed: {
    opacity: 0.85,
  },
  cardCover: {
    width: 68,
    height: 68,
    borderRadius: 16,
    backgroundColor: theme.colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
  },
  cardCoverEmoji: {
    fontSize: 32,
  },
  cardBody: {
    flex: 1,
    gap: 6,
  },
  cardTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: 17,
    color: theme.colors.text,
    lineHeight: 23,
  },
  cardSubtitle: {
    fontFamily: "Pretendard-Medium",
    fontSize: 13,
    color: theme.colors.textSecondary,
  },
  primaryButton: {
    marginTop: 8,
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
});
