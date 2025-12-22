# Git integration

MGX Agent supports Git-aware execution flows, including GitHub repository linking and automated branch/commit/PR operations.

## Primary docs

- **Repository linking (GitHub)**: [GITHUB_REPOSITORY_LINKING.md](./GITHUB_REPOSITORY_LINKING.md)
- **Git-aware execution**: [GIT_AWARE_EXECUTION.md](./GIT_AWARE_EXECUTION.md)

## API surface

Repository links are managed under `/api/repositories/*` (see the OpenAPI docs at `/docs` when running the server).

## Event streaming

Git operations emit events over WebSockets (see [API_EVENTS_DOCUMENTATION.md](./API_EVENTS_DOCUMENTATION.md)).
