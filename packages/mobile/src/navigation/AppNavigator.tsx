/**
 * 루트 네비게이터.
 *
 * 구조:
 *   RootStack
 *     ├─ Login (headerShown: false)
 *     ├─ MainTabs (headerShown: false) → BottomTab(홈/서재/마이)
 *     └─ Viewer (presentation: modal, 풀스크린)
 */

import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { LoginScreen } from "../screens/LoginScreen";
import { ViewerScreen } from "../screens/ViewerScreen";
import { MainTabNavigator } from "./MainTabNavigator";
import { colors } from "../theme";
import type { PurposeId } from "../data/purposes";
import type { ScenePlan, StoryPreview } from "../api/stories";
import type { RecommendationResult } from "../api/recommendations";

// ── 타입 정의 ─────────────────────────────────────────

/** HomeTab 내부 스택 */
export type HomeTabParamList = {
  Home: undefined;
  PurposeSelect: undefined;
  DescriptiveInput: { purpose: PurposeId };
  Preview: {
    plan: ScenePlan;
    preview: StoryPreview;
    childId: string;
    childName: string;
  };
  Generation: {
    plan: ScenePlan;
    childId: string;
    childName: string;
    style: string;
  };
  RecommendPurpose: undefined;
  RecommendInput: { purpose: PurposeId };
  RecommendResult: {
    result: RecommendationResult;
    childId: string;
    childName: string;
  };
};

/** LibraryTab 내부 스택 */
export type LibraryTabParamList = {
  Library: undefined;
};

/** MyPageTab 내부 스택 */
export type MyPageTabParamList = {
  MyPage: undefined;
  ProfileForm: undefined;
};

/** 루트 스택 */
export type RootStackParamList = {
  Login: undefined;
  MainTabs: undefined;
  Viewer: { storyId: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

interface AppNavigatorProps {
  initialRouteName: "MainTabs" | "Login";
}

export const AppNavigator: React.FC<AppNavigatorProps> = ({
  initialRouteName,
}) => {
  return (
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName={initialRouteName}
        screenOptions={{
          headerStyle: { backgroundColor: colors.neutral[50] },
          headerTintColor: colors.neutral[800],
          headerTitleStyle: { fontFamily: "Pretendard-SemiBold" },
          contentStyle: { backgroundColor: colors.neutral[50] },
        }}
      >
        <Stack.Screen
          name="Login"
          component={LoginScreen}
          options={{ headerShown: false }}
        />
        <Stack.Screen
          name="MainTabs"
          component={MainTabNavigator}
          options={{ headerShown: false }}
        />
        <Stack.Screen
          name="Viewer"
          component={ViewerScreen}
          options={{
            headerShown: false,
            presentation: "modal",
          }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
};
