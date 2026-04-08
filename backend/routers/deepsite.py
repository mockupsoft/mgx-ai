# -*- coding: utf-8 -*-
"""
DeepSite Projects Router

Handles CRUD operations for DeepSite projects stored in PostgreSQL.
"""

import json
import logging
from typing import List, Literal, Optional
from uuid import uuid4
import re

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.db.session import get_session
from backend.db.models.entities import DeepSiteProject, User
from backend.routers.auth import get_deepsite_user
from backend.services.llm.llm_service import get_llm_service
from backend.services.llm.provider import ProviderError, AllProvidersFailedError
from backend.services.deepsite.follow_up_patch import apply_search_replace_blocks
from backend.services.deepsite.prompts import FOLLOW_UP_SYSTEM_PROMPT
from backend.services.deepsite import DEEPSITE_CONTEXT_MAX_CHARS, web_team

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deepsite", tags=["deepsite"])

DEEPSITE_SYSTEM_INSTRUCTIONS = """You are DeepSite, an expert web developer AI.
Output a single complete HTML5 document only. Do not wrap the output in markdown code fences.
Use semantic HTML, embed CSS in <style> and JavaScript in <script> when needed.
Make the page responsive, accessible, and visually modern unless the user asks otherwise.
If the user asks for multiple pages, still return one HTML file; you may use simple client-side routing comments in HTML comments."""


# Pydantic models
class Page(BaseModel):
    path: str
    html: str


class File(BaseModel):
    path: str
    content: str
    type: Optional[str] = None


class Commit(BaseModel):
    id: str
    title: str
    message: Optional[str] = None
    timestamp: str
    author: Optional[str] = None


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    pages: List[Page] = Field(default_factory=list)
    files: List[File] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    pages: Optional[List[Page]] = None
    files: Optional[List[File]] = None
    is_active: Optional[bool] = None


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    slug: str
    description: Optional[str]
    pages: List[Page]
    files: List[File]
    commits: List[Commit]
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class SaveRequest(BaseModel):
    pages: List[Page]
    commit_title: Optional[str] = "Manual changes saved"


class AutosaveRequest(BaseModel):
    pages: List[Page]


class GenerateRequest(BaseModel):
    """Request body for AI HTML generation (streaming)."""

    prompt: str = Field(..., min_length=1, max_length=32000)
    context: Optional[str] = Field(
        default=None,
        max_length=DEEPSITE_CONTEXT_MAX_CHARS,
        description="Optional existing HTML or code to refine or extend",
    )
    provider: Optional[str] = Field(default=None, description="Override LLM provider (e.g. openrouter)")
    model: Optional[str] = Field(default=None, description="Override model id")
    temperature: float = Field(default=0.65, ge=0.0, le=2.0)
    max_tokens: int = Field(default=8192, ge=256, le=32768)
    mode: Literal["direct", "agent"] = Field(
        default="direct",
        description="direct: single LLM stream; agent: designer+coder pipeline",
    )


class FollowUpRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt: str = Field(..., min_length=1, max_length=16000)
    html: str = Field(..., min_length=1, max_length=500000)
    previous_prompt: Optional[str] = Field(None, alias="previousPrompt")
    selected_element_html: Optional[str] = Field(None, alias="selectedElementHtml")
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    max_tokens: int = Field(default=8192, ge=256, le=32768)


class RedesignRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    redesign_markdown: Optional[str] = Field(None, alias="redesignMarkdown")
    prompt: Optional[str] = None
    html: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = Field(default=0.65, ge=0.0, le=2.0)
    max_tokens: int = Field(default=8192, ge=256, le=32768)
    mode: Literal["direct", "agent"] = "direct"


def _normalize_model(model: Optional[str]) -> Optional[str]:
    if not model or model.strip().lower() in ("", "default", "gpt-4o-mini"):
        return None
    return model


def _normalize_provider(provider: Optional[str]) -> Optional[str]:
    """Treat UI 'auto' / empty as unset so router or _default_provider_model applies."""
    if not provider or not str(provider).strip():
        return None
    p = str(provider).strip().lower()
    if p in ("auto", "default"):
        return None
    return str(provider).strip()


