# 🎨 AI 맞춤형 동화책 앱 — Visual Brand Identity Guide

> **런타임**: React Native (Expo)
> **목적**: 디자인 일관성 유지 + AI/개발자가 코드 레벨 테마로 즉시 번역 가능한 시각 가이드
> **대상**: 프론트엔드 개발자, 디자이너, AI 코드 생성 에이전트
>
> ⚠️ 이 문서의 모든 코드 예시는 **React Native StyleSheet** 기준입니다.
> `CSS`, `className`, `div`, `box-shadow` 등 웹 전용 문법을 사용하지 마세요.

---

## 1. 디자인 철학 (Design Philosophy)

핵심 경험: **"부모와 아이가 함께 만드는 따뜻한 이야기"**

| 원칙 | 설명 |
|---|---|
| **Warmth (따뜻함)** | 파스텔 웜톤, 부드러운 곡선, 은은한 그림자로 포근한 분위기 전달 |
| **Safety (안전함)** | 날카로운 모서리, 강렬한 색상 대비, 갑작스러운 모션 배제 |
| **Delight (즐거움)** | 누르고 싶은 버튼, 살아 움직이는 캐릭터, 기분 좋은 인터랙션 |

---

## 2. 테마 토큰 구조 (Theme Tokens)

모든 디자인 토큰은 하나의 `theme.ts` 파일에서 관리합니다.

### 2.1 theme.ts — 전체 토큰 정의

```typescript
// theme.ts
import { Platform } from 'react-native';

export const colors = {
  // ── Primary: 따뜻한 크림 오렌지 ──
  primary: {
    50:  '#FFF8F0',
    100: '#FFEFD6',
    200: '#FFD9A8',
    300: '#FFC078',
    400: '#FFA94D',  // 메인 액센트
    500: '#F59030',
    600: '#D97218',
    700: '#B3580F',
  },
  // ── Secondary: 부드러운 라벤더 ──
  secondary: {
    50:  '#F8F5FF',
    100: '#EDE5FF',
    200: '#D9C8FF',
    300: '#BDA3F5',
    400: '#A07DE8',  // 보조 액센트
    500: '#8560D0',
    600: '#6B47B0',
  },
  // ── Tertiary: 민트 그린 ──
  tertiary: {
    50:  '#F0FDF9',
    100: '#D5F5EC',
    200: '#A8E8D5',
    300: '#6DD4B8',  // 성공/긍정 피드백
    400: '#3DBD9B',
    500: '#24A07E',
  },
  // ── Neutral: 웜 그레이 ──
  neutral: {
    0:   '#FFFFFF',
    50:  '#FDF9F5',   // 앱 기본 배경
    100: '#F5EDE3',
    200: '#E8DDD0',
    300: '#D4C5B3',
    400: '#B5A48F',
    500: '#8F7E6A',
    600: '#6B5D4D',
    700: '#4A3F33',
    800: '#2E2720',   // 본문 텍스트
    900: '#1A1510',
  },
  // ── Semantic ──
  semantic: {
    success: '#6DD4B8',
    warning: '#FFD166',
    error:   '#F28B82',
    info:    '#82B1FF',
  },
} as const;

export const typography = {
  family: {
    ui:    Platform.select({ ios: 'Pretendard', android: 'Pretendard' }) ?? 'System',
    story: Platform.select({ ios: 'Cafe24Ssurround', android: 'Cafe24Ssurround' }) ?? 'System',
  },
  size: {
    xs:   12,  // 캡션, 타임스탬프
    sm:   14,  // 보조 텍스트
    base: 16,  // 본문 기본
    lg:   18,  // 소제목
    xl:   22,  // 섹션 타이틀
    '2xl': 28, // 페이지 타이틀
    '3xl': 36, // 히어로 텍스트
  },
  lineHeight: {
    tight:  1.3,
    normal: 1.6,
    loose:  1.8,  // 동화 본문 전용
  },
  weight: {
    regular:  '400' as const,
    medium:   '500' as const,
    semibold: '600' as const,
    bold:     '700' as const,
  },
} as const;

export const storyTypography = {
  bodySize:   22,  // 최소 22 — 아이 시인성 확보
  titleSize:  32,
  lineHeight: 2.0,
  letterSpacing: 0.4,
} as const;

export const spacing = {
  xs:  4,
  sm:  8,
  md:  12,
  base: 16,
  lg:  24,
  xl:  32,
  '2xl': 48,
  '3xl': 64,
} as const;

export const radius = {
  sm:   8,   // 칩, 태그, 인풋 필드
  md:   14,  // 카드, 버튼
  lg:   20,  // 모달, 바텀시트
  xl:   28,  // 대형 카드, 동화 뷰어
  full: 9999, // 아바타, 원형 버튼
} as const;

// ── React Native 그림자 (웜톤) ──
// ⚠️ RN은 CSS box-shadow를 지원하지 않습니다.
// iOS: shadow* props, Android: elevation
export const shadows = {
  sm: {
    shadowColor: '#3E3225',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 3,
    elevation: 1,
  },
  md: {
    shadowColor: '#3E3225',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.08,
    shadowRadius: 12,
    elevation: 3,
  },
  lg: {
    shadowColor: '#3E3225',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.10,
    shadowRadius: 24,
    elevation: 6,
  },
  xl: {
    shadowColor: '#3E3225',
    shadowOffset: { width: 0, height: 16 },
    shadowOpacity: 0.12,
    shadowRadius: 40,
    elevation: 10,
  },
} as const;

// ── 모션 ──
// ⚠️ RN에서는 CSS transition/cubic-bezier 대신
// react-native-reanimated의 withSpring / withTiming을 사용합니다.
export const motion = {
  spring: {
    bounce:  { damping: 12, stiffness: 180 },  // 탄력 있는 등장
    gentle:  { damping: 20, stiffness: 120 },  // 부드러운 슬라이드
  },
  timing: {
    micro:    120,  // 버튼 색상 변경
    fast:     200,  // 호버/포커스, 토글
    normal:   300,  // 카드 등장, 모달 열림
    slow:     500,  // 페이지 전환
    dramatic: 800,  // 인트로, 캐릭터 등장
  },
  easing: {
    // react-native-reanimated Easing 또는 Animated.Easing 사용
    pageTurn: 'bezier(0.65, 0, 0.35, 1)',
  },
} as const;
```

