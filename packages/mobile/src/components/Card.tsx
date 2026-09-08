/**
 * 카드 컴포넌트 — softBase 섀도우 + 따뜻한 배경.
 *
 * v3.1 Tactile Depth: 넓은 radius + 낮은 opacity 프리미엄 그림자.
 */

import React from "react";
import {
  Pressable,
  View,
  StyleSheet,
  type ViewStyle,
  type StyleProp,
} from "react-native";
import { colors, radius, shadows, spacing } from "../theme";

interface CardProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  onPress?: () => void;
  onLongPress?: () => void;
  selected?: boolean;
  selectedBorderColor?: string;
  accessibilityLabel?: string;
  accessibilityHint?: string;
}

export function Card({
  children,
  style,
  onPress,
  onLongPress,
  selected = false,
  selectedBorderColor = colors.primary[400],
  accessibilityLabel,
  accessibilityHint,
}: CardProps) {
  const cardStyle: StyleProp<ViewStyle> = [
    styles.base,
    selected && {
      borderColor: selectedBorderColor,
      backgroundColor: colors.primary[50],
    },
    style,
  ];

  if (onPress != null || onLongPress != null) {
    return (
      <Pressable
        style={({ pressed }) => [cardStyle, pressed && styles.pressed]}
        onPress={onPress}
        onLongPress={onLongPress}
        delayLongPress={400}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel}
        accessibilityHint={accessibilityHint}
        accessibilityState={selected ? { selected: true } : undefined}
      >
        {children}
      </Pressable>
    );
  }

  return <View style={cardStyle}>{children}</View>;
}

const styles = StyleSheet.create({
  base: {
    backgroundColor: colors.neutral[0],
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.neutral[100],
    ...shadows.softBase,
  },
  pressed: {
    opacity: 0.85,
  },
});
