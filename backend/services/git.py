# -*- coding: utf-8 -*-
"""backend.services.git

Git/GitHub integration used by the repository linking API.

This module is intentionally structured around small interfaces so that tests can
mock GitHub API calls and git operations without spawning subprocesses or
touching the network.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol

from backend.config import settings


class GitServiceError(Exception):
    pass


class RepositoryNotFoundError(GitServiceError):
    pass


class RepositoryAccessError(GitServiceError):
    pass


class GitOperationError(GitServiceError):
    pass


@dataclass(frozen=True)
class RepoInfo:
    full_name: str
    default_branch: str
    private: Optional[bool] = None
    html_url: Optional[str] = None


class GitHubAPI(Protocol):
    def get_repo_info(self, repo_full_name: str) -> RepoInfo: ...

    def create_pull_request(
        self,
        repo_full_name: str,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> str: ...


class GitRepoManager(Protocol):
    def clone_or_update(self, clone_url: str, dest_dir: Path, default_branch: str) -> Path: ...

    def create_branch(self, repo_dir: Path, branch: str, base_branch: str) -> None: ...

    def push_branch(self, repo_dir: Path, branch: str) -> None: ...


_REPO_FULL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def normalize_repo_full_name(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Repository name is required")

    raw = raw.removesuffix(".git")

    if raw.startswith("git@github.com:"):
        raw = raw[len("git@github.com:") :]
    elif raw.startswith("https://github.com/"):
        raw = raw[len("https://github.com/") :]
    elif raw.startswith("http://github.com/"):
        raw = raw[len("http://github.com/") :]

    raw = raw.strip("/")

    if not _REPO_FULL_NAME_RE.match(raw):
        raise ValueError("Repository must be in the form 'owner/repo' (or a GitHub URL)")

    return raw


def build_https_clone_url(repo_full_name: str, token: Optional[str]) -> str:
    if token:
        return f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
    return f"https://github.com/{repo_full_name}.git"


class PyGithubAPI:
    def __init__(self, token: str):
        from github import Github
        from github.GithubException import GithubException

        self._Github = Github
        self._GithubException = GithubException
        self._token = token

    def get_repo_info(self, repo_full_name: str) -> RepoInfo:
        gh = self._Github(login_or_token=self._token)
        try:
            repo = gh.get_repo(repo_full_name)
        except self._GithubException as e:
            if getattr(e, "status", None) == 404:
                raise RepositoryNotFoundError("Repository not found") from e
            if getattr(e, "status", None) in {401, 403}:
                raise RepositoryAccessError("Access denied to repository") from e
            raise RepositoryAccessError("Failed to access repository") from e

        return RepoInfo(
            full_name=repo.full_name,
            default_branch=repo.default_branch,
            private=getattr(repo, "private", None),
            html_url=getattr(repo, "html_url", None),
        )

    def create_pull_request(self, repo_full_name: str, title: str, body: str, head: str, base: str) -> str:
        gh = self._Github(login_or_token=self._token)
        repo = gh.get_repo(repo_full_name)
        pr = repo.create_pull(title=title, body=body, head=head, base=base)
        return pr.html_url


class GitPythonRepoManager:
    def __init__(self):
        from git import Repo
        from git.exc import GitCommandError

        self._Repo = Repo
        self._GitCommandError = GitCommandError

    def clone_or_update(self, clone_url: str, dest_dir: Path, default_branch: str) -> Path:
        dest_dir.parent.mkdir(parents=True, exist_ok=True)

        try:
            if dest_dir.exists() and (dest_dir / ".git").exists():
                repo = self._Repo(str(dest_dir))
                repo.remotes.origin.set_url(clone_url)
                repo.remotes.origin.fetch(prune=True)
                repo.git.checkout(default_branch)
                repo.remotes.origin.pull(default_branch)
                return dest_dir

            repo = self._Repo.clone_from(clone_url, str(dest_dir))
            repo.git.checkout(default_branch)
            return dest_dir
        except self._GitCommandError as e:
            raise GitOperationError("Failed to clone or update repository") from e

    def create_branch(self, repo_dir: Path, branch: str, base_branch: str) -> None:
        try:
            repo = self._Repo(str(repo_dir))
            repo.git.checkout(base_branch)
            repo.git.pull("origin", base_branch)
            repo.git.checkout("-B", branch)
        except self._GitCommandError as e:
            raise GitOperationError("Failed to create branch") from e

    def push_branch(self, repo_dir: Path, branch: str) -> None:
        try:
            repo = self._Repo(str(repo_dir))
            repo.remotes.origin.push(refspec=f"{branch}:{branch}", set_upstream=True)
        except self._GitCommandError as e:
            raise GitOperationError("Failed to push branch") from e


class GitService:
    def __init__(
        self,
        github_api_factory: Optional[Callable[[str], GitHubAPI]] = None,
        repo_manager: Optional[GitRepoManager] = None,
        clone_cache_dir: Optional[str] = None,
    ):
        self._github_api_factory = github_api_factory or self._default_github_api_factory
        self._repo_manager = repo_manager or GitPythonRepoManager()
        self._clone_cache_dir = Path(clone_cache_dir or settings.github_clone_cache_dir)

    def _default_github_api_factory(self, token: str) -> GitHubAPI:
        return PyGithubAPI(token)

    def _load_app_private_key(self) -> str:
        if not settings.github_private_key_path:
            raise RepositoryAccessError("GitHub App private key is not configured")

        key_path = Path(settings.github_private_key_path)
        try:
            return key_path.read_text(encoding="utf-8")
        except OSError as e:
            raise RepositoryAccessError("Failed to read GitHub App private key") from e

    def _resolve_token(self, installation_id: Optional[int] = None, token_override: Optional[str] = None) -> str:
        if token_override:
            return token_override

        if installation_id and settings.github_app_id and settings.github_private_key_path:
            from github import GithubIntegration

            private_key = self._load_app_private_key()
            integration = GithubIntegration(settings.github_app_id, private_key)
            access = integration.get_access_token(installation_id)
            return access.token

        if settings.github_pat:
            return settings.github_pat

        raise RepositoryAccessError(
            "No GitHub credentials configured. Set GITHUB_PAT or configure GitHub App settings."
        )

    async def fetch_repo_info(
        self,
        repo_full_name: str,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> RepoInfo:
        normalized = normalize_repo_full_name(repo_full_name)
        token = self._resolve_token(installation_id=installation_id, token_override=token_override)
        api = self._github_api_factory(token)

        return await asyncio.to_thread(api.get_repo_info, normalized)

    async def ensure_clone(
        self,
        repo_full_name: str,
        default_branch: str,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> Path:
        normalized = normalize_repo_full_name(repo_full_name)
        token = self._resolve_token(installation_id=installation_id, token_override=token_override)
        clone_url = build_https_clone_url(normalized, token)

        safe_dir_name = normalized.replace("/", "__")
        dest_dir = self._clone_cache_dir / safe_dir_name

        return await asyncio.to_thread(self._repo_manager.clone_or_update, clone_url, dest_dir, default_branch)

    async def create_branch(self, repo_dir: Path, branch: str, base_branch: str) -> None:
        await asyncio.to_thread(self._repo_manager.create_branch, repo_dir, branch, base_branch)

    async def push_branch(self, repo_dir: Path, branch: str) -> None:
        await asyncio.to_thread(self._repo_manager.push_branch, repo_dir, branch)

    async def create_pull_request(
        self,
        repo_full_name: str,
        title: str,
        body: str,
        head: str,
        base: str,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> str:
        normalized = normalize_repo_full_name(repo_full_name)
        token = self._resolve_token(installation_id=installation_id, token_override=token_override)
        api = self._github_api_factory(token)
        return await asyncio.to_thread(api.create_pull_request, normalized, title, body, head, base)


_git_service: Optional[GitService] = None


def get_git_service() -> GitService:
    global _git_service
    if _git_service is None:
        _git_service = GitService()
    return _git_service


def set_git_service(service: Optional[GitService]) -> None:
    global _git_service
    _git_service = service


__all__ = [
    "GitService",
    "GitServiceError",
    "RepositoryAccessError",
    "RepositoryNotFoundError",
    "GitOperationError",
    "RepoInfo",
    "normalize_repo_full_name",
    "get_git_service",
    "set_git_service",
]
