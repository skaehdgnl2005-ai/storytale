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
  TextInput,
  Image,
  Pressable,
  StyleSheet,
  ScrollView,
  Alert,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import * as ImagePicker from "expo-image-picker";
import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { RootStackParamList } from "../navigation/AppNavigator";
import { theme } from "../theme";
import { createProfile, uploadPhoto } from "../api/profiles";
import { ApiClientError } from "../api/client";

type Props = NativeStackScreenProps<RootStackParamList, "ProfileForm">;

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

        {/* 이름 */}
        <Text style={styles.label}>이름 *</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="아이의 이름"
          placeholderTextColor={theme.colors.placeholder}
          maxLength={50}
          accessibilityLabel="아이 이름 입력"
        />

        {/* 나이 */}
        <Text style={styles.label}>나이 *</Text>
        <TextInput
          style={styles.input}
          value={age}
          onChangeText={setAge}
          placeholder="1~12"
          placeholderTextColor={theme.colors.placeholder}
          keyboardType="number-pad"
          maxLength={2}
          accessibilityLabel="아이 나이 입력"
        />

        {/* 성별 */}
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

        {/* 선택 필드 */}
        <Text style={styles.sectionHeader}>더 알려주시면 좋아요</Text>

        <Text style={styles.label}>애착 물건</Text>
        <TextInput
          style={styles.input}
          value={comfortObject}
          onChangeText={setComfortObject}
          placeholder="예: 토니 곰인형"
          placeholderTextColor={theme.colors.placeholder}
          maxLength={100}
          accessibilityLabel="애착 물건 입력"
        />

        <Text style={styles.label}>친한 친구 이름</Text>
        <TextInput
          style={styles.input}
          value={friendName}
          onChangeText={setFriendName}
          placeholder="예: 민준이"
          placeholderTextColor={theme.colors.placeholder}
          maxLength={50}
          accessibilityLabel="친한 친구 이름 입력"
        />

        <Text style={styles.label}>좋아하는 동물</Text>
        <TextInput
          style={styles.input}
          value={favoriteAnimal}
          onChangeText={setFavoriteAnimal}
          placeholder="예: 토끼"
          placeholderTextColor={theme.colors.placeholder}
          maxLength={50}
          accessibilityLabel="좋아하는 동물 입력"
        />

        {/* 제출 버튼 */}
        <Pressable
          style={[styles.submitButton, !isValid && styles.submitDisabled]}
          onPress={handleSubmit}
          disabled={!isValid || loading}
          accessibilityLabel="프로필 만들기"
          accessibilityRole="button"
        >
          {loading ? (
            <ActivityIndicator color={theme.colors.white} />
          ) : (
            <Text style={styles.submitText}>프로필 만들기</Text>
          )}
        </Pressable>
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
    backgroundColor: theme.colors.background,
  },
  content: {
    paddingHorizontal: 24,
    paddingTop: 24,
    paddingBottom: 48,
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
    marginBottom: 32,
  },
  label: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: 14,
    color: theme.colors.text,
    marginBottom: 8,
    marginTop: 16,
  },
  sectionHeader: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: 16,
    color: theme.colors.textSecondary,
    marginTop: 32,
    marginBottom: 8,
  },
  input: {
    fontFamily: "Pretendard-Medium",
    fontSize: 16,
    color: theme.colors.text,
    backgroundColor: theme.colors.white,
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderWidth: 1,
    borderColor: theme.colors.border,
    ...Platform.select({
      ios: {
        shadowColor: "#3E3225",
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.06,
        shadowRadius: 4,
      },
      android: {
        elevation: 1,
      },
    }),
  },
  genderRow: {
    flexDirection: "row",
    gap: 12,
  },
  genderButton: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: theme.colors.border,
    backgroundColor: theme.colors.white,
    alignItems: "center",
    minHeight: 44,
    justifyContent: "center",
  },
  genderSelected: {
    borderColor: theme.colors.primary,
    backgroundColor: theme.colors.primaryLight,
  },
  genderText: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: 15,
    color: theme.colors.textSecondary,
  },
  genderTextSelected: {
    color: theme.colors.primary,
  },
  submitButton: {
    marginTop: 32,
    backgroundColor: theme.colors.primary,
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: "center",
    minHeight: 52,
    justifyContent: "center",
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
  submitDisabled: {
    opacity: 0.5,
  },
  submitText: {
    fontFamily: "Pretendard-Bold",
    fontSize: 17,
    color: theme.colors.white,
  },
  photoButton: {
    alignSelf: "center",
    marginBottom: 16,
  },
  photoPreview: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: theme.colors.border,
  },
  photoPlaceholder: {
    width: 100,
    height: 100,
    borderRadius: 50,
    backgroundColor: theme.colors.white,
    borderWidth: 2,
    borderColor: theme.colors.border,
    borderStyle: "dashed",
    alignItems: "center",
    justifyContent: "center",
  },
  photoPlaceholderIcon: {
    fontSize: 28,
    color: theme.colors.placeholder,
    lineHeight: 32,
  },
  photoPlaceholderText: {
    fontFamily: "Pretendard-Medium",
    fontSize: 12,
    color: theme.colors.placeholder,
    marginTop: 2,
  },
});
