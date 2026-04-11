/**
 * 아이 프로필 API 함수.
 *
 * 계약: docs/contracts/user-service.ts (ChildProfileService)
 */

import { apiFetch } from "./client";

// ---------------------------------------------------------------------------
// 타입
// ---------------------------------------------------------------------------

export interface ChildProfile {
  id: string;
  name: string;
  age: number;
  gender: "male" | "female";
  comfort_object: string | null;
  friend_name: string | null;
  favorite_animal: string | null;
  character_sheet_url: string | null;
}

export interface CreateProfileInput {
  name: string;
  age: number;
  gender: "male" | "female";
  comfort_object?: string;
  friend_name?: string;
  favorite_animal?: string;
}

export interface UpdateProfileInput {
  name?: string;
  age?: number;
  comfort_object?: string;
  friend_name?: string;
  favorite_animal?: string;
}

interface PhotoUploadResult {
  photo_hash: string;
  exif_stripped: boolean;
}

// ---------------------------------------------------------------------------
// API 함수
// ---------------------------------------------------------------------------

export async function createProfile(input: CreateProfileInput): Promise<ChildProfile> {
  return apiFetch<ChildProfile>("/profiles", {
    method: "POST",
    body: input,
  });
}

export async function listProfiles(): Promise<ChildProfile[]> {
  return apiFetch<ChildProfile[]>("/profiles");
}

export async function getProfile(childId: string): Promise<ChildProfile> {
  return apiFetch<ChildProfile>(`/profiles/${childId}`);
}

export async function updateProfile(
  childId: string,
  input: UpdateProfileInput,
): Promise<ChildProfile> {
  return apiFetch<ChildProfile>(`/profiles/${childId}`, {
    method: "PUT",
    body: input,
  });
}

export async function deleteProfile(childId: string): Promise<void> {
  return apiFetch<void>(`/profiles/${childId}`, {
    method: "DELETE",
  });
}

export async function uploadPhoto(childId: string, photoUri: string): Promise<PhotoUploadResult> {
  const formData = new FormData();
  formData.append("photo", {
    uri: photoUri,
    type: "image/jpeg",
    name: "photo.jpg",
  } as unknown as Blob);

  return apiFetch<PhotoUploadResult>(`/profiles/${childId}/photo`, {
    method: "POST",
    body: formData,
  });
}
