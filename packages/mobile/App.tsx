import React, { useCallback, useEffect, useState } from "react";
import { View } from "react-native";
import { useFonts } from "expo-font";
import * as SplashScreen from "expo-splash-screen";
import { AppNavigator } from "./src/navigation/AppNavigator";
import { bootstrapAuth, type BootstrapRoute } from "./src/auth/bootstrap";

SplashScreen.preventAutoHideAsync();

export default function App() {
  const [fontsLoaded] = useFonts({
    "Pretendard-Medium": require("./assets/fonts/Pretendard-Medium.otf"),
    "Pretendard-SemiBold": require("./assets/fonts/Pretendard-SemiBold.otf"),
    "Pretendard-Bold": require("./assets/fonts/Pretendard-Bold.otf"),
    "Cafe24Ssurround": require("./assets/fonts/Cafe24Ssurround.ttf"),
  });

  // S27b — 부트스트랩 단계에서 저장 토큰을 확인하고 /auth/me 로 유효성을 검증한 뒤
  // 초기 라우트를 결정한다. 결과가 null 인 동안은 폰트 로딩과 동일하게 화면을
  // 띄우지 않아 Login ↔ Home flash 를 방지한다.
  const [initialRoute, setInitialRoute] = useState<BootstrapRoute | null>(null);

  useEffect(() => {
    let cancelled = false;
    bootstrapAuth().then((route) => {
      if (!cancelled) {
        setInitialRoute(route);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const ready = fontsLoaded && initialRoute !== null;

  const onLayoutRootView = useCallback(async () => {
    if (ready) {
      await SplashScreen.hideAsync();
    }
  }, [ready]);

  if (!ready) {
    return null;
  }

  return (
    <View style={{ flex: 1 }} onLayout={onLayoutRootView}>
      <AppNavigator initialRouteName={initialRoute} />
    </View>
  );
}
