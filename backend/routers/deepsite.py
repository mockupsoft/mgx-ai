# -*- coding: utf-8 -*-
"""
DeepSite Projects Router

Handles CRUD operations for DeepSite projects stored in PostgreSQL.
"""

import asyncio
import json
import logging
from typing import Dict, List, Literal, Optional
from uuid import uuid4
import re

from fastapi import APIRouter, HTTPException, Depends, Request, Query, status
from fastapi.responses import StreamingResponse, Response
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
If the user asks for multiple pages, still return one HTML file; you may use simple client-side routing comments in HTML comments.

CRITICAL IMAGE RULES — always follow:
- NEVER use placeholder images, local paths, or broken img tags.
- For ALL <img> tags use real Unsplash CDN URLs: https://images.unsplash.com/photo-{PHOTO_ID}?w={WIDTH}&h={HEIGHT}&fit=crop&auto=format
- Choose photo IDs matching the content (fashion, food, tech, nature, etc.).
- Set width and height HTML attributes on every <img> tag.
- Add descriptive alt text to every image.
- Fashion photo IDs: photo-1558618666-fcd25c85cd64 (hero 1600x900), photo-1539109136881-3be0616acf4b (dress 800x1000), photo-1469334031218-e382a71b716b (model 800x1000), photo-1523381210434-271e8be1f52b (summer 800x600), photo-1467043237213-65f2da53396f (winter 800x600), photo-1542291026-7eec264c27ff (shoes 800x600), photo-1515562141207-7a88fb7ce338 (accessories 800x600), photo-1483985988355-763728e1935b (shopping 800x600), photo-1490481651871-ab68de25d43d (lookbook 800x1000), photo-1507003211169-0a1dd7228f2d (square 600x600)."""


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
    chat_history: Optional[dict] = Field(
        None, description="Serialized chat timeline: {items, artifacts}"
    )


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
    chat_history: Optional[dict] = None
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
    """Request body for AI HTML/project generation (streaming)."""

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
        default="agent",
        description="direct: single LLM stream; agent: MGX multi-agent pipeline (Mike+Alex+Bob+Charlie)",
    )
    stack_type: Optional[Literal["html", "web", "mobile", "special"]] = Field(
        default=None,
        description=(
            "Project type hint for golden path selection. "
            "html=vanilla HTML, web=Laravel+Blade+PostgreSQL, "
            "mobile=Flutter+Laravel+PostgreSQL, special=Laravel+React+PostgreSQL"
        ),
    )
    prompt_history: Optional[List[str]] = Field(
        default=None,
        max_length=20,
        description="Previous prompts for this project (cross-run memory context)",
    )
    project_id: Optional[str] = Field(
        default=None,
        description="DeepSite project ID — used to save generated files and project rules",
    )
    existing_files: Optional[Dict[str, str]] = Field(
        default=None,
        description="Mevcut proje dosyaları (path → içerik özeti) — AI bağlamı",
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
    mode: Literal["direct", "agent"] = "agent"


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
    session: AsyncSession = Depends(get_session),
):
    """
    Stream AI-generated HTML/project for DeepSite (Server-Sent Events).

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

    # Projeye özgü kuralları DB'den çek
    project_rules_text: Optional[str] = None
    if body.project_id:
        try:
            from sqlalchemy import select as sa_select
            pr_query = sa_select(DeepSiteProject).where(DeepSiteProject.id == body.project_id)
            pr_result = await session.execute(pr_query)
            pr_project = pr_result.scalar_one_or_none()
            if pr_project and pr_project.project_rules:
                project_rules_text = pr_project.project_rules.get("rules_text")
        except Exception as _pr_err:
            logger.debug("Could not load project rules: %s", _pr_err)

    async def event_stream():
        try:
            if body.mode == "agent":
                try:
                    from backend.services.deepsite.mgx_bridge import stream_mgx_html as _mgx_stream
                    _gen = _mgx_stream(
                        user_prompt=body.prompt,
                        context=body.context,
                        provider=provider,
                        model=model,
                        temperature=body.temperature,
                        max_tokens=body.max_tokens,
                        prompt_history=body.prompt_history,
                        stack_type=body.stack_type,
                        project_id=body.project_id,
                        project_rules=project_rules_text,
                        existing_files=body.existing_files,
                    )
                except Exception as _mgx_import_err:
                    logger.warning(
                        "MGX bridge unavailable, falling back to web_team: %s", _mgx_import_err
                    )
                    _gen = web_team.stream_agent_html(
                        user_prompt=body.prompt,
                        context=body.context,
                        provider=provider,
                        model=model,
                        temperature=body.temperature,
                        max_tokens=body.max_tokens,
                    )
                async for chunk in _gen:
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
    # skip_auth modunda tüm projeler listelenir (geliştirme/demo ortamı)
    if settings.deepsite_skip_auth:
        lq = select(DeepSiteProject).order_by(DeepSiteProject.updated_at.desc())
    else:
        lq = (
            select(DeepSiteProject)
            .where(DeepSiteProject.user_id == current_user.id)
            .order_by(DeepSiteProject.updated_at.desc())
        )
    result = await session.execute(lq)
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
    # skip_auth modunda herhangi bir projeye ID ile erişilebilir (user_id filtresi yok)
    if settings.deepsite_skip_auth:
        q = select(DeepSiteProject).where(DeepSiteProject.id == project_id)
    else:
        q = select(DeepSiteProject).where(
            DeepSiteProject.id == project_id,
            DeepSiteProject.user_id == current_user.id,
        )
    result = await session.execute(q)
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
        chat_history=project.chat_history,
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
    # skip_auth modunda herhangi bir projeye ID ile güncelleme yapılabilir
    if settings.deepsite_skip_auth:
        uq = select(DeepSiteProject).where(DeepSiteProject.id == project_id)
    else:
        uq = select(DeepSiteProject).where(
            DeepSiteProject.id == project_id,
            DeepSiteProject.user_id == current_user.id,
        )
    result = await session.execute(uq)
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
    # chat_history: None → silme (DB'de null yap); dict → üstüne yaz
    if "chat_history" in project_data.model_fields_set:
        project.chat_history = project_data.chat_history
    
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
        chat_history=project.chat_history,
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



