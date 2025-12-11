# -*- coding: utf-8 -*-
"""
Example end-to-end tests for TEM Agent.

E2E tests verify complete workflows from start to finish.
"""

import pytest
from tests.helpers import create_fake_team


@pytest.mark.e2e
class TestFullPipeline:
    """End-to-end tests for complete workflows."""
    
    def test_team_creation_and_role_hiring(self):
        """Test complete team setup workflow."""
        team = create_fake_team(
            name="TestTeam",
            role_names=["Mike", "Alex", "Bob", "Charlie"]
        )
        
        assert team.name == "TestTeam"
        assert len(team.roles) == 4
        assert all(role.name in team.roles for role in team.roles.values())
