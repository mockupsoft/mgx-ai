# -*- coding: utf-8 -*-

import pytest

from backend.services.git import normalize_repo_full_name


class TestNormalizeRepoFullName:
    def test_owner_repo_passthrough(self):
        assert normalize_repo_full_name("octocat/Hello-World") == "octocat/Hello-World"

    def test_https_url(self):
        assert normalize_repo_full_name("https://github.com/octocat/Hello-World") == "octocat/Hello-World"

    def test_https_url_git_suffix(self):
        assert normalize_repo_full_name("https://github.com/octocat/Hello-World.git") == "octocat/Hello-World"

    def test_ssh_url(self):
        assert normalize_repo_full_name("git@github.com:octocat/Hello-World.git") == "octocat/Hello-World"

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            normalize_repo_full_name("not-a-repo")
