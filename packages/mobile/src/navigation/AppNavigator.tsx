import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { HomeScreen } from "../screens/HomeScreen";
import { LoginScreen } from "../screens/LoginScreen";
import { ProfileFormScreen } from "../screens/ProfileFormScreen";
import { PurposeSelectScreen } from "../screens/PurposeSelectScreen";
import { DescriptiveInputScreen } from "../screens/DescriptiveInputScreen";
import { PreviewScreen } from "../screens/PreviewScreen";
import { GenerationScreen } from "../screens/GenerationScreen";
import { ViewerScreen } from "../screens/ViewerScreen";
import { LibraryScreen } from "../screens/LibraryScreen";
import type { PurposeId } from "../data/purposes";
import type { ScenePlan, StoryPreview } from "../api/stories";
import { theme } from "../theme";

export type RootStackParamList = {
  // S27b — 이메일+비밀번호 로그인/회원가입. 최초 진입 + 401 fallback 양쪽에서 사용.
  // navigation.reset 로 진입 후 stack 을 비우므로 back 으로 복귀 불가.
  Login: undefined;
  Home: undefined;
  ProfileForm: undefined;
  PurposeSelect: undefined;
  // S30b — 서술형 입력 화면. 라우트 파라미터 모양은 S29에서 이미 고정.
  DescriptiveInput: { purpose: PurposeId };
  // S31 — 미리보기/수정 화면. S30b의 createStoryPlan 응답을 그대로 전달한다.
  Preview: {
    plan: ScenePlan;
    preview: StoryPreview;
    childId: string;
    childName: string;
  };
  // S32 — 생성 중 로딩 UX. PreviewScreen이 확정 시 넘어온다.
  // child 정보 전체는 GenerationScreen에서 getProfile(childId)로 재조회.
  Generation: {
    plan: ScenePlan;
    childId: string;
    childName: string;
    style: string;
  };
  // S33 — 그림책 뷰어. Generation이 완료 시 `navigation.reset({ routes: [Home, Viewer] })`
  // 로 진입하므로, Viewer 에서 back 시 바로 Home 으로 돌아간다(Generation 재방문 방지).
  Viewer: { storyId: string };
  // S34 — 내 서재. HomeScreen 의 "내 서재" 버튼에서 진입.
  // back 으로 Home 복귀(Library 는 stack 위에 자연스럽게 push 한다).
  Library: undefined;
};

const Stack = createNativeStackNavigator<RootStackParamList>();

interface AppNavigatorProps {
  /**
   * S27b — 부트스트랩 시 저장 토큰을 검증한 뒤 초기 라우트를 결정한다.
   * "Home" 이면 이미 로그인됨, "Login" 이면 로그인 필요.
   * `App.tsx::bootstrapAuth` 가 결정해서 전달.
   */
  initialRouteName: "Home" | "Login";
}

export const AppNavigator: React.FC<AppNavigatorProps> = ({ initialRouteName }) => {
  return (
    <NavigationContainer>
      <Stack.Navigator
        initialRouteName={initialRouteName}
        screenOptions={{
          headerStyle: { backgroundColor: theme.colors.background },
          headerTintColor: theme.colors.text,
          headerTitleStyle: { fontFamily: "Pretendard-SemiBold" },
          contentStyle: { backgroundColor: theme.colors.background },
        }}
      >
        <Stack.Screen
          name="Login"
          component={LoginScreen}
          // S27b — 로그인 화면은 헤더 숨김 (첫 인상 깔끔하게).
          // 401 fallback 진입 시에도 "돌아가기" 버튼을 일부러 노출하지 않아
          // 사용자가 혼란스러운 인증된 화면으로 돌아가지 못하도록 한다.
          options={{ headerShown: false }}
        />
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
        <Stack.Screen
          name="Preview"
          component={PreviewScreen}
          options={{ title: "이야기 미리보기" }}
        />
        <Stack.Screen
          name="Generation"
          component={GenerationScreen}
          options={{
            title: "이야기 만들기",
            // 생성 중 뒤로가기 버튼으로 도중 취소를 막는다.
            // 완료/실패 시에는 화면 내 CTA 로 Home 복귀.
            headerBackVisible: false,
            gestureEnabled: false,
          }}
        />
        <Stack.Screen
          name="Viewer"
          component={ViewerScreen}
          options={{ title: "그림책" }}
        />
        <Stack.Screen
          name="Library"
          component={LibraryScreen}
          options={{ title: "내 서재" }}
        />
      </Stack.Navigator>
    </NavigationContainer>
  );
};
