/**
 * 아이 프로필 등록 화면 (S28).
 *
 * 계약: docs/contracts/user-service.ts (CreateChildProfileInput)
 * 디자인: docs/visual-identity-guide-rn.md Section 12
 */

import React, { useState } from "react";
import {
  View,
  Text,
  Image,
  Pressable,
  StyleSheet,
  ScrollView,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { MyPageTabParamList } from "../navigation/AppNavigator";
import { colors, radius, shadows, typography, spacing } from "../theme";
import { createProfile, uploadPhoto } from "../api/profiles";
import { ApiClientError } from "../api/client";
import { Card } from "../components/Card";
import { StyledInput } from "../components/StyledInput";
import { PremiumCreateButton } from "../components/PremiumCreateButton";

type Props = NativeStackScreenProps<MyPageTabParamList, "ProfileForm">;

type Gender = "male" | "female";

export const ProfileFormScreen: React.FC<Props> = ({ navigation }) => {
  const [name, setName] = useState("");
  const [age, setAge] = useState("");
  const [gender, setGender] = useState<Gender | null>(null);
  const [comfortObject, setComfortObject] = useState("");
  const [friendName, setFriendName] = useState("");
  const [favoriteAnimal, setFavoriteAnimal] = useState("");
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const isValid = name.trim().length > 0 && age.trim().length > 0 && gender !== null;

  const handlePickPhoto = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("", "사진 접근 권한이 필요해요");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsEditing: true,
      aspect: [1, 1],
      quality: 0.8,
    });

    if (!result.canceled && result.assets[0]) {
      setPhotoUri(result.assets[0].uri);
    }
  };

  const handleSubmit = async () => {
    if (!isValid || gender === null) return;

    const ageNum = parseInt(age, 10);
    if (isNaN(ageNum) || ageNum < 1 || ageNum > 12) {
      Alert.alert("", "나이는 1~12 사이로 입력해주세요");
      return;
    }

    setLoading(true);
    try {
      const profile = await createProfile({
        name: name.trim(),
        age: ageNum,
        gender,
        comfort_object: comfortObject.trim() || undefined,
        friend_name: friendName.trim() || undefined,
        favorite_animal: favoriteAnimal.trim() || undefined,
      });

      if (photoUri) {
        try {
          await uploadPhoto(profile.id, photoUri);
        } catch {
          // 사진 업로드 실패해도 프로필은 이미 생성됨
        }
      }

      Alert.alert("", `${name.trim()}의 프로필이 만들어졌어요!`, [
        { text: "확인", onPress: () => navigation.goBack() },
      ]);
    } catch (err) {
      const message =
        err instanceof ApiClientError
          ? err.detail
          : "잠깐, 다시 한번 해볼게요";
      Alert.alert("", message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.title}>아이 프로필 만들기</Text>
        <Text style={styles.subtitle}>
          아이의 이야기를 만들기 위해 알려주세요
        </Text>

        {/* 사진 */}
        <Pressable
          style={styles.photoButton}
          onPress={handlePickPhoto}
          accessibilityLabel="아이 사진 선택"
          accessibilityRole="button"
        >
          {photoUri ? (
            <Image source={{ uri: photoUri }} style={styles.photoPreview} />
          ) : (
            <View style={styles.photoPlaceholder}>
              <Text style={styles.photoPlaceholderIcon}>+</Text>
              <Text style={styles.photoPlaceholderText}>사진 추가</Text>
            </View>
          )}
        </Pressable>

        {/* 기본 정보 섹션 */}
        <Card style={styles.formSection}>
          <Text style={styles.sectionHeader}>기본 정보</Text>

          <Text style={styles.label}>이름 *</Text>
          <StyledInput
            value={name}
            onChangeText={setName}
            placeholder="아이의 이름"
            maxLength={50}
            accessibilityLabel="아이 이름 입력"
          />

          <Text style={styles.label}>나이 *</Text>
          <StyledInput
            value={age}
            onChangeText={setAge}
            placeholder="1~12"
            keyboardType="number-pad"
            maxLength={2}
            accessibilityLabel="아이 나이 입력"
          />

          <Text style={styles.label}>성별 *</Text>
          <View style={styles.genderRow}>
            <Pressable
              style={[
                styles.genderButton,
                gender === "male" && styles.genderSelected,
              ]}
              onPress={() => setGender("male")}
              accessibilityLabel="남자아이"
              accessibilityRole="button"
            >
              <Text
                style={[
                  styles.genderText,
                  gender === "male" && styles.genderTextSelected,
                ]}
              >
                남자아이
              </Text>
            </Pressable>
            <Pressable
              style={[
                styles.genderButton,
                gender === "female" && styles.genderSelected,
              ]}
              onPress={() => setGender("female")}
              accessibilityLabel="여자아이"
              accessibilityRole="button"
            >
              <Text
                style={[
                  styles.genderText,
                  gender === "female" && styles.genderTextSelected,
                ]}
              >
                여자아이
              </Text>
            </Pressable>
          </View>
        </Card>

        {/* 선택 정보 섹션 */}
        <Card style={styles.formSection}>
          <Text style={styles.sectionHeader}>더 알려주시면 좋아요</Text>

          <Text style={styles.label}>애착 물건</Text>
          <StyledInput
            value={comfortObject}
            onChangeText={setComfortObject}
            placeholder="예: 토니 곰인형"
            maxLength={100}
            accessibilityLabel="애착 물건 입력"
          />

          <Text style={styles.label}>친한 친구 이름</Text>
          <StyledInput
            value={friendName}
            onChangeText={setFriendName}
            placeholder="예: 민준이"
            maxLength={50}
            accessibilityLabel="친한 친구 이름 입력"
          />

          <Text style={styles.label}>좋아하는 동물</Text>
          <StyledInput
            value={favoriteAnimal}
            onChangeText={setFavoriteAnimal}
            placeholder="예: 토끼"
            maxLength={50}
            accessibilityLabel="좋아하는 동물 입력"
          />
        </Card>

        {/* 제출 버튼 */}
        <View style={styles.submitWrapper}>
          <PremiumCreateButton
            label="프로필 만들기"
            onPress={handleSubmit}
            disabled={!isValid}
            loading={loading}
            accessibilityLabel="프로필 만들기"
          />
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

const styles = StyleSheet.create({
  flex: {
    flex: 1,
  },
  container: {
    flex: 1,
    backgroundColor: colors.neutral[50],
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.lg,
    paddingBottom: spacing["2xl"],
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
    marginBottom: spacing.xl,
  },
  formSection: {
    marginBottom: spacing.base,
  },
  sectionHeader: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.base,
    color: colors.neutral[800],
    marginBottom: spacing.base,
  },
  label: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.sm,
    color: colors.neutral[800],
    marginBottom: spacing.sm,
    marginTop: spacing.base,
  },
  genderRow: {
    flexDirection: "row",
    gap: spacing.md,
  },
  genderButton: {
    flex: 1,
    paddingVertical: spacing.md + 2,
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: colors.neutral[200],
    backgroundColor: colors.neutral[0],
    alignItems: "center",
    minHeight: 44,
    justifyContent: "center",
    ...shadows.softBase,
  },
  genderSelected: {
    borderColor: colors.primary[400],
    backgroundColor: colors.primary[50],
  },
  genderText: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.sm + 1,
    color: colors.neutral[300],
  },
  genderTextSelected: {
    color: colors.primary[400],
  },
  submitWrapper: {
    marginTop: spacing.xl,
  },
  photoButton: {
    alignSelf: "center",
    marginBottom: spacing.base,
  },
  photoPreview: {
    width: 100,
    height: 100,
    borderRadius: radius.full,
    backgroundColor: colors.neutral[100],
  },
  photoPlaceholder: {
    width: 100,
    height: 100,
    borderRadius: radius.full,
    backgroundColor: colors.neutral[0],
    borderWidth: 2,
    borderColor: colors.neutral[200],
    borderStyle: "dashed",
    alignItems: "center",
    justifyContent: "center",
    ...shadows.softBase,
  },
  photoPlaceholderIcon: {
    fontSize: 28,
    color: colors.neutral[200],
    lineHeight: 32,
  },
  photoPlaceholderText: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.xs,
    color: colors.neutral[200],
    marginTop: 2,
  },
});
