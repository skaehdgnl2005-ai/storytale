/**
 * 마이페이지 — 프로필 요약 + 관리.
 *
 * 바텀 탭 "마이"에서 진입.
 */

import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { MyPageTabParamList } from "../navigation/AppNavigator";
import { colors, spacing, typography, radius } from "../theme";
import { Card } from "../components/Card";
import { PremiumCreateButton } from "../components/PremiumCreateButton";
import { SecondaryButton } from "../components/SecondaryButton";
import { listProfiles, type ChildProfile } from "../api/profiles";

type Props = NativeStackScreenProps<MyPageTabParamList, "MyPage">;

export const MyPageScreen: React.FC<Props> = ({ navigation }) => {
  const [profile, setProfile] = useState<ChildProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        try {
          const profiles = await listProfiles();
          if (cancelled) return;
          if (profiles.length > 0) {
            setProfile(profiles[0]);
          } else {
            setProfile(null);
          }
        } catch {
          if (!cancelled) setProfile(null);
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, []),
  );

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.primary[400]} size="large" />
      </View>
    );
  }

  if (profile == null) {
    return (
      <View style={styles.centered}>
        <View style={styles.mascotAnchor}>
          <Text style={styles.mascotEmoji}>👤</Text>
        </View>
        <View style={styles.contentCard}>
          <Text style={styles.emptyTitle}>아이를 알려주세요</Text>
          <Text style={styles.emptyHint}>
            프로필을 등록하면 맞춤 이야기를{"\n"}만들 수 있어요
          </Text>
          <PremiumCreateButton
            label="프로필 만들기"
            onPress={() => navigation.navigate("ProfileForm")}
          />
        </View>
      </View>
    );
  }

  const genderLabel = profile.gender === "male" ? "남자아이" : "여자아이";

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
    >
      <Card>
        <Text style={styles.profileName}>{profile.name}</Text>
        <Text style={styles.profileDetail}>
          {profile.age}세 · {genderLabel}
        </Text>
      </Card>

      <SecondaryButton
        label="프로필 수정"
        onPress={() => navigation.navigate("ProfileForm")}
        style={styles.editButton}
      />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  centered: {
    flex: 1,
    backgroundColor: colors.neutral[50],
    justifyContent: "center",
    alignItems: "center",
  },
  mascotAnchor: {
    height: 160,
    alignItems: "center",
    justifyContent: "flex-end",
  },
  mascotEmoji: {
    fontSize: 48,
  },
  contentCard: {
    width: "100%",
    backgroundColor: colors.neutral[0],
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    padding: spacing.lg,
    alignItems: "center",
    gap: spacing.base,
    flex: 1,
  },
  emptyTitle: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.xl,
    color: colors.neutral[800],
    textAlign: "center",
    marginTop: spacing.lg,
  },
  emptyHint: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.sm,
    color: colors.neutral[300],
    textAlign: "center",
    lineHeight: 22,
    marginBottom: spacing.md,
  },
  container: {
    flex: 1,
    backgroundColor: colors.neutral[50],
  },
  content: {
    padding: spacing.lg,
    gap: spacing.base,
  },
  profileName: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size["2xl"],
    color: colors.neutral[800],
    marginBottom: spacing.xs,
  },
  profileDetail: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.base,
    color: colors.neutral[300],
  },
  editButton: {
    marginTop: spacing.sm,
  },
});
