# StoryTale 프론트엔드 전체 재디자인 — 설계 문서

> **날짜**: 2026-04-15
> **범위**: 모바일 프론트엔드 전체 (12개 화면 + 디자인 시스템 + 네비게이션 + 디자인 가이드 재작성)
> **디자인 기반**: `docs/visual-identity-guide-rn.md` v3.1 (Clean Premium & Mascot Integration)

---

## 1. 배경 및 목적

### 문제
- 백엔드는 완성되어 있지만 프론트엔드가 **프로토타입 수준**의 시각적 완성도
- 테마 시스템이 19줄짜리 플랫 컬러 목록 — 가이드의 토큰 체계 미구현
- 공유 컴포넌트 없이 12개 화면에 버튼/카드/입력 스타일이 복붙됨
- 애니메이션 전무 (reanimated 설치됐지만 미사용)
- 네비게이션이 단일 스택이라 Home↔Library 이동 불편
- 동화책 뷰어가 UI 폰트(Pretendard 16px)로 스토리 표시

### 목표
- v3.1 디자인 가이드의 **Clean & Familiar + Focused Delight** 철학을 충실히 구현
- 기존 기능 로직(API 연동, 에러 처리, 접근성)은 100% 보존
- "완성된 앱" 느낌이 나는 시각적 폴리시

---

## 2. 디자인 시스템

### 2.1 테마 토큰 (`src/theme/index.ts` 재작성)

v3.1 가이드의 색상/radius/typography를 그대로 구현하되, 현재 코드에서 사용 중인 실용적 토큰을 보강.

```typescript
// 구현할 토큰 구조
export const colors = {
  primary:   { 50, 100, 300, 400, 500 },  // v3.1 그대로
  secondary: { 50, 300, 400 },
  neutral:   { 0, 50, 100, 200, 300, 800 },
  semantic:  { error: '#E74C3C', success: '#6DD4B8' },
} as const;

export const shadows = {
  softBase:  { shadowRadius: 24, shadowOpacity: 0.04, ... },
  softHover: { shadowRadius: 32, shadowOpacity: 0.08, ... },
  accentGlow: { shadowColor: '#FFA94D', shadowOpacity: 0.3, ... }, // Primary CTA 전용
} as const;

export const radius = { sm: 8, md: 14, lg: 20, xl: 28, full: 9999 };

export const typography = {
  family: { ui: 'Pretendard', story: 'Cafe24Ssurround' },
  size: { xs: 12, sm: 14, base: 16, lg: 18, xl: 22, '2xl': 28, '3xl': 36 },
};

export const spacing = { xs: 4, sm: 8, md: 12, base: 16, lg: 24, xl: 32, '2xl': 48 };

export const motion = {
  springPressIn:  { damping: 15 },              // PremiumButton pressIn (묵직하게 들어감)
  springPressOut: { damping: 10, mass: 1.2 },   // PremiumButton pressOut (부드럽게 복귀)
  timing: { fast: 200, normal: 300, slow: 500 },
};

export const storyViewer = {
  bg: '#FFF9EE',
  text: '#3D3225',
  accent: '#E88D5A',
};
```

**변경 파일**: `packages/mobile/src/theme/index.ts`
**변경 내용**: 현재 19줄 → ~80줄. 기존 `theme.colors.primary` 등을 사용하는 모든 화면도 마이그레이션.

### 2.2 공유 컴포넌트 라이브러리 (`src/components/`)

새로 생성할 컴포넌트 6개:

| 컴포넌트 | 파일 | 역할 | v3.1 근거 |
|----------|------|------|----------|
| `PaperBackground` | `PaperBackground.tsx` | 앱 루트 종이 노이즈 오버레이 (3% opacity) | Section 3.1 |
| `PremiumCreateButton` | `PremiumCreateButton.tsx` | Primary CTA 전용. withSpring 바운스 + 액센트 글로우 | Section 3.3 Focused Delight |
| `SecondaryButton` | `SecondaryButton.tsx` | 보조 버튼. 표준 opacity 전환만 | Focused Delight: secondary는 표준 |
| `Card` | `Card.tsx` | 흰색 배경 + softBase + radius.lg | Section 2.2 Tactile Shadows |
| `StyledInput` | `StyledInput.tsx` | 포커스 시 borderColor 전환 | Clean & Familiar |
| `ScreenLayout` | `ScreenLayout.tsx` | SafeAreaView + padding + PaperBackground | 레이아웃 통합 |

**에셋 필요**: `assets/images/paper-noise-pattern.png` — 128x128px 미세한 노이즈 타일 이미지. 생성 방법: 흰색 배경에 1-2% 밀도의 회색 노이즈를 추가한 PNG. 온라인 노이즈 텍스처 생성기 또는 Figma에서 제작 가능. 없으면 이 컴포넌트를 빈 View로 대체해도 앱 동작에 영향 없음.

