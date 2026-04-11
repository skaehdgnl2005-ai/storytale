# @storytale/mobile

StoryTale의 React Native (Expo) 기반 모바일 앱입니다. (Task S5)

## 주요 구성요소
- **AppNavigator**: React Navigation 기반의 라우팅 구조 (`src/navigation/AppNavigator.tsx`)
- **Theme**: 색상 및 디자인 시스템 (`src/theme/index.ts`)
- **HomeScreen**: 초기 구동을 확인하기 위한 스크린 placeholder (`src/screens/HomeScreen.tsx`)

## 사용 및 실행
```bash
cd packages/mobile
npm install --legacy-peer-deps
npx expo start
```

## 테스트
의존성 문제 및 Babel 충돌을 방지하기 위해 일차적으로 TDD 및 코딩 컨벤션 확인은 타입 체크를 수행합니다.
```bash
npm run typecheck
```
