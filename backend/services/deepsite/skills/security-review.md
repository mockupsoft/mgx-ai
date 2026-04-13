# Security Review — Checklist

## Purpose
Charlie must run this checklist on every code review.
Mark each item [PASS] or [FAIL] with a one-line explanation.

---

## 1. Secrets & Credentials

- [ ] No API keys, passwords, or tokens hardcoded in source files
- [ ] `.env` used for all secrets; `.env.example` committed (not `.env`)
- [ ] No `console.log()` / `var_dump()` / `dd()` leaking sensitive data
- [ ] Database credentials only in environment variables

**FAIL trigger:** Any hardcoded secret found → immediate CHANGES REQUIRED

---

## 2. SQL Injection

- [ ] All database queries use parameterized statements / ORM binding
- [ ] No raw SQL with string concatenation (e.g., `"SELECT * FROM users WHERE id=" + id`)
- [ ] Laravel: Eloquent or `DB::select()` with bindings only
- [ ] Direct PDO: always `prepare()` + `bindParam()`

---

## 3. XSS (Cross-Site Scripting)

- [ ] User input is never inserted into HTML without escaping
- [ ] Laravel Blade: `{{ $var }}` (escaped) not `{!! $var !!}` for user data
- [ ] React: `dangerouslySetInnerHTML` not used with user content
- [ ] Content-Security-Policy header set where applicable

---

## 4. CSRF Protection

- [ ] Laravel: `@csrf` in all HTML forms; `VerifyCsrfToken` middleware active
- [ ] React+Sanctum: CSRF cookie fetched before mutating requests
- [ ] API-only routes: use token auth, not session (CSRF not needed)

---

## 5. Authentication & Authorization

- [ ] No endpoints accessible without authentication check
- [ ] Authorization: policy/gate check before resource access
- [ ] Password hashed with `bcrypt` / `Hash::make()` — never plaintext
- [ ] Token expiration configured (Sanctum token expiry)

---

## 6. Input Validation

- [ ] All user inputs validated before processing
- [ ] Laravel: FormRequest class or `$request->validate()` with rules
- [ ] React: Zod schema validation before API submission
- [ ] File uploads: type/size validation + store outside webroot

---

---

## 7. Laravel Project Completeness (Non-HTML Stacks Only)

This section is **mandatory** for Laravel / Flutter-Laravel / Laravel-React projects.
Skip for HTML-only output.

- [ ] `routes/web.php` (or `routes/api.php`) exists with at least one route
- [ ] At least one `app/Http/Controllers/` file exists with CRUD methods
- [ ] At least one `resources/views/` directory with Blade templates
- [ ] `resources/views/layouts/app.blade.php` (or equivalent layout) exists
- [ ] No controller method contains `// TODO` or placeholder-only body
- [ ] Every `Route::resource()` has a matching controller class

**FAIL trigger (any one):**
- Zero controller files → **CHANGES REQUIRED: missing entire HTTP layer**
- Zero view files → **CHANGES REQUIRED: missing entire UI layer**
- Routes file missing → **CHANGES REQUIRED: app has no navigable URLs**
- Controllers exist but have empty/TODO methods → **CHANGES REQUIRED: incomplete implementation**

---

## Verdict

If ANY item in sections 1–2 fails → **CHANGES REQUIRED** (critical risk)
If section 7 has ANY fail (Laravel projects) → **CHANGES REQUIRED** (project cannot run)
If 3+ items total fail across all sections → **CHANGES REQUIRED**
Otherwise → contribute [PASS] to SECURITY field in review output
