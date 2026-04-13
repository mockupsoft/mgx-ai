# -*- coding: utf-8 -*-
"""
MGX-DeepSite Bridge

MGX multi-agent takımını (Mike/Alex/Bob/Charlie) DeepSite chat timeline
formatına bağlayan köprü modül.

Akış:
  1. Kullanıcı promptunu stack'e göre MGX görevine dönüştür.
  2. MGXTeamProvider.run_task_stream() ile ajan mesajlarını yakala.
  3. Her mesajı NDJSON event satırı olarak yield et (frontend chat timeline).
  4. HTML üretilince __HTML_START__ sentinel + ham HTML gönder.
     Çok dosyalı stack'lerde dosyaları file_ready eventleriyle emit et.
  5. HTML bulunamazsa: direkt LLM ile HTML üret (Alex-style), web_team fallback.

NDJSON formatı:
  {"type":"task_created","task":"...","ts":...}
  {"type":"agent_start","agent":"Mike","role":"Team Leader","ts":...}
  {"type":"step","agent":"Alex","action":"write_file","label":"index.html"}
  {"type":"file_ready","path":"routes/web.php","content":"..."}
  {"type":"project_rules","rules":"..."}
  {"type":"html_ready","char_count":14200}
  {"type":"done"}
  __HTML_START__
  <!DOCTYPE html>...
"""

from __future__ import annotations

import json
import logging
import os
import re
import time as _time
from typing import AsyncIterator, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Skill / rule loader
# ---------------------------------------------------------------------------

def _load_skill(name: str, max_chars: int = 3000) -> str:
    """Skills dizininden markdown dosyasını yükler. Bulunamazsa boş string döner."""
    skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    path = os.path.join(skills_dir, name)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()[:max_chars]
    except FileNotFoundError:
        logger.debug("Skill file not found: %s", path)
        return ""
    except Exception as exc:
        logger.warning("Could not load skill %s: %s", name, exc)
        return ""


def _load_rule(path_parts: list[str], max_chars: int = 800) -> str:
    """rules/ dizininden kural dosyası yükler."""
    rules_dir = os.path.join(os.path.dirname(__file__), "rules")
    path = os.path.join(rules_dir, *path_parts)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()[:max_chars]
    except FileNotFoundError:
        return ""
    except Exception as exc:
        logger.debug("Could not load rule %s: %s", path, exc)
        return ""


def _build_skill_context(stack_hint: str = "html") -> str:
    """
    Stack'e göre ilgili skill + rule dosyalarını yükler.
    Toplam token bütçesi: max 4000 karakter.
    Öncelik: security > architect skill > stack rules > design
    """
    # Laravel stack için daha geniş bütçe: tam skill dosyası + örnekler yüklenir
    is_laravel = stack_hint.lower() in ("laravel-blade", "laravel", "laravel-react", "flutter-laravel")
    _TOKEN_BUDGET = 8000 if is_laravel else 4000
    sections: list[str] = []
    used = 0

    def _add(label: str, content: str, budget: int) -> None:
        nonlocal used
        if not content or used >= _TOKEN_BUDGET:
            return
        snippet = content[:budget]
        sections.append(f"--- {label} ---\n{snippet}")
        used += len(snippet)

    _add("SECURITY STANDARDS", _load_skill("security-review.md", 800), min(800, _TOKEN_BUDGET - used))

    arch_map = {
        "laravel-blade":   "laravel-blade-architect.md",
        "laravel":         "laravel-blade-architect.md",
        "flutter-laravel": "flutter-mobile-architect.md",
        "flutter":         "flutter-mobile-architect.md",
        "laravel-react":   "laravel-react-architect.md",
        "react":           "laravel-react-architect.md",
    }
    # Laravel için tam skill dosyasını yükle (5000 char) — controller/view/route örnekleri dahil
    arch_budget = 5000 if is_laravel else 1200
    arch_file = arch_map.get(stack_hint.lower(), "")
    if arch_file:
        _add("ARCHITECTURE GUIDE", _load_skill(arch_file, arch_budget), min(arch_budget, _TOKEN_BUDGET - used))

    rule_map = {
        "laravel-blade":   [["php", "laravel.md"], ["postgresql", "best-practices.md"]],
        "laravel":         [["php", "laravel.md"]],
        "flutter-laravel": [["dart", "flutter.md"], ["php", "laravel.md"]],
        "flutter":         [["dart", "flutter.md"]],
        "laravel-react":   [["php", "laravel.md"], ["postgresql", "best-practices.md"]],
    }
    for rule_path in rule_map.get(stack_hint.lower(), []):
        rule_content = _load_rule(rule_path, 600)
        label = rule_path[-1].replace(".md", "").replace("-", " ").upper() + " RULES"
        _add(label, rule_content, min(600, _TOKEN_BUDGET - used))

    _add("COMMON SECURITY RULES", _load_rule(["common", "security.md"], 500), min(500, _TOKEN_BUDGET - used))

    if stack_hint == "html":
        _add("HTML DESIGN QUALITY", _load_skill("html-design.md", 800), min(800, _TOKEN_BUDGET - used))

    # Laravel projeleri için Alex'in tam-stack manifesto'sunu yükle
    if is_laravel:
        _add("ALEX ENGINEERING MANIFESTO", _load_skill("alex-laravel.md", 4000), min(4000, _TOKEN_BUDGET - used))

    _add("PLANNING PROTOCOL", _load_skill("mike-planner.md", 800), min(800, _TOKEN_BUDGET - used))

    return "\n\n".join(sections) if sections else ""


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

