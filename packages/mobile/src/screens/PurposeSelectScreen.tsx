/**
 * 목적 선택 화면 (S29).
 *
 * 부모가 4가지 목적 중 하나를 골라 다음 단계(서술형 입력, S30)로 진입한다.
 *
 * 디자인: docs/visual-identity-guide-rn.md Section 12
 *   - warm pastel, borderRadius: cards = 20, buttons = 14
 *   - Pretendard 폰트, shadowColor "#3E3225"
 *   - 최소 터치 타겟 44x44, accessibilityLabel 필수
 * 계약: docs/contracts/story-engine.ts IntentCategory (4종)
 */

import React, { useState } from "react";
import {
  View,
  Text,
  Pressable,
  StyleSheet,
  ScrollView,
  Platform,
} from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { theme } from "../theme";
import { PURPOSE_CARDS, type PurposeId } from "../data/purposes";

type Props = NativeStackScreenProps<RootStackParamList, "PurposeSelect">;

export const PurposeSelectScreen: React.FC<Props> = ({ navigation }) => {
  const [selectedId, setSelectedId] = useState<PurposeId | null>(null);

  const handleContinue = () => {
    if (!selectedId) return;
    navigation.navigate("DescriptiveInput", { purpose: selectedId });
  };

  return (
    <View style={styles.flex}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.title}>어떤 이야기를 담아볼까요?</Text>
        <Text style={styles.subtitle}>
          가장 가까운 마음을 하나만 골라주세요
        </Text>

        {PURPOSE_CARDS.map((card) => {
          const isSelected = selectedId === card.id;
          return (
            <Pressable
              key={card.id}
              style={[styles.card, isSelected && styles.cardSelected]}
              onPress={() => setSelectedId(card.id)}
              accessibilityRole="button"
              accessibilityState={{ selected: isSelected }}
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
            </Pressable>
          );
        })}
      </ScrollView>

      <View style={styles.footer}>
        <Pressable
          style={[
            styles.continueButton,
            !selectedId && styles.continueDisabled,
          ]}
          onPress={handleContinue}
          disabled={!selectedId}
          accessibilityRole="button"
          accessibilityLabel="다음 단계로"
          accessibilityState={{ disabled: !selectedId }}
        >
          <Text style={styles.continueText}>다음</Text>
        </Pressable>
      </View>
    </View>
  );
};

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

const styles = StyleSheet.create({
  flex: {
    flex: 1,
    backgroundColor: theme.colors.background,
  },
  container: {
    flex: 1,
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 24,
  },
  title: {
    fontFamily: "Pretendard-Bold",
    fontSize: 24,
    color: theme.colors.text,
    marginBottom: 8,
  },
  subtitle: {
    fontFamily: "Pretendard-Medium",
    fontSize: 15,
    color: theme.colors.textSecondary,
    marginBottom: 24,
  },
  card: {
    backgroundColor: theme.colors.white,
    borderRadius: 20,
    paddingVertical: 20,
    paddingHorizontal: 20,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: theme.colors.border,
    minHeight: 88,
    justifyContent: "center",
    ...cardShadow,
  },
  cardSelected: {
    borderColor: theme.colors.primary,
    backgroundColor: theme.colors.primaryLight,
  },
  cardRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
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
    fontSize: 17,
    color: theme.colors.text,
    marginBottom: 4,
  },
  cardTitleSelected: {
    color: theme.colors.primary,
  },
  cardDescription: {
    fontFamily: "Pretendard-Medium",
    fontSize: 13,
    color: theme.colors.textSecondary,
    lineHeight: 18,
  },
  footer: {
    paddingHorizontal: 24,
    paddingTop: 12,
    paddingBottom: 24,
    backgroundColor: theme.colors.background,
    borderTopWidth: 1,
    borderTopColor: theme.colors.border,
  },
  continueButton: {
    backgroundColor: theme.colors.primary,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 52,
    ...buttonShadow,
  },
  continueDisabled: {
    opacity: 0.5,
  },
  continueText: {
    fontFamily: "Pretendard-Bold",
    fontSize: 17,
    color: theme.colors.white,
  },
});
