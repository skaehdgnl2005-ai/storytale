/**
 * 홈 화면 (R-UI 개편 v3.1).
 *
 * ScrollView 기반 카드 대시보드.
 * 핵심 CTA: "이야기의 힘을 빌려보세요" → 추천 플로우 진입.
 * 프로필 필수화: 프로필이 없으면 프로필 등록을 먼저 유도한다.
 */

import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  FlatList,
  StyleSheet,
  ActivityIndicator,
} from "react-native";
import { useFocusEffect, CommonActions } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { HomeTabParamList } from "../navigation/AppNavigator";
import { colors, shadows, radius, typography, spacing } from "../theme";
import { listProfiles } from "../api/profiles";
import { listStories, type StoryListItem } from "../api/stories";
import { Card } from "../components/Card";
import { PremiumCreateButton } from "../components/PremiumCreateButton";

type Props = NativeStackScreenProps<HomeTabParamList, "Home">;

// ---------------------------------------------------------------------------
// 헬퍼 — story id 해시로 커버 컬러 결정
// ---------------------------------------------------------------------------

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

export const HomeScreen: React.FC<Props> = ({ navigation }) => {
  const [hasProfile, setHasProfile] = useState<boolean | null>(null);
  const [childName, setChildName] = useState<string | null>(null);
  const [recentStories, setRecentStories] = useState<StoryListItem[]>([]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        try {
          const profiles = await listProfiles();
          if (cancelled) return;
          if (profiles.length > 0) {
            setHasProfile(true);
            setChildName(profiles[0].name);
          } else {
            setHasProfile(false);
            setChildName(null);
          }
        } catch {
          if (!cancelled) setHasProfile(false);
        }

        // 최근 스토리 로드 (프로필 유무와 무관하게 시도)
        try {
          const result = await listStories({ limit: 5, offset: 0 });
          if (!cancelled) setRecentStories(result.items);
        } catch {
          // 실패 시 빈 목록 유지 — 섹션이 숨겨지므로 에러 노출 불필요
        }
      })();
      return () => {
        cancelled = true;
      };
    }, []),
  );

  // ── 로딩 ────────────────────────────────────────────
  if (hasProfile === null) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator color={colors.primary[400]} size="large" />
      </View>
    );
  }

  // ── 프로필 없음 ─────────────────────────────────────
  if (!hasProfile) {
    return (
      <View style={styles.noProfileContainer}>
        {/* 마스코트 앵커 영역 */}
        <View style={styles.mascotAnchor} />

        {/* 콘텐츠 카드 */}
        <View style={styles.contentCard}>
          <Text style={styles.noProfileTitle}>아이를 알려주세요</Text>
          <Text style={styles.noProfileSubtitle}>
            아이에게 딱 맞는 이야기를 찾으려면{"\n"}프로필이 필요해요
          </Text>

          <PremiumCreateButton
            label="아이 프로필 만들기"
            onPress={() =>
              navigation.dispatch(
                CommonActions.navigate("MyPageTab", {
                  screen: "ProfileForm",
                }),
              )
            }
            accessibilityLabel="아이 프로필 만들기"
          />
        </View>
      </View>
    );
  }

  // ── 메인 대시보드 ───────────────────────────────────
  return (
    <ScrollView
      style={styles.scrollView}
      contentContainerStyle={styles.scrollContent}
      showsVerticalScrollIndicator={false}
    >
      {/* 인사 헤더 */}
      <Text style={styles.greeting}>안녕, {childName}!</Text>
      <Text style={styles.subtitle}>
        오늘은 어떤 이야기를 만들어볼까요?
      </Text>

      {/* CTA 카드 1: 추천 플로우 */}
      <Card
        style={styles.ctaCard}
        onPress={() => navigation.navigate("RecommendPurpose")}
        accessibilityLabel="이야기의 힘을 빌려보세요"
      >
        <Text style={styles.ctaCardTitle}>이야기의 힘을 빌려보세요</Text>
        <Text style={styles.ctaCardDesc}>
          아이의 상황에 맞는 이야기를 추천해드릴게요
        </Text>
      </Card>

      {/* CTA 카드 2: 맞춤 동화 만들기 (PremiumCreateButton 스타일) */}
      <View style={styles.premiumCtaWrap}>
        <PremiumCreateButton
          label="맞춤 동화 만들기"
          onPress={() => navigation.navigate("PurposeSelect")}
          accessibilityLabel="맞춤 동화 만들기"
        />
      </View>

      {/* 최근 이야기 섹션 */}
      {recentStories.length > 0 && (
        <View style={styles.recentSection}>
          <Text style={styles.recentTitle}>최근 이야기</Text>
          <FlatList
            horizontal
            data={recentStories}
            keyExtractor={(item) => item.id}
            showsHorizontalScrollIndicator={false}
            contentContainerStyle={styles.recentListContent}
            renderItem={({ item }) => (
              <Card
                style={styles.recentCard}
                onPress={() =>
                  navigation.dispatch(
                    CommonActions.navigate("Viewer", { storyId: item.id }),
                  )
                }
                accessibilityLabel={`${item.title} 열기`}
              >
                <View
                  style={[
                    styles.recentCover,
                    { backgroundColor: coverColorForId(item.id) },
                  ]}
                />
                <Text style={styles.recentCardTitle} numberOfLines={2}>
                  {item.title || "제목 없는 이야기"}
                </Text>
              </Card>
            )}
          />
        </View>
      )}
    </ScrollView>
  );
};

// ---------------------------------------------------------------------------
// 스타일
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    backgroundColor: colors.neutral[50],
    justifyContent: "center",
    alignItems: "center",
  },

  // ── 프로필 없음 ─────────────────────────────────────
  noProfileContainer: {
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
  noProfileTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.xl,
    color: colors.neutral[800],
    textAlign: "center",
    marginBottom: spacing.sm,
  },
  noProfileSubtitle: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[300],
    textAlign: "center",
    lineHeight: 22,
    marginBottom: spacing.xl,
  },

  // ── 메인 대시보드 ───────────────────────────────────
  scrollView: {
    flex: 1,
    backgroundColor: colors.neutral[50],
  },
  scrollContent: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl,
    paddingBottom: spacing["2xl"],
  },
  greeting: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.xl,
    color: colors.neutral[800],
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[300],
    marginBottom: spacing.lg,
  },
  ctaCard: {
    marginBottom: spacing.base,
  },
  ctaCardTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.lg,
    color: colors.neutral[800],
    marginBottom: spacing.xs,
  },
  ctaCardDesc: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[300],
  },
  premiumCtaWrap: {
    marginBottom: spacing.lg,
  },

  // ── 최근 이야기 ─────────────────────────────────────
  recentSection: {
    marginTop: spacing.sm,
  },
  recentTitle: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.base,
    color: colors.neutral[800],
    marginBottom: spacing.md,
  },
  recentListContent: {
    gap: spacing.md,
  },
  recentCard: {
    width: 120,
    padding: spacing.sm,
  },
  recentCover: {
    width: 68,
    height: 68,
    borderRadius: radius.md,
    alignSelf: "center",
    marginBottom: spacing.sm,
  },
  recentCardTitle: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs,
    color: colors.neutral[800],
    textAlign: "center",
    lineHeight: 16,
  },
});
