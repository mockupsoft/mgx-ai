# Common Security Rules

These rules apply to ALL stacks and ALL project types.

---

## Secrets Management

- NEVER commit `.env` files — only `.env.example` with placeholder values
- NEVER hardcode API keys, passwords, or tokens in source code
- Use environment variables for ALL external service credentials
- Rotate secrets immediately if accidentally committed

## Input Validation

- Validate ALL user inputs on the server side — client-side validation is UX only
- Reject unexpected fields (whitelist, not blacklist)
- Sanitize file names: strip path traversal characters (`../`, `..\\`)
- Limit input lengths to prevent memory/storage abuse

## SQL Injection Prevention

- Use parameterized queries or ORM bindings exclusively
- Never concatenate user input into SQL strings
- Apply principle of least privilege for DB users (SELECT/INSERT/UPDATE only — no DROP)

## Authentication

- Hash passwords with bcrypt (cost factor ≥ 12) — never MD5/SHA1
- Implement rate limiting on login endpoints (max 5 attempts / minute)
- Use secure, httpOnly, sameSite cookies for session tokens
- Invalidate sessions on logout — server side

## HTTPS & Headers

- Enforce HTTPS in production
- Set security headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`
- Content-Security-Policy: restrict script sources

## Dependencies

- Pin dependency versions — avoid `*` or `latest`
- Run `composer audit` / `npm audit` before deploy
- Remove unused packages
