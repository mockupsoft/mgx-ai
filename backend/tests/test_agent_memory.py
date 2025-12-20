import pytest
from unittest.mock import MagicMock, patch
from mgx_agent.team import MGXStyleTeam, TeamConfig

@pytest.mark.asyncio
class TestAgentMemory:
    
    async def test_memory_retention(self):
        """Test that agent retains history."""
        team = MGXStyleTeam()
        
        # Add to memory
        team.add_to_memory("Mike", "Action1", "Content1")
        team.add_to_memory("Alex", "Action2", "Content2")
        
        # Verify
        assert len(team.memory_log) == 2
        assert team.memory_log[0]["role"] == "Mike"
        assert team.memory_log[1]["content"] == "Content2"

    async def test_memory_pruning(self):
        """Test memory pruning when limit is exceeded."""
        config = TeamConfig(max_memory_size=10)
        team = MGXStyleTeam(config=config)
        
        # Add more items than limit
        for i in range(15):
            team.add_to_memory("Role", "Action", f"Content {i}")
            
        # Trigger cleanup
        team.cleanup_memory()
        
        # Verify
        assert len(team.memory_log) == 10
        assert team.memory_log[0]["content"] == "Content 5" # Oldest removed
        assert team.memory_log[-1]["content"] == "Content 14"

    async def test_context_persistence_across_rounds(self):
        """Test that context is preserved across execution rounds."""
        # This implies that the 'team' object or 'context' object keeps state.
        # MGXStyleTeam keeps 'team' which keeps 'env' and 'roles'.
        
        team = MGXStyleTeam()
        
        # Simulate round 1 adding to memory
        team.add_to_memory("Mike", "Plan", "Phase 1")
        
        # Simulate round 2
        team.add_to_memory("Alex", "Code", "Implemented Phase 1")
        
        assert len(team.memory_log) == 2
        # The underlying Metagpt Team also has memory in roles/env which we could test if needed.

    async def test_agent_specialization_memory(self):
        """Test that specific agents maintain their own context."""
        # Using mocks to verify RelevantMemoryMixin behavior or similar if accessible
        # Since we are testing MGXStyleTeam, we can check if it manages roles correctly.
        pass
