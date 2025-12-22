# Release Pipeline (Phase 16)

This module packages generated projects into deployable artifacts:

- Docker image build / scan (Trivy) / sign (Cosign) / push
- docker-compose.yml generation (healthchecks, volumes, networks, logging)
- Helm chart generation
- Release notes generation
- Migration plan generation

## API

### Build artifacts

`POST /api/artifacts/build`

```json
{
  "execution_id": "00000000-0000-0000-0000-000000000000",
  "project_id": "<generated_project_id>",
  "project_path": "/tmp/generator_workspace/<id_name>",
  "version": "1.0.0",
  "changes": ["Feature: ...", "Fix: ..."],
  "breaking_changes": [],
  "migration_changes": {},
  "build_config": {
    "docker": { "enabled": true, "registry": "docker.io", "tag": "v1.0.0", "scan": true, "sign": true },
    "compose": { "enabled": true },
    "helm": { "enabled": true, "version": "1.0.0" },
    "release_notes": { "enabled": true },
    "migration_plan": { "enabled": true }
  }
}
```

Returns a `build_id`. The build runs as a background task.

### Check build status

`GET /api/artifacts/builds/{build_id}`

### Publish

`POST /api/artifacts/publish`

```json
{ "build_id": "...", "targets": ["docker_registry"] }
```

## CLI requirements (optional)

The pipeline auto-detects tools. Missing tools will cause scan/sign/validation steps to be skipped.

- Docker build/push: `docker` (and optionally `buildx`)
- Security scan: `trivy`
- Image signing: `cosign`
- Compose validation: `docker compose` or `docker-compose`
- Helm validation: `helm`

## Registry setup

### Docker Hub / GHCR

Authenticate using `docker login` before running builds, or run the pipeline in an environment that already has a logged-in Docker config.

### AWS ECR

For ECR login you need AWS CLI configured:

```bash
aws configure
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account_id>.dkr.ecr.us-east-1.amazonaws.com
```

## Output locations

Artifacts are written under the generated project directory:

- `deploy/compose/docker-compose.yml`
- `deploy/helm/<project>/...`
- `deploy/release-notes/release_<version>.md`
- `deploy/migrations/migration_previous_to_<version>.md`
- `deploy/security/trivy_*.json` (if Trivy installed)