HTML_SENTINEL = "__HTML_START__"

# HTML stack için görsel kalite kuralları (vanilla sayfalar için)
_HTML_TASK_PREFIX = (
    "Create a SINGLE complete HTML5 page as a standalone .html file.\n"
    "Requirements:\n"
    "- Use Tailwind CSS via CDN in <head> when useful, but also write custom CSS in <style>.\n"
    "- Embed all CSS in <style> and JavaScript in <script> tags.\n"
    "- Output ONE file named index.html — no React, no build step.\n"
    "- The output must be a valid <!DOCTYPE html> document.\n\n"
    "DESIGN NON-NEGOTIABLES — every page MUST meet ALL of these:\n"
    "1. DISTINCTIVE VISUAL IDENTITY — do NOT produce a generic purple-to-blue gradient on white. "
    "Every page must have a unique aesthetic anchored to the user's content type.\n"
    "2. ATMOSPHERIC BACKGROUND — layered CSS gradients, SVG noise texture, or geometric pattern. "
    "A flat solid color or a simple two-stop gradient alone is insufficient.\n"
    "3. STRONG TYPE HIERARCHY — minimum 3 font-size levels. ALL font sizes MUST use clamp(). "
    "Example: font-size: clamp(2.5rem, 6vw, 5rem). Load a web font from Google Fonts CDN.\n"
    "4. CSS CUSTOM PROPERTIES — define ALL theme values (colors, spacing, font sizes) in :root {}. "
    "No hardcoded hex values repeated in the stylesheet.\n"
    "5. MEANINGFUL ANIMATIONS — Intersection Observer scroll reveals + hover micro-interactions on "
    "every interactive element. prefers-reduced-motion must be respected.\n\n"
    "ANTI-PATTERNS — NEVER produce:\n"
    "- The startup template: white/dark bg, Inter font, generic gradient hero, three feature cards\n"
    "- Flat background with no texture or depth\n"
    "- System fonts without an explicitly loaded web font\n"
    "- Static page with zero animations or interactions\n"
    "- Monotone palette (needs minimum 2 distinct hue families + accent)\n"
    "- font-size: 14px or font-size: 24px (use clamp() always)\n"
    "- Inline style color values (all visual logic in CSS)\n\n"
    "CRITICAL IMAGE RULES:\n"
    "- NEVER use placeholder images, local paths, or broken img tags.\n"
    "- For ALL <img> tags use real Unsplash CDN URLs:\n"
    "  https://images.unsplash.com/photo-{PHOTO_ID}?w={WIDTH}&h={HEIGHT}&fit=crop&auto=format\n"
    "- Match the photo to the actual content. Add descriptive alt text.\n\n"
    "User request: "
)

_CONTEXT_SUFFIX = (
    "\n\nExisting HTML to refine (update/extend it rather than starting from scratch):\n"
)

_ALEX_HTML_SYSTEM = (
    "You are Alex, a senior frontend engineer specializing in VISUALLY STUNNING HTML/CSS/JS.\n"
    "Target quality: Awwwards / Dribbble. You do not produce 'functional' pages. You produce remarkable ones.\n\n"
    "DESIGN NON-NEGOTIABLES:\n"
    "- Atmospheric backgrounds: layered radial gradients + subtle SVG noise or geometric pattern.\n"
    "- Strong type hierarchy: ALL font sizes use clamp(). Load at least one Google Font.\n"
    "- CSS custom properties: define every theme value in :root {}.\n"
    "- Intersection Observer for scroll-triggered reveals.\n"
    "- Hover micro-interactions on every interactive element.\n"
    "- @media (prefers-reduced-motion: reduce) present.\n\n"
    "Use real Unsplash CDN images (never placeholders).\n"
    "OUTPUT: Single <!DOCTYPE html> file only. No markdown fences. Start immediately with <!DOCTYPE html>."
)

_CHARLIE_REVIEW_GATE = (
    "You are Charlie, the Code Quality Reviewer.\n\n"
    "Review ALL generated files against these criteria. Write [PASS] or [FAIL] for each:\n\n"
    "1. SECURITY — No hardcoded secrets, XSS risks, unsafe patterns, missing @csrf on forms.\n"
    "2. CODE_QUALITY — Clean, readable, well-structured code. No TODO placeholders or empty method bodies.\n"
    "3. STACK_COMPLIANCE — Uses the correct stack (technologies, libraries, patterns).\n"
    "4. FUNCTIONALITY — All requested features are implemented and working.\n"
    "5. BUILD_READINESS — The output can be deployed/run without errors.\n"
    "6. COMPLETENESS (Laravel/Flutter projects) — Check ALL of the following:\n"
    "   - routes/web.php (or api.php) exists with Route::resource() for every entity → [PASS/FAIL]\n"
    "   - At least one Controller per entity with all CRUD methods implemented → [PASS/FAIL]\n"
    "   - resources/views/ directory with Blade views for EVERY entity (index/create/edit/show) → [PASS/FAIL]\n"
    "   - resources/views/layouts/app.blade.php with nav links to all entities → [PASS/FAIL]\n"
    "   If ANY COMPLETENESS sub-check fails → COMPLETENESS = [FAIL]\n\n"
    "Hard gates — if ANY of these FAIL, write exactly: CHANGES REQUIRED\n"
    "- SECURITY fail → always CHANGES REQUIRED\n"
    "- STACK_COMPLIANCE fail → always CHANGES REQUIRED\n"
    "- BUILD_READINESS fail → always CHANGES REQUIRED\n"
    "- COMPLETENESS fail (criterion 6) → always CHANGES REQUIRED\n\n"
    "If 5+ PASS (including COMPLETENESS for Laravel) and no hard gate failure → write exactly: APPROVED\n"
    "On CHANGES REQUIRED: list specific, actionable fix instructions for Alex.\n"
    "Be precise — name the exact missing files and what must be added."
)

