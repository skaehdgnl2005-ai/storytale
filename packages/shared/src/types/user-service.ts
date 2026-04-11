// packages/shared/src/types/user-service.ts

import type { ChildProfile, Gender } from "./story-engine";
import type { ImageBuffer } from "./illustration-pipeline";

// ============================================================
// 인증
// ============================================================

type AuthProvider = "google" | "kakao" | "apple";

interface AuthTokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
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
  deleteUser(userId: string): Promise<void>;
}

// ============================================================
// 아이 프로필 관리
// ============================================================

interface CreateChildProfileInput {
  name: string;
  age: number;
  gender: Gender;
  photo?: ImageBuffer;
  comfortObject?: string;
  friendName?: string;
  favoriteAnimal?: string;
}

interface UpdateChildProfileInput {
  name?: string;
  age?: number;
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
  coverImageUrl?: string;
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
