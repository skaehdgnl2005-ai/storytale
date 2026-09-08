/**
 * Primary CTA 전용 버튼 — v3.1 Section 3.3 Focused Delight.
 *
 * 이 버튼만 스프링 바운스 + 액센트 글로우를 가진다.
 * 나머지 버튼(SecondaryButton)은 표준 opacity 전환만 사용.
 *
 * RN 내장 Animated API 사용 — Expo Go 호환성 보장.
 */

import React, { useRef } from "react";
import {
  Animated,
  Pressable,
  Text,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import { colors, radius, shadows, typography, motion } from "../theme";

interface PremiumCreateButtonProps {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
  accessibilityLabel?: string;
}

export function PremiumCreateButton({
  label,
  onPress,
  disabled = false,
  loading = false,
  accessibilityLabel,
}: PremiumCreateButtonProps) {
  const scaleAnim = useRef(new Animated.Value(1)).current;

  const handlePressIn = () => {
    if (disabled || loading) return;
    Animated.spring(scaleAnim, {
      toValue: 0.96,
      damping: motion.springPressIn.damping,
      useNativeDriver: true,
    }).start();
  };

  const handlePressOut = () => {
    Animated.spring(scaleAnim, {
      toValue: 1,
      damping: motion.springPressOut.damping,
      mass: motion.springPressOut.mass,
      useNativeDriver: true,
    }).start();
  };

  return (
    <Animated.View style={{ transform: [{ scale: scaleAnim }] }}>
      <Pressable
        style={[
          styles.button,
          (disabled || loading) && styles.disabled,
        ]}
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        onPress={onPress}
        disabled={disabled || loading}
        accessibilityRole="button"
        accessibilityLabel={accessibilityLabel ?? label}
        accessibilityState={{ disabled: disabled || loading }}
      >
        {loading ? (
          <ActivityIndicator color={colors.neutral[0]} />
        ) : (
          <Text style={styles.label}>{label}</Text>
        )}
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  button: {
    backgroundColor: colors.primary[400],
    borderRadius: radius.md,
    paddingVertical: 18,
    paddingHorizontal: 32,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 52,
    ...shadows.accentGlow,
  },
  disabled: {
    opacity: 0.5,
  },
  label: {
    fontFamily: "Pretendard-Bold",
    fontSize: typography.size.lg,
    color: colors.neutral[0],
  },
});