### 2.2 다크 모드 토큰

```typescript
// theme.dark.ts
import { colors as lightColors } from './theme';

export const darkColors = {
  ...lightColors,
  neutral: {
    0:   '#1E1A15',   // 카드 배경
    50:  '#161310',   // 앱 배경
    100: '#2A2520',
    200: '#3D362E',
    300: '#5A5045',
    400: '#7A6E60',
    500: '#9C8E7D',
    600: '#BDB0A0',
    700: '#D6CBBF',
    800: '#EDE5DA',   // 본문 텍스트
    900: '#F8F3ED',
  },
  primary: {
    ...lightColors.primary,
    400: '#FFB86B',   // 밝기 보정
  },
  secondary: {
    ...lightColors.secondary,
    400: '#B99AEF',
  },
  tertiary: {
    ...lightColors.tertiary,
    300: '#7EDCBC',
  },
} as const;

export const darkShadows = {
  sm: { shadowColor: '#000000', shadowOffset: { width: 0, height: 1 }, shadowOpacity: 0.20, shadowRadius: 3, elevation: 1 },
  md: { shadowColor: '#000000', shadowOffset: { width: 0, height: 4 }, shadowOpacity: 0.25, shadowRadius: 12, elevation: 3 },
  lg: { shadowColor: '#000000', shadowOffset: { width: 0, height: 8 }, shadowOpacity: 0.30, shadowRadius: 24, elevation: 6 },
} as const;

export const darkStoryViewer = {
  bg:     '#1F1B15',
  text:   '#E8DECE',
  accent: '#F0A06A',
} as const;
```

### 2.3 테마 컨텍스트 연동

