/**
 * 화면 레이아웃 — SafeAreaView + PaperBackground 통합.
 *
 * 모든 화면에서 일관된 패딩과 배경을 제공한다.
 */

import React from "react";
import { StyleSheet, type ViewStyle, type StyleProp } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { PaperBackground } from "./PaperBackground";
import { spacing } from "../theme";

interface ScreenLayoutProps {
  children: React.ReactNode;
  paddingHorizontal?: number;
  style?: StyleProp<ViewStyle>;
}

export function ScreenLayout({
  children,
  paddingHorizontal = spacing.lg,
  style,
}: ScreenLayoutProps) {
  return (
    <PaperBackground>
      <SafeAreaView
        style={[styles.container, { paddingHorizontal }, style]}
        edges={["bottom"]}
      >
        {children}
      </SafeAreaView>
    </PaperBackground>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});
