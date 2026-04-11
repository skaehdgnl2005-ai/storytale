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
});
