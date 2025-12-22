# -*- coding: utf-8 -*-
"""GitHub Diff viewing service."""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from backend.services.git import GitService, get_git_service

logger = logging.getLogger(__name__)


@dataclass
class DiffFile:
    """Diff file information."""
    filename: str
    status: str  # added, removed, modified, renamed
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = None
    previous_filename: Optional[str] = None


@dataclass
class DiffStatistics:
    """Diff statistics."""
    files_changed: int
    additions: int
    deletions: int
    total_changes: int


@dataclass
class DiffResponse:
    """Complete diff response."""
    base_sha: str
    head_sha: str
    files: List[DiffFile]
    statistics: DiffStatistics


class DiffViewer:
    """Views GitHub diffs."""
    
    def __init__(self, git_service: Optional[GitService] = None):
        """
        Initialize Diff viewer.
        
        Args:
            git_service: Git service instance (uses default if not provided)
        """
        self._git_service = git_service or get_git_service()
    
    def _get_github_api(self, installation_id: Optional[int] = None, token_override: Optional[str] = None):
        """Get GitHub API instance."""
        from github import Github
        from github.GithubException import GithubException
        
        token = self._git_service._resolve_token(installation_id=installation_id, token_override=token_override)
        return Github(login_or_token=token), GithubException
    
    async def get_commit_diff(
        self,
        repo_full_name: str,
        commit_sha: str,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> DiffResponse:
        """
        Get diff for a specific commit.
        
        Args:
            repo_full_name: Repository full name
            commit_sha: Commit SHA
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Diff response
        """
        def _get_commit_diff():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                commit = repo.get_commit(commit_sha)
                
                files = []
                total_additions = 0
                total_deletions = 0
                
                for file in commit.files:
                    files.append(DiffFile(
                        filename=file.filename,
                        status=file.status,
                        additions=file.additions,
                        deletions=file.deletions,
                        changes=file.changes,
                        patch=file.patch,
                        previous_filename=file.previous_filename if hasattr(file, 'previous_filename') else None,
                    ))
                    total_additions += file.additions
                    total_deletions += file.deletions
                
                return DiffResponse(
                    base_sha=commit.parents[0].sha if commit.parents else "",
                    head_sha=commit.sha,
                    files=files,
                    statistics=DiffStatistics(
                        files_changed=len(files),
                        additions=total_additions,
                        deletions=total_deletions,
                        total_changes=total_additions + total_deletions,
                    ),
                )
            except GithubException as e:
                logger.error(f"Error getting commit diff: {e}")
                raise
        
        return await asyncio.to_thread(_get_commit_diff)
    
    async def get_compare_diff(
        self,
        repo_full_name: str,
        base: str,
        head: str,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> DiffResponse:
        """
        Get diff between two branches/commits.
        
        Args:
            repo_full_name: Repository full name
            base: Base branch/commit
            head: Head branch/commit
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Diff response
        """
        def _get_compare_diff():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                comparison = repo.compare(base, head)
                
                files = []
                total_additions = 0
                total_deletions = 0
                
                for file in comparison.files:
                    files.append(DiffFile(
                        filename=file.filename,
                        status=file.status,
                        additions=file.additions,
                        deletions=file.deletions,
                        changes=file.changes,
                        patch=file.patch,
                        previous_filename=file.previous_filename if hasattr(file, 'previous_filename') else None,
                    ))
                    total_additions += file.additions
                    total_deletions += file.deletions
                
                return DiffResponse(
                    base_sha=comparison.base_commit.sha if comparison.base_commit else "",
                    head_sha=comparison.merge_base_commit.sha if comparison.merge_base_commit else comparison.head_commit.sha if comparison.head_commit else "",
                    files=files,
                    statistics=DiffStatistics(
                        files_changed=len(files),
                        additions=total_additions,
                        deletions=total_deletions,
                        total_changes=total_additions + total_deletions,
                    ),
                )
            except GithubException as e:
                logger.error(f"Error getting compare diff: {e}")
                raise
        
        return await asyncio.to_thread(_get_compare_diff)


_diff_viewer: Optional[DiffViewer] = None


def get_diff_viewer() -> DiffViewer:
    """Get Diff viewer instance."""
    global _diff_viewer
    if _diff_viewer is None:
        _diff_viewer = DiffViewer()
    return _diff_viewer


def set_diff_viewer(viewer: Optional[DiffViewer]) -> None:
    """Set Diff viewer instance (for testing)."""
    global _diff_viewer
    _diff_viewer = viewer


__all__ = [
    "DiffViewer",
    "DiffFile",
    "DiffStatistics",
    "DiffResponse",
    "get_diff_viewer",
    "set_diff_viewer",
]

