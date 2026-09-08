/**
 * 보조 버튼 — 표준 opacity 전환만 (스프링 없음).
 *
 * variant:
 * - 'outlined': 흰 배경 + primary 테두리
 * - 'text': 투명 배경 + 밑줄 텍스트
 */

import React from "react";
import { Pressable, Text, StyleSheet, type ViewStyle } from "react-native";
import { colors, radius, typography } from "../theme";

interface SecondaryButtonProps {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  variant?: "outlined" | "text";
  accessibilityLabel?: string;
  style?: ViewStyle;
}

export function SecondaryButton({
  label,
  onPress,
  disabled = false,
  variant = "outlined",
  accessibilityLabel,
  style,
}: SecondaryButtonProps) {
  const isText = variant === "text";

  return (
    <Pressable
      style={({ pressed }) => [
        isText ? styles.textBase : styles.outlinedBase,
        pressed && styles.pressed,
        disabled && styles.disabled,
        style,
      ]}
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ disabled }}
    >
      <Text style={isText ? styles.textLabel : styles.outlinedLabel}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  outlinedBase: {
    backgroundColor: colors.neutral[0],
    borderRadius: radius.md,
    borderWidth: 1.5,
    borderColor: colors.primary[400],
    paddingVertical: 16,
    paddingHorizontal: 32,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 52,
  },
  outlinedLabel: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.base,
    color: colors.primary[400],
  },
  textBase: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 44,
  },
  textLabel: {
    fontFamily: "Pretendard-SemiBold",
    fontSize: typography.size.sm,
    color: colors.neutral[300],
    textDecorationLine: "underline",
  },
  pressed: {
    opacity: 0.7,
  },
  disabled: {
    opacity: 0.5,
  },
});
