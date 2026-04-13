# -*- coding: utf-8 -*-
"""
DeepSite Project Runner

Gerçek proje dosyaları için Docker tabanlı canlı preview yönetimi.
Docker daemon ile Docker REST API (tcp://dind:2375) üzerinden konuşur.
docker CLI veya docker-py gerekmez — sadece httpx kullanır.

Akış:
  1. Proje dosyaları DB'den alınır.
  2. /tmp/deepsite_projects/{project_id}/ altına yazılır.
  3. Stack'e uygun Docker image ile container başlatılır.
  4. Port Redis'ten tahsis edilir (9100-9999 aralığı).
  5. Frontend preview URL'si döner: http://localhost:{port}
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import pathlib
import re
import tarfile
import time
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Port aralığı
PORT_MIN = int(os.getenv("PROJECT_PREVIEW_PORT_MIN", "9100"))
PORT_MAX = int(os.getenv("PROJECT_PREVIEW_PORT_MAX", "9999"))
PREVIEW_HOST = os.getenv("PROJECT_PREVIEW_HOST", "localhost")

# Docker daemon URL (DinD veya lokal socket)
DOCKER_HOST = os.getenv("DOCKER_HOST", "tcp://dind:2375")
if DOCKER_HOST.startswith("tcp://"):
    _DOCKER_BASE_URL = "http://" + DOCKER_HOST[6:]
else:
    # Unix socket — httpx transport kullan
    _DOCKER_BASE_URL = "http://docker"

_PROJECTS_TMP = pathlib.Path("/tmp/deepsite_projects")

# Stack → image eşlemesi
_STACK_IMAGES: Dict[str, str] = {
    "laravel-blade": "php:8.3-cli-alpine",
    "laravel-react": "php:8.3-cli-alpine",
    "flutter-laravel": "php:8.3-cli-alpine",
}

# Stack → basit başlatma komutu (PHP built-in server — DB gerektirmez)
_STACK_START_CMD: Dict[str, List[str]] = {
    "laravel-blade": ["php", "-S", "0.0.0.0:8000", "-t", "/app/public"],
    "laravel-react": ["php", "-S", "0.0.0.0:8000", "-t", "/app/public"],
    "flutter-laravel": ["php", "-S", "0.0.0.0:8000", "-t", "/app/public"],
}


# ---------------------------------------------------------------------------
# Docker HTTP client
# ---------------------------------------------------------------------------

def _docker_client() -> httpx.AsyncClient:
    """Docker REST API için httpx client döndürür."""
    if DOCKER_HOST.startswith("unix://"):
        socket_path = DOCKER_HOST[7:]
        transport = httpx.AsyncHTTPTransport(uds=socket_path)
        return httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=30)
    return httpx.AsyncClient(base_url=_DOCKER_BASE_URL, timeout=30)


async def _docker_available() -> bool:
    """Docker daemon'a bağlanılabilir mi?"""
    try:
        async with _docker_client() as client:
            r = await client.get("/version")
            return r.status_code == 200
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Port tahsisi
# ---------------------------------------------------------------------------

async def allocate_port(project_id: str) -> int:
    """Redis veya dosya tabanlı port tahsisi."""
    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        r = await aioredis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)

        existing = await asyncio.wait_for(r.get(f"deepsite:project_port:{project_id}"), timeout=3)
        if existing:
            return int(existing)

        for port in range(PORT_MIN, PORT_MAX + 1):
            acquired = await r.set(f"deepsite:port_used:{port}", project_id, nx=True, ex=86400)
            if acquired:
                await r.set(f"deepsite:project_port:{project_id}", str(port), ex=86400)
                logger.info("Allocated port %d for project %s", port, project_id)
                return port

        raise RuntimeError(f"No free ports in range {PORT_MIN}-{PORT_MAX}")

    except ImportError:
        return await _allocate_port_file(project_id)