# Agent adı → rol eşleşmesi
_AGENT_ROLES = {
    "Mike": "Team Leader",
    "Alex": "Engineer",
    "Bob": "Tester",
    "Charlie": "Reviewer",
    "System": "System",
}

# msg_type → StepAction eşleşmesi
_MSG_TYPE_TO_ACTION = {
    "plan": "message",
    "message": "message",
    "status": "message",
    "test": "write_file",
    "review": "review",
    "code": "write_file",
    "error": "message",
}

# Stack type UI → stack hint eşlemesi
_STACK_TYPE_MAP = {
    "html": "html",
    "web": "laravel-blade",
    "mobile": "flutter-laravel",
    "special": "laravel-react",
}


# ---------------------------------------------------------------------------
# Task builder
# ---------------------------------------------------------------------------

def _build_task(
    user_prompt: str,
    context: Optional[str],
    stack_hint: str = "html",
    prompt_history: Optional[List[str]] = None,
    project_rules: Optional[str] = None,
    existing_files: Optional[Dict[str, str]] = None,
) -> str:
    """
    Stack'e göre agent görev metni oluşturur.

    html: HTML görsel kalite kuralları dahil, tek dosya çıktısı
    laravel-blade / flutter-laravel / laravel-react: mimari rehber + çok dosyalı FILE manifest çıktısı
    """
    is_html = (stack_hint == "html")
    skill_ctx = _build_skill_context(stack_hint)

    parts: list[str] = []

    if is_html:
        # HTML stack: görsel kalite odaklı prefix
        parts.append(_HTML_TASK_PREFIX + user_prompt.strip())
    else:
        # Gerçek proje stack'leri: mimari odaklı
        stack_desc = {
            "laravel-blade": "Laravel 11 + Blade + PostgreSQL 16",
            "laravel-react": "Laravel 11 API + React + PostgreSQL 16",
            "flutter-laravel": "Flutter 3 + Laravel 11 API + PostgreSQL 16",
        }.get(stack_hint, stack_hint)

        parts.append(
            f"## STACK: {stack_desc}\n\n"
            f"Generate a COMPLETE, FULLY FUNCTIONAL {stack_desc} project with ALL layers.\n"
            f"Output ALL files using the FILE: manifest format:\n\n"
            f"FILE: path/to/file.ext\n"
            f"[file content]\n\n"
            f"FILE: path/to/another.ext\n"
            f"[file content]\n\n"
            f"## MANDATORY FILE CHECKLIST — you MUST include ALL of these:\n"
            f"- routes/web.php (or api.php) — all CRUD routes for every entity\n"
            f"- app/Http/Controllers/ — one controller per entity with index/show/create/store/edit/update/destroy\n"
            f"- resources/views/ — Blade templates for every page (list, create/edit forms, show detail)\n"
            f"- resources/views/layouts/app.blade.php — shared layout with working nav links\n"
            f"- app/Models/ — Eloquent models with relationships\n"
            f"- database/migrations/ — all table migrations\n"
            f"- database/seeders/ — sample data seeders\n"
            f"- public/index.php — Laravel entry point (if not using artisan serve)\n"
            f"- composer.json — with correct Laravel dependencies\n\n"
            f"CRITICAL: Do NOT stop at migrations/models only. "
            f"A working web app REQUIRES controllers, routes, and views. "
            f"Every menu item in the UI MUST have a working route, controller action, and view.\n\n"
            f"## USER REQUEST\n{user_prompt.strip()}"
        )

    # Skill/mimari context
    if skill_ctx:
        parts.append(f"## QUALITY STANDARDS\n{skill_ctx}")

    # Proje-özel kurallar (önceki oturumlardan)
    if project_rules and project_rules.strip():
        parts.append(f"## PROJECT RULES (from previous sessions)\n{project_rules.strip()}")

    # Önceki promptlar (bağlam)
    if prompt_history:
        recent = prompt_history[-5:]
        history_text = "\n".join(f"  {i+1}. {p.strip()}" for i, p in enumerate(recent))
        parts.append(f"## PREVIOUS REQUESTS (context only)\n{history_text}")

    # Mevcut kod
    if context and context.strip():
        if is_html:
            parts.append(_CONTEXT_SUFFIX + context[:8000])
        else:
            parts.append(f"## EXISTING CODE (refine/extend, do not start from scratch)\n{context[:6000]}")

    # DB'den gelen çok dosyalı proje — yollar ve içerik özeti
    if not is_html and existing_files:
        lines: list[str] = ["## CURRENT PROJECT FILES ON DISK"]
        lines.append(
            "These files already exist in the project. UPDATE them in place when the user request "
            "requires changes; preserve unrelated files. Output full FILE: blocks for any file you change or add.\n"
        )
        for path, content in sorted(existing_files.items())[:60]:
            snippet = (content or "")[:3500]
            lines.append(f"### FILE: {path}\n```\n{snippet}\n```")
        parts.append("\n".join(lines))

    separator = "\n\n" if is_html else "\n\n---\n\n"
    return separator.join(parts)


