# Laravel API + React + PostgreSQL — Architecture Guide

## Golden Path: Special Mode

**Stack:** Laravel 11+ (API backend), React 18+ (Vite + TypeScript), PostgreSQL 16+

---

## Mandatory Dependencies

**React Frontend (package.json):**
```json
{
  "react": "^18.3.0",
  "react-router-dom": "^6.22.0",
  "@tanstack/react-query": "^5.28.0",
  "zustand": "^4.5.0",
  "axios": "^1.6.0",
  "tailwindcss": "^3.4.0",
  "react-hook-form": "^7.51.0",
  "zod": "^3.22.0"
}
```

**Laravel Backend (composer.json):**
```json
{
  "laravel/framework": "^11.0",
  "laravel/sanctum": "^4.0"
}
```

---

## React Folder Structure

```
src/
  features/
    auth/
      api.ts               # API calls for this feature
      hooks.ts             # React Query + Zustand hooks
      components/          # Feature-specific components
      pages/               # Route-level components
    <feature>/
      api.ts
      hooks.ts
      components/
      pages/
  components/              # Shared UI components
  hooks/                   # Shared custom hooks
  lib/
    api/
      client.ts            # Axios instance with CSRF + auth
      types.ts             # API response types
  stores/
    auth.store.ts          # Zustand auth store
  App.tsx
  main.tsx
```

---

## Laravel API Structure

```
app/Http/Controllers/Api/    # Resource controllers (index/show/store/update/destroy)
app/Http/Resources/          # JSON resource transformers
app/Http/Requests/Api/       # API validation requests
routes/api.php               # /api/v1/ versioned routes
config/cors.php              # CORS: allow React dev origin
config/sanctum.php           # SPA stateful domains
```

---

## Sanctum SPA Auth Setup

**Laravel config/sanctum.php:**
```php
'stateful' => explode(',', env('SANCTUM_STATEFUL_DOMAINS', 'localhost:5173')),
```

**Axios client (src/lib/api/client.ts):**
```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  withCredentials: true,  // Required for Sanctum cookie
  headers: { 'Accept': 'application/json' },
});

// CSRF cookie fetch before first mutating request
export async function initCsrf() {
  await api.get('/sanctum/csrf-cookie');
}

export default api;
```

---

## TanStack Query Pattern

```typescript
// features/auth/hooks.ts
import { useMutation, useQuery } from '@tanstack/react-query';
import { login, getProfile } from './api';

export function useProfile() {
  return useQuery({ queryKey: ['profile'], queryFn: getProfile });
}

export function useLogin() {
  return useMutation({
    mutationFn: login,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['profile'] }),
  });
}
```

---

## Non-Negotiables

1. **TanStack Query for server state** — not `useEffect + useState` for API data
2. **Zustand for global client state** — not Context for frequently-changing state
3. **Sanctum SPA mode** — cookie-based CSRF, `withCredentials: true`
4. **Feature-based folder structure** — each feature is self-contained
5. **Zod for form + API validation** — never trust raw user input
6. **API versioning** — all routes under `/api/v1/`
7. **CORS config explicit** — always set allowed origins in `config/cors.php`

---

## Anti-Patterns — NEVER Do

- `useEffect` + `useState` for data fetching — use TanStack Query
- Redux for new projects — Zustand is sufficient and simpler
- Storing JWT in localStorage — use Sanctum cookies
- `any` TypeScript type for API responses — always define interfaces
- Controllers returning raw Eloquent models — always use Resource classes
- Missing CSRF on mutating requests — always fetch `/sanctum/csrf-cookie` first
- MySQL as database — PostgreSQL is mandatory for golden path
