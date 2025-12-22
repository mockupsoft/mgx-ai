# -*- coding: utf-8 -*-
"""GitHub Activity feed service.

Combines commits, pull requests, and issues into a unified activity timeline.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

from backend.services.git import GitService, get_git_service
from backend.services.github.pr_manager import PRManager, get_pr_manager
from backend.services.github.issues_manager import IssuesManager, get_issues_manager

logger = logging.getLogger(__name__)


@dataclass
class ActivityEvent:
    """Activity event in the feed."""
    id: str
    type: str  # commit, pull_request, issue, issue_comment, pr_review
    timestamp: str
    actor: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ActivityFeed:
    """Generates unified activity feed from GitHub events."""
    
    def __init__(
        self,
        git_service: Optional[GitService] = None,
        pr_manager: Optional[PRManager] = None,
        issues_manager: Optional[IssuesManager] = None,
    ):
        """
        Initialize Activity feed.
        
        Args:
            git_service: Git service instance
            pr_manager: PR manager instance
            issues_manager: Issues manager instance
        """
        self._git_service = git_service or get_git_service()
        self._pr_manager = pr_manager or get_pr_manager()
        self._issues_manager = issues_manager or get_issues_manager()
    
    def _get_github_api(self, installation_id: Optional[int] = None, token_override: Optional[str] = None):
        """Get GitHub API instance."""
        from github import Github
        from github.GithubException import GithubException
        
        token = self._git_service._resolve_token(installation_id=installation_id, token_override=token_override)
        return Github(login_or_token=token), GithubException
    
    async def get_commit_history(
        self,
        repo_full_name: str,
        branch: str = "main",
        limit: int = 50,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> List[ActivityEvent]:
        """
        Get commit history as activity events.
        
        Args:
            repo_full_name: Repository full name
            branch: Branch name
            limit: Maximum number of commits
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            List of commit activity events
        """
        def _get_commits():
            gh, GithubException = self._get_github_api(installation_id, token_override)
            try:
                repo = gh.get_repo(repo_full_name)
                branch_ref = repo.get_branch(branch)
                commits = repo.get_commits(sha=branch_ref.commit.sha)
                
                result = []
                count = 0
                for commit in commits:
                    if count >= limit:
                        break
                    
                    result.append(ActivityEvent(
                        id=f"commit_{commit.sha}",
                        type="commit",
                        timestamp=commit.commit.author.date.isoformat() if commit.commit.author.date else "",
                        actor=commit.commit.author.name if commit.commit.author else None,
                        title=commit.commit.message.split("\n")[0] if commit.commit.message else None,
                        body=commit.commit.message,
                        url=commit.html_url,
                        metadata={
                            "sha": commit.sha,
                            "branch": branch,
                        },
                    ))
                    count += 1
                
                return result
            except GithubException as e:
                logger.error(f"Error getting commit history: {e}")
                raise
        
        return await asyncio.to_thread(_get_commits)
    
    async def get_activity_feed(
        self,
        repo_full_name: str,
        limit: int = 50,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> List[ActivityEvent]:
        """
        Get combined activity feed (commits, PRs, issues).
        
        Args:
            repo_full_name: Repository full name
            limit: Maximum number of events
            installation_id: GitHub App installation ID
            token_override: Override token
        
        Returns:
            Combined activity events sorted by timestamp
        """
        # Fetch commits, PRs, and issues in parallel
        commits, prs, issues = await asyncio.gather(
            self.get_commit_history(repo_full_name, limit=limit, installation_id=installation_id, token_override=token_override),
            self._get_pr_events(repo_full_name, limit=limit, installation_id=installation_id, token_override=token_override),
            self._get_issue_events(repo_full_name, limit=limit, installation_id=installation_id, token_override=token_override),
            return_exceptions=True,
        )
        
        # Handle exceptions
        if isinstance(commits, Exception):
            logger.error(f"Error fetching commits: {commits}")
            commits = []
        if isinstance(prs, Exception):
            logger.error(f"Error fetching PRs: {prs}")
            prs = []
        if isinstance(issues, Exception):
            logger.error(f"Error fetching issues: {issues}")
            issues = []
        
        # Combine and sort by timestamp
        all_events = list(commits) + list(prs) + list(issues)
        all_events.sort(key=lambda e: e.timestamp, reverse=True)
        
        return all_events[:limit]
    
    async def _get_pr_events(
        self,
        repo_full_name: str,
        limit: int = 50,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> List[ActivityEvent]:
        """Get PR events as activity events."""
        prs = await self._pr_manager.list_pull_requests(
            repo_full_name=repo_full_name,
            state="all",
            installation_id=installation_id,
            token_override=token_override,
        )
        
        events = []
        for pr in prs[:limit]:
            events.append(ActivityEvent(
                id=f"pr_{pr.number}",
                type="pull_request",
                timestamp=pr.updated_at,
                actor=pr.author,
                title=f"PR #{pr.number}: {pr.title}",
                body=pr.body,
                url=pr.html_url,
                metadata={
                    "number": pr.number,
                    "state": pr.state,
                    "head_branch": pr.head_branch,
                    "base_branch": pr.base_branch,
                },
            ))
        
        return events
    
    async def _get_issue_events(
        self,
        repo_full_name: str,
        limit: int = 50,
        installation_id: Optional[int] = None,
        token_override: Optional[str] = None,
    ) -> List[ActivityEvent]:
        """Get issue events as activity events."""
        issues = await self._issues_manager.list_issues(
            repo_full_name=repo_full_name,
            state="all",
            installation_id=installation_id,
            token_override=token_override,
        )
        
        events = []
        for issue in issues[:limit]:
            events.append(ActivityEvent(
                id=f"issue_{issue.number}",
                type="issue",
                timestamp=issue.updated_at,
                actor=issue.author,
                title=f"Issue #{issue.number}: {issue.title}",
                body=issue.body,
                url=issue.html_url,
                metadata={
                    "number": issue.number,
                    "state": issue.state,
                    "labels": issue.labels or [],
                },
            ))
        
        return events


_activity_feed: Optional[ActivityFeed] = None


def get_activity_feed() -> ActivityFeed:
    """Get Activity feed instance."""
    global _activity_feed
    if _activity_feed is None:
        _activity_feed = ActivityFeed()
    return _activity_feed


def set_activity_feed(feed: Optional[ActivityFeed]) -> None:
    """Set Activity feed instance (for testing)."""
    global _activity_feed
    _activity_feed = feed


__all__ = [
    "ActivityFeed",
    "ActivityEvent",
    "get_activity_feed",
    "set_activity_feed",
]

