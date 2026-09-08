/**
 * 스타일드 입력 필드 — Clean & Familiar.
 *
 * 포커스 시 borderColor만 primary로 전환. 과도한 애니메이션 없음.
 */

import React, { useState } from "react";
import {
  TextInput,
  StyleSheet,
  type TextInputProps,
  type StyleProp,
  type TextStyle,
} from "react-native";
import { colors, radius, typography, spacing, shadows } from "../theme";

interface StyledInputProps extends TextInputProps {
  style?: StyleProp<TextStyle>;
}

export function StyledInput({ style, onFocus, onBlur, ...props }: StyledInputProps) {
  const [focused, setFocused] = useState(false);

  return (
    <TextInput
      style={[styles.base, focused && styles.focused, style]}
      placeholderTextColor={colors.neutral[200]}
      onFocus={(e) => {
        setFocused(true);
        onFocus?.(e);
      }}
      onBlur={(e) => {
        setFocused(false);
        onBlur?.(e);
      }}
      {...props}
    />
  );
}

const styles = StyleSheet.create({
  base: {
    fontFamily: "Pretendard-Medium",
    fontSize: typography.size.base,
    color: colors.neutral[800],
    backgroundColor: colors.neutral[0],
    borderWidth: 1.5,
    borderColor: colors.neutral[200],
    borderRadius: radius.sm,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.base,
    ...shadows.softBase,
  },
  focused: {
    borderColor: colors.primary[400],
  },
});
