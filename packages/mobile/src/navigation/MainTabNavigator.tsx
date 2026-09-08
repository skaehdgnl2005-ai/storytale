/**
 * 바텀 탭 네비게이터 — 홈 / 서재 / 마이.
 *
 * 각 탭은 독립 스택을 가지며, 탭 간 이동 시 스택 상태 보존.
 */

import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { Home, BookOpen, User } from "lucide-react-native";

import { HomeScreen } from "../screens/HomeScreen";
import { PurposeSelectScreen } from "../screens/PurposeSelectScreen";
import { DescriptiveInputScreen } from "../screens/DescriptiveInputScreen";
import { PreviewScreen } from "../screens/PreviewScreen";
import { GenerationScreen } from "../screens/GenerationScreen";
import { RecommendPurposeScreen } from "../screens/RecommendPurposeScreen";
import { RecommendInputScreen } from "../screens/RecommendInputScreen";
import { RecommendResultScreen } from "../screens/RecommendResultScreen";
import { LibraryScreen } from "../screens/LibraryScreen";
import { MyPageScreen } from "../screens/MyPageScreen";
import { ProfileFormScreen } from "../screens/ProfileFormScreen";
import { colors, shadows } from "../theme";
import type {
  HomeTabParamList,
  LibraryTabParamList,
  MyPageTabParamList,
} from "./AppNavigator";

// ── Home Tab Stack ────────────────────────────────────
const HomeStack = createNativeStackNavigator<HomeTabParamList>();

function HomeTabNavigator() {
  return (
    <HomeStack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.neutral[50] },
        headerTintColor: colors.neutral[800],
        headerTitleStyle: { fontFamily: "Pretendard-SemiBold" },
        contentStyle: { backgroundColor: colors.neutral[50] },
      }}
    >
      <HomeStack.Screen
        name="Home"
        component={HomeScreen}
        options={{ headerShown: false }}
      />
      <HomeStack.Screen
        name="PurposeSelect"
        component={PurposeSelectScreen}
        options={{ title: "어떤 이야기를 만들까요" }}
      />
      <HomeStack.Screen
        name="DescriptiveInput"
        component={DescriptiveInputScreen}
        options={{ title: "이야기 담기" }}
      />
      <HomeStack.Screen
        name="Preview"
        component={PreviewScreen}
        options={{ title: "이야기 미리보기" }}
      />
      <HomeStack.Screen
        name="Generation"
        component={GenerationScreen}
        options={{
          title: "이야기 만들기",
          headerBackVisible: false,
          gestureEnabled: false,
        }}
      />
      <HomeStack.Screen
        name="RecommendPurpose"
        component={RecommendPurposeScreen}
        options={{ title: "이야기의 힘을 빌려보세요" }}
      />
      <HomeStack.Screen
        name="RecommendInput"
        component={RecommendInputScreen}
        options={{ title: "이야기 찾기" }}
      />
      <HomeStack.Screen
        name="RecommendResult"
        component={RecommendResultScreen}
        options={{ title: "추천 결과" }}
      />
    </HomeStack.Navigator>
  );
}

// ── Library Tab Stack ─────────────────────────────────
const LibraryStack = createNativeStackNavigator<LibraryTabParamList>();

function LibraryTabNavigator() {
  return (
    <LibraryStack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.neutral[50] },
        headerTintColor: colors.neutral[800],
        headerTitleStyle: { fontFamily: "Pretendard-SemiBold" },
        contentStyle: { backgroundColor: colors.neutral[50] },
      }}
    >
      <LibraryStack.Screen
        name="Library"
        component={LibraryScreen}
        options={{ title: "내 서재" }}
      />
    </LibraryStack.Navigator>
  );
}

// ── MyPage Tab Stack ──────────────────────────────────
const MyPageStack = createNativeStackNavigator<MyPageTabParamList>();

function MyPageTabNavigator() {
  return (
    <MyPageStack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.neutral[50] },
        headerTintColor: colors.neutral[800],
        headerTitleStyle: { fontFamily: "Pretendard-SemiBold" },
        contentStyle: { backgroundColor: colors.neutral[50] },
      }}
    >
      <MyPageStack.Screen
        name="MyPage"
        component={MyPageScreen}
        options={{ title: "마이" }}
      />
      <MyPageStack.Screen
        name="ProfileForm"
        component={ProfileFormScreen}
        options={{ title: "프로필 등록" }}
      />
    </MyPageStack.Navigator>
  );
}

// ── Bottom Tabs ───────────────────────────────────────
const Tab = createBottomTabNavigator();

export function MainTabNavigator() {
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.neutral[0],
          borderTopWidth: 1,
          borderTopColor: colors.neutral[100],
          ...shadows.softBase,
        },
        tabBarActiveTintColor: colors.primary[400],
        tabBarInactiveTintColor: colors.neutral[300],
        tabBarLabelStyle: {
          fontFamily: "Pretendard-Medium",
          fontSize: 11,
        },
      }}
    >
      <Tab.Screen
        name="HomeTab"
        component={HomeTabNavigator}
        options={{
          tabBarLabel: "홈",
          tabBarIcon: ({ color, size }) => (
            <Home size={size} color={color} strokeWidth={1.5} />
          ),
        }}
      />
      <Tab.Screen
        name="LibraryTab"
        component={LibraryTabNavigator}
        options={{
          tabBarLabel: "서재",
          tabBarIcon: ({ color, size }) => (
            <BookOpen size={size} color={color} strokeWidth={1.5} />
          ),
        }}
      />
      <Tab.Screen
        name="MyPageTab"
        component={MyPageTabNavigator}
        options={{
          tabBarLabel: "마이",
          tabBarIcon: ({ color, size }) => (
            <User size={size} color={color} strokeWidth={1.5} />
          ),
        }}
      />
    </Tab.Navigator>
  );
}
