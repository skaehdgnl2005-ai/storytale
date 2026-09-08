/**
 * 추천 결과 화면 (R-UI Step 4).
 *
 * 키워드 뱃지 + 추천 도서 카드(3권) + 독후 가이드 + 맞춤 동화 CTA.
 * 맞춤 동화 CTA 탭 시 intentAnalysis를 활용해 Preview로 직행 (shortcut).
 */

import React, { useState } from "react";
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  ScrollView,
  Image,
  Alert,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { HomeTabParamList } from "../navigation/AppNavigator";
import { colors, radius, shadows, typography, spacing } from "../theme";
import type {
  BookRecommendation,
  RecommendationResult,
} from "../api/recommendations";
import { createStoryPlan } from "../api/stories";
import { ApiClientError } from "../api/client";
import { Card } from "../components/Card";
import { PremiumCreateButton } from "../components/PremiumCreateButton";

type Props = NativeStackScreenProps<HomeTabParamList, "RecommendResult">;

export const RecommendResultScreen: React.FC<Props> = ({
  navigation,
  route,
}) => {
  const { result, childId, childName } = route.params;
  const { intent_analysis, recommendations, custom_story_prompt } = result;
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [shortcutLoading, setShortcutLoading] = useState(false);

  const handleToggleGuide = (index: number) => {
    setExpandedIndex(expandedIndex === index ? null : index);
  };

  const handleCustomStory = async () => {
    setShortcutLoading(true);
    try {
      const purposeCategory = intent_analysis.intent_category as
        | "value_teaching"
        | "interest_story"
        | "problem_solving"
        | "celebration";

      const parentText = intent_analysis.emotional_keywords.join(", ");
      const { plan, preview } = await createStoryPlan({
        parent_text: parentText,
        purpose_category: purposeCategory,
        child_id: childId,
      });

      navigation.navigate("Preview", {
        plan,
        preview,
        childId,
        childName,
      });
    } catch (err) {
      const message =
        err instanceof ApiClientError
          ? err.detail
          : "잠깐, 다시 한번 해볼게요 😊";
      Alert.alert("", message);
    } finally {
      setShortcutLoading(false);
    }
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      {/* 키워드 뱃지 */}
      <Text style={styles.sectionLabel}>분석된 키워드</Text>
      <View style={styles.badgeRow}>
        {intent_analysis.emotional_keywords.map((keyword, i) => (
          <View key={i} style={styles.badge}>
            <Text style={styles.badgeText}>{keyword}</Text>
          </View>
        ))}
      </View>

      {/* 추천 도서 리스트 */}
      <Text style={styles.sectionTitle}>
        {childName}에게 딱 맞는 이야기들이에요
      </Text>

      {recommendations.map((rec, index) => (
        <BookCard
          key={rec.book.id}
          rec={rec}
          index={index}
          isExpanded={expandedIndex === index}
          onToggle={() => handleToggleGuide(index)}
        />
      ))}

      {/* 맞춤 동화 전환 CTA */}
      <Card style={styles.ctaSection}>
        <Text style={styles.ctaTitle}>{custom_story_prompt}</Text>
        <Text style={styles.ctaSubtitle}>
          {childName}만의 특별한 이야기를 만들어보세요
        </Text>
        <PremiumCreateButton
          label="맞춤 동화 만들기"
          onPress={handleCustomStory}
          disabled={shortcutLoading}
          loading={shortcutLoading}
          accessibilityLabel="맞춤 동화 만들기"
        />
      </Card>
    </ScrollView>
  );
};

// ---------------------------------------------------------------------------
// BookCard 컴포넌트
// ---------------------------------------------------------------------------

interface BookCardProps {
  rec: BookRecommendation;
  index: number;
  isExpanded: boolean;
  onToggle: () => void;
}