def _default_provider_model() -> tuple[Optional[str], Optional[str]]:
    """Map settings.llm_default_provider to an explicit provider/model when possible."""
    p = (settings.llm_default_provider or "openrouter").lower().strip()
    if p == "gemini" and settings.google_api_key:
        return "gemini", settings.gemini_model or "gemini-2.0-flash"
    if p == "openrouter" and settings.openrouter_api_key:
        return "openrouter", "nex-agi/deepseek-v3.1-nex-n1:free"
    if p == "openai" and settings.openai_api_key:
        return "openai", "gpt-4-turbo"
    if p == "anthropic" and settings.anthropic_api_key:
        return "anthropic", "claude-3-sonnet"
    if p == "mistral" and settings.mistral_api_key:
        return "mistral", "mistral-large-latest"
    if p == "together" and settings.together_api_key:
        return "together", "mistralai/Mistral-7B-Instruct-v0.2"
    return None, None


# Helper functions
async def generate_slug(name: str, user_id: str, session: AsyncSession) -> str:
    """Generate a unique slug from project name."""
    base_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    slug = f"{base_slug}-{user_id[:8]}"
    
    # Ensure uniqueness
    counter = 1
    original_slug = slug
    while True:
        result = await session.execute(select(DeepSiteProject).where(DeepSiteProject.slug == slug))
        if result.scalar_one_or_none() is None:
            break
        slug = f"{original_slug}-{counter}"
        counter += 1
    
    return slug