```typescript
// ThemeProvider.tsx
import React, { createContext, useContext } from 'react';
import { useColorScheme } from 'react-native';
import * as light from './theme';
import { darkColors, darkShadows } from './theme.dark';

type Theme = {
  colors: typeof light.colors;
  shadows: typeof light.shadows;
  typography: typeof light.typography;
  spacing: typeof light.spacing;
  radius: typeof light.radius;
  motion: typeof light.motion;
};

const ThemeContext = createContext<Theme>({
  colors: light.colors,
  shadows: light.shadows,
  typography: light.typography,
  spacing: light.spacing,
  radius: light.radius,
  motion: light.motion,
});

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const scheme = useColorScheme();
  const isDark = scheme === 'dark';

  const theme: Theme = {
    colors:     isDark ? darkColors : light.colors,
    shadows:    isDark ? darkShadows : light.shadows,
    typography: light.typography,
    spacing:    light.spacing,
    radius:     light.radius,
    motion:     light.motion,
  };

  return (
    <ThemeContext.Provider value={theme}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);
```

---

## 3. 컬러 사용 규칙 (Color Usage)

| 용도 | 토큰 | 사용 예시 |
|---|---|---|
| 앱 배경 | `colors.neutral[50]` | 전체 화면 기본 배경 |
| 카드 배경 | `colors.neutral[0]` | 콘텐츠 카드, 모달 |
| 주요 CTA | `colors.primary[400]` | "동화 만들기", "다음" |
| 보조 기능 | `colors.secondary[400]` | 태그, 배지 |
| 긍정 피드백 | `colors.tertiary[300]` | 완료 체크, 성공 |
| 본문 텍스트 | `colors.neutral[800]` | 일반 본문 |
| 보조 텍스트 | `colors.neutral[500]` | 캡션, 힌트 |
| 비활성 상태 | `colors.neutral[300]` | 비활성 버튼, 구분선 |

### Storybook 뷰어 전용 팔레트

```typescript
export const storyViewerColors = {
  bg:     '#FFF9EE',  // 오래된 종이 느낌
  text:   '#3D3225',  // 따뜻한 다크 브라운
  accent: '#E88D5A',  // 삽화 하이라이트
  shadow: 'rgba(62, 50, 37, 0.08)',
} as const;
```

---

## 4. 타이포그래피 규칙 (Typography)

### 4.1 폰트 로딩 (Expo)

```typescript
// App.tsx 또는 _layout.tsx
import { useFonts } from 'expo-font';

const [fontsLoaded] = useFonts({
  'Pretendard':           require('./assets/fonts/Pretendard-Regular.otf'),
  'Pretendard-Medium':    require('./assets/fonts/Pretendard-Medium.otf'),
  'Pretendard-SemiBold':  require('./assets/fonts/Pretendard-SemiBold.otf'),
  'Pretendard-Bold':      require('./assets/fonts/Pretendard-Bold.otf'),
  'Cafe24Ssurround':      require('./assets/fonts/Cafe24Ssurround.ttf'),
  'Cafe24SsurroundAir':   require('./assets/fonts/Cafe24SsurroundAir.ttf'),
});
```

### 4.2 사용 예시

```typescript
import { StyleSheet } from 'react-native';
import { typography, colors, storyTypography, storyViewerColors } from './theme';

const textStyles = StyleSheet.create({
  pageTitle: {
    fontFamily: 'Pretendard-Bold',
    fontSize: typography.size['2xl'],
    lineHeight: typography.size['2xl'] * typography.lineHeight.tight,
    color: colors.neutral[800],
  },
  body: {
    fontFamily: 'Pretendard',
    fontSize: typography.size.base,
    lineHeight: typography.size.base * typography.lineHeight.normal,
    color: colors.neutral[800],
  },
  caption: {
    fontFamily: 'Pretendard',
    fontSize: typography.size.sm,
    color: colors.neutral[500],
  },
  // ── 동화 뷰어 전용 ──
  storyBody: {
    fontFamily: 'Cafe24Ssurround',
    fontSize: storyTypography.bodySize,
    lineHeight: storyTypography.bodySize * storyTypography.lineHeight,
    letterSpacing: storyTypography.letterSpacing,
    color: storyViewerColors.text,
  },
  storyTitle: {
    fontFamily: 'Cafe24SsurroundAir',
    fontSize: storyTypography.titleSize,
    color: storyViewerColors.text,
  },
});
```

