import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { HomeScreen } from "../screens/HomeScreen";
import { ProfileFormScreen } from "../screens/ProfileFormScreen";
import { PurposeSelectScreen } from "../screens/PurposeSelectScreen";
import { DescriptiveInputScreen } from "../screens/DescriptiveInputScreen";
import type { PurposeId } from "../data/purposes";
import { theme } from "../theme";

export type RootStackParamList = {
  Home: undefined;
  ProfileForm: undefined;
  PurposeSelect: undefined;
  // S30b — 서술형 입력 화면. 라우트 파라미터 모양은 S29에서 이미 고정.
  DescriptiveInput: { purpose: PurposeId };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

export const AppNavigator = () => {
  return (
    <NavigationContainer>
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: theme.colors.background },
          headerTintColor: theme.colors.text,
          headerTitleStyle: { fontFamily: "Pretendard-SemiBold" },
          contentStyle: { backgroundColor: theme.colors.background },
        }}
      >
        <Stack.Screen name="Home" component={HomeScreen} />
        <Stack.Screen
          name="ProfileForm"
          component={ProfileFormScreen}
          options={{ title: "프로필 등록" }}
        />
        <Stack.Screen
          name="PurposeSelect"
          component={PurposeSelectScreen}
          options={{ title: "어떤 이야기를 만들까요" }}
        />
        <Stack.Screen
          name="DescriptiveInput"
          component={DescriptiveInputScreen}
          options={{ title: "이야기 담기" }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
};