async def _allocate_port_file(project_id: str) -> int:
    lock_dir = pathlib.Path("/tmp/deepsite_ports")
    lock_dir.mkdir(parents=True, exist_ok=True)

    proj_lock = lock_dir / f"project_{project_id}.port"
    if proj_lock.exists():
        return int(proj_lock.read_text().strip())

    for port in range(PORT_MIN, PORT_MAX + 1):
        port_lock = lock_dir / f"port_{port}.lock"
        if not port_lock.exists():
            port_lock.write_text(project_id)
            proj_lock.write_text(str(port))
            return port

    raise RuntimeError(f"No free ports in range {PORT_MIN}-{PORT_MAX}")


async def release_port(project_id: str) -> None:
    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        r = await aioredis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
        port_str = await asyncio.wait_for(
            r.get(f"deepsite:project_port:{project_id}"),
            timeout=3,
        )
        if port_str:
            await r.delete(f"deepsite:port_used:{port_str}")
            await r.delete(f"deepsite:project_port:{project_id}")
    except Exception:
        lock_dir = pathlib.Path("/tmp/deepsite_ports")
        proj_lock = lock_dir / f"project_{project_id}.port"
        if proj_lock.exists():
            port = int(proj_lock.read_text().strip())
            (lock_dir / f"port_{port}.lock").unlink(missing_ok=True)
            proj_lock.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Dosya arşivi (tar.gz → Docker container'a yükle)
# ---------------------------------------------------------------------------

def _strip_blade(content: str) -> str:
    """Blade direktiflerini ve PHP bloklarını temizleyerek saf HTML çıkarır."""
    import re as _re
    # PHP blokları kaldır
    content = _re.sub(r"<\?php.*?\?>", "", content, flags=_re.DOTALL)
    content = _re.sub(r"<\?=.*?\?>", "...", content, flags=_re.DOTALL)
    # Blade yorumları
    content = _re.sub(r"\{\{--.*?--\}\}", "", content, flags=_re.DOTALL)
    # Blade {{ expr }} → placeholder değer
    content = _re.sub(r"\{!!\s*.*?\s*!!\}", "Sample Value", content, flags=_re.DOTALL)
    content = _re.sub(r"\{\{\s*.*?\s*\}\}", "Sample Value", content, flags=_re.DOTALL)
    # Blade direktifleri — blok açan/kapayan
    for directive in ["section", "endsection", "yield", "push", "stack", "component",
                      "slot", "endslot", "endcomponent", "extends", "include",
                      "if", "elseif", "else", "endif", "foreach", "endforeach",
                      "for", "endfor", "while", "endwhile", "switch", "case",
                      "break", "endswitch", "auth", "endauth", "guest", "endguest",
                      "isset", "endisset", "empty", "endempty", "can", "endcan",
                      "cannot", "endcannot", "hasSection", "sectionMissing",
                      "php", "endphp", "verbatim", "endverbatim", "csrf",
                      "method", "error", "enderror", "env", "production",
                      "livewire", "once", "endonce", "props", "aware"]:
        content = _re.sub(rf"@{directive}(\s*(\([^)]*\)|\{{[^}}]*\}}))?", "", content)
    content = _re.sub(r"@\w+(\s*(\([^)]*\)|\{[^}]*\}))?", "", content)
    return content.strip()


def _build_preview_index(files: Dict[str, str]) -> str:
    """
    Blade view'larından gerçek HTML render ederek public/index.php üretir.
    Layout + dashboard view birleştirilir, Blade direktifleri temizlenir.
    """
    import re as _re

    view_files = {
        p: c for p, c in files.items()
        if p.startswith("resources/views/") and p.endswith(".blade.php")
    }

    # Layout view'ı bul
    layout_priority = ["layouts/app", "layouts/admin", "layouts/main", "layouts/base"]
    layout_content = ""
    for prio in layout_priority:
        matches = [c for p, c in view_files.items() if prio in p.lower()]
        if matches:
            layout_content = matches[0]
            break

    # Dashboard / ana view'ı bul
    content_priority = ["admin/dashboard", "dashboard", "home", "index", "welcome"]
    chosen_content = ""
    chosen_view_name = ""
    for prio in content_priority:
        for p, c in view_files.items():
            if prio in p.lower():
                chosen_content = c
                chosen_view_name = p
                break
        if chosen_content:
            break
    if not chosen_content and view_files:
        chosen_view_name, chosen_content = next(iter(view_files.items()))

    # @section('content') bloğunu çıkar
    content_body = chosen_content
    m = _re.search(r"@section\(['\"]content['\"]\)(.*?)@(?:endsection|stop)", content_body, _re.DOTALL)
    if m:
        content_body = m.group(1)
    else:
        content_body = chosen_content

    content_html = _strip_blade(content_body)

    # Layout varsa @yield('content') yerine koy
    if layout_content and "@yield('content')" in layout_content or (layout_content and '@yield("content")' in layout_content):
        merged = layout_content.replace("@yield('content')", content_html).replace('@yield("content")', content_html)
        # Diğer yield'ları boşalt
        merged = _re.sub(r"@yield\(['\"][^'\"]+['\"]\)", "", merged)
        final_html = _strip_blade(merged)
    else:
        final_html = content_html

    # Tailwind CDN enjekte et (eğer yoksa)
    if "tailwind" not in final_html.lower() and "<head>" in final_html.lower():
        final_html = final_html.replace(
            "<head>",
            '<head>\n<script src="https://cdn.tailwindcss.com"></script>',
            1,
        )
    elif "tailwind" not in final_html.lower():
        final_html = f'<script src="https://cdn.tailwindcss.com"></script>\n{final_html}'

    # Relative asset URL'lerini kaldır (broken link olmasın)
    final_html = _re.sub(r'(src|href)="/[^"]*\.(css|js|png|jpg|svg|ico)"', r'\1="#"', final_html)

    total_files = len(files)

    # Yeterli HTML yoksa migration dosyalarından entity çıkararak admin dashboard mock-up oluştur
    if len(final_html.strip()) < 200:
        # Migration dosya isimlerinden entity'leri çıkar
        migration_files = [p for p in files if "migrations" in p and p.endswith(".php")]
        entities = []
        for mf in migration_files:
            m = _re.search(r"create_(\w+)_table", mf)
            if m:
                entity = m.group(1).replace("_", " ").title()
                entities.append(entity)

        nav_items = entities[:10] if entities else ["Users", "Dashboard", "Settings"]
        first_entity = nav_items[0] if nav_items else "Records"

        # Her entity için örnek satır verisi üret (JS'e gömülecek)
        import json as _json
        entities_data = {}
        for idx, e in enumerate(nav_items):
            singular = e.rstrip('s') if e.endswith('s') else e
            entities_data[e] = [
                {"id": i+1, "name": f"Sample {singular} {i+1}",
                 "status": "Active" if i % 3 != 2 else "Inactive",
                 "created": f"2024-01-{i+1:02d}"}
                for i in range(8)
            ]
        entities_json = _json.dumps(entities_data, ensure_ascii=False)

        nav_html = "".join(
            f'<li><a href="#" data-entity="{e}" onclick="navigate(event,\'{e}\')" '
            f'class="nav-link flex items-center gap-2 px-3 py-2 rounded-lg text-slate-400 hover:bg-slate-700/60 hover:text-white text-sm transition-colors">'
            f'<span class="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>{e}</a></li>'
            for e in nav_items
        )
        stats_html = "".join(
            f'<div class="bg-slate-800 border border-slate-700/50 rounded-xl p-5 flex flex-col gap-1 cursor-pointer hover:border-indigo-500/50 transition-colors" onclick="navigate(null,\'{e}\')">'
            f'<div class="text-2xl font-bold text-indigo-400">{(idx+1)*24}</div>'
            f'<div class="text-xs text-slate-500">{e}</div></div>'
            for idx, e in enumerate(nav_items[:4])
        )
        final_html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Admin Panel</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex">
  <!-- Sidebar -->
  <aside class="w-56 bg-slate-900 border-r border-slate-800 flex flex-col min-h-screen shrink-0">
    <div class="px-5 py-4 border-b border-slate-800">
      <div class="text-base font-bold text-white">AdminPanel</div>
      <div class="text-xs text-slate-500 mt-0.5">Laravel + PostgreSQL</div>
    </div>
    <nav class="flex-1 px-3 py-4">
      <ul class="space-y-1" id="nav-list">{nav_html}</ul>
    </nav>
    <div class="px-4 py-3 border-t border-slate-800">
      <div class="flex items-center gap-2">
        <div class="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-xs font-bold">A</div>
        <div><div class="text-xs font-medium text-slate-300">Admin User</div><div class="text-xs text-slate-600">super-admin</div></div>
      </div>
    </div>
  </aside>
  <!-- Main -->
  <div class="flex-1 flex flex-col min-h-screen overflow-auto">
    <header class="bg-slate-900 border-b border-slate-800 px-6 py-3 flex items-center justify-between">
      <div class="text-sm font-semibold text-white" id="page-title">Dashboard</div>
      <div class="flex items-center gap-3">
        <span class="flex items-center gap-1.5 text-xs text-emerald-400"><span class="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse"></span>Running</span>
        <span class="text-xs text-slate-500">PHP 8.3 · Container</span>
      </div>
    </header>
    <main class="flex-1 p-6" id="main-content">
      <!-- Dashboard view -->
      <div id="view-dashboard">
        <div class="mb-6">
          <h1 class="text-lg font-bold text-white">Overview</h1>
          <p class="text-sm text-slate-500 mt-0.5">{total_files} files generated · Laravel Blade + PostgreSQL</p>
        </div>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">{stats_html}</div>
      </div>
      <!-- Entity table view (hidden by default) -->
      <div id="view-entity" class="hidden">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h1 class="text-lg font-bold text-white" id="entity-title">{first_entity}</h1>
            <p class="text-sm text-slate-500 mt-0.5">Manage records</p>
          </div>
          <button class="text-sm bg-indigo-600 hover:bg-indigo-500 text-white px-4 py-2 rounded-lg transition-colors font-medium">+ New</button>
        </div>
        <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
          <table class="w-full">
            <thead><tr class="border-b border-slate-800 text-left">
              <th class="px-4 py-3 text-xs text-slate-500 font-medium">#</th>
              <th class="px-4 py-3 text-xs text-slate-500 font-medium">Name</th>
              <th class="px-4 py-3 text-xs text-slate-500 font-medium">Status</th>
              <th class="px-4 py-3 text-xs text-slate-500 font-medium">Created</th>
              <th class="px-4 py-3 text-xs text-slate-500 font-medium">Actions</th>
            </tr></thead>
            <tbody id="entity-tbody"></tbody>
          </table>
        </div>
      </div>
    </main>
  </div>
<script>
var ENTITIES = {entities_json};
var current = null;

function navigate(e, name) {{
  if (e) e.preventDefault();
  current = name;
  document.getElementById('page-title').textContent = name;
  document.getElementById('entity-title').textContent = name;
  document.getElementById('view-dashboard').classList.add('hidden');
  document.getElementById('view-entity').classList.remove('hidden');

  // Aktif nav link
  document.querySelectorAll('.nav-link').forEach(function(a) {{
    a.classList.toggle('bg-slate-700/60', a.dataset.entity === name);
    a.classList.toggle('text-white', a.dataset.entity === name);
    a.classList.toggle('text-slate-400', a.dataset.entity !== name);
  }});

  // Tablo satırları
  var rows = (ENTITIES[name] || []).map(function(r) {{
    var statusCls = r.status === 'Active'
      ? 'bg-emerald-900/60 text-emerald-400'
      : 'bg-red-900/60 text-red-400';
    return '<tr class="border-b border-slate-800 hover:bg-slate-800/40 transition-colors">' +
      '<td class="px-4 py-3 text-sm text-slate-300">' + r.id + '</td>' +
      '<td class="px-4 py-3 text-sm text-slate-300">' + r.name + '</td>' +
      '<td class="px-4 py-3"><span class="text-xs px-2 py-0.5 rounded-full ' + statusCls + '">' + r.status + '</span></td>' +
      '<td class="px-4 py-3 text-xs text-slate-500">' + r.created + '</td>' +
      '<td class="px-4 py-3"><div class="flex gap-2">' +
        '<button class="text-xs text-indigo-400 hover:text-indigo-300">Edit</button>' +
        '<button class="text-xs text-red-400 hover:text-red-300">Delete</button>' +
      '</div></td></tr>';
  }}).join('');
  document.getElementById('entity-tbody').innerHTML = rows || '<tr><td colspan="5" class="px-4 py-8 text-center text-slate-500 text-sm">No records found</td></tr>';
}}
</script>
</body>
</html>"""

    import base64 as _b64
    encoded = _b64.b64encode(final_html.encode("utf-8")).decode("ascii")
    return f"""<?php
header('Content-Type: text/html; charset=utf-8');
echo base64_decode('{encoded}');
"""


def _make_tar_archive(files: Dict[str, str]) -> bytes:
    """Proje dosyalarından in-memory tar arşivi oluştur."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel_path, content in files.items():
            if ".." in rel_path or rel_path.startswith("/"):
                continue
            encoded = content.encode("utf-8")
            info = tarfile.TarInfo(name=rel_path)
            info.size = len(encoded)
            info.mtime = int(time.time())
            tar.addfile(info, io.BytesIO(encoded))
    return buf.getvalue()


def _write_project_files(project_id: str, files: Dict[str, str]) -> pathlib.Path:
    """Proje dosyalarını geçici dizine yaz."""
    project_dir = _PROJECTS_TMP / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    for rel_path, content in files.items():
        if ".." in rel_path or rel_path.startswith("/"):
            continue
        file_path = project_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    # PHP public/index.php yoksa minimal bir tane oluştur
    public_dir = project_dir / "public"
    public_dir.mkdir(exist_ok=True)
    index_php = public_dir / "index.php"
    if not index_php.exists():
        # Basit PHP sayfası — Laravel routes'tan home route'unu simüle et
        project_name = project_dir.name
        index_php.write_text(
            "<?php\n"
            "echo '<!DOCTYPE html><html lang=\"tr\"><head><meta charset=\"UTF-8\">"
            f"<title>Laravel Project</title>"
            "<script src=\"https://cdn.tailwindcss.com\"></script></head>"
            "<body class=\"bg-slate-900 text-white flex items-center justify-center min-h-screen\">"
            "<div class=\"text-center\">"
            "<h1 class=\"text-4xl font-bold mb-4\">Laravel Project Running</h1>"
            "<p class=\"text-slate-400\">PHP built-in server — full Laravel requires database setup</p>"
            "<p class=\"text-slate-500 text-sm mt-4\">Stack: Laravel 11 + Blade + PostgreSQL</p>"
            "</div></body></html>';\n",
            encoding="utf-8",
        )

    return project_dir


def _get_container_name(project_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", project_id)[:20]
    return f"deepsite_proj_{safe}"


# ---------------------------------------------------------------------------
# Container yönetimi (Docker REST API)
# ---------------------------------------------------------------------------

async def _ensure_image(client: httpx.AsyncClient, image: str) -> None:
    """Image yoksa pull et. Streaming API kullanarak bloklamadan bekler."""
    # Image mevcut mu?
    r = await client.get(f"/images/{image}/json")
    if r.status_code == 200:
        return  # Zaten var

    logger.info("Pulling Docker image: %s ...", image)
    # Docker /images/create streaming response döner — aiter_lines ile tüketiriz
    async with httpx.AsyncClient(base_url=_DOCKER_BASE_URL, timeout=600) as pull_client:
        async with pull_client.stream(
            "POST",
            "/images/create",
            params={"fromImage": image},
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise RuntimeError(f"Image pull başarısız ({image}): {body[:200]}")
            # Response satırlarını tüket (bu olmadan pull tamamlanmaz)
            async for line in resp.aiter_lines():
                if "error" in line.lower():
                    logger.warning("Pull warning: %s", line[:120])
    logger.info("Docker image ready: %s", image)


async def start_project(
    project_id: str,
    files: Dict[str, str],
    stack: str,
) -> Dict[str, object]:
    """
    Proje container'ını başlatır.

    Image yoksa önce pull eder (birkaç dakika sürebilir).

    Returns:
        {"port": int, "url": str, "container": str}
    """
    if not await _docker_available():
        raise RuntimeError(
            "Docker daemon'a bağlanılamadı. "
            f"DinD servisi çalışıyor mu? (DOCKER_HOST={DOCKER_HOST})"
        )

    container_name = _get_container_name(project_id)

    # Var olan container'ı durdur
    await stop_project(project_id, _silent=True)

    # Dosyaları geçici dizine yaz
    project_dir = _write_project_files(project_id, files)

    # Port tahsis et
    port = await allocate_port(project_id)

    image = _STACK_IMAGES.get(stack, "php:8.3-cli-alpine")
    cmd = _STACK_START_CMD.get(stack, ["php", "-S", "0.0.0.0:8000"])

    async with _docker_client() as client:
        # Image pull (gerekirse)
        try:
            await _ensure_image(client, image)
        except Exception as pull_err:
            logger.warning("Image pull failed for %s: %s — trying anyway", image, pull_err)

        # Container oluştur — bind mount YOK (DinD host filesystem'i mgx-ai'dan farklı)
        create_payload = {
            "Image": image,
            "Cmd": cmd,
            "WorkingDir": "/app",
            "ExposedPorts": {"8000/tcp": {}},
            "HostConfig": {
                "PortBindings": {
                    "8000/tcp": [{"HostIp": "0.0.0.0", "HostPort": str(port)}]
                },
                # AutoRemove=False — dosyaları kopyalamak için önce durdurmamız gerekebilir
            },
        }

        r = await client.post(
            f"/containers/create?name={container_name}",
            json=create_payload,
        )
        # Conflict: aynı isimli container var → force remove + retry
        if r.status_code == 409:
            logger.info("Container conflict, force removing: %s", container_name)
            await client.delete(f"/containers/{container_name}?force=true")
            r = await client.post(
                f"/containers/create?name={container_name}",
                json=create_payload,
            )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Container oluşturulamadı: {r.text[:300]}")

        container_id = r.json()["Id"]

        # Dosyaları container'a TAR arşivi olarak kopyala (Docker Archive API)
        tar_data = _make_tar_archive(files)
        r_copy = await client.put(
            f"/containers/{container_id}/archive",
            params={"path": "/app"},
            content=tar_data,
            headers={"Content-Type": "application/x-tar"},
        )
        if r_copy.status_code not in (200, 204):
            logger.warning("File copy warning: %s", r_copy.text[:200])

        # Projenin "çalışabilir" olup olmadığını kontrol et:
        # Gerçek bir Laravel uygulaması için routes/ + views/ + bootstrap/app.php gereklidir.
        # Yalnızca migrations/models/seeders varsa Laravel bootstrap başarısız olur.
        has_views = any(p.startswith("resources/views/") for p in files)
        has_routes = any(p.startswith("routes/") for p in files)
        has_bootstrap = any(p.startswith("bootstrap/") for p in files)
        has_vendor_autoload = any("vendor/autoload" in p for p in files)
        needs_mock = not (has_views and has_routes)

        if needs_mock:
            # Gerçek Laravel app çalışamaz — mock-up preview ile override
            logger.info(
                "Project %s lacks views/routes (has_views=%s, has_routes=%s) — using mock-up preview",
                project_id, has_views, has_routes,
            )
            index_tar = _make_tar_archive({
                "public/index.php": _build_preview_index(files),
            })
            await client.put(
                f"/containers/{container_id}/archive",
                params={"path": "/app"},
                content=index_tar,
                headers={"Content-Type": "application/x-tar"},
            )
        elif not any(p.startswith("public/") for p in files):
            # public/index.php yok ama views + routes var — minimal entry oluştur
            index_tar = _make_tar_archive({
                "public/index.php": _build_preview_index(files),
            })
            await client.put(
                f"/containers/{container_id}/archive",
                params={"path": "/app"},
                content=index_tar,
                headers={"Content-Type": "application/x-tar"},
            )

        # Container'ı başlat
        r2 = await client.post(f"/containers/{container_id}/start")
        if r2.status_code not in (200, 204):
            raise RuntimeError(f"Container başlatılamadı: {r2.text[:300]}")

    url = f"http://{PREVIEW_HOST}:{port}"
    logger.info("Container started: %s → %s (project: %s)", container_id[:12], url, project_id)

    return {
        "port": port,
        "url": url,
        "container": container_name,
        "container_id": container_id[:12],
    }


async def stop_project(project_id: str, *, _silent: bool = False) -> bool:
    """Proje container'ını durdurur ve kaldırır."""
    container_name = _get_container_name(project_id)
    try:
        async with _docker_client() as client:
            # Durdur
            await client.post(f"/containers/{container_name}/stop", params={"t": 5})
            # Kaldır (varsa)
            r_rm = await client.delete(f"/containers/{container_name}", params={"force": "true"})
            removed = r_rm.status_code in (204, 404)
            if removed:
                await release_port(project_id)
                logger.info("Removed container: %s", container_name)
            return removed
    except Exception as e:
        if not _silent:
            logger.warning("stop_project failed for %s: %s", project_id, e)
        # Zorla silmeyi dene
        try:
            async with _docker_client() as client:
                await client.delete(f"/containers/{container_name}", params={"force": "true"})
        except Exception:
            pass
        return False


async def get_project_status(project_id: str) -> Dict[str, object]:
    """Container çalışıyor mu?"""
    container_name = _get_container_name(project_id)
    running = False
    try:
        async with _docker_client() as client:
            r = await client.get(f"/containers/{container_name}/json")
            if r.status_code == 200:
                state = r.json().get("State", {})
                running = state.get("Running", False)
    except Exception:
        pass

    if running:
        try:
            import redis.asyncio as aioredis
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
            r = await aioredis.from_url(redis_url, decode_responses=True)
            port_str = await r.get(f"deepsite:project_port:{project_id}")
            port = int(port_str) if port_str else None
        except Exception:
            proj_lock = pathlib.Path("/tmp/deepsite_ports") / f"project_{project_id}.port"
            port = int(proj_lock.read_text().strip()) if proj_lock.exists() else None

        # Proxy için DinD hostname kullan (docker compose network üzerinden erişilebilir)
        dind_host = os.getenv("DIND_HOST", "dind")
        internal_url = f"http://{dind_host}:{port}" if port else None
        return {
            "running": True,
            "port": port,
            "url": internal_url,
            "preview_url": internal_url,
            "container": container_name,
        }

    return {
        "running": False,
        "port": None,
        "url": None,
        "preview_url": None,
        "container": container_name,
    }
