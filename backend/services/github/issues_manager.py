# -*- coding: utf-8 -*-
"""GitHub Issues management service."""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from backend.services.git import GitService, get_git_service
from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class IssueInfo:
    """Issue information."""
    number: int
    title: str
    body: str
    state: str  # open, closed
    html_url: str
    created_at: str
    updated_at: str
    closed_at: Optional[str] = None
    author: Optional[str] = None
    labels: List[str] = field(default_factory=list)
    assignees: List[str] = field(default_factory=list)
    comment_count: int = 0


@dataclass
class IssueComment:
    """Issue comment."""
    id: int
    body: str
    author: str
    created_at: str
    updated_at: Optional[str] = None


class IssuesManager:
    """Manages GitHub Issues."""
    
    def __init__(self, git_service: Optional[GitService] = None):
        """
        Initialize Issues manager.
        
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
    
    async def list_issues(
        self,
        repo_full_name: str,
        state: str = "open",  # open, closed, all
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> List[IssueInfo]:
        """
        List issues for a repository.
        
        Args:
            repo_full_name: Repository full name (owner/repo)
            state: Issue state filter (open, closed, all)
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            List of issue info
        """
        def _list_issues():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                issues = repo.get_issues(state=state, sort="updated", direction="desc")
                
                result = []
                for issue in issues:
                    # Skip pull requests (they have pull_request attribute)
                    if hasattr(issue, 'pull_request') and issue.pull_request:
                        continue
                    
                    labels = [label.name for label in issue.labels] if issue.labels else []
                    assignees = [assignee.login for assignee in issue.assignees] if issue.assignees else []
                    result.append(IssueInfo(
                        number=issue.number,
                        title=issue.title,
                        body=issue.body or "",
                        state=issue.state,
                        html_url=issue.html_url,
                        created_at=issue.created_at.isoformat() if issue.created_at else "",
                        updated_at=issue.updated_at.isoformat() if issue.updated_at else "",
                        closed_at=issue.closed_at.isoformat() if issue.closed_at else None,
                        author=issue.user.login if issue.user else None,
                        labels=labels,
                        assignees=assignees,
                        comment_count=issue.comments,
                    ))
                return result
            except GithubException as e:
                logger.error(f"Error listing issues: {e}")
                raise
        
        return await asyncio.to_thread(_list_issues)
    
    async def get_issue(
        self,
        repo_full_name: str,
        issue_number: int,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> IssueInfo:
        """
        Get issue details.
        
        Args:
            repo_full_name: Repository full name
            issue_number: Issue number
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Issue info
        """
        def _get_issue():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                issue = repo.get_issue(issue_number)
                
                labels = [label.name for label in issue.labels] if issue.labels else []
                assignees = [assignee.login for assignee in issue.assignees] if issue.assignees else []
                return IssueInfo(
                    number=issue.number,
                    title=issue.title,
                    body=issue.body or "",
                    state=issue.state,
                    html_url=issue.html_url,
                    created_at=issue.created_at.isoformat() if issue.created_at else "",
                    updated_at=issue.updated_at.isoformat() if issue.updated_at else "",
                    closed_at=issue.closed_at.isoformat() if issue.closed_at else None,
                    author=issue.user.login if issue.user else None,
                    labels=labels,
                    assignees=assignees,
                    comment_count=issue.comments,
                )
            except GithubException as e:
                logger.error(f"Error getting issue {issue_number}: {e}")
                raise
        
        return await asyncio.to_thread(_get_issue)
    
    async def create_issue(
        self,
        repo_full_name: str,
        title: str,
        body: Optional[str] = None,
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> IssueInfo:
        """
        Create an issue.
        
        Args:
            repo_full_name: Repository full name
            title: Issue title
            body: Issue body
            labels: Issue labels
            assignees: Issue assignees
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Created issue info
        """
        def _create_issue():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                issue = repo.create_issue(
                    title=title,
                    body=body or "",
                    labels=labels or [],
                    assignees=assignees or [],
                )
                
                labels_list = [label.name for label in issue.labels] if issue.labels else []
                assignees_list = [assignee.login for assignee in issue.assignees] if issue.assignees else []
                return IssueInfo(
                    number=issue.number,
                    title=issue.title,
                    body=issue.body or "",
                    state=issue.state,
                    html_url=issue.html_url,
                    created_at=issue.created_at.isoformat() if issue.created_at else "",
                    updated_at=issue.updated_at.isoformat() if issue.updated_at else "",
                    closed_at=issue.closed_at.isoformat() if issue.closed_at else None,
                    author=issue.user.login if issue.user else None,
                    labels=labels_list,
                    assignees=assignees_list,
                    comment_count=issue.comments,
                )
            except GithubException as e:
                logger.error(f"Error creating issue: {e}")
                raise
        
        return await asyncio.to_thread(_create_issue)
    
    async def update_issue(
        self,
        repo_full_name: str,
        issue_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        state: Optional[str] = None,  # open, closed
        labels: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> IssueInfo:
        """
        Update an issue.
        
        Args:
            repo_full_name: Repository full name
            issue_number: Issue number
            title: New title
            body: New body
            state: New state (open, closed)
            labels: New labels
            assignees: New assignees
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Updated issue info
        """
        def _update_issue():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                issue = repo.get_issue(issue_number)
                
                if title is not None:
                    issue.edit(title=title)
                if body is not None:
                    issue.edit(body=body)
                if state is not None:
                    if state == "closed":
                        issue.edit(state="closed")
                    elif state == "open":
                        issue.edit(state="open")
                if labels is not None:
                    issue.edit(labels=labels)
                if assignees is not None:
                    issue.edit(assignees=assignees)
                
                # Reload issue to get updated data
                issue = repo.get_issue(issue_number)
                
                labels_list = [label.name for label in issue.labels] if issue.labels else []
                assignees_list = [assignee.login for assignee in issue.assignees] if issue.assignees else []
                return IssueInfo(
                    number=issue.number,
                    title=issue.title,
                    body=issue.body or "",
                    state=issue.state,
                    html_url=issue.html_url,
                    created_at=issue.created_at.isoformat() if issue.created_at else "",
                    updated_at=issue.updated_at.isoformat() if issue.updated_at else "",
                    closed_at=issue.closed_at.isoformat() if issue.closed_at else None,
                    author=issue.user.login if issue.user else None,
                    labels=labels_list,
                    assignees=assignees_list,
                    comment_count=issue.comments,
                )
            except GithubException as e:
                logger.error(f"Error updating issue {issue_number}: {e}")
                raise
        
        return await asyncio.to_thread(_update_issue)
    
    async def close_issue(
        self,
        repo_full_name: str,
        issue_number: int,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> IssueInfo:
        """
        Close an issue.
        
        Args:
            repo_full_name: Repository full name
            issue_number: Issue number
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Closed issue info
        """
        return await self.update_issue(
            repo_full_name=repo_full_name,
            issue_number=issue_number,
            state="closed",
            installation_id=installation_id,
            token_override=token_override,
        )
    
    async def create_comment(
        self,
        repo_full_name: str,
        issue_number: int,
        body: str,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> IssueComment:
        """
        Create an issue comment.
        
        Args:
            repo_full_name: Repository full name
            issue_number: Issue number
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
                issue = repo.get_issue(issue_number)
                comment = issue.create_comment(body)
                
                return IssueComment(
                    id=comment.id,
                    body=comment.body,
                    author=comment.user.login if comment.user else None,
                    created_at=comment.created_at.isoformat() if comment.created_at else "",
                    updated_at=comment.updated_at.isoformat() if comment.updated_at else None,
                )
            except GithubException as e:
                logger.error(f"Error creating comment for issue {issue_number}: {e}")
                raise
        
        return await asyncio.to_thread(_create_comment)
    
    async def list_comments(
        self,
        repo_full_name: str,
        issue_number: int,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> List[IssueComment]:
        """
        List issue comments.
        
        Args:
            repo_full_name: Repository full name
            issue_number: Issue number
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            List of comments
        """
        def _list_comments():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                issue = repo.get_issue(issue_number)
                
                comments = issue.get_comments()
                result = []
                for comment in comments:
                    result.append(IssueComment(
                        id=comment.id,
                        body=comment.body,
                        author=comment.user.login if comment.user else None,
                        created_at=comment.created_at.isoformat() if comment.created_at else "",
                        updated_at=comment.updated_at.isoformat() if comment.updated_at else None,
                    ))
                return result
            except GithubException as e:
                logger.error(f"Error listing comments for issue {issue_number}: {e}")
                raise
        
        return await asyncio.to_thread(_list_comments)


_issues_manager: Optional[IssuesManager] = None


def get_issues_manager() -> IssuesManager:
    """Get Issues manager instance."""
    global _issues_manager
    if _issues_manager is None:
        _issues_manager = IssuesManager()
    return _issues_manager


def set_issues_manager(manager: Optional[IssuesManager]) -> None:
    """Set Issues manager instance (for testing)."""
    global _issues_manager
    _issues_manager = manager


__all__ = [
    "IssuesManager",
    "IssueInfo",
    "IssueComment",
    "get_issues_manager",
    "set_issues_manager",
]