const BookCard: React.FC<BookCardProps> = ({
  rec,
  index,
  isExpanded,
  onToggle,
}) => {
  const { book, why_this_book, reading_questions, conversation_guide } = rec;

  return (
    <Card style={styles.bookCard}>
      <View style={styles.bookRow}>
        {book.cover_image_url ? (
          <Image
            source={{ uri: book.cover_image_url }}
            style={styles.bookCover}
            accessibilityLabel={`${book.title} 표지`}
          />
        ) : (
          <View style={[styles.bookCover, styles.bookCoverPlaceholder]}>
            <Text style={styles.bookCoverEmoji}>📖</Text>
          </View>
        )}
        <View style={styles.bookInfo}>
          <Text style={styles.bookTitle}>{book.title}</Text>
          <Text style={styles.bookAuthor}>
            {book.author} | {book.publisher}
          </Text>
          <Text style={styles.bookAge}>
            {book.target_age_min}~{book.target_age_max}세
          </Text>
        </View>
      </View>

      <Text style={styles.whyThisBook}>{why_this_book}</Text>

      <Pressable
        onPress={onToggle}
        style={styles.guideToggle}
        accessibilityRole="button"
        accessibilityLabel={isExpanded ? "가이드 접기" : "독후 가이드 보기"}
      >
        <Text style={styles.guideToggleText}>
          {isExpanded ? "가이드 접기" : "독후 가이드 보기"}
        </Text>
      </Pressable>

      {isExpanded && (
        <View style={styles.guideSection}>
          {reading_questions.length > 0 && (
            <>
              <Text style={styles.guideLabel}>읽어줄 때 이렇게 물어보세요</Text>
              {reading_questions.map((q, i) => (
                <Text key={i} style={styles.guideItem}>
                  {"\u2022"} {q}
                </Text>
              ))}
            </>
          )}
          {conversation_guide.length > 0 && (
            <>
              <Text style={[styles.guideLabel, { marginTop: spacing.base }]}>
                읽고 나서 이야기 나눠보세요
              </Text>
              {conversation_guide.map((g, i) => (
                <Text key={i} style={styles.guideItem}>
                  {"\u2022"} {g}
                </Text>
              ))}
            </>
          )}
        </View>
      )}
    </Card>
  );
};

// ---------------------------------------------------------------------------
// 스타일
// ---------------------------------------------------------------------------

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.neutral[50],
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing["2xl"],
  },

  // 키워드 뱃지
  sectionLabel: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs + 1,
    color: colors.neutral[300],
    marginBottom: spacing.sm,
  },
  badgeRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  badge: {
    backgroundColor: colors.secondary[50],
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md + 2,
    paddingVertical: spacing.xs + 2,
  },
  badgeText: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.sm,
    color: colors.secondary[400],
  },

  // 섹션 타이틀
  sectionTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.xl - 2,
    color: colors.neutral[800],
    marginBottom: spacing.base,
  },

  // 책 카드
  bookCard: {
    marginBottom: spacing.base,
  },
  bookRow: {
    flexDirection: "row",
    gap: spacing.base,
    marginBottom: spacing.md,
  },
  bookCover: {
    width: 72,
    height: 100,
    borderRadius: radius.sm,
    backgroundColor: colors.neutral[100],
  },
  bookCoverPlaceholder: {
    alignItems: "center",
    justifyContent: "center",
  },
  bookCoverEmoji: {
    fontSize: 28,
  },
  bookInfo: {
    flex: 1,
    justifyContent: "center",
  },
  bookTitle: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.base + 1,
    color: colors.neutral[800],
    marginBottom: spacing.xs,
  },
  bookAuthor: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs + 1,
    color: colors.neutral[300],
    marginBottom: 2,
  },
  bookAge: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs,
    color: colors.neutral[200],
  },
  whyThisBook: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[800],
    lineHeight: 22,
    marginBottom: spacing.md,
  },

  // 가이드 토글
  guideToggle: {
    paddingVertical: spacing.sm,
    minHeight: 44,
    justifyContent: "center",
  },
  guideToggleText: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.sm,
    color: colors.primary[400],
  },

  // 가이드 섹션
  guideSection: {
    marginTop: spacing.sm,
    paddingTop: spacing.base,
    borderTopWidth: 1,
    borderTopColor: colors.neutral[100],
  },
  guideLabel: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.sm,
    color: colors.neutral[800],
    marginBottom: spacing.sm,
  },
  guideItem: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[300],
    lineHeight: 22,
    marginBottom: spacing.xs,
    paddingLeft: spacing.xs,
  },

  // 맞춤 동화 CTA
  ctaSection: {
    marginTop: spacing.base,
    alignItems: "center",
    borderColor: colors.secondary[300],
  },
  ctaTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.base + 1,
    color: colors.neutral[800],
    textAlign: "center",
    marginBottom: spacing.sm,
  },
  ctaSubtitle: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[300],
    textAlign: "center",
    marginBottom: spacing.lg - 4,
  },
});
