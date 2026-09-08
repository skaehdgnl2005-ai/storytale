/**
 * 추천 서술 입력 화면 (R-UI Step 3).
 *
 * 부모가 고민/관심사를 자유 서술하면 추천 API를 호출하고
 * 결과 화면(RecommendResult)으로 이동한다.
 */

import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Alert,
  Keyboard,
} from "react-native";
import { CommonActions } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { HomeTabParamList } from "../navigation/AppNavigator";
import { colors, typography, spacing } from "../theme";
import { PARENT_TEXT_MAX_LENGTH } from "../api/stories";
import { createRecommendation } from "../api/recommendations";
import { listProfiles } from "../api/profiles";
import { ApiClientError } from "../api/client";
import { StyledInput } from "../components/StyledInput";
import { PremiumCreateButton } from "../components/PremiumCreateButton";

type Props = NativeStackScreenProps<HomeTabParamList, "RecommendInput">;

const PURPOSE_PLACEHOLDERS: Record<string, string> = {
  value_teaching: "예) 거짓말하면 안 된다는 걸 알려주고 싶어요",
  interest_story: "예) 공룡을 너무 좋아해요, 특히 트리케라톱스",
  problem_solving: "예) 동생이 태어났는데 자꾸 밀쳐요",
  celebration: "예) 다음 주가 생일인데 특별한 책을 만들어주고 싶어요",
};

export const RecommendInputScreen: React.FC<Props> = ({
  navigation,
  route,
}) => {
  const { purpose } = route.params;
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);

  const placeholder =
    PURPOSE_PLACEHOLDERS[purpose] ?? "어떤 이야기가 필요한지 편하게 적어주세요";

  const canSubmit = text.trim().length > 0 && !loading;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    Keyboard.dismiss();
    setLoading(true);

    try {
      const profiles = await listProfiles();
      if (profiles.length === 0) {
        Alert.alert(
          "프로필이 필요해요",
          "아이 프로필을 먼저 등록해주세요",
          [{ text: "확인", onPress: () => navigation.dispatch(CommonActions.navigate("MyPageTab", { screen: "ProfileForm" })) }],
        );
        setLoading(false);
        return;
      }

      const child = profiles[0];
      const result = await createRecommendation({
        parent_text: text.trim(),
        child_age: child.age,
        purpose_category: purpose,
        child_id: child.id,
      });

      navigation.navigate("RecommendResult", {
        result,
        childId: child.id,
        childName: child.name,
      });
    } catch (err) {
      const message =
        err instanceof ApiClientError
          ? err.detail
          : "잠깐, 다시 한번 해볼게요 😊";
      Alert.alert("", message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.flex}>
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.title}>어떤 상황인지 알려주세요</Text>
        <Text style={styles.subtitle}>
          편하게 적어주시면, 딱 맞는 이야기를 찾아드릴게요
        </Text>

        <StyledInput
          style={styles.textInput}
          placeholder={placeholder}
          value={text}
          onChangeText={setText}
          maxLength={PARENT_TEXT_MAX_LENGTH}
          multiline
          textAlignVertical="top"
          accessibilityLabel="상황 설명 입력"
        />

        <Text style={styles.charCount}>
          {text.length}/{PARENT_TEXT_MAX_LENGTH}
        </Text>
      </ScrollView>

      <View style={styles.footer}>
        <PremiumCreateButton
          label="이야기 찾아보기"
          onPress={handleSubmit}
          disabled={!canSubmit}
          loading={loading}
          accessibilityLabel="이야기 찾기"
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
  textInput: {
    minHeight: 160,
    lineHeight: 24,
    textAlignVertical: "top",
  },
  charCount: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs + 1,
    color: colors.neutral[300],
    textAlign: "right",
    marginTop: spacing.sm,
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
