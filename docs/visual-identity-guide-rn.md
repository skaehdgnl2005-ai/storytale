# AI 맞춤형 동화책 앱 — Visual Brand Identity Guide

> **런타임**: React Native (Expo)
> **목적**: 친숙하고 깔끔한 사용성을 기본으로, 오직 핵심적인 프리미엄 요소(캐릭터, 깊이감, 인터랙션)만을 가미한 실무 디자인 가이드라인
> **대상**: 프론트엔드 개발자, 디자이너, AI 코드 생성 에이전트
>
> ⚠️ 이 문서의 모든 코드 예시는 **React Native StyleSheet** 기준입니다. `CSS`, `className`, `div` 등 웹 전용 문법을 피하세요.

---

## 1. 디자인 철학 (Design Philosophy)

핵심 경험: **"익숙해서 편안한 베이스 위, 시선을 사로잡는 확실한 디테일"**

| 원칙 | 설명 |
|---|---|
| **Clean & Familiar** | 과도한 몽환적 배경(글래스모피즘 등)을 배제하고, 깔끔한 오프화이트 베이스와 탄탄한 구획을 통해 부모가 안심하고 쓸 수 있는 앱 구조를 유지합니다. |
| **Mascot-Driven (캐릭터 중심 레이아웃)** | 곧 추가될 '캐릭터'가 활동할 공간을 항상 비워두고(빈 화면, 헤더, 로딩), UI가 캐릭터와 간섭되지 않도록 앵커(Anchor) 포인트를 통일합니다. |
| **Tactile Depth (정교한 깊이감)** | 종이처럼 깔끔한 질감 위에, 부드럽고 넓은 분산형 그림자(softBase/softHover)를 사용하여 고급스러운 입체감을 줍니다. |
| **Focused Delight** | 모든 걸 빛나게 하지 않고, 오직 '동화책 만들기', '결과 보기' 등 가장 중요한 CTA 버튼 하나에만 바운스 모션 및 하이라이트 인터랙션을 집중합니다. |

---

## 2. 테마 토큰 구조 (Theme Tokens)

모든 디자인 토큰은 `packages/mobile/src/theme/index.ts` 에서 관리합니다.

### 2.1 색상 (Colors)

```typescript
export const colors = {
  primary: {
    50:  '#FFF8F0',
    100: '#FFEFD6',
    300: '#FFC078',
    400: '#FFA94D',  // 메인 액센트
    500: '#F59030',
  },
  secondary: {
    50:  '#F8F5FF',
    300: '#BDA3F5',
    400: '#A07DE8',
  },
  neutral: {
    0:   '#FFFFFF',   // 카드 배경
    50:  '#FDF9F5',   // 앱 기본 배경 (종이 질감 기반)
    100: '#F5EDE3',
    200: '#E8DDD0',
    300: '#D4C5B3',
    800: '#2E2720',   // 본문 텍스트
  },
  semantic: {
    error:   '#E74C3C',
    success: '#6DD4B8',
  },
} as const;
```

| 용도 | 토큰 | 사용 예시 |
|---|---|---|
| 앱 배경 | `colors.neutral[50]` | 전체 화면 기본 배경 |
| 카드 배경 | `colors.neutral[0]` | 콘텐츠 카드, 모달 |
| 주요 CTA | `colors.primary[400]` | PremiumCreateButton |
| 보조 기능 | `colors.secondary[400]` | 태그, 배지 |
| 본문 텍스트 | `colors.neutral[800]` | 일반 본문 |
| 보조 텍스트 | `colors.neutral[300]` | 캡션, 힌트 |
| 비활성 상태 | `colors.neutral[200]` | 비활성 버튼, 구분선 |

### 2.2 프리미엄 섀도우 (Tactile Shadows)

단순한 1단 그림자가 아니라, 크고 부드러운 분산형 프리미엄 그림자를 사용합니다.

```typescript
export const shadows = {
  softBase: Platform.select({
    ios: {
      shadowColor: '#3E3225',
      shadowOffset: { width: 0, height: 8 },
      shadowOpacity: 0.04,
      shadowRadius: 24,
    },
    android: { elevation: 3 },
  })!,
  softHover: Platform.select({
    ios: {
      shadowColor: '#3E3225',
      shadowOffset: { width: 0, height: 16 },
      shadowOpacity: 0.08,
      shadowRadius: 32,
    },
    android: { elevation: 6 },
  })!,
  accentGlow: Platform.select({
    ios: {
      shadowColor: '#FFA94D',
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.3,
      shadowRadius: 16,
    },
    android: { elevation: 4 },
  })!,
} as const;
```

> **규칙**: `shadowColor`에 `#000000`을 사용하지 않습니다. 항상 웜 브라운 `#3E3225`. 단, `accentGlow`만 Primary 색상 `#FFA94D`를 사용합니다.

### 2.3 모서리 (Radius)