> **⚠️ Android 폰트 규칙**: `fontWeight`와 커스텀 `fontFamily`를 동시에 쓰면 Android에서 무시됩니다.
> 반드시 weight별로 별도 fontFamily를 등록하세요 (`Pretendard-Bold` 등).

---

## 5. 간격 및 레이아웃 (Spacing & Layout)

```
┌────────────────────────────────────────┐
│  SafeAreaView                          │
│  ┌──────────────────────────────────┐  │
│  │  paddingHorizontal: spacing.lg   │  │
│  │           (24)                   │  │
│  │  ┌────────────────────────────┐  │  │
│  │  │      Content Area          │  │  │
│  │  │                            │  │  │
│  │  │  Card gap: spacing.base    │  │  │
│  │  │           (16)             │  │  │
│  │  │  Section gap: spacing.xl   │  │  │
│  │  │           (32)             │  │  │
│  │  └────────────────────────────┘  │  │
│  └──────────────────────────────────┘  │
│        Bottom Tab Bar (56 + inset)     │
└────────────────────────────────────────┘
```

```typescript
const layoutStyles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.neutral[50],
    paddingHorizontal: spacing.lg,  // 24
  },
  sectionGap: {
    marginBottom: spacing.xl,       // 32
  },
  cardGap: {
    marginBottom: spacing.base,     // 16
  },
});
```

---

## 6. 모서리와 그림자 (Radius & Elevation)

### 6.1 Radius 규칙

```typescript
const radiusExamples = StyleSheet.create({
  chip:     { borderRadius: radius.sm },    // 8
  button:   { borderRadius: radius.md },    // 14
  card:     { borderRadius: radius.lg },    // 20
  bookCard: { borderRadius: radius.xl },    // 28
  avatar:   { borderRadius: radius.full },  // 9999
});
```

> **규칙**: `borderRadius: 0`은 사용하지 않습니다. 최소 `radius.sm(8)` 이상.

### 6.2 그림자 규칙

```typescript
const cardStyle = StyleSheet.create({
  card: {
    backgroundColor: colors.neutral[0],
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.neutral[100],
    ...shadows.sm,  // 스프레드로 iOS shadow* + Android elevation 모두 적용
  },
});
```

> **규칙**: `shadowColor`에 `#000000`을 사용하지 않습니다 (다크 모드 제외). 항상 `#3E3225`.

---

## 7. 컴포넌트 스타일 가이드 (Components)

### 7.1 버튼 (Buttons)

```typescript
import { Pressable, Text, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue, useAnimatedStyle, withSpring,
} from 'react-native-reanimated';

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

export function PrimaryButton({ label, onPress }: { label: string; onPress: () => void }) {
  const scale = useSharedValue(1);
  const animStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  return (
    <AnimatedPressable
      style={[btnStyles.primary, animStyle]}
      onPressIn={() => { scale.value = withSpring(0.97, motion.spring.bounce); }}
      onPressOut={() => { scale.value = withSpring(1, motion.spring.bounce); }}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <Text style={btnStyles.primaryLabel}>{label}</Text>
    </AnimatedPressable>
  );
}

const btnStyles = StyleSheet.create({
  // ── Primary CTA ──
  primary: {
    backgroundColor: colors.primary[400],
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48,
    ...shadows.md,
  },
  primaryLabel: {
    fontFamily: 'Pretendard-SemiBold',
    fontSize: typography.size.base,
    color: '#FFFFFF',
  },
  // ── Secondary ──
  secondary: {
    backgroundColor: colors.primary[50],
    borderRadius: radius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderWidth: 1.5,
    borderColor: colors.primary[200],
    alignItems: 'center',
    minHeight: 48,
  },
  secondaryLabel: {
    fontFamily: 'Pretendard-Medium',
    fontSize: typography.size.base,
    color: colors.primary[600],
  },
  // ── Icon Button (원형) ──
  icon: {
    width: 48,
    height: 48,
    borderRadius: radius.full,
    backgroundColor: colors.secondary[50],
    borderWidth: 1.5,
    borderColor: colors.secondary[100],
    alignItems: 'center',
    justifyContent: 'center',
  },
});
```

> **터치 타겟**: 모든 `Pressable`의 `minHeight` ≥ `44`. 필요 시 `hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}`.

