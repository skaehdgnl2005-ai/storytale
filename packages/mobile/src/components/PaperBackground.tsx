/**
 * 종이 텍스처 배경 — v3.1 Section 3.1.
 *
 * 앱 루트에 한 번만 배치하여 미세한 종이 질감을 제공한다.
 * 에셋(paper-noise-pattern.png)이 없으면 단색 배경으로 폴백.
 */

import React from "react";
import { View, Image, StyleSheet } from "react-native";
import { colors } from "../theme";

let paperNoiseSource: ReturnType<typeof require> | null = null;
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  paperNoiseSource = require("../../assets/images/paper-noise-pattern.png");
} catch {
  paperNoiseSource = null;
}

interface PaperBackgroundProps {
  children: React.ReactNode;
}

export function PaperBackground({ children }: PaperBackgroundProps) {
  return (
    <View style={styles.container}>
      {paperNoiseSource != null && (
        <Image
          source={paperNoiseSource}
          style={styles.noiseOverlay}
          resizeMode="repeat"
        />
      )}
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.neutral[50],
  },
  noiseOverlay: {
    ...StyleSheet.absoluteFillObject,
    opacity: 0.03,
  },
});
