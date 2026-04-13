# Flutter + Laravel API + PostgreSQL — Architecture Guide

## Golden Path: Mobile Mode

**Stack:** Flutter 3.x (Dart), Laravel 11+ (API-only), PostgreSQL 16+

---

## Mandatory Dependencies

**Flutter (pubspec.yaml):**
```yaml
dependencies:
  flutter_riverpod: ^2.5.0    # State management
  dio: ^5.4.0                  # HTTP client
  flutter_secure_storage: ^9.0.0
  go_router: ^13.0.0           # Navigation
  json_annotation: ^4.8.1

dev_dependencies:
  flutter_test:
    sdk: flutter
  mockito: ^5.4.4
  build_runner: ^2.4.8
  json_serializable: ^6.7.1
```

**Laravel Backend (composer.json):**
```json
{
  "laravel/sanctum": "^4.0"
}
```

---

## Flutter Folder Structure

```
lib/
  app/
    router.dart             # go_router config
    theme.dart              # ThemeData
  core/
    network/
      api_client.dart       # Dio instance + interceptors
      auth_interceptor.dart # Token injection
    storage/
      secure_storage.dart   # flutter_secure_storage wrapper
    error/
      app_exception.dart    # Unified error types
  features/
    auth/
      data/                 # Repository implementations
      domain/               # Use cases, entities
      presentation/         # Screens, widgets, providers
    <feature>/
      data/
      domain/
      presentation/
  shared/
    widgets/                # Common UI components
    utils/                  # Helpers
  main.dart
```

---

## Laravel API Structure

```
app/Http/Controllers/Api/    # API-only controllers
app/Http/Resources/          # JSON resource transformers
app/Http/Requests/Api/       # API validation requests
routes/api.php               # Versioned API routes (/api/v1/)
config/cors.php              # CORS for Flutter client
```

---

## Non-Negotiables

1. **Riverpod for state management** — not Provider or setState for complex state
2. **Dio with interceptors** — token injection, error handling, retry logic
3. **Feature-based folder structure** — not layer-based (`models/`, `screens/`)
4. **`flutter_secure_storage`** — never SharedPreferences for tokens
5. **go_router for navigation** — not Navigator.push() directly
6. **Laravel Sanctum token-based auth** — mobile uses token, not session
7. **JSON:API resources** — always transform Eloquent via Resource classes

---

## Dio Interceptor Pattern

```dart
class AuthInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final token = SecureStorage.getToken();
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    if (err.response?.statusCode == 401) {
      // Redirect to login
    }
    handler.next(err);
  }
}
```

---

## Anti-Patterns — NEVER Do

- `setState` for cross-widget state — use Riverpod providers
- `SharedPreferences` for auth tokens — use `flutter_secure_storage`
- Direct `http` package instead of Dio — no interceptor support
- Hardcoded API base URL — use `--dart-define` or `.env`
- Returning `dynamic` from API methods — always type API responses
- Missing error handling in network calls — always try/catch DioException
