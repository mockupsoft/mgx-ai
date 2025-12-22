# GitHub Repository Linking

This backend supports linking a **Project** to one or more GitHub repositories via `RepositoryLink` records.

## Environment variables

The repository linking feature uses the following environment variables (see `.env.example`):

- `GITHUB_APP_ID` (optional): GitHub App ID
- `GITHUB_CLIENT_ID` (optional): GitHub OAuth client ID (not currently used by the backend router; reserved for future OAuth flow)
- `GITHUB_PRIVATE_KEY_PATH` (optional): Path to the GitHub App private key PEM file
- `GITHUB_PAT` (optional): Personal Access Token fallback (used when app auth is not configured)
- `GITHUB_CLONE_CACHE_DIR` (optional): Directory where the backend caches git clones (default: `/tmp/mgx-agent-repos`)

Auth resolution order:

1. If `installation_id` is provided in the API request and GitHub App settings are configured (`GITHUB_APP_ID` + `GITHUB_PRIVATE_KEY_PATH`), the backend uses an installation access token.
2. Otherwise, `GITHUB_PAT` is used.

## Required GitHub permissions/scopes

### GitHub App

The GitHub App must have access to the target repository and sufficient permissions for the operations you want:

- Read repository metadata
- Read contents (for cloning)
- Write contents (for pushing branches)
- Pull requests: write (for PR creation)

### PAT fallback

For a classic PAT, the simplest scope set is:

- `repo` (private repos) or `public_repo` (public repos only)

For a fine-grained token, grant:

- Repository permissions: `Contents` (Read/Write)
- Repository permissions: `Pull requests` (Read/Write)
- Repository permissions: `Metadata` (Read)

## API

Base path: `/api/repositories`

### Test access

`POST /api/repositories/test`

```json
{
  "repo_full_name": "octocat/Hello-World",
  "installation_id": 123456
}
```

Response:

```json
{
  "ok": true,
  "repo_full_name": "octocat/Hello-World",
  "default_branch": "main"
}
```

### Connect a repository to a project

`POST /api/repositories/connect`

```json
{
  "project_id": "<project-id>",
  "repo_full_name": "octocat/Hello-World",
  "installation_id": 123456,
  "reference_branch": "main",
  "set_as_primary": true
}
```

Notes:

- The backend validates access to the repository before persisting the link.
- If `set_as_primary` is true, the Project fields `repo_full_name`, `default_branch`, and `primary_repository_link_id` are updated.

### List repository links

`GET /api/repositories?project_id=<project-id>`

### Refresh repository metadata

`POST /api/repositories/{link_id}/refresh`

Refreshes `repo_full_name` and `default_branch` from GitHub.

### Update branch preferences / primary link

`PATCH /api/repositories/{link_id}`

```json
{
  "reference_branch": "develop",
  "set_as_primary": true
}
```

### Disconnect

`DELETE /api/repositories/{link_id}`

Marks the link as `disconnected` and clears stored auth metadata.
