# -*- coding: utf-8 -*-
"""GitHub Pull Request management service."""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from backend.services.git import GitService, get_git_service
from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class PullRequestInfo:
    """Pull request information."""
    number: int
    title: str
    body: str
    state: str  # open, closed, merged
    head_branch: str
    base_branch: str
    head_sha: str
    base_sha: str
    html_url: str
    created_at: str
    updated_at: str
    merged_at: Optional[str] = None
    mergeable: Optional[bool] = None
    mergeable_state: Optional[str] = None
    author: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    review_count: int = 0
    comment_count: int = 0


@dataclass
class PRReview:
    """Pull request review."""
    id: int
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
    body: Optional[str]
    author: str
    submitted_at: str


@dataclass
class PRComment:
    """Pull request comment."""
    id: int
    body: str
    author: str
    created_at: str
    path: Optional[str] = None  # File path for inline comments
    line: Optional[int] = None  # Line number for inline comments


class PRManager:
    """Manages GitHub Pull Requests."""
    
    def __init__(self, git_service: Optional[GitService] = None):
        """
        Initialize PR manager.
        
        Args:
            git_service: Git service instance (uses default if not provided)
        """
        self._git_service = git_service or get_git_service()
    
    def _get_github_api(self, installation_id: Optional[int] = None, token_override: Optional[str] = None):
        """Get GitHub API instance."""
        from github import Github
        from github.GithubException import GithubException
        
        # Access the private method through the service
        token = self._git_service._resolve_token(installation_id=installation_id, token_override=token_override)
        return Github(login_or_token=token), GithubException
    
    async def list_pull_requests(
        self,
        repo_full_name: str,
        state: str = "open",  # open, closed, all
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> List[PullRequestInfo]:
        """
        List pull requests for a repository.
        
        Args:
            repo_full_name: Repository full name (owner/repo)
            state: PR state filter (open, closed, all)
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            List of pull request info
        """
        def _list_prs():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                prs = repo.get_pulls(state=state, sort="updated", direction="desc")
                
                result = []
                for pr in prs:
                    labels = [label.name for label in pr.labels] if pr.labels else []
                    result.append(PullRequestInfo(
                        number=pr.number,
                        title=pr.title,
                        body=pr.body or "",
                        state=pr.state,
                        head_branch=pr.head.ref,
                        base_branch=pr.base.ref,
                        head_sha=pr.head.sha,
                        base_sha=pr.base.sha,
                        html_url=pr.html_url,
                        created_at=pr.created_at.isoformat() if pr.created_at else "",
                        updated_at=pr.updated_at.isoformat() if pr.updated_at else "",
                        merged_at=pr.merged_at.isoformat() if pr.merged_at else None,
                        mergeable=pr.mergeable,
                        mergeable_state=pr.mergeable_state,
                        author=pr.user.login if pr.user else None,
                        labels=labels,
                        review_count=pr.reviews.totalCount if hasattr(pr.reviews, 'totalCount') else 0,
                        comment_count=pr.comments if isinstance(pr.comments, int) else 0,
                    ))
                return result
            except GithubException as e:
                logger.error(f"Error listing PRs: {e}")
                raise
        
        return await asyncio.to_thread(_list_prs)
    
    async def get_pull_request(
        self,
        repo_full_name: str,
        pr_number: int,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> PullRequestInfo:
        """
        Get pull request details.
        
        Args:
            repo_full_name: Repository full name
            pr_number: Pull request number
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Pull request info
        """
        def _get_pr():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                pr = repo.get_pull(pr_number)
                
                labels = [label.name for label in pr.labels] if pr.labels else []
                return PullRequestInfo(
                    number=pr.number,
                    title=pr.title,
                    body=pr.body or "",
                    state=pr.state,
                    head_branch=pr.head.ref,
                    base_branch=pr.base.ref,
                    head_sha=pr.head.sha,
                    base_sha=pr.base.sha,
                    html_url=pr.html_url,
                    created_at=pr.created_at.isoformat() if pr.created_at else "",
                    updated_at=pr.updated_at.isoformat() if pr.updated_at else "",
                    merged_at=pr.merged_at.isoformat() if pr.merged_at else None,
                    mergeable=pr.mergeable,
                    mergeable_state=pr.mergeable_state,
                    author=pr.user.login if pr.user else None,
                    labels=labels,
                    review_count=pr.reviews.totalCount if hasattr(pr.reviews, 'totalCount') else 0,
                    comment_count=pr.comments if isinstance(pr.comments, int) else 0,
                )
            except GithubException as e:
                logger.error(f"Error getting PR {pr_number}: {e}")
                raise
        
        return await asyncio.to_thread(_get_pr)
    
    async def merge_pull_request(
        self,
        repo_full_name: str,
        pr_number: int,
        merge_method: str = "merge",  # merge, squash, rebase
        commit_title: Optional[str] = None,
        commit_message: Optional[str] = None,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Merge a pull request.
        
        Args:
            repo_full_name: Repository full name
            pr_number: Pull request number
            merge_method: Merge method (merge, squash, rebase)
            commit_title: Custom commit title
            commit_message: Custom commit message
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Merge result
        """
        def _merge_pr():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                pr = repo.get_pull(pr_number)
                
                merge_result = pr.merge(
                    merge_method=merge_method,
                    commit_title=commit_title,
                    commit_message=commit_message,
                )
                
                return {
                    "merged": merge_result.merged,
                    "message": merge_result.message,
                    "sha": merge_result.sha,
                }
            except GithubException as e:
                logger.error(f"Error merging PR {pr_number}: {e}")
                raise
        
        return await asyncio.to_thread(_merge_pr)
    
    async def create_review(
        self,
        repo_full_name: str,
        pr_number: int,
        state: str,  # APPROVE, REQUEST_CHANGES, COMMENT
        body: Optional[str] = None,
        event: Optional[str] = None,  # APPROVE, REQUEST_CHANGES, COMMENT
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> PRReview:
        """
        Create a pull request review.
        
        Args:
            repo_full_name: Repository full name
            pr_number: Pull request number
            state: Review state (APPROVE, REQUEST_CHANGES, COMMENT)
            body: Review body/comment
            event: Review event (overrides state if provided)
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Created review
        """
        def _create_review():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                pr = repo.get_pull(pr_number)
                
                review_event = event or state
                review = pr.create_review(
                    body=body or "",
                    event=review_event,
                )
                
                return PRReview(
                    id=review.id,
                    state=review.state,
                    body=review.body,
                    author=review.user.login if review.user else None,
                    submitted_at=review.submitted_at.isoformat() if review.submitted_at else "",
                )
            except GithubException as e:
                logger.error(f"Error creating review for PR {pr_number}: {e}")
                raise
        
        return await asyncio.to_thread(_create_review)
    
    async def create_comment(
        self,
        repo_full_name: str,
        pr_number: int,
        body: str,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> PRComment:
        """
        Create a pull request comment.
        
        Args:
            repo_full_name: Repository full name
            pr_number: Pull request number
            body: Comment body
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Created comment
        """
        def _create_comment():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                pr = repo.get_pull(pr_number)
                issue = repo.get_issue(pr_number)
                
                comment = issue.create_comment(body)
                
                return PRComment(
                    id=comment.id,
                    body=comment.body,
                    author=comment.user.login if comment.user else None,
                    created_at=comment.created_at.isoformat() if comment.created_at else "",
                )
            except GithubException as e:
                logger.error(f"Error creating comment for PR {pr_number}: {e}")
                raise
        
        return await asyncio.to_thread(_create_comment)
    
    async def list_reviews(
        self,
        repo_full_name: str,
        pr_number: int,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> List[PRReview]:
        """
        List pull request reviews.
        
        Args:
            repo_full_name: Repository full name
            pr_number: Pull request number
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            List of reviews
        """
        def _list_reviews():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                pr = repo.get_pull(pr_number)
                
                reviews = pr.get_reviews()
                result = []
                for review in reviews:
                    result.append(PRReview(
                        id=review.id,
                        state=review.state,
                        body=review.body,
                        author=review.user.login if review.user else None,
                        submitted_at=review.submitted_at.isoformat() if review.submitted_at else "",
                    ))
                return result
            except GithubException as e:
                logger.error(f"Error listing reviews for PR {pr_number}: {e}")
                raise
        
        return await asyncio.to_thread(_list_reviews)
    
    async def list_comments(
        self,
        repo_full_name: str,
        pr_number: int,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> List[PRComment]:
        """
        List pull request comments.
        
        Args:
            repo_full_name: Repository full name
            pr_number: Pull request number
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            List of comments
        """
        def _list_comments():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                issue = repo.get_issue(pr_number)
                
                comments = issue.get_comments()
                result = []
                for comment in comments:
                    result.append(PRComment(
                        id=comment.id,
                        body=comment.body,
                        author=comment.user.login if comment.user else None,
                        created_at=comment.created_at.isoformat() if comment.created_at else "",
                    ))
                return result
            except GithubException as e:
                logger.error(f"Error listing comments for PR {pr_number}: {e}")
                raise
        
        return await asyncio.to_thread(_list_comments)


_pr_manager: Optional[PRManager] = None


def get_pr_manager() -> PRManager:
    """Get PR manager instance."""
    global _pr_manager
    if _pr_manager is None:
        _pr_manager = PRManager()
    return _pr_manager


def set_pr_manager(manager: Optional[PRManager]) -> None:
    """Set PR manager instance (for testing)."""
    global _pr_manager
    _pr_manager = manager


__all__ = [
    "PRManager",
    "PullRequestInfo",
    "PRReview",
    "PRComment",
    "get_pr_manager",
    "set_pr_manager",
]