# ---------------------------------------------------------------------------
# File manifest parser
# ---------------------------------------------------------------------------

def _parse_file_manifest(content: str) -> Dict[str, str]:
    """
    Alex'in FILE manifest çıktısını parse eder.
    'FILE: path/to/file.ext\\n[content]' bloklarını dict'e çevirir.
    """
    files: Dict[str, str] = {}
    pattern = re.compile(
        r"FILE:\s*(\S+)\s*\n([\s\S]*?)(?=\nFILE:|\Z)",
        re.MULTILINE,
    )
    for m in pattern.finditer(content):
        path = m.group(1).strip()
        file_content = m.group(2).strip()
        # Güvenlik: path traversal engelle
        if ".." in path or path.startswith("/"):
            continue
        if path and file_content:
            files[path] = file_content
    return files


def _extract_html_from_content(content: str) -> Optional[str]:
    """Alex'in çıktısından HTML belgesini çıkar."""
    file_pattern = re.compile(
        r"FILE:\s*\S*\.html\s*\n([\s\S]*?)(?=\nFILE:|\Z)",
        re.IGNORECASE,
    )
    m = file_pattern.search(content)
    if m:
        candidate = m.group(1).strip()
        if "<!DOCTYPE" in candidate or "<html" in candidate:
            return candidate

    fence_pattern = re.compile(r"```html\s*\n([\s\S]*?)\n```", re.IGNORECASE)
    m = fence_pattern.search(content)
    if m:
        candidate = m.group(1).strip()
        if "<!DOCTYPE" in candidate or "<html" in candidate:
            return candidate

    doc_match = re.search(r"<!DOCTYPE html>[\s\S]*", content, re.IGNORECASE)
    if doc_match:
        return doc_match.group(0).strip()

    return None


def _check_laravel_completeness(files: Dict[str, str]) -> list[str]:
    """
    Laravel projesinin zorunlu katmanlarını kontrol eder.
    Eksik katmanları liste olarak döndürür; tamamsa boş liste.
    """
    missing: list[str] = []

    has_routes = any(
        p.startswith("routes/web") or p.startswith("routes/api")
        for p in files
    )
    if not has_routes:
        missing.append("routes/ (web.php veya api.php yok)")

    has_controllers = any(
        p.startswith("app/Http/Controllers/") and p.endswith(".php")
        for p in files
    )
    if not has_controllers:
        missing.append("app/Http/Controllers/ (hiç controller yok)")

    has_views = any(p.startswith("resources/views/") for p in files)
    if not has_views:
        missing.append("resources/views/ (hiç Blade view yok)")

    has_layout = any(
        "layouts/app" in p or "layouts/main" in p or "layouts/base" in p
        for p in files
    )
    if not has_layout:
        missing.append("resources/views/layouts/app.blade.php (ana layout yok)")

    return missing


def _extract_project_rules(content: str) -> Optional[str]:
    """
    Mike'ın AnalyzeTask çıktısından PROJE_KURALLARI: bölümünü çıkarır.
    """
    m = re.search(
        r"PROJE_KURALLARI:\s*\n((?:[-*]\s*.+\n?)+)",
        content,
        re.IGNORECASE | re.MULTILINE,
    )
    if m:
        return m.group(1).strip()

    # Alternatif format: PROJECT_RULES:
    m = re.search(
        r"PROJECT_RULES:\s*\n((?:[-*]\s*.+\n?)+)",
        content,
        re.IGNORECASE | re.MULTILINE,
    )
    if m:
        return m.group(1).strip()

    return None


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------

def _event(obj: dict) -> str:
    """Dict'i tek satır NDJSON'a çevir (boşluksuz, \\n ile sonlanan)."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def _ts() -> int:
    return int(_time.time())


def _agent_name(raw: str) -> str:
    """Ham agent string'den temiz isim çıkar."""
    for name in ("Mike", "Alex", "Bob", "Charlie"):
        if name.lower() in raw.lower():
            return name
    return "System"


def _emit_html(html_content: str):
    """HTML sentinel + HTML içeriği yield eden generator döndür."""
    async def _gen():
        yield _event({"type": "html_ready", "char_count": len(html_content)})
        yield _event({"type": "done"})
        yield HTML_SENTINEL + "\n"
        chunk_size = 4096
        for i in range(0, len(html_content), chunk_size):
            yield html_content[i: i + chunk_size]
    return _gen()


# ---------------------------------------------------------------------------
# Ana stream fonksiyonu
# ---------------------------------------------------------------------------