def _extract_files_from_pages_html(project) -> dict:
    """
    Dosya gezgini HTML'inden `const files = {...}` JSON bloğunu çıkar.
    Bu, AI üretimi sırasında `files` DB alanı kaydedilmemiş projeleri kurtarır.
    """
    import re as _re
    pages = project.pages or []
    for page in pages:
        html = page.get("html", "") if isinstance(page, dict) else ""
        if 'data-deepsite-preview="project-files"' not in html:
            continue
        # `const files = ` başlangıcını bul, ardından JSON decoder ile parse et
        marker = "const files = "
        idx = html.find(marker)
        if idx == -1:
            continue
        json_start = idx + len(marker)
        try:
            decoder = json.JSONDecoder()
            files_data, _ = decoder.raw_decode(html, json_start)
            if isinstance(files_data, dict) and files_data:
                logger.info("Extracted %d files from pages HTML for project %s", len(files_data), project.id)
                return files_data
        except Exception as _ex:
            logger.debug("JSON decode failed for pages HTML: %s", _ex)
    return {}


def _generate_setup_instructions(project_name: str, stack: str) -> str:
    """Proje dosyaları DB'de yokken gösterilecek kurulum talimatları HTML'i."""
    stack_display = {
        "laravel-blade": "Laravel + Blade + PostgreSQL",
        "laravel-react": "Laravel API + React + PostgreSQL",
        "flutter-laravel": "Flutter + Laravel API + PostgreSQL",
    }.get(stack, stack)

    return f"""<!DOCTYPE html>
<html lang="tr" data-deepsite-preview="project-files">
<head><meta charset="UTF-8"><title>{project_name}</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-slate-900 text-slate-200 p-8 font-mono">
  <div class="max-w-2xl mx-auto">
    <div class="mb-6">
      <span class="bg-indigo-600 text-white text-xs px-3 py-1 rounded-full">{stack_display}</span>
      <h1 class="text-2xl font-bold mt-3">{project_name}</h1>
    </div>
    <div class="bg-amber-900/30 border border-amber-600 rounded-lg p-4 mb-6">
      <p class="text-amber-400 text-sm">⚠ Proje dosyaları henüz veritabanına kaydedilmemiş.</p>
      <p class="text-amber-300 text-xs mt-1">Canlı önizleme için "Web App" seçerek yeniden üretim başlatın.</p>
    </div>
    <h2 class="text-slate-400 text-sm uppercase tracking-widest mb-3">Yerel Kurulum</h2>
    <div class="bg-slate-800 rounded-lg p-4 space-y-2 text-sm">
      <div class="text-green-400"># 1. Bağımlılıkları yükle</div>
      <div class="text-slate-300">composer install</div>
      <div class="text-green-400 mt-2"># 2. Ortam dosyasını hazırla</div>
      <div class="text-slate-300">cp .env.example .env && php artisan key:generate</div>
      <div class="text-green-400 mt-2"># 3. Veritabanını oluştur (PostgreSQL)</div>
      <div class="text-slate-300">php artisan migrate</div>
      <div class="text-green-400 mt-2"># 4. Geliştirme sunucusunu başlat</div>
      <div class="text-slate-300">php artisan serve</div>
    </div>
    <h2 class="text-slate-400 text-sm uppercase tracking-widest mb-3 mt-6">Docker ile Çalıştır</h2>
    <div class="bg-slate-800 rounded-lg p-4 text-sm text-slate-300">docker-compose up -d</div>
  </div>
</body></html>"""


