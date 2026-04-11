"""아이 프로필 Pydantic 스키마.

계약: docs/contracts/user-service.ts (CreateChildProfileInput, UpdateChildProfileInput)
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class Gender(StrEnum):
    male = "male"
    female = "female"


class ChildProfileCreate(BaseModel):
    """프로필 생성 요청."""

    name: str = Field(..., min_length=1, max_length=50)
    age: int = Field(..., ge=1, le=12)
    gender: Gender
    comfort_object: str | None = Field(None, max_length=100)
    friend_name: str | None = Field(None, max_length=50)
    favorite_animal: str | None = Field(None, max_length=50)


class ChildProfileUpdate(BaseModel):
    """프로필 수정 요청. gender는 캐릭터 시트 연동으로 변경 불가."""

    name: str | None = Field(None, min_length=1, max_length=50)
    age: int | None = Field(None, ge=1, le=12)
    comfort_object: str | None = None
    friend_name: str | None = None
    favorite_animal: str | None = None


class ChildProfileResponse(BaseModel):
    """프로필 응답."""

    id: str
    name: str
    age: int
    gender: str
    comfort_object: str | None = None
    friend_name: str | None = None
    favorite_animal: str | None = None
    character_sheet_url: str | None = None

    model_config = {"from_attributes": True}


class PhotoUploadResponse(BaseModel):
    """사진 업로드 응답."""

    photo_hash: str
    exif_stripped: bool
