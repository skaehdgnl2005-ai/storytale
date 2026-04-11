import React from "react";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { HomeScreen } from "../screens/HomeScreen";
import { ProfileFormScreen } from "../screens/ProfileFormScreen";
import { theme } from "../theme";

export type RootStackParamList = {
  Home: undefined;
  ProfileForm: undefined;
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
      </Stack.Navigator>
    </NavigationContainer>
  );
};