### 2.3 마스코트 앵커 패턴

빈 화면(Empty State), 로딩 화면에서 상단 120-160px 공간을 확보하는 레이아웃 패턴:

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

적용 대상: Login, Home(프로필없음), Library(빈상태), Generation(로딩중)

---

## 3. 네비게이션 구조 변경

### 3.1 현재 → 변경

```
현재:
  Stack.Navigator
    ├─ Login
    ├─ Home
    ├─ ProfileForm
    ├─ PurposeSelect
    ├─ DescriptiveInput
    ├─ Preview
    ├─ Generation
    ├─ Viewer
    ├─ Library
    ├─ RecommendPurpose
    ├─ RecommendInput
    └─ RecommendResult

변경:
  Stack.Navigator (Root)
    ├─ Login
    └─ MainTabs (BottomTab.Navigator)
         ├─ HomeTab (Stack.Navigator)
         │    ├─ Home
         │    ├─ PurposeSelect
         │    ├─ DescriptiveInput
         │    ├─ Preview
         │    ├─ Generation
         │    ├─ RecommendPurpose
         │    ├─ RecommendInput
         │    └─ RecommendResult
         ├─ LibraryTab (Stack.Navigator)
         │    ├─ Library
         │    └─ (Viewer는 Root 모달)
         └─ MyPageTab (Stack.Navigator)
              ├─ MyPage (신규)
              └─ ProfileForm
    └─ Viewer (Root Stack, modal presentation, 탭바 숨김)
```

### 3.2 패키지 추가

- `@react-navigation/bottom-tabs` — 바텀 탭
- `lucide-react-native` — 탭 아이콘 (Home, BookOpen, User)

### 3.3 탭바 스타일

```typescript
tabBarStyle: {
  backgroundColor: colors.neutral[0],
  borderTopWidth: 1,
  borderTopColor: colors.neutral[100],
  height: 56 + bottomInset,
  ...shadows.softBase,
}
tabBarActiveTintColor: colors.primary[400]
tabBarInactiveTintColor: colors.neutral[300]
```

### 3.4 MyPage (신규 화면)

마이페이지 탭에 표시되는 새 화면:
- 아이 프로필 요약 카드 (이름, 나이, 성별)
- "프로필 수정" 버튼 → ProfileForm으로 navigate
- 향후: 설정, 로그아웃, 앱 정보

---

## 4. 화면별 상세 설계

### 4.1 LoginScreen

**변경 전**: 제네릭 폼. 앱 이름/브랜딩 없음.
**변경 후**:
- 상단에 StoryTale 텍스트 로고 (Pretendard-Bold 28px, neutral[800])
- mascotAnchor 영역 (120px) — 향후 캐릭터 인사 애니메이션
- 따뜻한 웰컴 메시지 유지
- 폼 영역은 현재와 동일한 기능 로직
- 로그인 버튼: PremiumCreateButton (유일한 스프링 버튼)
- 모드 전환 버튼: 표준 텍스트 버튼

### 4.2 HomeScreen

**변경 전**: 텍스트 + 버튼 3개 세로 나열.
**변경 후**:
```
┌────────────────────────┐
│  안녕, 서준이! 👋        │  ← 인사 헤더 (아이 이름 반영)
│  오늘은 어떤 이야기를    │
│  만들어볼까요?           │
│                        │
│  ┌────────────────────┐│
│  │ ⭐ 이야기의 힘을     ││  ← Card (softBase)
│  │    빌려보세요       ││
│  │  아이에게 딱 맞는    ││
│  │  책을 추천받아보세요 ││
│  └────────────────────┘│
│                        │
│  ┌────────────────────┐│
│  │ ✨ 맞춤 동화 만들기  ││  ← Card (softBase) + PremiumCreateButton 글로우
│  │  우리 아이만의       ││
│  │  특별한 이야기       ││
│  └────────────────────┘│
│                        │
│  최근 이야기             │
│  ┌──────┐┌──────┐      │  ← 가로 스크롤 FlatList
│  │ 📚  ││ 📚  │      │
│  │곰돌이││별나라│      │
│  └──────┘└──────┘      │
├────────┬───────┬───────┤
│  🏠   │  📚  │  👤   │  ← BottomTab
└────────┴───────┴───────┘
```

- **프로필 없음 상태**: mascotAnchor(160px) + contentCard 패턴. "아이를 알려주세요" + 프로필 만들기 CTA
- **최근 이야기 섹션**: `listStories(limit=5)` 호출, 가로 스크롤 미니 카드 (색상 그라데이션 표지)
- **최근 이야기 없음**: 섹션 자체를 숨기거나 "첫 이야기를 만들어볼까요?" 한 줄

