# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.services.auth.rbac import require_permission
from backend.services.feature_flag_service import get_feature_flag_service


router = APIRouter(prefix="/admin/feature-flags", tags=["feature-flags", "admin"])


class FeatureFlagResponse(BaseModel):
    name: str
    enabled: bool
    rollout_percentage: int = Field(ge=0, le=100)
    user_overrides: dict[str, bool]
    workspace_overrides: dict[str, bool]
    created_at: str
    created_by: str
    description: str

    @classmethod
    def from_flag(cls, flag: Any) -> "FeatureFlagResponse":
        return cls(
            name=flag.name,
            enabled=flag.enabled,
            rollout_percentage=flag.rollout_percentage,
            user_overrides=dict(flag.user_overrides),
            workspace_overrides=dict(flag.workspace_overrides),
            created_at=flag.created_at.isoformat(),
            created_by=flag.created_by,
            description=flag.description,
        )


class FeatureFlagUpdateRequest(BaseModel):
    enabled: bool | None = None
    rollout_percentage: int | None = Field(default=None, ge=0, le=100)
    description: str | None = None


class RolloutRequest(BaseModel):
    percentage: int = Field(ge=0, le=100)


class OverrideRequest(BaseModel):
    value: bool


@router.get("", response_model=list[FeatureFlagResponse])
async def list_feature_flags(user_context=Depends(require_permission("settings", "manage"))):
    service = get_feature_flag_service()
    return [FeatureFlagResponse.from_flag(f) for f in service.list_flags()]


@router.patch("/{name}", response_model=FeatureFlagResponse)
async def update_feature_flag(
    name: str,
    payload: FeatureFlagUpdateRequest,
    user_context=Depends(require_permission("settings", "manage")),
):
    service = get_feature_flag_service()

    try:
        updated = service.update_flag(
            name,
            enabled=payload.enabled,
            rollout_percentage=payload.rollout_percentage,
            description=payload.description,
            actor=user_context.get("user_id"),
        )
        return FeatureFlagResponse.from_flag(updated)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{name}/enable", response_model=FeatureFlagResponse)
async def enable_feature_flag(
    name: str,
    user_context=Depends(require_permission("settings", "manage")),
):
    service = get_feature_flag_service()

    try:
        service.enable_flag(name, actor=user_context.get("user_id"))
        flag = service.get_flag(name)
        if flag is None:
            raise KeyError(name)
        return FeatureFlagResponse.from_flag(flag)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Unknown feature flag: {name}") from e


@router.post("/{name}/disable", response_model=FeatureFlagResponse)
async def disable_feature_flag(
    name: str,
    user_context=Depends(require_permission("settings", "manage")),
):
    service = get_feature_flag_service()

    try:
        service.disable_flag(name, actor=user_context.get("user_id"))
        flag = service.get_flag(name)
        if flag is None:
            raise KeyError(name)
        return FeatureFlagResponse.from_flag(flag)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Unknown feature flag: {name}") from e


@router.post("/{name}/rollout", response_model=FeatureFlagResponse)
async def set_rollout_percentage(
    name: str,
    payload: RolloutRequest,
    user_context=Depends(require_permission("settings", "manage")),
):
    service = get_feature_flag_service()

    try:
        service.set_rollout_percentage(
            name,
            payload.percentage,
            actor=user_context.get("user_id"),
        )
        flag = service.get_flag(name)
        if flag is None:
            raise KeyError(name)
        return FeatureFlagResponse.from_flag(flag)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Unknown feature flag: {name}") from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{name}/override/{user_id}", response_model=FeatureFlagResponse)
async def override_feature_flag_for_user(
    name: str,
    user_id: str,
    payload: OverrideRequest,
    user_context=Depends(require_permission("settings", "manage")),
):
    service = get_feature_flag_service()

    try:
        service.override_flag(name, user_id, payload.value)
        flag = service.get_flag(name)
        if flag is None:
            raise KeyError(name)
        return FeatureFlagResponse.from_flag(flag)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=f"Unknown feature flag: {name}") from e