# Routes
@router.post("/generate")
async def generate_stream(
    body: GenerateRequest,
    current_user: User = Depends(get_deepsite_user),
):
    """
    Stream AI-generated HTML for DeepSite (Server-Sent Events).

    Each line is `data: {"text":"..."}` JSON chunks; final message includes `"done": true`.
    On error: `data: {"error":"..."}`.
    """
    llm = get_llm_service()

    parts: List[str] = [DEEPSITE_SYSTEM_INSTRUCTIONS, "\n\nUser request:\n", body.prompt]
    if body.context:
        parts.extend(
            ["\n\nExisting HTML to refine (optional):\n", body.context[:DEEPSITE_CONTEXT_MAX_CHARS]]
        )
    full_prompt = "".join(parts)

    provider, model = _normalize_provider(body.provider), _normalize_model(body.model)
    if provider is None and model is None:
        provider, model = _default_provider_model()

    async def event_stream():
        try:
            if body.mode == "agent":
                async for chunk in web_team.stream_agent_html(
                    user_prompt=body.prompt,
                    context=body.context,
                    provider=provider,
                    model=model,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                ):
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
            else:
                async for chunk in llm.stream_generate(
                    prompt=full_prompt,
                    provider=provider,
                    model=model,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                    task_type="code_generation",
                    required_capability="code",
                ):
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except (ProviderError, AllProvidersFailedError) as e:
            logger.warning("DeepSite generate provider error: %s", e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        except Exception as e:
            logger.exception("DeepSite generate failed")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.put("/follow-up")
async def follow_up_patch(
    body: FollowUpRequest,
    current_user: User = Depends(get_deepsite_user),
):
    """Apply a diff-style update to HTML using SEARCH/REPLACE blocks (non-streaming)."""
    llm = get_llm_service()
    provider, model = _normalize_provider(body.provider), _normalize_model(body.model)
    if provider is None and model is None:
        provider, model = _default_provider_model()

    user_content_parts: List[str] = []
    if body.previous_prompt:
        user_content_parts.append(
            f"You are modifying the HTML file based on the user's request.\nPrevious context: {body.previous_prompt}"
        )
    else:
        user_content_parts.append("You are modifying the HTML file based on the user's request.")
    sel = body.selected_element_html or ""
    assistant_content = f"The current code is: \n```html\n{body.html}\n```"
    if sel:
        assistant_content += (
            f"\n\nYou have to update ONLY the following element, NOTHING ELSE: \n\n```html\n{sel}\n```"
        )

    messages_prompt = f"{FOLLOW_UP_SYSTEM_PROMPT}\n\nUser message: {body.prompt}\n\n{assistant_content}"

    try:
        resp = await llm.generate(
            prompt=messages_prompt,
            provider=provider,
            model=model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            task_type="code_generation",
            required_capability="code",
        )
        chunk = (resp.content or "").strip()
        if not chunk:
            return {"ok": False, "message": "Model returned empty response"}
        new_html, updated_lines = apply_search_replace_blocks(chunk, body.html)
        return {"ok": True, "html": new_html, "updatedLines": updated_lines}
    except (ProviderError, AllProvidersFailedError) as e:
        logger.warning("DeepSite follow-up error: %s", e)
        return {"ok": False, "message": str(e)}
    except Exception as e:
        logger.exception("DeepSite follow-up failed")
        return {"ok": False, "message": str(e)}


@router.post("/redesign")
async def redesign_html(
    body: RedesignRequest,
    current_user: User = Depends(get_deepsite_user),
):
    """Rebuild HTML from markdown description or prompt (non-streaming)."""
    llm = get_llm_service()
    provider, model = _normalize_provider(body.provider), _normalize_model(body.model)
    if provider is None and model is None:
        provider, model = _default_provider_model()

    if body.redesign_markdown:
        user_part = f"Here is my current design as a markdown:\n\n{body.redesign_markdown}\n\nCreate a new design based on this markdown as a single HTML file."
    elif body.html:
        user_part = f"Here is my current HTML:\n\n```html\n{body.html[:80000]}\n```\n\nCreate a new design based on this HTML."
    else:
        user_part = body.prompt or "Create a beautiful landing page."

    full_prompt = f"{DEEPSITE_SYSTEM_INSTRUCTIONS}\n\n{user_part}"

    try:
        if body.mode == "agent":
            text_parts: List[str] = []
            async for part in web_team.stream_agent_html(
                user_prompt=user_part,
                context=None,
                provider=provider,
                model=model,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            ):
                text_parts.append(part)
            text = "".join(text_parts)
        else:
            resp = await llm.generate(
                prompt=full_prompt,
                provider=provider,
                model=model,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
                task_type="code_generation",
                required_capability="code",
            )
            text = (resp.content or "").strip()
        return {"ok": True, "html": text}
    except (ProviderError, AllProvidersFailedError) as e:
        return {"ok": False, "message": str(e)}
    except Exception as e:
        logger.exception("DeepSite redesign failed")
        return {"ok": False, "message": str(e)}


@router.get("/projects", response_model=List[ProjectResponse])
async def list_projects(
    current_user: User = Depends(get_deepsite_user),
    session: AsyncSession = Depends(get_session)
):
    """Get all projects for the current user."""
    result = await session.execute(
        select(DeepSiteProject)
        .where(DeepSiteProject.user_id == current_user.id)
        .order_by(DeepSiteProject.updated_at.desc())
    )
    projects = result.scalars().all()
    
    return [
        ProjectResponse(
            id=project.id,
            user_id=project.user_id,
            name=project.name,
            slug=project.slug,
            description=project.description,
            pages=project.pages or [],
            files=project.files or [],
            commits=project.commits or [],
            is_active=project.is_active,
            created_at=project.created_at.isoformat(),
            updated_at=project.updated_at.isoformat()
        )
        for project in projects
    ]


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_deepsite_user),
    session: AsyncSession = Depends(get_session)
):
    """Create a new project."""
    slug = await generate_slug(project_data.name, current_user.id, session)
    
    new_project = DeepSiteProject(
        id=str(uuid4()),
        user_id=current_user.id,
        name=project_data.name,
        slug=slug,
        description=project_data.description,
        pages=[page.dict() for page in project_data.pages],
        files=[file.dict() for file in project_data.files],
        commits=[],
        is_active=True
    )
    
    session.add(new_project)
    await session.commit()
    await session.refresh(new_project)
    
    logger.info(f"Created project: {new_project.name} ({new_project.slug}) for user {current_user.id}")
    
    return ProjectResponse(
        id=new_project.id,
        user_id=new_project.user_id,
        name=new_project.name,
        slug=new_project.slug,
        description=new_project.description,
        pages=new_project.pages or [],
        files=new_project.files or [],
        commits=new_project.commits or [],
        is_active=new_project.is_active,
        created_at=new_project.created_at.isoformat(),
        updated_at=new_project.updated_at.isoformat()
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    current_user: User = Depends(get_deepsite_user),
    session: AsyncSession = Depends(get_session)
):
    """Get a specific project by ID."""
    result = await session.execute(
        select(DeepSiteProject).where(
            DeepSiteProject.id == project_id,
            DeepSiteProject.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        pages=project.pages or [],
        files=project.files or [],
        commits=project.commits or [],
        is_active=project.is_active,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat()
    )


@router.put("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    current_user: User = Depends(get_deepsite_user),
    session: AsyncSession = Depends(get_session)
):
    """Update a project."""
    result = await session.execute(
        select(DeepSiteProject).where(
            DeepSiteProject.id == project_id,
            DeepSiteProject.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    if project_data.name is not None:
        project.name = project_data.name
    if project_data.description is not None:
        project.description = project_data.description
    if project_data.pages is not None:
        project.pages = [page.dict() for page in project_data.pages]
    if project_data.files is not None:
        project.files = [file.dict() for file in project_data.files]
    if project_data.is_active is not None:
        project.is_active = project_data.is_active
    
    await session.commit()
    await session.refresh(project)
    
    logger.info(f"Updated project: {project.name} ({project.slug})")
    
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        pages=project.pages or [],
        files=project.files or [],
        commits=project.commits or [],
        is_active=project.is_active,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat()
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: User = Depends(get_deepsite_user),
    session: AsyncSession = Depends(get_session)
):
    """Delete a project."""
    result = await session.execute(
        select(DeepSiteProject).where(
            DeepSiteProject.id == project_id,
            DeepSiteProject.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    await session.delete(project)
    await session.commit()
    
    logger.info(f"Deleted project: {project.name} ({project.slug})")
    
    return None


@router.post("/projects/{project_id}/save", response_model=ProjectResponse)
async def save_project(
    project_id: str,
    save_data: SaveRequest,
    current_user: User = Depends(get_deepsite_user),
    session: AsyncSession = Depends(get_session)
):
    """Manually save project changes with commit."""
    result = await session.execute(
        select(DeepSiteProject).where(
            DeepSiteProject.id == project_id,
            DeepSiteProject.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update pages
    project.pages = [page.dict() for page in save_data.pages]
    
    # Add commit
    from datetime import datetime
    commit = {
        "id": str(uuid4()),
        "title": save_data.commit_title or "Manual changes saved",
        "message": None,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "author": current_user.username
    }
    
    commits = project.commits or []
    commits.append(commit)
    project.commits = commits
    
    await session.commit()
    await session.refresh(project)
    
    logger.info(f"Saved project: {project.name} ({project.slug})")
    
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        pages=project.pages or [],
        files=project.files or [],
        commits=project.commits or [],
        is_active=project.is_active,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat()
    )


@router.post("/projects/{project_id}/autosave", response_model=ProjectResponse)
async def autosave_project(
    project_id: str,
    save_data: AutosaveRequest,
    current_user: User = Depends(get_deepsite_user),
    session: AsyncSession = Depends(get_session)
):
    """Automatically save project changes (no commit created)."""
    result = await session.execute(
        select(DeepSiteProject).where(
            DeepSiteProject.id == project_id,
            DeepSiteProject.user_id == current_user.id
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update pages only (no commit)
    project.pages = [page.dict() for page in save_data.pages]
    
    await session.commit()
    await session.refresh(project)
    
    logger.debug(f"Autosaved project: {project.name} ({project.slug})")
    
    return ProjectResponse(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        pages=project.pages or [],
        files=project.files or [],
        commits=project.commits or [],
        is_active=project.is_active,
        created_at=project.created_at.isoformat(),
        updated_at=project.updated_at.isoformat()
    )


__all__ = ["router"]
