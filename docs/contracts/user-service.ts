// docs/contracts/user-service.ts
// 사용자 서비스 인터페이스 계약

import type { ChildProfile, Gender } from "./story-engine";

// ============================================================
// 인증
// ============================================================

type AuthProvider = "google" | "kakao" | "apple";

interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;               // 초 단위
}

interface AuthService {
  socialLogin(
    provider: AuthProvider,
    authCode: string
  ): Promise<AuthTokens>;

  refreshToken(
    refreshToken: string
  ): Promise<AuthTokens>;

  logout(userId: string): Promise<void>;
}

// ============================================================
// 사용자
// ============================================================

interface User {
  id: string;
  email: string;
  provider: AuthProvider;
  createdAt: string;
}

interface UserService {
  getUser(userId: string): Promise<User>;
  deleteUser(userId: string): Promise<void>;  // 탈퇴
}

// ============================================================
// 아이 프로필 관리
// ============================================================

interface CreateChildProfileInput {
  name: string;
  age: number;
  gender: Gender;
  photo?: Buffer;                  // 캐릭터 생성용 (처리 후 삭제)
  comfortObject?: string;
  friendName?: string;
  favoriteAnimal?: string;
}

interface UpdateChildProfileInput {
  name?: string;
  age?: number;
  // gender는 캐릭터 시트와 연동되므로 생성 후 변경 불가
  comfortObject?: string;
  friendName?: string;
  favoriteAnimal?: string;
}

interface ChildProfileService {
  createProfile(
    userId: string,
    input: CreateChildProfileInput
  ): Promise<ChildProfile>;

  getProfiles(userId: string): Promise<ChildProfile[]>;

  getProfile(
    userId: string,
    childId: string
  ): Promise<ChildProfile>;

  updateProfile(
    userId: string,
    childId: string,
    input: UpdateChildProfileInput
  ): Promise<ChildProfile>;

  deleteProfile(
    userId: string,
    childId: string
  ): Promise<void>;
}

// ============================================================
// 스토리 히스토리 (내 서재)
// ============================================================

interface StoryListItem {
  storyId: string;
  title: string;
  childName: string;
  coverImageUrl?: string;          // 첫 장면 일러스트 축소판
  createdAt: string;
  pageCount: number;
}

interface LibraryService {
  getStories(
    userId: string,
    limit: number,
    offset: number
  ): Promise<{ stories: StoryListItem[]; total: number }>;

  deleteStory(
    userId: string,
    storyId: string
  ): Promise<void>;
}

export type {
  AuthProvider,
  AuthTokens,
  AuthService,
  User,
  UserService,
  CreateChildProfileInput,
  UpdateChildProfileInput,
  ChildProfileService,
  StoryListItem,
  LibraryService,
};