```typescript
export const radius = {
  sm:   8,    // 칩, 태그, 인풋 필드
  md:   14,   // 버튼
  lg:   20,   // 카드
  xl:   28,   // 대형 카드, contentCard
  full: 9999, // 아바타, 원형 버튼
} as const;
```

> **규칙**: `borderRadius: 0`은 사용하지 않습니다. 최소 `radius.sm(8)` 이상.

### 2.4 타이포그래피 (Typography)

```typescript
export const typography = {
  family: {
    ui:    'Pretendard',
    story: 'Cafe24Ssurround',
  },
  size: {
    xs:   12,  // 캡션, 타임스탬프
    sm:   14,  // 보조 텍스트
    base: 16,  // 본문 기본
    lg:   18,  // 소제목, PremiumCreateButton 라벨
    xl:   22,  // 섹션 타이틀, 동화책 본문 최소 크기
    '2xl': 28, // 페이지 타이틀, StoryTale 로고
    '3xl': 36, // 히어로 텍스트
  },
} as const;
```

> **Android 폰트 규칙**: `fontWeight`와 커스텀 `fontFamily`를 동시에 쓰면 Android에서 무시됩니다. 반드시 weight별로 별도 fontFamily를 등록하세요 (`Pretendard-Bold` 등).

### 2.5 스페이싱 (4px Grid)

```typescript
export const spacing = {
  xs:   4,
  sm:   8,
  md:   12,
  base: 16,
  lg:   24,
  xl:   32,
  '2xl': 48,
} as const;
```

### 2.6 모션 (Focused Delight)

```typescript
export const motion = {
  springPressIn:  { damping: 15 },              // PremiumButton 누를 때
  springPressOut: { damping: 10, mass: 1.2 },   // PremiumButton 놓을 때
  timing: {
    fast:   200,  // 버튼 상태 전환
    normal: 300,  // 카드 등장
    slow:   500,  // 페이지 전환
  },
} as const;
```

### 2.7 동화책 뷰어 전용 팔레트

```typescript
export const storyViewer = {
  bg:     '#FFF9EE',  // 오래된 종이 느낌
  text:   '#3D3225',  // 따뜻한 다크 브라운
  accent: '#E88D5A',  // 페이지 번호 배지
} as const;
```

---

## 3. 공유 컴포넌트 라이브러리 (Shared Components)

모든 컴포넌트는 `packages/mobile/src/components/`에 위치합니다.

### 3.1 PaperBackground — 종이 텍스처

앱 루트에 한 번만 배치. 미세한 노이즈 이미지 타일(3% opacity)로 종이 질감 제공.

```tsx
<PaperBackground>
  {children}
</PaperBackground>
```

### 3.2 PremiumCreateButton — Primary CTA (Focused Delight)

**이 버튼만** 스프링 바운스 + 액센트 글로우를 가집니다. 나머지 버튼은 표준 전환.

```tsx
<PremiumCreateButton
  label="맞춤 동화 만들기"
  onPress={handleCreate}
  disabled={!isValid}
  loading={submitting}
/>
```

