# Laravel Best Practices

## Eloquent & Database

- Always eager load relationships: `User::with('posts')->get()` — never lazy load in loops
- Chunk large queries: `User::chunk(200, fn($users) => ...)`
- Use `select()` to limit columns fetched
- Define `$fillable` on every model — never use `$guarded = []` in production
- Migration naming: `YYYY_MM_DD_HHMMSS_create_<table>_table.php`
- Always add PostgreSQL indexes for foreign keys and search columns
- Use `jsonb` not `json` for PostgreSQL JSON columns

## Controllers

- Thin controllers — business logic belongs in Service classes
- One action per controller method (index/show/store/update/destroy)
- Use FormRequest for all validation — no `$request->validate()` in controllers
- Return Resource classes from API controllers — never raw Eloquent models

## Routing

- Group routes by middleware: `Route::middleware('auth:sanctum')->group()`
- Use route model binding: `Route::get('/users/{user}', ...)` not manual `User::find($id)`
- Name all routes: `->name('users.index')`
- API routes versioned: prefix with `/api/v1/`

## Security

- CSRF: `@csrf` in every HTML form — never disable VerifyCsrfToken globally
- Sanctum: use `auth:sanctum` middleware for API, `auth` for web
- Policies: one Policy per model — never inline `$user->role` checks
- Validation: `'email' => 'required|email|max:255'` — always include max

## Testing

- Use `RefreshDatabase` trait in Feature tests
- Factory for all test data — never raw INSERT in tests
- Test happy path + validation errors + unauthorized access for each endpoint
- Use `actingAs($user)` for auth tests

## Anti-Patterns

- `User::all()` — always paginate or chunk
- `@php` blocks in Blade with complex logic
- Storing passwords unhashed
- `Auth::user()` inside a loop (N+1 on auth)
- `dd()` or `var_dump()` in production code
