# DeepSite üretim sunucusu

## Mimari

- **Frontend (Next.js):** `/deepsite` — `AppEditor` (`components/deepsite-v2/`), AI istekleri `/api/deepsite/ask-ai` üzerinden aynı origin’e gider, route FastAPI’ye proxy eder.
- **Backend (FastAPI):** `/api/deepsite/generate` (SSE), `/api/deepsite/follow-up` (SEARCH/REPLACE), `/api/deepsite/redesign`, proje CRUD `/api/deepsite/projects/*`.
- **Agent modu:** `GenerateRequest.mode = "agent"` — `backend/services/deepsite/web_team.py` (Designer brief + Coder stream). Anahtarlar sunucu ortamında (`OPENROUTER_API_KEY`, vb.).

## Ortam değişkenleri

### Backend (`mgx-ai` / `.env`)

- `DEEPSITE_SKIP_AUTH=false` — üretimde JWT zorunlu (anonim kullanıcı kapatılır).
- `MGX_ENV=production` — `deepsite_skip_auth` zorunlu olarak kapatılır (`backend/config.py`).
- LLM anahtarları: `OPENROUTER_API_KEY`, `GOOGLE_API_KEY`, vb. (mevcut MGX ayarları).

### Frontend (build zamanı)

- `NEXT_PUBLIC_API_BASE_URL=https://api.example.com` — tarayıcıdan erişilen API kökü.
- `NEXT_PUBLIC_DEEPSITE_SKIP_AUTH=false` — login akışı açık.
- `NEXT_PUBLIC_DEEPSITE_SKIP_AUTH` üretimde `false` olmalı.

## Reverse proxy (ör. Nginx)

- `location /api/` → FastAPI upstream (8000).
- `location /` → Next.js static/server.
- WebSocket gerekirse `/ws` ayrı upstream.

## SSL

- Let’s Encrypt veya barındırıcı sertifikası; `https` zorunlu (JWT + cookie güvenliği).

## Docker

Kök `docker-compose.yml` + geliştirme için `docker-compose.override.yml` içinde `mgx-frontend` ve `mgx-ai` servisleri tanımlıdır. Üretimde override kullanmayın veya env’leri production değerleriyle override edin.
