# -*- coding: utf-8 -*-
"""
Example integration tests for TEM Agent.

Integration tests verify how multiple components work together.
"""

import pytest
from tests.helpers import (
    create_fake_team,
    create_fake_role,
)


@pytest.mark.integration
class TestTeamIntegration:
    """Integration tests for team and roles."""
    
    def test_team_with_multiple_roles(self):
        """Test team with multiple roles."""
        team = create_fake_team(num_roles=3)
        
        assert len(team.roles) == 3
        for role in team.roles.values():
            assert role is not None
    
    def test_role_integration_with_team(self, fake_team):
        """Test role integration with team."""
        role = create_fake_role(name="Engineer", num_actions=2)
        
        fake_team.hire(role)
        
        assert fake_team.get_role("Engineer") is not None
        assert len(fake_team.roles) >= 4
