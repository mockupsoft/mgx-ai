# -*- coding: utf-8 -*-
"""GitHub Branch management service."""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from backend.services.git import GitService, get_git_service

logger = logging.getLogger(__name__)


@dataclass
class BranchInfo:
    """Branch information."""
    name: str
    sha: str
    protected: bool
    default: bool = False


@dataclass
class BranchCompare:
    """Branch comparison result."""
    ahead_by: int
    behind_by: int
    total_commits: int
    commits: List[Dict[str, Any]]


class BranchManager:
    """Manages GitHub Branches."""
    
    def __init__(self, git_service: Optional[GitService] = None):
        """
        Initialize Branch manager.
        
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
    
    async def list_branches(
        self,
        repo_full_name: str,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> List[BranchInfo]:
        """
        List branches for a repository.
        
        Args:
            repo_full_name: Repository full name (owner/repo)
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            List of branch info
        """
        def _list_branches():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                branches = repo.get_branches()
                default_branch = repo.default_branch
                
                result = []
                for branch in branches:
                    result.append(BranchInfo(
                        name=branch.name,
                        sha=branch.commit.sha,
                        protected=branch.protected,
                        default=(branch.name == default_branch),
                    ))
                return result
            except GithubException as e:
                logger.error(f"Error listing branches: {e}")
                raise
        
        return await asyncio.to_thread(_list_branches)
    
    async def create_branch(
        self,
        repo_full_name: str,
        branch_name: str,
        from_branch: str = "main",
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> BranchInfo:
        """
        Create a new branch.
        
        Args:
            repo_full_name: Repository full name
            branch_name: New branch name
            from_branch: Source branch
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Created branch info
        """
        def _create_branch():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                source_branch = repo.get_branch(from_branch)
                source_sha = source_branch.commit.sha
                
                # Create new branch by creating a reference
                ref = repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=source_sha)
                
                # Get the created branch
                branch = repo.get_branch(branch_name)
                default_branch = repo.default_branch
                
                return BranchInfo(
                    name=branch.name,
                    sha=branch.commit.sha,
                    protected=branch.protected,
                    default=(branch.name == default_branch),
                )
            except GithubException as e:
                logger.error(f"Error creating branch {branch_name}: {e}")
                raise
        
        return await asyncio.to_thread(_create_branch)
    
    async def delete_branch(
        self,
        repo_full_name: str,
        branch_name: str,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> bool:
        """
        Delete a branch.
        
        Args:
            repo_full_name: Repository full name
            branch_name: Branch name to delete
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            True if deleted successfully
        """
        def _delete_branch():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                ref = repo.get_git_ref(f"heads/{branch_name}")
                ref.delete()
                return True
            except GithubException as e:
                logger.error(f"Error deleting branch {branch_name}: {e}")
                raise
        
        return await asyncio.to_thread(_delete_branch)
    
    async def compare_branches(
        self,
        repo_full_name: str,
        base_branch: str,
        head_branch: str,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> BranchCompare:
        """
        Compare two branches.
        
        Args:
            repo_full_name: Repository full name
            base_branch: Base branch
            head_branch: Head branch
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Branch comparison result
        """
        def _compare_branches():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                comparison = repo.compare(base_branch, head_branch)
                
                commits = []
                for commit in comparison.commits:
                    commits.append({
                        "sha": commit.sha,
                        "message": commit.commit.message,
                        "author": commit.commit.author.name if commit.commit.author else None,
                        "date": commit.commit.author.date.isoformat() if commit.commit.author and commit.commit.author.date else None,
                    })
                
                return BranchCompare(
                    ahead_by=comparison.ahead_by,
                    behind_by=comparison.behind_by,
                    total_commits=comparison.total_commits,
                    commits=commits,
                )
            except GithubException as e:
                logger.error(f"Error comparing branches: {e}")
                raise
        
        return await asyncio.to_thread(_compare_branches)


_branch_manager: Optional[BranchManager] = None


def get_branch_manager() -> BranchManager:
    """Get Branch manager instance."""
    global _branch_manager
    if _branch_manager is None:
        _branch_manager = BranchManager()
    return _branch_manager


def set_branch_manager(manager: Optional[BranchManager]) -> None:
    """Set Branch manager instance (for testing)."""
    global _branch_manager
    _branch_manager = manager


__all__ = [
    "BranchManager",
    "BranchInfo",
    "BranchCompare",
    "get_branch_manager",
    "set_branch_manager",
]

