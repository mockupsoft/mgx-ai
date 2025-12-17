# -*- coding: utf-8 -*-

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import requests


@dataclass
class ArtifactRepoPublishResult:
    target_url: str
    success: bool
    status_code: Optional[int]
    message: str


class ArtifactRepoPublisher:
    """Upload build artifacts to a generic artifact repository (JFrog/Nexus)."""

    def __init__(self, *, base_url: str, token: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.username = username
        self.password = password

    def publish_file(self, *, file_path: str, destination_path: str) -> ArtifactRepoPublishResult:
        path = Path(file_path)
        if not path.exists():
            return ArtifactRepoPublishResult(
                target_url="",
                success=False,
                status_code=None,
                message=f"File not found: {file_path}",
            )

        url = f"{self.base_url}/{destination_path.lstrip('/')}"
        headers: Dict[str, str] = {}
        auth = None

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        elif self.username and self.password:
            auth = (self.username, self.password)

        resp = requests.put(url, data=path.read_bytes(), headers=headers, auth=auth, timeout=60)
        ok = 200 <= resp.status_code < 300

        return ArtifactRepoPublishResult(
            target_url=url,
            success=ok,
            status_code=resp.status_code,
            message=resp.text[:1000],
        )