- 프레스 시: `withSpring(0.96, {damping: 15})` — 묵직하게 들어감
- 릴리스 시: `withSpring(1, {damping: 10, mass: 1.2})` — 부드럽게 복귀
- 섀도우: `accentGlow` (shadowColor: #FFA94D, opacity 0.3)

### 3.3 SecondaryButton — 보조 버튼

```tsx
<SecondaryButton label="프로필 수정" onPress={handleEdit} variant="outlined" />
<SecondaryButton label="이미 계정이 있어요" onPress={toggleMode} variant="text" />
```

- `outlined`: 흰 배경 + primary 테두리
- `text`: 투명 배경 + 밑줄 텍스트
- 인터랙션: 표준 opacity 0.7 전환 (스프링 없음)

### 3.4 Card — 프리미엄 카드

```tsx
<Card onPress={handleTap} selected={isSelected}>
  <Text>{content}</Text>
</Card>
```

- 기본: bg neutral[0], radius lg(20), padding lg(24), border neutral[100], softBase 섀도우
- selected: borderColor → primary[400], bg → primary[50]

### 3.5 StyledInput — 입력 필드

```tsx
<StyledInput
  placeholder="어떤 이야기를 담아볼까요?"
  value={text}
  onChangeText={setText}
  multiline
/>
```

- 포커스 시: borderColor → primary[400] (애니메이션 없음, Clean & Familiar)

### 3.6 ScreenLayout — 화면 래퍼

```tsx
<ScreenLayout paddingHorizontal={24}>
  {children}
</ScreenLayout>
```

- SafeAreaView + PaperBackground 통합

---

## 4. 핵심 UI 패턴 (Key Patterns)

### 4.1 마스코트 앵커 (Mascot Integration)

빈 화면(Empty State), 로딩 화면에서 상단 120-160px 공간을 확보합니다.

```
┌────────────────────────┐
│   mascotAnchorTop      │  ← 160px, 향후 Lottie 캐릭터
│   (빈 공간 / 이모지)    │
├────────────────────────┤
│   contentCard          │  ← radius.xl 상단 라운드
│   (카드 영역)           │     + softHover shadow
│                        │
│   본문 / CTA           │
└────────────────────────┘
```

**적용 화면**: Login, Home(프로필없음), Library(빈상태), Generation(로딩중), MyPage(프로필없음)

### 4.2 카드 대시보드 (Home)

```
┌────────────────────────┐
│  안녕, 서준이!           │  ← 인사 헤더
│  오늘은 어떤 이야기를    │
│  만들어볼까요?           │
│                        │
│  ┌────────────────────┐│  ← Card (softBase)
│  │ 이야기의 힘을        ││
│  │ 빌려보세요           ││
│  └────────────────────┘│
│                        │
│  [맞춤 동화 만들기]      │  ← PremiumCreateButton
│                        │
│  최근 이야기             │
│  ┌──────┐┌──────┐      │  ← 가로 스크롤
│  │ 📚  ││ 📚  │      │
│  └──────┘└──────┘      │
├────────┬───────┬───────┤
│  홈   │ 서재  │  마이  │  ← BottomTab
└────────┴───────┴───────┘
```

### 4.3 동화책 뷰어 (Viewer)

```
┌────────────────────────┐
│ 지우기             [X] │  ← 커스텀 헤더 (탭바 숨김)
│  ┌────────────────────┐│
│  │   일러스트 (4:3)    ││  ← storyViewer.bg 배경
│  └────────────────────┘│
│                        │
│  Cafe24Ssurround 22px  │
│  "곰돌이는 신나는      │
│   숲속에서 눈을 떴어요" │
│                        │
│     · ● · · ·  3/8     │  ← 도트 인디케이터
└────────────────────────┘
```

---

## 5. 네비게이션 구조 (Navigation)

```
RootStack
  ├─ Login (headerShown: false)
  ├─ MainTabs (BottomTab)
  │    ├─ HomeTab (Stack)
  │    │    ├─ Home
  │    │    ├─ PurposeSelect
  │    │    ├─ DescriptiveInput
  │    │    ├─ Preview
  │    │    ├─ Generation
  │    │    ├─ RecommendPurpose
  │    │    ├─ RecommendInput
  │    │    └─ RecommendResult
  │    ├─ LibraryTab (Stack)
  │    │    └─ Library
  │    └─ MyPageTab (Stack)
  │         ├─ MyPage
  │         └─ ProfileForm
  └─ Viewer (modal, fullscreen, 탭바 숨김)
```

탭바 스타일: bg neutral[0], borderTop neutral[100], activeTint primary[400], inactiveTint neutral[300]
아이콘: lucide-react-native (Home, BookOpen, User)

---

## 6. Quick Reference — AI 프롬프트용 요약

```
You are building a clean, character-ready children's AI storybook app with React Native (Expo).

VISION: Clean and Familiar baseline, elevated by very specific premium details. Standard approachable UI (solid off-white background, clean white cards).

PLATFORM: React Native + Expo. Never use HTML, CSS, div, className, or web APIs. Use View, Text, Pressable, StyleSheet, and react-native-reanimated.

COLORS: Warm pastel. Primary=#FFA94D, Secondary=#A07DE8. Background=neutral[50]=#FDF9F5. Text=neutral[800]=#2E2720. Never use pure #000 or #FFF for backgrounds.

TYPOGRAPHY: UI uses 'Pretendard' (weight variants: Pretendard-Medium/SemiBold/Bold). Storybook content uses 'Cafe24Ssurround'. NEVER combine fontFamily with fontWeight on Android. Story viewer min font size = 22.

SHADOWS: Use shadows.softBase (radius:24, opacity:0.04) for cards. shadows.accentGlow (color:#FFA94D, opacity:0.3) ONLY for PremiumCreateButton. shadowColor always '#3E3225', never '#000000'.

SHAPE: All corners rounded. Min borderRadius = 8. Cards = 20. Buttons = 14. No borderRadius: 0 anywhere.

SPACING: 4px grid. Screen paddingHorizontal = 24. Card gap = 16. Section gap = 32.

INTERACTION: Limit spring animations to PRIMARY CTA button ONLY (PremiumCreateButton). Secondary buttons use standard opacity transition. Cards use instant color transition on selection.

MASCOT: Reserve 120-160px vertical space in empty states, loading screens, onboarding for future character animation.

NAVIGATION: BottomTab 3 tabs (Home/Library/MyPage). Viewer opens as fullscreen modal (no tabs).

TONE: Everything should feel warm, safe, and delightful — like a cozy bedtime story.
```

---

*문서 버전: 4.0 (Implemented Design System) | 최종 수정: 2026-04-15*
