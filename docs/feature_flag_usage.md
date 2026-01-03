# Feature Flag Usage

## Runtime Check

```python
from backend.services.feature_flag_service import get_feature_flag_service

ff = get_feature_flag_service()

if ff.is_enabled("new_provider", user_id=user_id, workspace_id=workspace_id):
    return new_provider_execute(task)
else:
    return existing_provider_execute(task)
```

## Health Check

- `GET /health/feature-flags`

## Admin Endpoints

Admin endpoints are protected by RBAC and require `settings:manage` permission.

- `GET /admin/feature-flags`
- `PATCH /admin/feature-flags/{name}`
- `POST /admin/feature-flags/{name}/enable`
- `POST /admin/feature-flags/{name}/disable`
- `POST /admin/feature-flags/{name}/rollout`
- `POST /admin/feature-flags/{name}/override/{user_id}`