async def stream_mgx_html(
    *,
    user_prompt: str,
    context: Optional[str],
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.65,
    max_tokens: int = 8192,
    prompt_history: Optional[List[str]] = None,
    stack_type: Optional[str] = None,
    project_id: Optional[str] = None,
    project_rules: Optional[str] = None,
    existing_files: Optional[Dict[str, str]] = None,
) -> AsyncIterator[str]:
    """
    MGX takımıyla proje üret; NDJSON event satırları + HTML sentinel olarak yield et.

    stack_type: UI'dan gelen seçim (html/web/mobile/special)
    project_id: DB'de güncellenecek proje ID'si (proje kuralları ve dosyalar için)
    project_rules: Önceki oturumlardan proje-özel kurallar
    """
    yield _event({"type": "task_created", "task": user_prompt[:200], "ts": _ts()})

    try:
        from backend.services.team_provider import get_team_provider
    except Exception as e:
        logger.warning("MGX team provider import failed, falling back: %s", e)
        async for chunk in _direct_llm_stream(
            user_prompt=user_prompt,
            context=context,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_history=prompt_history,
            fallback_reason=f"team_provider import hatası: {e}",
        ):
            yield chunk
        return

    # Stack seçimi: UI → stack hint → compliance guard
    from mgx_agent.stack_specs import infer_stack_from_task, validate_and_correct_stack

    if stack_type and stack_type in _STACK_TYPE_MAP:
        resolved_stack = _STACK_TYPE_MAP[stack_type]
    else:
        resolved_stack = infer_stack_from_task(user_prompt)

    # Compliance guard: yanlış DB/stack → düzelt + uyar
    resolved_stack, compliance_warning = validate_and_correct_stack(resolved_stack, user_prompt)
    if compliance_warning:
        logger.info("Stack compliance correction: %s", compliance_warning)
        for line in compliance_warning.strip().splitlines():
            line = line.strip()
            if line:
                yield _event({"type": "warning", "message": line, "ts": _ts()})

    is_html_stack = (resolved_stack == "html")

    # Görev metni oluştur (hardcoded detection YOK — Mike LLM ile anlasın)
    task = _build_task(
        user_prompt=user_prompt,
        context=context,
        stack_hint=resolved_stack,
        prompt_history=prompt_history,
        project_rules=project_rules,
        existing_files=existing_files,
    )
    task_with_hint = task + f"\n\n[STACK: {resolved_stack}] [RUN:{_ts()}]"

    provider_instance = get_team_provider()
    html_content: Optional[str] = None
    collected_files: Dict[str, str] = {}

    # Ajan adına göre step sayacı
    current_agent: Optional[str] = None
    agent_step_counts: dict[str, int] = {}

    # Mike çıktısından proje kurallarını topla
    mike_output_buffer: list[str] = []
    extracted_rules: Optional[str] = None

    try:
        async for msg in provider_instance.run_task_stream(task_with_hint):
            raw_agent = msg.get("agent", "System")
            agent = _agent_name(raw_agent)
            msg_type = msg.get("type", "message")
            content = msg.get("content", "")

            if not content:
                continue

            # MetaGPT iç serializasyon formatını filtrele
            if "---JSON_START---" in content or "---JSON_END---" in content:
                continue

            # Task prefix'i filtrele
            if content.strip().startswith("Create a SINGLE complete HTML5") or \
               content.strip().startswith("## STACK:") or \
               content.strip().startswith("## USER REQUEST"):
                continue

            # Yeni ajan → agent_start event
            if agent != current_agent:
                current_agent = agent
                agent_step_counts.setdefault(agent, 0)
                yield _event({
                    "type": "agent_start",
                    "agent": agent,
                    "role": _AGENT_ROLES.get(agent, "System"),
                    "ts": _ts(),
                })

            agent_step_counts[agent] = agent_step_counts.get(agent, 0) + 1

            # Mike çıktısını tampon tut (proje kuralları için)
            if agent == "Mike":
                mike_output_buffer.append(content)

            if msg_type == "code":
                if is_html_stack:
                    # HTML stack: HTML çıkart
                    extracted = _extract_html_from_content(content)
                    if not extracted:
                        extracted = _extract_html_from_content(content.replace("\\n", "\n"))
                    if extracted:
                        html_content = extracted
                        yield _event({
                            "type": "step",
                            "agent": agent,
                            "action": "write_file",
                            "label": "index.html",
                            "ts": _ts(),
                        })
                    else:
                        yield _event({
                            "type": "step",
                            "agent": agent,
                            "action": "message",
                            "label": "Kod üretildi (HTML ayrıştırılıyor...)",
                            "ts": _ts(),
                        })
                else:
                    # Gerçek proje stack'i: FILE manifest parse et
                    manifest = _parse_file_manifest(content)
                    if manifest:
                        collected_files.update(manifest)
                        for file_path in manifest:
                            yield _event({
                                "type": "step",
                                "agent": agent,
                                "action": "write_file",
                                "label": file_path,
                                "ts": _ts(),
                            })
                        # Dosyaları file_ready event olarak da yay
                        for file_path, file_content in manifest.items():
                            yield _event({
                                "type": "file_ready",
                                "path": file_path,
                                "content": file_content[:500],  # preview
                                "ts": _ts(),
                            })
                    else:
                        # FILE manifest yoksa HTML dene (fallback)
                        extracted = _extract_html_from_content(content)
                        if extracted:
                            html_content = extracted
                            yield _event({
                                "type": "step",
                                "agent": agent,
                                "action": "write_file",
                                "label": "index.html (fallback)",
                                "ts": _ts(),
                            })

            elif msg_type == "error":
                yield _event({"type": "error", "agent": agent, "message": content[:400]})

            else:
                # plan, status, test, review, message
                action = _MSG_TYPE_TO_ACTION.get(msg_type, "message")
                raw_preview = re.sub(r"```[\s\S]*?```", "[kod bloğu]", content)
                preview = " ".join(raw_preview.split())[:280].strip()
                if not preview:
                    continue
                yield _event({
                    "type": "step",
                    "agent": agent,
                    "action": action,
                    "label": preview,
                    "ts": _ts(),
                })

        # Son agent_end
        if current_agent:
            yield _event({
                "type": "agent_end",
                "agent": current_agent,
                "step_count": agent_step_counts.get(current_agent, 0),
                "summary": "Görev tamamlandı.",
            })

    except Exception as e:
        logger.error("MGX stream error: %s", e, exc_info=True)
        yield _event({"type": "error", "agent": "System", "message": str(e)})

    # Mike çıktısından proje kurallarını çıkar ve yay
    if mike_output_buffer:
        mike_full = "\n".join(mike_output_buffer)
        extracted_rules = _extract_project_rules(mike_full)
        if extracted_rules:
            logger.info("Project rules extracted from Mike's output (%d chars)", len(extracted_rules))
            yield _event({
                "type": "project_rules",
                "rules": extracted_rules,
                "stack": resolved_stack,
                "ts": _ts(),
            })

    # Gerçek proje stack'i: dosyaları DB'ye kaydet
    if not is_html_stack and collected_files and project_id:
        try:
            await _save_project_files(project_id, collected_files, resolved_stack, extracted_rules)
            logger.info("Saved %d files for project %s", len(collected_files), project_id)
            yield _event({
                "type": "step",
                "agent": "System",
                "action": "message",
                "label": f"{len(collected_files)} dosya projeye kaydedildi.",
                "ts": _ts(),
            })
        except Exception as e:
            logger.warning("Could not save project files: %s", e)

    # Post-generation completeness validator (Laravel stacks)
    if not is_html_stack and collected_files:
        is_laravel_stack = resolved_stack.lower() in ("laravel-blade", "laravel", "laravel-react", "flutter-laravel")
        if is_laravel_stack:
            missing_layers = _check_laravel_completeness(collected_files)
            if missing_layers:
                warning_msg = (
                    f"⚠️ KALİTE UYARISI: Proje eksik katmanlara sahip — {', '.join(missing_layers)}. "
                    f"Bu, uygulamanın tarayıcıda çalışmaması anlamına gelir. "
                    f"Alex'in talimatlarını güncelleyin veya yeniden üretin."
                )
                logger.warning("Completeness check failed for project %s: missing %s", project_id, missing_layers)
                yield _event({
                    "type": "step",
                    "agent": "Charlie",
                    "action": "review",
                    "label": warning_msg,
                    "ts": _ts(),
                })
            else:
                yield _event({
                    "type": "step",
                    "agent": "Charlie",
                    "action": "review",
                    "label": "✅ Proje eksiksiz: routes, controllers ve views katmanları mevcut.",
                    "ts": _ts(),
                })

    # HTML çıktı
    if html_content:
        async for chunk in _emit_html(html_content):
            yield chunk
        return

    # Gerçek proje stack'i ve HTML yoksa: basit preview oluştur
    if not is_html_stack and collected_files:
        preview_html = _generate_project_preview(collected_files, resolved_stack, user_prompt)
        async for chunk in _emit_html(preview_html):
            yield chunk
        return

    # HTML üretilemedi — yalnızca HTML stack'te direkt LLM fallback (Laravel vb. için HTML üretme)
    if is_html_stack:
        logger.warning("MGX did not produce output, falling back to direct LLM (html stack)")
        async for chunk in _direct_llm_stream(
            user_prompt=user_prompt,
            context=context,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            prompt_history=prompt_history,
            fallback_reason="MGX takımı çıktı üretemedi",
        ):
            yield chunk
    else:
        logger.warning(
            "MGX did not produce file manifest for stack=%s; skipping HTML fallback",
            resolved_stack,
        )
        yield _event({
            "type": "error",
            "agent": "System",
            "message": (
                f"MGX takımı '{resolved_stack}' için dosya üretemedi. "
                "Lütfen projeyi yeniden oluşturmayı deneyin. "
                "Sorun devam ederse prompt'u daha açık yazın."
            ),
            "ts": _ts(),
        })
        yield _event({"type": "done"})


