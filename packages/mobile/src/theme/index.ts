/**
 * Design tokens — docs/visual-identity-guide-rn.md v3.1 기반.
 *
 * Clean & Familiar + Focused Delight 철학:
 * - 깔끔한 오프화이트 베이스, 정교한 프리미엄 섀도우
 * - Primary CTA 하나에만 스프링 + 액센트 글로우 집중
 */

import { Platform } from "react-native";

// ── 색상 ──────────────────────────────────────────────
export const colors = {
  primary: {
    50: "#FFF8F0",
    100: "#FFEFD6",
    300: "#FFC078",
    400: "#FFA94D", // 메인 액센트
    500: "#F59030",
  },
  secondary: {
    50: "#F8F5FF",
    300: "#BDA3F5",
    400: "#A07DE8",
  },
  neutral: {
    0: "#FFFFFF", // 카드 배경
    50: "#FDF9F5", // 앱 기본 배경
    100: "#F5EDE3",
    200: "#E8DDD0",
    300: "#D4C5B3",
    800: "#2E2720", // 본문 텍스트
  },
  semantic: {
    error: "#E74C3C",
    success: "#6DD4B8",
  },
} as const;

// ── 섀도우 (Tactile Depth) ────────────────────────────
// 넓은 radius + 낮은 opacity → 프리미엄 입체감
export const shadows = {
  softBase: Platform.select({
    ios: {
      shadowColor: "#3E3225",
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: 0.04,
      shadowRadius: 24,
    },
    android: { elevation: 3 },
  })!,
  softHover: Platform.select({
    ios: {
      shadowColor: "#3E3225",
      shadowOffset: { width: 0, height: 16 },
      shadowOpacity: 0.08,
      shadowRadius: 32,
    },
    android: { elevation: 6 },
  })!,
  accentGlow: Platform.select({
    ios: {
      shadowColor: "#FFA94D",
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.3,
      shadowRadius: 16,
    },
    android: { elevation: 4 },
  })!,
} as const;

// ── 모서리 ────────────────────────────────────────────
export const radius = {
  sm: 8, // 칩, 태그, 인풋
  md: 14, // 버튼
  lg: 20, // 카드
  xl: 28, // 대형 카드, contentCard
  full: 9999, // 원형
} as const;

// ── 타이포그래피 ──────────────────────────────────────
export const typography = {
  family: {
    ui: "Pretendard",
    story: "Cafe24Ssurround",
  },
  size: {
    xs: 12,
    sm: 14,
    base: 16,
    lg: 18,
    xl: 22,
    "2xl": 28,
    "3xl": 36,
  },
} as const;

// ── 스페이싱 (4px grid) ──────────────────────────────
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 24,
  xl: 32,
  "2xl": 48,
} as const;

// ── 모션 ──────────────────────────────────────────────
// Focused Delight: Primary CTA만 스프링 사용
export const motion = {
  springPressIn: { damping: 15 },
  springPressOut: { damping: 10, mass: 1.2 },
  timing: {
    fast: 200,
    normal: 300,
    slow: 500,
  },
} as const;

// ── 동화책 뷰어 전용 ─────────────────────────────────
export const storyViewer = {
  bg: "#FFF9EE",
  text: "#3D3225",
  accent: "#E88D5A",
} as const;

// ── 호환성 래퍼 (기존 화면 마이그레이션 전까지 유지) ──
// @deprecated colors.primary[400] 등을 직접 사용할 것
export const theme = {
  colors: {
    primary: colors.primary[400],
    primaryLight: colors.primary[50],
    secondary: colors.secondary[400],
    tertiary: colors.semantic.success,
    background: colors.neutral[50],
    white: colors.neutral[0],
    text: colors.neutral[800],
    textSecondary: colors.neutral[300],
    placeholder: colors.neutral[200],
    border: colors.neutral[100],
    error: colors.semantic.error,
    success: colors.semantic.success,
    shadow: "#3E3225",
  },
  spacing,
};