# ---------------------------------------------------------------------------
# Project Runner endpoints (Docker-based live preview)
# ---------------------------------------------------------------------------

# Proje başına lock: paralel POST /run isteklerini serialize et
_run_locks: dict[str, asyncio.Lock] = {}

def _get_run_lock(project_id: str) -> asyncio.Lock:
    if project_id not in _run_locks:
        _run_locks[project_id] = asyncio.Lock()
    return _run_locks[project_id]


@router.post("/projects/{project_id}/run")
async def run_project(
    project_id: str,
    current_user: User = Depends(get_deepsite_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Start a Docker container for the project and return the preview URL.
    Works only for non-HTML stacks (laravel-blade, laravel-react, flutter-laravel).
    """
    if settings.deepsite_skip_auth:
        q = select(DeepSiteProject).where(DeepSiteProject.id == project_id)
    else:
        q = select(DeepSiteProject).where(
            DeepSiteProject.id == project_id,
            DeepSiteProject.user_id == current_user.id,
        )
    result = await session.execute(q)
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    stack = project.stack_hint or "laravel-blade"

    # Convert file list to dict
    files_dict: dict[str, str] = {}
    for f in (project.files or []):
        if isinstance(f, dict) and "path" in f and "content" in f:
            files_dict[f["path"]] = f["content"]

    # Dosyalar DB'de yoksa → pages HTML'inden çıkarmaya çalış
    if not files_dict:
        files_dict = _extract_files_from_pages_html(project)
        if files_dict:
            # Çıkarılan dosyaları DB'ye kaydet
            try:
                from backend.services.deepsite.mgx_bridge import _save_project_files
                await _save_project_files(
                    project_id, files_dict, stack,
                    project.project_rules.get("rules_text") if project.project_rules else None,
                )
                logger.info("Extracted and saved %d files from pages HTML for %s", len(files_dict), project_id)
            except Exception as _ex:
                logger.warning("Could not save extracted files: %s", _ex)
        else:
            return {
                "ok": True,
                "port": None,
                "url": None,
                "message": "Proje dosyaları henüz kaydedilmemiş. Lütfen yeni bir AI üretimi yapın.",
            }

    try:
        from backend.services.deepsite.project_runner import start_project
        # Lock: aynı proje için paralel run isteklerini serialize et
        lock = _get_run_lock(project_id)
        async with lock:
            # Image pull + container başlatma — 5 dakikaya kadar sürebilir
            runner_result = await asyncio.wait_for(
                start_project(project_id, files_dict, stack),
                timeout=300,
            )
        port = runner_result["port"]
        return {
            "ok": True,
            "port": port,
            "url": f"http://localhost:{port}",
            "proxy_url": f"/api/deepsite/projects/{project_id}/proxy/",
            "container": runner_result["container"],
        }
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Container başlatma timeout (5 dakika)")
    except Exception as e:
        logger.error("Project run failed for %s: %s", project_id, e)
        raise HTTPException(status_code=500, detail=f"Container başlatılamadı: {e}")


@router.delete("/projects/{project_id}/run")
async def stop_project_run(
    project_id: str,
    current_user: User = Depends(get_deepsite_user),
    session: AsyncSession = Depends(get_session),
):
    """Stop the Docker container for the project."""
    if not settings.deepsite_skip_auth:
        q = select(DeepSiteProject).where(
            DeepSiteProject.id == project_id,
            DeepSiteProject.user_id == current_user.id,
        )
        result = await session.execute(q)
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")

    try:
        from backend.services.deepsite.project_runner import stop_project
        stopped = await stop_project(project_id)
        return {"ok": True, "stopped": stopped}
    except Exception as e:
        logger.error("Project stop failed for %s: %s", project_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/run/status")
async def get_project_run_status(
    project_id: str,
    current_user: User = Depends(get_deepsite_user),
    session: AsyncSession = Depends(get_session),
):
    """Get the running status and preview URL for the project container."""
    try:
        from backend.services.deepsite.project_runner import get_project_status
        status = await get_project_status(project_id)
        return {"ok": True, **status}
    except Exception as e:
        return {"ok": False, "running": False, "error": str(e)}


@router.get("/projects/{project_id}/screenshot")
async def get_project_preview_screenshot(
    project_id: str,
    full_page: bool = Query(False, description="Tam sayfa uzunluğunda PNG"),
    width: int = Query(1280, ge=320, le=3840, description="Viewport genişliği"),
    height: int = Query(720, ge=240, le=2160, description="Viewport yüksekliği"),
    wait_ms: int = Query(2000, ge=0, le=60_000, description="Yükleme sonrası ek bekleme (ms)"),
    current_user: User = Depends(get_deepsite_user),
    session: AsyncSession = Depends(get_session),
):
    """
    Çalışan önizleme konteynerinin URL'sine Playwright ile gidip PNG ekran görüntüsü döndürür.
    Önizleme çalışmıyorsa veya Playwright kurulu değilse 4xx/5xx.
    """
    if settings.deepsite_skip_auth:
        q = select(DeepSiteProject).where(DeepSiteProject.id == project_id)
    else:
        q = select(DeepSiteProject).where(
            DeepSiteProject.id == project_id,
            DeepSiteProject.user_id == current_user.id,
        )
    result = await session.execute(q)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    from backend.services.deepsite.project_runner import get_project_status
    from backend.services.deepsite.preview_screenshot import (
        capture_url_png,
        describe_playwright_setup,
    )

    st = await get_project_status(project_id)
    if not st.get("running"):
        raise HTTPException(
            status_code=409,
            detail="Önizleme çalışmıyor. Önce POST /api/deepsite/projects/{id}/run ile başlatın.",
        )
    preview_url = st.get("preview_url") or st.get("url")
    if not preview_url or not isinstance(preview_url, str):
        raise HTTPException(status_code=503, detail="preview_url alınamadı")

    try:
        png = await capture_url_png(
            preview_url,
            viewport_width=width,
            viewport_height=height,
            full_page=full_page,
            wait_ms=wait_ms,
        )
    except RuntimeError as e:
        logger.warning("Screenshot runtime (Playwright eksik?): %s", e)
        raise HTTPException(status_code=501, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("Screenshot failed for %s: %s", project_id, e)
        raise HTTPException(
            status_code=503,
            detail=describe_playwright_setup(),
        ) from e

    return Response(content=png, media_type="image/png")


import httpx as _httpx_module


async def _do_proxy(project_id: str, path: str, request: Request) -> Response:
    """Reverse proxy iç implementasyonu."""
    from backend.services.deepsite.project_runner import get_project_status

    status = await get_project_status(project_id)
    if not status.get("running"):
        return _FastAPIResponse(
            content=b"<h1>Container not running</h1>",
            status_code=503,
            media_type="text/html",
        )

    port = status.get("port")
    if not port:
        return _FastAPIResponse(content=b"<h1>No port</h1>", status_code=503, media_type="text/html")

    import os as _os_mod
    dind_host = _os_mod.getenv("DIND_HOST", "dind")
    target_url = f"http://{dind_host}:{port}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    body = await request.body()
    skip_headers = {"host", "content-length", "transfer-encoding"}
    fwd_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in skip_headers
    }

    try:
        async with _httpx_module.AsyncClient(timeout=30) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=fwd_headers,
                content=body,
                follow_redirects=True,
            )

        content_type = resp.headers.get("content-type", "")
        content = resp.content

        if "text/html" in content_type:
            proxy_base = f"/api/deepsite/projects/{project_id}/proxy"
            content_str = content.decode("utf-8", errors="replace")
            for attr in ('href="/', 'src="/', 'action="/'):
                content_str = content_str.replace(attr, f'{attr[:-1]}{proxy_base}/')
            content = content_str.encode("utf-8")

        skip_resp = {"transfer-encoding", "content-encoding", "content-length", "x-frame-options"}
        resp_headers = {
            k: v for k, v in resp.headers.items()
            if k.lower() not in skip_resp
        }
        # Proxy içerik iframe içinde gösterilebilsin
        resp_headers["X-Frame-Options"] = "SAMEORIGIN"

        return Response(
            content=content,
            status_code=resp.status_code,
            headers=resp_headers,
            media_type=content_type.split(";")[0] if content_type else None,
        )
    except _httpx_module.ConnectError:
        return Response(
            content=b"<h1>Container not reachable</h1>",
            status_code=502,
            media_type="text/html",
        )
    except Exception as e:
        logger.error("Proxy error for %s: %s", project_id, e)
        return Response(
            content=f"<h1>Proxy error: {e}</h1>".encode(),
            status_code=502,
            media_type="text/html",
        )


@router.api_route(
    "/projects/{project_id}/proxy",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
@router.api_route(
    "/projects/{project_id}/proxy/",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
async def proxy_project_preview_root(
    project_id: str,
    request: Request,
):
    """Proxy root — boş path için ayrı route."""
    return await _do_proxy(project_id, "", request)


@router.api_route(
    "/projects/{project_id}/proxy/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
)
async def proxy_project_preview(
    project_id: str,
    path: str,
    request: Request,
):
    """
    Reverse proxy: browser'dan gelen istekleri DinD içindeki container'a iletir.
    Bu sayede tarayıcı localhost:8000 üzerinden projeye erişebilir.
    """
    return await _do_proxy(project_id, path, request)




__all__ = ["router"]
