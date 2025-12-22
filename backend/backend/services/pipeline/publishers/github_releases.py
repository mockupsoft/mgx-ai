# -*- coding: utf-8 -*-

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


@dataclass
class GitHubReleasePublishResult:
    repo: str
    tag: str
    release_id: Optional[int]
    success: bool
    message: str


class GitHubReleasesPublisher:
    """Create GitHub releases and upload assets."""

    def __init__(self, *, token: str, repo: str):
        self.token = token
        self.repo = repo

    def create_release(self, *, tag: str, name: str, body: str, draft: bool = False, prerelease: bool = False) -> GitHubReleasePublishResult:
        url = f"https://api.github.com/repos/{self.repo}/releases"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
        }
        payload = {
            "tag_name": tag,
            "name": name,
            "body": body,
            "draft": draft,
            "prerelease": prerelease,
        }

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code not in (200, 201):
            return GitHubReleasePublishResult(
                repo=self.repo,
                tag=tag,
                release_id=None,
                success=False,
                message=resp.text[:1000],
            )

        data = resp.json()
        return GitHubReleasePublishResult(
            repo=self.repo,
            tag=tag,
            release_id=data.get("id"),
            success=True,
            message="created",
        )

    def upload_asset(self, *, release_id: int, file_path: str, asset_name: Optional[str] = None) -> GitHubReleasePublishResult:
        path = Path(file_path)
        if not path.exists():
            return GitHubReleasePublishResult(
                repo=self.repo,
                tag="",
                release_id=release_id,
                success=False,
                message=f"File not found: {file_path}",
            )

        asset_name = asset_name or path.name
        url = f"https://uploads.github.com/repos/{self.repo}/releases/{release_id}/assets"
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/octet-stream",
        }
        resp = requests.post(url, params={"name": asset_name}, data=path.read_bytes(), headers=headers, timeout=60)
        ok = resp.status_code in (200, 201)

        return GitHubReleasePublishResult(
            repo=self.repo,
            tag="",
            release_id=release_id,
            success=ok,
            message=resp.text[:1000] if not ok else "uploaded",
        )