### 4.3 PurposeSelectScreen / RecommendPurposeScreen

**변경 전**: 기능적이지만 정적인 카드.
**변경 후**:
- Card 컴포넌트로 교체 (softBase 섀도우)
- 선택 시: borderColor + backgroundColor 즉시 전환 (스프링 없음, Clean & Familiar)
- "다음" 버튼: PremiumCreateButton (이 화면의 유일한 스프링 버튼)

### 4.4 DescriptiveInputScreen / RecommendInputScreen

**변경 전**: 기능적 입력 폼.
**변경 후**:
- StyledInput 컴포넌트 (포커스 시 borderColor 전환)
- 글자수 표시 개선 (프로그레스 바 스타일)
- "다음" 버튼: PremiumCreateButton

### 4.5 PreviewScreen

**변경 전**: 기능적 프리뷰.
**변경 후**:
- 장면 하이라이트를 Card 컴포넌트로 감싸기
- 스타일 선택 칩 (watercolor/pastel_crayon/clean_digital)
- 수정 카운터: 태그 배지 (primary[50] 배경)
- "확정하기": PremiumCreateButton + 액센트 글로우

### 4.6 GenerationScreen

**변경 전**: LayoutAnimation 기반 장면 카드 등장.
**변경 후**:
- 상단 mascotAnchor 영역 (160px) — "이야기가 자라고 있어요 🌱"
- 하단 contentCard 패턴 — 장면 카드 목록
- 진행률: 원형 또는 바 인디케이터 (neutral[200] 트랙 + primary[400] 필)
- 완료된 장면 카드: Card(softBase) + 체크 표시

### 4.7 ViewerScreen (전면 개편)

