/**
 * 내 서재 (S34 — v3.1 디자인).
 *
 * 흐름: Home → Library → (카드 탭) Viewer → (back) Library → (back) Home
 *
 * - 마운트 시 `listStories()` 1회 호출 → 카드 그리드 렌더.
 * - Pull-to-refresh 로 다시 불러올 수 있음.
 * - 카드 탭 → `navigation.navigate("Viewer", { storyId })` (Library back 가능).
 * - 카드 long-press → 삭제 확인 Alert → `deleteStory(id)` + 로컬 state 제거.
 *
 * 상태 분기 (4종):
 *   1) loading — 첫 로드 중. ActivityIndicator.
 *   2) error — 401/그 외. CTA "다시 시도" 로 재호출.
 *   3) empty — items.length === 0. 마스코트 + 만들기 CTA.
 *   4) list — Card 컴포넌트 그리드. created_at 내림차순(서버 정렬).
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
  type ListRenderItemInfo,
} from "react-native";
import { CommonActions } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { LibraryTabParamList } from "../navigation/AppNavigator";
import { colors, shadows, radius, typography, spacing } from "../theme";
import { ApiClientError } from "../api/client";
import { forceLogoutToLogin } from "../auth/bootstrap";
import {
  deleteStory,
  listStories,
  type StoryListItem,
} from "../api/stories";
import { Card } from "../components/Card";
import { PremiumCreateButton } from "../components/PremiumCreateButton";

type Props = NativeStackScreenProps<LibraryTabParamList, "Library">;

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

/**
 * story id 해시로 커버 컬러 결정 — emoji 대신 색상 배경 사용.
 */
const COVER_COLORS = [
  colors.primary[300],
  colors.primary[400],
  colors.secondary[300],
  colors.secondary[400],
  colors.primary[100],
  colors.secondary[50],
] as const;

function coverColorForId(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) | 0;
  }
  return COVER_COLORS[Math.abs(hash) % COVER_COLORS.length];
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
          // S27b — 토큰 만료/폐기 감지 시 저장소 비우고 Login 으로 강제 이동.
          void forceLogoutToLogin(navigation);
        } else {
          setErrorMessage("잠깐, 다시 한번 해볼게요 😊");
        }
      } else {
        setErrorMessage("예상치 못한 오류가 생겼어요.");
      }
    }
  }, [navigation]);

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
      navigation.dispatch(CommonActions.navigate("Viewer", { storyId }));
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
    },
    [],
  );

  const handleStartCreate = useCallback((): void => {
    navigation.dispatch(CommonActions.navigate("HomeTab", { screen: "PurposeSelect" }));
  }, [navigation]);

  // -------------------------------------------------------------------------
  // 렌더 — 카드 1장
  // -------------------------------------------------------------------------

  const renderCard = useCallback(
    ({ item }: ListRenderItemInfo<StoryListItem>) => {
      const subtitle = `${formatCreatedAt(item.created_at)} · ${item.page_count}페이지 · ${statusLabel(item.status)}`;
      return (
        <Card
          onPress={() => handleOpenStory(item.id)}
          onLongPress={() => handleDeleteStory(item)}
          accessibilityLabel={`${item.title} 열기`}
          accessibilityHint="길게 누르면 지울 수 있어요"
          style={styles.card}
        >
          <View style={styles.cardRow}>
            <View
              style={[
                styles.cardCover,
                { backgroundColor: coverColorForId(item.id) },
              ]}
            />
            <View style={styles.cardBody}>
              <Text style={styles.cardTitle} numberOfLines={2}>
                {item.title || "제목 없는 이야기"}
              </Text>
              <Text style={styles.cardSubtitle} numberOfLines={1}>
                {subtitle}
              </Text>
            </View>
          </View>
        </Card>
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
        <ActivityIndicator color={colors.primary[400]} size="large" />
        <Text style={styles.loadingText}>이야기를 펼치고 있어요 📖</Text>
      </View>
    );
  }

  if (errorMessage !== null) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{errorMessage}</Text>
        <PremiumCreateButton
          label="다시 시도"
          onPress={async () => {
            setLoading(true);
            await load();
            setLoading(false);
          }}
          accessibilityLabel="다시 시도"
        />
      </View>
    );
  }

  if (items.length === 0) {
    return (
      <View style={styles.emptyContainer}>
        {/* 마스코트 앵커 영역 */}
        <View style={styles.mascotAnchor} />

        {/* 콘텐츠 카드 */}
        <View style={styles.contentCard}>
          <Text style={styles.emptyTitle}>첫 번째 이야기를 만들어볼까요?</Text>
          <Text style={styles.emptyHint}>
            만든 이야기들이 여기 모일 거예요.
          </Text>
          <PremiumCreateButton
            label="이야기 만들기"
            onPress={handleStartCreate}
            accessibilityLabel="이야기 만들기 시작"
          />
        </View>
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
          tintColor={colors.primary[400]}
        />
      }
      ItemSeparatorComponent={() => <View style={styles.separator} />}
    />
  );
};

// ---------------------------------------------------------------------------
// 스타일
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    backgroundColor: colors.neutral[50],
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
    gap: spacing.md,
  },
  loadingText: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[300],
    textAlign: "center",
  },
  errorText: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[800],
    textAlign: "center",
    lineHeight: 22,
  },

  // ── 빈 상태 ─────────────────────────────────────────
  emptyContainer: {
    flex: 1,
    backgroundColor: colors.neutral[50],
  },
  mascotAnchor: {
    height: 160,
    backgroundColor: colors.primary[50],
  },
  contentCard: {
    flex: 1,
    backgroundColor: colors.neutral[0],
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl,
    alignItems: "center",
    ...shadows.softBase,
  },
  emptyTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.xl,
    color: colors.neutral[800],
    textAlign: "center",
    marginBottom: spacing.sm,
  },
  emptyHint: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[300],
    textAlign: "center",
    marginBottom: spacing.lg,
  },

  // ── 리스트 ──────────────────────────────────────────
  list: {
    flex: 1,
    backgroundColor: colors.neutral[50],
  },
  listContent: {
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.base,
  },
  separator: {
    height: spacing.md,
  },
  card: {
    padding: spacing.md,
  },
  cardRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  cardCover: {
    width: 68,
    height: 68,
    borderRadius: radius.md,
  },
  cardBody: {
    flex: 1,
    gap: spacing.xs + 2,
  },
  cardTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.base,
    color: colors.neutral[800],
    lineHeight: 23,
  },
  cardSubtitle: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs,
    color: colors.neutral[300],
  },
});
