"""아이 프로필 CRUD API 라우터.

계약: docs/contracts/user-service.ts (ChildProfileService)
엔드포인트: POST /profiles, GET /profiles, GET /profiles/{child_id},
           PUT /profiles/{child_id}, DELETE /profiles/{child_id},
           POST /profiles/{child_id}/photo
"""

import hashlib
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storytale.api.auth_router import CurrentUserDep
from storytale.api.dependencies import get_db
from storytale.db.models import ChildProfile

from .schemas import (
    ChildProfileCreate,
    ChildProfileResponse,
    ChildProfileUpdate,
    PhotoUploadResponse,
)

MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5MB
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png"}

router = APIRouter(prefix="/profiles", tags=["profiles"])


async def _get_own_profile(
    user_id: str, child_id: UUID, db: AsyncSession
) -> ChildProfile:
    """사용자 소유 프로필 조회. 없으면 404."""
    result = await db.execute(
        select(ChildProfile).where(
            ChildProfile.id == child_id,
            ChildProfile.user_id == UUID(user_id),
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="프로필을 찾을 수 없습니다")
    return profile


# ---------------------------------------------------------------------------
# POST /profiles
# ---------------------------------------------------------------------------


@router.post("", response_model=ChildProfileResponse, status_code=201)
async def create_profile(
    body: ChildProfileCreate,
    user_id: CurrentUserDep,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ChildProfileResponse:
    """아이 프로필 생성."""
    profile = ChildProfile(
        user_id=UUID(user_id),
        name=body.name,
        age=body.age,
        gender=body.gender.value,
        comfort_object=body.comfort_object,
        friend_name=body.friend_name,
        favorite_animal=body.favorite_animal,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return _to_response(profile)


# ---------------------------------------------------------------------------
# GET /profiles
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ChildProfileResponse])
async def list_profiles(
    user_id: CurrentUserDep,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[ChildProfileResponse]:
    """로그인 사용자의 아이 프로필 목록."""
    result = await db.execute(
        select(ChildProfile).where(ChildProfile.user_id == UUID(user_id))
    )
    profiles = result.scalars().all()
    return [_to_response(p) for p in profiles]


# ---------------------------------------------------------------------------
# GET /profiles/{child_id}
# ---------------------------------------------------------------------------


@router.get("/{child_id}", response_model=ChildProfileResponse)
async def get_profile(
    child_id: UUID,
    user_id: CurrentUserDep,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ChildProfileResponse:
    """단일 아이 프로필 조회."""
    profile = await _get_own_profile(user_id, child_id, db)
    return _to_response(profile)


# ---------------------------------------------------------------------------
# PUT /profiles/{child_id}
# ---------------------------------------------------------------------------


@router.put("/{child_id}", response_model=ChildProfileResponse)
async def update_profile(
    child_id: UUID,
    body: ChildProfileUpdate,
    user_id: CurrentUserDep,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ChildProfileResponse:
    """아이 프로필 수정. gender는 변경 불가."""
    profile = await _get_own_profile(user_id, child_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    return _to_response(profile)


# ---------------------------------------------------------------------------
# DELETE /profiles/{child_id}
# ---------------------------------------------------------------------------


@router.delete("/{child_id}", status_code=204)
async def delete_profile(
    child_id: UUID,
    user_id: CurrentUserDep,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Response:
    """아이 프로필 삭제."""
    profile = await _get_own_profile(user_id, child_id, db)
    await db.delete(profile)
    await db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# POST /profiles/{child_id}/photo
# ---------------------------------------------------------------------------


@router.post("/{child_id}/photo", response_model=PhotoUploadResponse)
async def upload_photo(
    child_id: UUID,
    photo: UploadFile,
    user_id: CurrentUserDep,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PhotoUploadResponse:
    """아이 사진 업로드. EXIF 제거 후 해시만 저장, 원본은 보관하지 않음."""
    profile = await _get_own_profile(user_id, child_id, db)

    # 형식 검증
    if photo.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="JPEG 또는 PNG만 허용됩니다")

    # 크기 검증
    raw = await photo.read()
    if len(raw) > MAX_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="파일 크기는 5MB 이하여야 합니다")

    # EXIF 제거 + 해시 계산
    cleaned, exif_stripped = _strip_exif(raw)
    photo_hash = hashlib.sha256(cleaned).hexdigest()

    profile.photo_hash = photo_hash
    await db.commit()
    await db.refresh(profile)

    return PhotoUploadResponse(photo_hash=photo_hash, exif_stripped=exif_stripped)


def _strip_exif(data: bytes) -> tuple[bytes, bool]:
    """이미지에서 EXIF 메타데이터를 제거한다. (cleaned_bytes, was_stripped)."""
    img = Image.open(io.BytesIO(data))
    original_format = img.format or "JPEG"

    has_exif = bool(img.info.get("exif"))

    # 새 이미지로 저장하면 EXIF가 제거됨
    buf = io.BytesIO()
    img.save(buf, format=original_format)
    return buf.getvalue(), has_exif


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------


def _to_response(profile: ChildProfile) -> ChildProfileResponse:
    return ChildProfileResponse(
        id=str(profile.id),
        name=profile.name,
        age=profile.age,
        gender=profile.gender,
        comfort_object=profile.comfort_object,
        friend_name=profile.friend_name,
        favorite_animal=profile.favorite_animal,
        character_sheet_url=profile.character_sheet_url,
    )