# ---------------------------------------------------------------------------
# Proje dosya kayıt (DB)
# ---------------------------------------------------------------------------

async def _save_project_files(
    project_id: str,
    files: Dict[str, str],
    stack: str,
    project_rules: Optional[str],
) -> None:
    """Üretilen dosyaları ve proje kurallarını DB'ye kaydeder."""
    try:
        from backend.db.models.entities import DeepSiteProject
        from backend.db.engine import get_session_factory
        from sqlalchemy import update

        file_list = [
            {"path": path, "content": content, "type": _guess_file_type(path)}
            for path, content in files.items()
        ]

        update_data: dict = {
            "files": file_list,
            "stack_hint": stack,
        }
        if project_rules:
            update_data["project_rules"] = {
                "stack": stack,
                "rules_text": project_rules,
            }

        session_factory = await get_session_factory()
        async with session_factory() as session:
            await session.execute(
                update(DeepSiteProject)
                .where(DeepSiteProject.id == project_id)
                .values(**update_data)
            )
            await session.commit()
    except Exception as e:
        logger.warning("_save_project_files failed: %s", e)
        raise


def _guess_file_type(path: str) -> str:
    """Dosya yolundan MIME tipi tahmin et."""
    ext_map = {
        ".php": "text/x-php",
        ".blade.php": "text/x-php",
        ".js": "text/javascript",
        ".ts": "text/typescript",
        ".jsx": "text/jsx",
        ".tsx": "text/tsx",
        ".css": "text/css",
        ".html": "text/html",
        ".json": "application/json",
        ".yaml": "text/yaml",
        ".yml": "text/yaml",
        ".env": "text/plain",
        ".md": "text/markdown",
        ".dart": "text/x-dart",
        ".py": "text/x-python",
        ".sh": "text/x-shellscript",
        ".sql": "text/x-sql",
    }
    path_lower = path.lower()
    for ext, mime in ext_map.items():
        if path_lower.endswith(ext):
            return mime
    return "text/plain"