**변경 전**: Pretendard 16px, 표준 배경, 헤더/탭 노출.
**변경 후**:
- **배경**: storyViewer.bg (#FFF9EE — 오래된 종이)
- **텍스트**: Cafe24Ssurround 22px, storyViewer.text (#3D3225), lineHeight 2.0
- **헤더/탭바**: 숨김 (fullScreenModal presentation)
- **페이지 넘김**: withTiming 슬라이드 (Easing.bezier(0.65, 0, 0.35, 1))
- **페이지 인디케이터**: 도트 형식 (현재 페이지만 primary[400])
- **종료**: "X" 닫기 버튼 (우상단) → 이전 화면으로 복귀
- **삭제**: 닫기 버튼 좌측에 "지우기" 텍스트 버튼 배치 (기존 headerRight 대체)

```
┌────────────────────────┐
│                    [X] │  ← 닫기 버튼
│  ┌────────────────────┐│
│  │                    ││
│  │   🌟 일러스트      ││  ← 4:3 비율
│  │      (4:3)         ││
│  │                    ││
│  └────────────────────┘│
│                        │
│  Cafe24Ssurround 22px  │
│  "곰돌이는 신나는      │
│   숲속에서 눈을         │
│   떴어요..."            │
│                        │
│     · ● · · ·  3/8     │  ← 도트 인디케이터
│   ← 스와이프 →         │
└────────────────────────┘
```

### 4.8 LibraryScreen

**변경 전**: 이모지(📖) 썸네일 카드.
**변경 후**:
- 카드 표지: 이모지 대신 색상 그라데이션 placeholder (스토리 id의 hashCode % N으로 primary/secondary/tertiary 팔레트 중 선택, LinearGradient 또는 단색 배경)
- Card 컴포넌트 (softBase)
- **빈 서재**: mascotAnchor 패턴 + "첫 번째 이야기를 만들어볼까요?" + PremiumCreateButton

### 4.9 RecommendResultScreen

**변경 전**: 기능적 추천 결과.
**변경 후**:
- 감정 키워드: 태그 칩 (secondary[50] 배경 + secondary[400] 텍스트)
- 추천 도서 카드: Card(softBase) + 정보 레이아웃 개선
- "맞춤 동화 만들기" CTA: PremiumCreateButton

### 4.10 MyPageScreen (신규)

프로필 정보 표시 + 관리:
- 아이 이름/나이/성별 정보 카드
- "프로필 수정" → ProfileForm navigate
- 향후: 로그아웃, 설정, 앱 정보

---

## 5. 애니메이션 전략 — Focused Delight

v3.1의 핵심 원칙: **모든 걸 빛나게 하지 않고, Primary CTA 하나에만 집중**

| 요소 | 인터랙션 | 구현 방법 |
|------|---------|----------|
| PremiumCreateButton | 프레스 시 scale 0.96 바운스 | `withSpring(0.96, {damping:15})` / `withSpring(1, {damping:10, mass:1.2})` |
| PremiumCreateButton | 액센트 글로우 | `shadowColor: '#FFA94D', shadowOpacity: 0.3, shadowRadius: 16` |
| SecondaryButton | 프레스 시 opacity 0.7 | 표준 Pressable style callback |
| 카드 선택 | border/bg 색상 전환 | 즉시 전환 (애니메이션 없음) |
| Viewer 페이지 | 슬라이드 전환 | `withTiming(0, {duration:500, easing:bezier})` |
| 로딩 상태 | ActivityIndicator | RN 기본 (mascot 공간만 확보) |

---

## 6. 파일 변경 목록

### 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `src/theme/index.ts` | 전면 재작성 (색상 스케일, shadows, radius, typography, spacing, motion, storyViewer) |
| `src/navigation/AppNavigator.tsx` | Stack → Stack + BottomTab 구조 변경 |
| `src/screens/LoginScreen.tsx` | 브랜딩 + mascotAnchor + 컴포넌트 교체 |
| `src/screens/HomeScreen.tsx` | 카드 대시보드 레이아웃 + 최근 이야기 섹션 |
| `src/screens/ProfileFormScreen.tsx` | Card/StyledInput 컴포넌트 교체 + 섹션 구분 |
| `src/screens/PurposeSelectScreen.tsx` | Card 컴포넌트 + softBase 섀도우 |
| `src/screens/DescriptiveInputScreen.tsx` | StyledInput + 글자수 프로그레스 |
| `src/screens/PreviewScreen.tsx` | Card + 스타일 칩 + PremiumCreateButton |
| `src/screens/GenerationScreen.tsx` | mascotAnchor + 진행률 인디케이터 |
| `src/screens/ViewerScreen.tsx` | 전면 개편 (storyViewer 팔레트, Cafe24 폰트, 풀스크린) |
| `src/screens/LibraryScreen.tsx` | Card + 그라데이션 표지 + 빈상태 mascotAnchor |
| `src/screens/RecommendPurposeScreen.tsx` | PurposeSelect과 동일한 패턴 |
| `src/screens/RecommendInputScreen.tsx` | DescriptiveInput과 동일한 패턴 |
| `src/screens/RecommendResultScreen.tsx` | Card + 태그 칩 + PremiumCreateButton |
| `App.tsx` | PaperBackground 루트 래핑 |
| `docs/visual-identity-guide-rn.md` | 구현 기준으로 확장 재작성 |

### 신규 파일

| 파일 | 내용 |
|------|------|
| `src/components/PaperBackground.tsx` | 종이 노이즈 오버레이 |
| `src/components/PremiumCreateButton.tsx` | Primary CTA (스프링 + 글로우) |
| `src/components/SecondaryButton.tsx` | 보조 버튼 (opacity 전환) |
| `src/components/Card.tsx` | softBase 섀도우 카드 |
| `src/components/StyledInput.tsx` | 포커스 borderColor 전환 |
| `src/components/ScreenLayout.tsx` | SafeAreaView + padding 통합 |
| `src/screens/MyPageScreen.tsx` | 마이페이지 (신규 탭) |
| `src/navigation/MainTabNavigator.tsx` | 바텀 탭 네비게이터 |
| `assets/images/paper-noise-pattern.png` | 종이 텍스처 에셋 |

---

## 7. 검증 방법

1. **Expo Dev Server**: `npx expo start` → 실기기/시뮬레이터에서 전체 플로우 테스트
2. **TypeScript**: `npx tsc --noEmit` — 타입 에러 없음 확인
3. **기능 보존 체크리스트**:
   - [ ] Login → Home 인증 플로우 동작
   - [ ] 프로필 CRUD 동작
   - [ ] PurposeSelect → DescriptiveInput → Preview → Generation → Viewer 전체 플로우
   - [ ] RecommendPurpose → RecommendInput → RecommendResult 플로우
   - [ ] Library 목록/삭제/Viewer 진입 동작
   - [ ] 401 에러 시 Login 강제 이동 동작
   - [ ] BottomTab 3탭 전환 동작
   - [ ] Viewer 풀스크린 모달 + 닫기 동작
4. **시각 검증**:
   - [ ] 모든 카드에 softBase/softHover 그림자 적용
   - [ ] PremiumCreateButton만 스프링 바운스 + 글로우
   - [ ] Viewer에서 Cafe24Ssurround 22px + #FFF9EE 배경
   - [ ] 빈 상태에 mascotAnchor 공간 확보
   - [ ] PaperBackground 노이즈 오버레이 3%

---

## 8. 스코프 제외

- 다크 모드 (MVP 불필요)
- 실제 마스코트 Lottie 애니메이션 (공간만 확보, 에셋은 향후)
- 소셜 로그인 (S27c 별도)
- SSE 실시간 스트리밍 (현재 폴링 유지)
- 실제 일러스트/표지 이미지 (Generation은 placeholder 유지)

---

*스펙 버전: 1.0 | 작성: 2026-04-15*
