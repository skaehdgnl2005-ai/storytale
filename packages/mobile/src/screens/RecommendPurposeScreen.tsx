/**
 * 추천 목적 선택 화면 (R-UI Step 2).
 *
 * PURPOSE_CARDS 4가지를 보여주고, 선택 후 RecommendInput으로 이동.
 * PurposeSelectScreen과 유사하나 추천 맥락의 타이틀/서브타이틀 사용.
 */

import React, { useState } from "react";
import { View, Text, StyleSheet, ScrollView } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { HomeTabParamList } from "../navigation/AppNavigator";
import { colors, radius, typography, spacing } from "../theme";
import { PURPOSE_CARDS, type PurposeId } from "../data/purposes";
import { Card } from "../components/Card";
import { PremiumCreateButton } from "../components/PremiumCreateButton";

type Props = NativeStackScreenProps<HomeTabParamList, "RecommendPurpose">;

export const RecommendPurposeScreen: React.FC<Props> = ({ navigation }) => {
  const [selectedId, setSelectedId] = useState<PurposeId | null>(null);

  const handleContinue = () => {
    if (!selectedId) return;
    navigation.navigate("RecommendInput", { purpose: selectedId });
  };

  return (
    <View style={styles.flex}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.title}>어떤 이야기가 필요한가요?</Text>
        <Text style={styles.subtitle}>
          가장 가까운 마음을 하나 골라주세요
        </Text>

        {PURPOSE_CARDS.map((card) => {
          const isSelected = selectedId === card.id;
          return (
            <Card
              key={card.id}
              style={styles.card}
              selected={isSelected}
              onPress={() => setSelectedId(card.id)}
              accessibilityLabel={card.title}
              accessibilityHint={card.description}
            >
              <View style={styles.cardRow}>
                <Text style={styles.cardEmoji}>{card.emoji}</Text>
                <View style={styles.cardTextWrap}>
                  <Text
                    style={[
                      styles.cardTitle,
                      isSelected && styles.cardTitleSelected,
                    ]}
                  >
                    {card.title}
                  </Text>
                  <Text style={styles.cardDescription}>{card.description}</Text>
                </View>
              </View>
            </Card>
          );
        })}
      </ScrollView>

      <View style={styles.footer}>
        <PremiumCreateButton
          label="다음"
          onPress={handleContinue}
          disabled={!selectedId}
          accessibilityLabel="다음 단계로"
        />
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  flex: {
    flex: 1,
    backgroundColor: colors.neutral[50],
  },
  container: {
    flex: 1,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing.lg,
  },
  title: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.xl,
    color: colors.neutral[800],
    marginBottom: spacing.sm,
  },
  subtitle: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm + 1,
    color: colors.neutral[300],
    marginBottom: spacing.lg,
  },
  card: {
    marginBottom: spacing.base,
    minHeight: 88,
    justifyContent: "center",
  },
  cardRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.base,
  },
  cardEmoji: {
    fontSize: 32,
    lineHeight: 38,
  },
  cardTextWrap: {
    flex: 1,
  },
  cardTitle: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.base + 1,
    color: colors.neutral[800],
    marginBottom: spacing.xs,
  },
  cardTitleSelected: {
    color: colors.primary[400],
  },
  cardDescription: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs + 1,
    color: colors.neutral[300],
    lineHeight: 18,
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