# ---------------------------------------------------------------------------
# Proje preview HTML üretici
# ---------------------------------------------------------------------------

def _generate_project_preview(
    files: Dict[str, str],
    stack: str,
    user_prompt: str,
) -> str:
    """
    Gerçek proje dosyaları için tarayıcıda gösterilecek dosya gezgini HTML üretir.
    Kullanıcı dosyaları görebilir, kopyalayabilir.
    """
    stack_display = {
        "laravel-blade": "Laravel + Blade + PostgreSQL",
        "laravel-react": "Laravel API + React + PostgreSQL",
        "flutter-laravel": "Flutter + Laravel API + PostgreSQL",
    }.get(stack, stack)

    file_items_html = ""
    for path, content in sorted(files.items()):
        escaped_content = (
            content.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
        file_type = _guess_file_type(path)
        icon = "📄"
        if ".php" in path:
            icon = "🐘"
        elif ".js" in path or ".ts" in path:
            icon = "📦"
        elif ".css" in path:
            icon = "🎨"
        elif ".blade.php" in path:
            icon = "🔧"
        elif ".dart" in path:
            icon = "💙"
        elif "migration" in path.lower():
            icon = "🗄️"
        elif "test" in path.lower():
            icon = "✅"

        file_items_html += f"""
        <div class="file-item" onclick="showFile('{path}')">
            <span class="file-icon">{icon}</span>
            <span class="file-path">{path}</span>
        </div>"""

    file_contents_js = "const files = " + json.dumps(
        {path: content for path, content in files.items()},
        ensure_ascii=False,
    ) + ";"

    return f"""<!DOCTYPE html>
<html lang="tr" data-deepsite-preview="project-files">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Project: {stack_display}</title>
<style>
  :root {{
    --bg: #0f172a;
    --surface: #1e293b;
    --border: #334155;
    --text: #e2e8f0;
    --muted: #94a3b8;
    --accent: #6366f1;
    --green: #10b981;
    --font: 'JetBrains Mono', monospace;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: var(--font); background: var(--bg); color: var(--text); height: 100vh; display: flex; flex-direction: column; }}
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap');
  .header {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 12px 20px;
    display: flex;
    align-items: center;
    gap: 12px;
  }}
  .stack-badge {{
    background: var(--accent);
    color: white;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
  }}
  .header h1 {{ font-size: 14px; color: var(--muted); }}
  .header .file-count {{
    margin-left: auto;
    color: var(--muted);
    font-size: 12px;
  }}
  .layout {{ display: flex; flex: 1; overflow: hidden; }}
  .sidebar {{
    width: 280px;
    background: var(--surface);
    border-right: 1px solid var(--border);
    overflow-y: auto;
    padding: 12px 0;
  }}
  .sidebar-title {{
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted);
    padding: 0 16px 8px;
  }}
  .file-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 16px;
    cursor: pointer;
    transition: background 0.15s;
    font-size: 12px;
  }}
  .file-item:hover {{ background: rgba(99,102,241,0.1); }}
  .file-item.active {{ background: rgba(99,102,241,0.2); color: var(--accent); }}
  .file-icon {{ font-size: 14px; }}
  .file-path {{ color: var(--muted); }}
  .file-item.active .file-path {{ color: var(--text); }}
  .content {{ flex: 1; overflow: auto; padding: 0; }}
  .no-file {{
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--muted);
    font-size: 14px;
    flex-direction: column;
    gap: 12px;
  }}
  .no-file svg {{ opacity: 0.3; }}
  pre {{
    padding: 24px;
    font-size: 13px;
    line-height: 1.6;
    color: var(--text);
    white-space: pre-wrap;
    word-break: break-word;
    min-height: 100%;
  }}
  .info-bar {{
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 6px 16px;
    font-size: 11px;
    color: var(--muted);
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .copy-btn {{
    margin-left: auto;
    background: var(--accent);
    color: white;
    border: none;
    padding: 3px 10px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 11px;
  }}
  .copy-btn:hover {{ opacity: 0.8; }}
</style>
</head>
<body>
<div class="header">
  <span class="stack-badge">{stack_display}</span>
  <h1>{user_prompt[:80]}{"..." if len(user_prompt) > 80 else ""}</h1>
  <span class="file-count">{len(files)} dosya</span>
</div>
<div class="layout">
  <div class="sidebar">
    <div class="sidebar-title">Proje Dosyaları</div>
    {file_items_html}
  </div>
  <div class="content" id="content">
    <div class="no-file">
      <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14,2 14,8 20,8"/>
      </svg>
      <span>Dosya görmek için sol panelden seçin</span>
    </div>
  </div>
</div>
<script>
{file_contents_js}

let currentFile = null;

function showFile(path) {{
  currentFile = path;
  const content = files[path] || '';
  const escaped = content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  document.querySelectorAll('.file-item').forEach(el => el.classList.remove('active'));
  const items = document.querySelectorAll('.file-item');
  items.forEach(el => {{
    if (el.querySelector('.file-path')?.textContent === path) {{
      el.classList.add('active');
    }}
  }});

  document.getElementById('content').innerHTML = `
    <div class="info-bar">
      <span>📄 ${{path}}</span>
      <span>·</span>
      <span>${{content.split('\\n').length}} satır</span>
      <button class="copy-btn" onclick="copyFile()">Kopyala</button>
    </div>
    <pre>${{escaped}}</pre>
  `;
}}

function copyFile() {{
  if (currentFile && files[currentFile]) {{
    navigator.clipboard.writeText(files[currentFile]).then(() => {{
      const btn = document.querySelector('.copy-btn');
      if (btn) {{ btn.textContent = 'Kopyalandı!'; setTimeout(() => {{ btn.textContent = 'Kopyala'; }}, 2000); }}
    }});
  }}
}}

// İlk dosyayı otomatik seç
const firstFile = Object.keys(files)[0];
if (firstFile) showFile(firstFile);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Direkt LLM üretim (Alex-style fallback)
# ---------------------------------------------------------------------------

async def _direct_llm_stream(
    *,
    user_prompt: str,
    context: Optional[str],
    provider: Optional[str],
    model: Optional[str],
    temperature: float,
    max_tokens: int,
    prompt_history: Optional[List[str]] = None,
    fallback_reason: str = "",
) -> AsyncIterator[str]:
    """Direkt LLM ile HTML üret (MGX team olmadan)."""
    yield _event({"type": "agent_start", "agent": "Alex", "role": "Engineer", "ts": _ts()})
    yield _event({
        "type": "step",
        "agent": "Alex",
        "action": "message",
        "label": f"Direkt üretim modu{': ' + fallback_reason if fallback_reason else ''}",
        "ts": _ts(),
    })

    try:
        from backend.services.llm.llm_service import get_llm_service
        llm = get_llm_service()
        task = _build_task(user_prompt, context, "html", prompt_history)

        yield _event({"type": "step", "agent": "Alex", "action": "write_file", "label": "index.html", "ts": _ts()})

        html_chunks: list[str] = []
        async for chunk in llm.stream_generate(
            prompt=task,
            system_prompt=_ALEX_HTML_SYSTEM,
            provider=provider,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            task_type="code_generation",
            required_capability="code",
        ):
            html_chunks.append(chunk)

        raw = "".join(html_chunks)
        html_content = _extract_html_from_content(raw) or raw.strip()

        yield _event({"type": "step", "agent": "Charlie", "action": "review", "label": "HTML kalite kontrolü tamamlandı.", "ts": _ts()})
        yield _event({"type": "agent_end", "agent": "Alex", "step_count": 2, "summary": f"HTML üretildi ({len(html_content)} karakter)."})

        async for chunk in _emit_html(html_content):
            yield chunk

    except Exception as e:
        logger.error("Direct HTML generation failed: %s", e, exc_info=True)
        yield _event({"type": "error", "agent": "Alex", "message": str(e)})

        try:
            from backend.services.deepsite import web_team
            yield _event({"type": "step", "agent": "System", "action": "message", "label": "web_team fallback devreye giriyor...", "ts": _ts()})
            web_chunks: list[str] = []
            async for chunk in web_team.stream_agent_html(
                user_prompt=user_prompt, context=context,
                provider=provider, model=model,
                temperature=temperature, max_tokens=max_tokens,
            ):
                web_chunks.append(chunk)
            raw_web = "".join(web_chunks)
            html_from_web = _extract_html_from_content(raw_web) or raw_web.strip()
            if html_from_web:
                yield _event({"type": "agent_end", "agent": "System", "step_count": 1, "summary": "web_team ile HTML üretildi."})
                async for chunk in _emit_html(html_from_web):
                    yield chunk
        except Exception as e2:
            logger.error("web_team fallback also failed: %s", e2, exc_info=True)
            yield _event({"type": "error", "agent": "System", "message": f"Tüm fallback'ler başarısız: {e2}"})
            yield _event({"type": "done"})