### 7.2 카드 (Cards)

```typescript
const cardStyles = StyleSheet.create({
  base: {
    backgroundColor: colors.neutral[0],
    borderRadius: radius.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.neutral[100],
    ...shadows.sm,
  },
  storybook: {
    borderRadius: radius.xl,
    overflow: 'hidden',
    aspectRatio: 3 / 4,
    borderWidth: 3,
    borderColor: colors.neutral[100],
    ...shadows.lg,
  },
});
```

### 7.3 입력 필드 (TextInput)

```typescript
import { useState } from 'react';
import { TextInput, StyleSheet } from 'react-native';

export function StyledInput({ placeholder, ...props }) {
  const [focused, setFocused] = useState(false);

  return (
    <TextInput
      style={[
        inputStyles.base,
        focused && inputStyles.focused,
      ]}
      placeholder={placeholder}
      placeholderTextColor={colors.neutral[400]}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      {...props}
    />
  );
}

const inputStyles = StyleSheet.create({
  base: {
    backgroundColor: colors.neutral[0],
    borderWidth: 1.5,
    borderColor: colors.neutral[200],
    borderRadius: radius.sm,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.base,
    fontFamily: 'Pretendard',
    fontSize: typography.size.base,
    color: colors.neutral[800],
  },
  focused: {
    borderColor: colors.primary[400],
    // ⚠️ RN에는 CSS outline/box-shadow 포커스 링이 없습니다.
    // 시각적 포커스는 borderColor 변경으로 표현합니다.
  },
});
```

### 7.4 태그/칩 (Tags)

```typescript
const tagStyles = StyleSheet.create({
  primary: {
    backgroundColor: colors.primary[50],
    paddingVertical: 3,
    paddingHorizontal: 10,
    borderRadius: radius.sm,
  },
  primaryLabel: {
    fontFamily: 'Pretendard',
    fontSize: typography.size.xs,
    color: colors.primary[600],
  },
});
```

---

## 8. 모션 & 애니메이션 (Motion)

### 8.1 필수 라이브러리

| 라이브러리 | 용도 |
|---|---|
| `react-native-reanimated` | 모든 인터랙션 애니메이션 |
| `react-native-gesture-handler` | 스와이프, 드래그 제스처 |
| `expo-haptics` | 버튼 탭 햅틱 피드백 |

### 8.2 핵심 모션 패턴

```typescript
import Animated, {
  withSpring, withTiming, FadeInDown, Easing,
} from 'react-native-reanimated';
import { motion } from './theme';

// ── 카드 등장 (아래→위 + 페이드) ──
<Animated.View
  entering={FadeInDown.duration(motion.timing.normal).springify().damping(12)}
/>

// ── 동화 페이지 넘김 ──
const pageX = useSharedValue(300);
const pageOpacity = useSharedValue(0);

function enterPage() {
  pageX.value = withTiming(0, {
    duration: motion.timing.slow,
    easing: Easing.bezier(0.65, 0, 0.35, 1),
  });
  pageOpacity.value = withTiming(1, { duration: motion.timing.slow });
}

// ── 버튼 탭 바운스 ──
function onPressIn() {
  scale.value = withSpring(0.95, motion.spring.bounce);
}
function onPressOut() {
  scale.value = withSpring(1, motion.spring.bounce);
}
```

### 8.3 접근성: 모션 축소

```typescript
import { AccessibilityInfo } from 'react-native';

const [reduceMotion, setReduceMotion] = useState(false);

useEffect(() => {
  AccessibilityInfo.isReduceMotionEnabled().then(setReduceMotion);
  const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', setReduceMotion);
  return () => sub.remove();
}, []);

const duration = reduceMotion ? 0 : motion.timing.normal;
```

---

## 9. 아이코노그래피 & 일러스트레이션 (Iconography)

### 9.1 아이콘

| 속성 | 값 |
|---|---|
| 라이브러리 | `lucide-react-native` 또는 `phosphor-react-native` |
| 기본 크기 | `24` (앱 UI), `32` (동화 내비) |
| 선 두께 | `strokeWidth={1.5}` ~ `{2}` |
| 색상 | `colors.neutral[600]` 기본, `colors.primary[400]` 활성 |

