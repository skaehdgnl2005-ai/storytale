import React from "react";
import { View, Text, Pressable, StyleSheet, Platform } from "react-native";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { theme } from "../theme";

type Props = NativeStackScreenProps<RootStackParamList, "Home">;

export const HomeScreen: React.FC<Props> = ({ navigation }) => {
  return (
    <View style={styles.container}>
      <Text style={styles.greeting}>첫 번째 이야기를 만들어볼까요?</Text>

      <Pressable
        style={styles.profileButton}
        onPress={() => navigation.navigate("ProfileForm")}
        accessibilityLabel="아이 프로필 만들기"
        accessibilityRole="button"
      >
        <Text style={styles.profileButtonText}>아이 프로필 만들기</Text>
      </Pressable>

      <Pressable
        style={styles.startButton}
        onPress={() => navigation.navigate("PurposeSelect")}
        accessibilityLabel="이야기 만들기 시작"
        accessibilityRole="button"
      >
        <Text style={styles.startButtonText}>이야기 만들기</Text>
      </Pressable>

      <Pressable
        style={styles.libraryButton}
        onPress={() => navigation.navigate("Library")}
        accessibilityLabel="내 서재 열기"
        accessibilityRole="button"
      >
        <Text style={styles.libraryButtonText}>내 서재</Text>
      </Pressable>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.background,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 24,
  },
  greeting: {
    fontFamily: "Pretendard-Bold",
    fontSize: 22,
    color: theme.colors.text,
    textAlign: "center",
    marginBottom: 32,
  },
  profileButton: {
    backgroundColor: theme.colors.primary,
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 32,
    minHeight: 52,
    justifyContent: "center",
    alignItems: "center",
    ...Platform.select({
      ios: {
        shadowColor: "#3E3225",
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.15,
        shadowRadius: 8,
      },
      android: {
        elevation: 4,
      },
    }),
  },
  profileButtonText: {
    fontFamily: "Pretendard-Bold",
    fontSize: 17,
    color: theme.colors.white,
  },
  startButton: {
    marginTop: 16,
    backgroundColor: theme.colors.white,
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: theme.colors.primary,
    paddingVertical: 16,
    paddingHorizontal: 32,
    minHeight: 52,
    justifyContent: "center",
    alignItems: "center",
  },
  startButtonText: {
    fontFamily: "Pretendard-Bold",
    fontSize: 17,
    color: theme.colors.primary,
  },
  // S34 — 내 서재 진입. 아웃라인 보다 약한 텍스트 버튼으로 1차/2차 CTA 와 시각적
  // 우선순위를 낮춰 첫 사용자에게 "프로필 만들기 → 이야기 만들기" 흐름을 유도한다.
  libraryButton: {
    marginTop: 16,
    paddingVertical: 12,
    paddingHorizontal: 16,
    minHeight: 44,
    justifyContent: "center",
    alignItems: "center",
  },
  libraryButtonText: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: 15,
    color: theme.colors.textSecondary,
    textDecorationLine: "underline",
  },
});
