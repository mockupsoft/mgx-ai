# Flutter + Dart Best Practices

## State Management (Riverpod)

- Use `Provider`, `StateNotifierProvider`, or `AsyncNotifierProvider` — not bare `setState` for shared state
- `StateNotifier` for mutable state with logic; `AsyncNotifier` for async data
- Keep providers small and focused — one provider per concern
- Declare providers at top-level (not inside widgets)
- Use `ref.watch()` in build, `ref.read()` in callbacks

## Network Layer (Dio)

- Single Dio instance — configure via `DioHelper` or provider
- `AuthInterceptor` for token injection on every request
- `RetryInterceptor` for transient network failures (max 3 retries)
- Always handle `DioException` — never let network errors crash the app
- Type API responses with model classes — never use `dynamic`

## Navigation (go_router)

- Declare all routes in `router.dart` — never `Navigator.push()` scattered across widgets
- Use `GoRouter.of(context).go()` for navigation — not `Navigator.pushNamed()`
- Implement `redirect` in router for auth guard

## Widget Structure

- Prefer `StatelessWidget` — extract state to providers
- Split large widgets into smaller composable ones (< 100 lines per widget)
- Use `const` constructors wherever possible
- Name widget files in `snake_case.dart`

## Security

- `flutter_secure_storage` for auth tokens — never `SharedPreferences`
- NEVER hardcode API base URLs — use `--dart-define` or `.env` at build time
- Obfuscate release builds: `flutter build apk --obfuscate --split-debug-info=...`
- Certificate pinning for sensitive apps

## Testing

- Widget tests with `flutter_test` for all UI components
- `mockito` for mocking network/service dependencies
- Integration tests with `flutter_driver` for critical flows (login, checkout)
- Test edge cases: empty lists, network errors, loading states

## Anti-Patterns

- `setState` in large widgets managing multiple state pieces
- `SharedPreferences` for sensitive data
- `print()` in production — use `debugPrint()` or a logger package
- `dynamic` return type from API methods
- Returning `Future<void>` from build methods
- Rebuilding entire widget trees for small state changes