```typescript
import { BookOpen } from 'lucide-react-native';

<BookOpen size={24} strokeWidth={1.5} color={colors.neutral[600]} />
```

### 9.2 일러스트레이션 가이드 (AI 삽화용)

| 속성 | 기준 |
|---|---|
| 스타일 | 수채화/크레파스 질감 소프트 일러스트 |
| 외곽선 | 검정 외곽선 없음 — 색면 경계로 형태 구분 |
| 색온도 | 웜톤 중심, 찬색은 보조로만 |
| 캐릭터 | 단순화된 비율, 둥근 형태, 큰 눈, 부드러운 표정 |

---

## 10. 접근성 체크리스트 (Accessibility)

| 항목 | 기준 | RN 구현 |
|---|---|---|
| 색상 대비 | WCAG AA — 본문 `4.5:1` | — |
| 터치 타겟 | 최소 `44×44` | `minHeight: 44` 또는 `hitSlop` |
| 스크린 리더 | 모든 버튼에 라벨 | `accessibilityLabel`, `accessibilityRole` |
| 폰트 스케일 | 시스템 글꼴 크기 존중 | `allowFontScaling={true}` |
| 모션 축소 | 시스템 설정 감지 | `AccessibilityInfo.isReduceMotionEnabled()` |
| 색맹 대응 | 색상만으로 정보 전달 금지 | 아이콘·텍스트 레이블 병행 |

---

## 11. 플랫폼별 주의사항 (Platform Notes)

### 그림자

```typescript
// iOS: shadow* props 동작. Android: elevation만 지원.
// shadows 객체는 둘 다 포함하므로 스프레드 사용.
// Android elevation 색상 커스텀은 API 28+ 필요.
```

### 폰트

```typescript
// ❌ Android에서 깨짐
{ fontFamily: 'Pretendard', fontWeight: '700' }

// ✅ weight별 별도 family
{ fontFamily: 'Pretendard-Bold' }
```

### borderRadius + overflow

```typescript
// ⚠️ Android: borderRadius + overflow:'hidden' 시 자식 elevation 잘림.
// 그림자가 필요한 자식은 overflow:'hidden' 밖으로 분리.
```

---

## 12. Quick Reference — AI 프롬프트용 요약

```
You are building a children's AI storybook app with React Native (Expo). Follow these rules strictly:

PLATFORM: React Native + Expo. Never use HTML, CSS, div, className, or web APIs. Use View, Text, Pressable, StyleSheet, and react-native-reanimated.

COLORS: Warm pastel palette. Primary=#FFA94D (cream orange), Secondary=#A07DE8 (lavender), Tertiary=#6DD4B8 (mint). Background=neutral[50]=#FDF9F5. Text=neutral[800]=#2E2720. Never use pure #000 or #FFF for backgrounds. Shadow color is always '#3E3225', never '#000000' (except dark mode).

TYPOGRAPHY: App UI uses fontFamily 'Pretendard' (weight variants: Pretendard-Medium, Pretendard-SemiBold, Pretendard-Bold). Storybook content uses 'Cafe24Ssurround'. NEVER combine fontFamily with fontWeight on Android — use the weight-specific family name. Min story font size = 22.

SHAPE: All corners rounded. Min borderRadius = 8. Cards = 20. Storybook cards = 28. Buttons = 14. No borderRadius: 0 anywhere.

SHADOWS: Use platform shadow props, not CSS box-shadow. iOS: shadowColor/shadowOffset/shadowOpacity/shadowRadius. Android: elevation. Always include both. shadowColor='#3E3225'.

SPACING: 4px base grid. Screen paddingHorizontal = 24. Card gap = 16. Section gap = 32.

MOTION: Use react-native-reanimated (withSpring, withTiming). Bounce spring: { damping: 12, stiffness: 180 }. Button press: scale to 0.97. Check AccessibilityInfo.isReduceMotionEnabled().

TOUCH: Min touch target = 44x44. Use hitSlop when needed. Add accessibilityLabel to all interactive elements.

TONE: Everything should feel warm, safe, and delightful — like a cozy bedtime story.
```

---

*문서 버전: 2.0 (React Native / Expo) | 최종 수정: 2026-04-07*
