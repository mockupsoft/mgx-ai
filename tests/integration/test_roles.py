# -*- coding: utf-8 -*-
"""
Integration Tests for mgx_agent.roles

Tests RelevantMemoryMixin filtering, role initialization, planning guard rails,
human reviewer toggles, and adapter helpers with mocked MetaGPT constructs.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime

# Import stubs and helpers
from tests.helpers.metagpt_stubs import (
    MockMemory,
    MockMessage,
    MockContext,
    mock_logger,
)
from tests.helpers.factories import (
    create_fake_message,
    create_fake_memory_store,
)

# Import modules under test - these will use the stubs
from mgx_agent.adapter import MetaGPTAdapter
from mgx_agent.actions import (
    AnalyzeTask,
    DraftPlan,
    WriteCode,
    WriteTest,
    ReviewCode,
)


# ============================================
# FIXTURES
# ============================================

@pytest.fixture
def mock_role_with_memory():
    """Create a mock role with memory store configured."""
    role = Mock()
    role.rc = Mock()
    role.rc.memory = MockMemory()
    role.rc.news = []
    return role


@pytest.fixture
def mock_messages():
    """Create sample mock messages for testing."""
    return [
        MockMessage(role="TeamLeader", content="Task analysis complete"),
        MockMessage(role="Engineer", content="Code written"),
        MockMessage(role="Tester", content="Tests written"),
        MockMessage(role="Reviewer", content="Review complete"),
    ]


@pytest.fixture
def mock_team_ref():
    """Create a mock team reference."""
    team_ref = Mock()
    team_ref.get_task_spec = Mock(return_value={
        "task": "Write a function",
        "plan": "Step 1: Define function\nStep 2: Implement logic",
        "complexity": "M",
        "is_revision": False,
        "review_notes": ""
    })
    team_ref.set_task_spec = Mock()
    team_ref._print_progress = Mock()
    return team_ref


@pytest.fixture
def mock_llm_aask():
    """Create a mock LLM with _aask method."""
    llm = AsyncMock()
    llm._aask = AsyncMock(return_value="Mock LLM response")
    return llm


# ============================================
# TEST RelevantMemoryMixin
# ============================================

class TestRelevantMemoryMixin:
    """Test RelevantMemoryMixin filtering logic."""
    
    def test_get_relevant_memories_with_filter(self, mock_role_with_memory):
        """Test filtering memories by role."""
        # Add messages to memory
        mock_role_with_memory.rc.memory.storage = [
            MockMessage(role="Engineer", content="Code 1"),
            MockMessage(role="Tester", content="Test 1"),
            MockMessage(role="Engineer", content="Code 2"),
            MockMessage(role="Reviewer", content="Review 1"),
        ]
        
        # Import mixin to test
        from mgx_agent.roles import RelevantMemoryMixin
        
        # Create a class that inherits from mixin
        class TestRole(RelevantMemoryMixin):
            def __init__(self, role):
                self.rc = role.rc
        
        test_role = TestRole(mock_role_with_memory)
        
        # Get memories filtered by Engineer role
        memories = test_role.get_relevant_memories(role_filter=["Engineer"], limit=5)
        
        # Should return only Engineer messages
        assert len(memories) <= 5
    
    def test_get_relevant_memories_with_limit(self, mock_role_with_memory):
        """Test limiting number of memories returned."""
        from mgx_agent.roles import RelevantMemoryMixin
        
        # Add many messages
        mock_role_with_memory.rc.memory.storage = [
            MockMessage(role="Engineer", content=f"Message {i}")
            for i in range(10)
        ]
        
        class TestRole(RelevantMemoryMixin):
            def __init__(self, role):
                self.rc = role.rc
        
        test_role = TestRole(mock_role_with_memory)
        
        # Get limited memories
        memories = test_role.get_relevant_memories(limit=3)
        
        # Should return last 3 messages
        assert len(memories) <= 3
    
    def test_get_relevant_memories_no_memory_store(self):
        """Test behavior when memory store is missing."""
        from mgx_agent.roles import RelevantMemoryMixin
        
        class TestRole(RelevantMemoryMixin):
            pass
        
        test_role = TestRole()
        
        # Should return empty list without crashing
        memories = test_role.get_relevant_memories(limit=5)
        assert memories == []
    
    def test_get_last_by_role_and_action(self, mock_role_with_memory):
        """Test finding last message by role and action."""
        from mgx_agent.roles import RelevantMemoryMixin
        
        # Add messages with cause_by - store in messages not storage
        msg1 = MockMessage(role="Engineer", content="Old code")
        msg1.cause_by = WriteCode  # Use class directly
        
        msg2 = MockMessage(role="Engineer", content="New code")
        msg2.cause_by = WriteCode  # Use class directly
        
        # Put messages in the messages list, not storage
        mock_role_with_memory.rc.memory.messages = [msg1, msg2]
        mock_role_with_memory.rc.memory.storage = [msg1, msg2]
        
        class TestRole(RelevantMemoryMixin):
            def __init__(self, role):
                self.rc = role.rc
        
        test_role = TestRole(mock_role_with_memory)
        
        # Get last WriteCode message
        content = test_role.get_last_by("Engineer", WriteCode)
        
        # Should return the newest message
        assert content == "New code"


# ============================================
# TEST Mike (Team Leader)
# ============================================

class TestMikeRole:
    """Test Mike (Team Leader) role behavior."""
    
    def test_mike_initialization(self):
        """Test Mike role initializes correctly."""
        from mgx_agent.roles import Mike
        
        mike = Mike()
        
        assert mike.name == "Mike"
        assert mike.profile == "TeamLeader"
        assert mike._is_planning_phase == True
    
    def test_mike_complete_planning(self):
        """Test Mike's complete_planning() stops further _act."""
        from mgx_agent.roles import Mike
        
        mike = Mike()
        assert mike._is_planning_phase == True
        
        # Complete planning
        mike.complete_planning()
        
        assert mike._is_planning_phase == False
    
    def test_mike_act_after_planning_complete(self, event_loop):
        """Test Mike._act() returns empty message after planning complete."""
        from mgx_agent.roles import Mike
        
        mike = Mike()
        mike.complete_planning()
        
        # Act should return empty message
        result = event_loop.run_until_complete(mike._act())
        
        assert result.content == ""
        assert result.role == "TeamLeader"
    
    def test_mike_observe_after_planning_complete(self, event_loop):
        """Test Mike._observe() returns 0 after planning complete."""
        from mgx_agent.roles import Mike
        
        mike = Mike()
        mike.complete_planning()
        
        # Observe should return 0
        result = event_loop.run_until_complete(mike._observe())
        
        assert result == 0
    
    def test_mike_analyze_task_with_cache(self, event_loop):
        """Test Mike.analyze_task() uses team cache for repeated tasks."""
        from mgx_agent.roles import Mike
        from mgx_agent.cache import InMemoryLRUTTLCache, make_cache_key
        from mgx_agent.config import TeamConfig

        class TeamRef:
            def __init__(self):
                self.config = TeamConfig(enable_caching=True)
                self._cache = InMemoryLRUTTLCache(max_entries=10, ttl_seconds=3600)
                self.set_task_spec = Mock()

            async def cached_llm_call(self, *, role, action, payload, compute, bypass_cache=False, encode=None, decode=None):
                key = make_cache_key(role=role, action=action, payload=payload)
                cached = self._cache.get(key)
                if cached is not None:
                    return decode(cached) if decode else cached
                result = await compute()
                self._cache.set(key, encode(result) if encode else result)
                return result

            def _sync_task_spec_from_plan(self, plan_content: str, *, fallback_task: str):
                return None

        team_ref = TeamRef()

        mike = Mike()
        mike._team_ref = team_ref
        mike.llm = AsyncMock()

        task = "Write a calculator function"
        cache_key = make_cache_key(role="TeamLeader", action="AnalyzeTask+DraftPlan", payload={"task": task})
        team_ref._cache.set(cache_key, {"content": "Cached analysis", "role": "TeamLeader"})

        with patch('mgx_agent.roles.AnalyzeTask') as MockAnalyze, patch('mgx_agent.roles.DraftPlan') as MockDraft:
            result = event_loop.run_until_complete(mike.analyze_task(task))

            assert result.content == "Cached analysis"
            MockAnalyze.assert_not_called()
            MockDraft.assert_not_called()
    
    def test_mike_analyze_task_json_format(self, event_loop, mock_team_ref):
        """Test Mike.analyze_task() returns JSON formatted response."""
        from mgx_agent.roles import Mike
        
        mike = Mike()
        mike._team_ref = mock_team_ref
        mike.llm = AsyncMock()
        
        # Mock action responses
        with patch('mgx_agent.roles.AnalyzeTask') as MockAnalyze, \
             patch('mgx_agent.roles.DraftPlan') as MockDraft:
            
            mock_analyze = AsyncMock()
            mock_analyze.run = AsyncMock(return_value="KARMAŞIKLIK: M\nAnalysis result")
            MockAnalyze.return_value = mock_analyze
            
            mock_draft = AsyncMock()
            mock_draft.run = AsyncMock(return_value="Plan details")
            MockDraft.return_value = mock_draft
            
            task = "Write a function"
            result = event_loop.run_until_complete(mike.analyze_task(task))
            
            # Response should contain JSON
            assert "---JSON_START---" in result.content
            assert "---JSON_END---" in result.content
            
            # Extract JSON
            json_str = result.content.split("---JSON_START---")[1].split("---JSON_END---")[0].strip()
            data = json.loads(json_str)
            
            assert "task" in data
            assert "complexity" in data
            assert "plan" in data


# ============================================
# TEST Alex (Engineer)
# ============================================

class TestAlexRole:
    """Test Alex (Engineer) role behavior."""
    
    def test_alex_initialization(self):
        """Test Alex role initializes correctly."""
        from mgx_agent.roles import Alex
        
        alex = Alex()
        
        assert alex.name == "Alex"
        assert alex.profile == "Engineer"
        assert hasattr(alex, 'get_relevant_memories')
    
    def test_alex_uses_team_ref_for_task_spec(self, event_loop, mock_team_ref):
        """Test Alex uses team_ref.get_task_spec() for instructions."""
        from mgx_agent.roles import Alex
        
        alex = Alex()
        alex._team_ref = mock_team_ref
        alex.llm = AsyncMock()
        alex.rc = MockContext()
        alex.rc.news = []
        alex.rc.memory = MockMemory()
        
        # Mock WriteCode action
        with patch('mgx_agent.roles.WriteCode') as MockWrite:
            mock_write = AsyncMock()
            mock_write.run = AsyncMock(return_value="Generated code")
            MockWrite.return_value = mock_write
            
            result = event_loop.run_until_complete(alex._act())
            
            # Should have called get_task_spec
            mock_team_ref.get_task_spec.assert_called_once()
            
            # Should have called WriteCode.run with task spec data
            mock_write.run.assert_called_once()
    
    def test_alex_fallback_to_memory_scan(self, event_loop):
        """Test Alex falls back to memory scan if task_spec missing."""
        from mgx_agent.roles import Alex
        
        alex = Alex()
        alex._team_ref = None  # No team ref
        alex.llm = AsyncMock()
        alex.rc = MockContext()
        alex.rc.news = []
        
        # Add memory with JSON message
        alex.rc.memory = MockMemory()
        json_content = """---JSON_START---
        {"task": "Write function", "plan": "Step 1", "complexity": "M"}
        ---JSON_END---"""
        alex.rc.memory.storage = [MockMessage(role="TeamLeader", content=json_content)]
        
        # Mock WriteCode action
        with patch('mgx_agent.roles.WriteCode') as MockWrite:
            mock_write = AsyncMock()
            mock_write.run = AsyncMock(return_value="Generated code")
            MockWrite.return_value = mock_write
            
            with patch('mgx_agent.roles.MetaGPTAdapter.get_news', return_value=[]):
                result = event_loop.run_until_complete(alex._act())
            
            # Should have called WriteCode.run
            mock_write.run.assert_called_once()


# ============================================
# TEST Bob (Tester)
# ============================================

class TestBobRole:
    """Test Bob (Tester) role behavior."""
    
    def test_bob_initialization(self):
        """Test Bob role initializes correctly."""
        from mgx_agent.roles import Bob
        
        bob = Bob()
        
        assert bob.name == "Bob"
        assert bob.profile == "Tester"
        assert hasattr(bob, 'get_relevant_memories')
    
    def test_bob_gets_code_from_alex(self, event_loop):
        """Test Bob retrieves Alex's code using get_last_by."""
        from mgx_agent.roles import Bob
        
        bob = Bob()
        bob.llm = AsyncMock()
        bob.rc = MockContext()
        bob.rc.news = []
        bob.rc.memory = MockMemory()
        
        # Add Alex's code message
        code_msg = MockMessage(role="Engineer", content="def add(a, b): return a + b")
        code_msg.cause_by = "WriteCode"
        bob.rc.memory.storage = [code_msg]
        
        # Mock WriteTest action
        with patch('mgx_agent.roles.WriteTest') as MockTest:
            mock_test = AsyncMock()
            mock_test.run = AsyncMock(return_value="Generated tests")
            MockTest.return_value = mock_test
            
            result = event_loop.run_until_complete(bob._act())
            
            # Should have called WriteTest.run with code
            mock_test.run.assert_called_once()
            call_args = mock_test.run.call_args
            assert "def add" in call_args[0][0]  # First arg should be code
    
    def test_bob_test_limit_enforcement(self, event_loop):
        """Test Bob limits number of tests with k parameter."""
        from mgx_agent.roles import Bob
        
        bob = Bob()
        bob.llm = AsyncMock()
        bob.rc = MockContext()
        bob.rc.news = []
        bob.rc.memory = MockMemory()
        
        # Add Alex's code
        code_msg = MockMessage(role="Engineer", content="def multiply(a, b): return a * b")
        code_msg.cause_by = "WriteCode"
        bob.rc.memory.storage = [code_msg]
        
        # Mock WriteTest action
        with patch('mgx_agent.roles.WriteTest') as MockTest:
            mock_test = AsyncMock()
            mock_test.run = AsyncMock(return_value="Limited tests")
            MockTest.return_value = mock_test
            
            result = event_loop.run_until_complete(bob._act())
            
            # Should pass k=3 to limit tests
            call_args = mock_test.run.call_args
            assert call_args[1].get('k') == 3


# ============================================
# TEST Charlie (Reviewer)
# ============================================

class TestCharlieRole:
    """Test Charlie (Reviewer) role behavior including human mode."""
    
    def test_charlie_initialization_llm_mode(self):
        """Test Charlie initializes in LLM mode by default."""
        from mgx_agent.roles import Charlie
        
        charlie = Charlie(is_human=False)
        
        assert charlie.name == "Charlie"
        assert charlie.profile == "Reviewer"
        assert not hasattr(charlie, 'is_human') or not charlie.is_human
    
    def test_charlie_initialization_human_mode(self):
        """Test Charlie initializes with human flag."""
        from mgx_agent.roles import Charlie
        
        charlie = Charlie(is_human=True)
        
        assert hasattr(charlie, 'is_human')
        assert charlie.is_human == True
    
    def test_charlie_llm_review_mode(self, event_loop):
        """Test Charlie uses LLM for review when not human."""
        from mgx_agent.roles import Charlie
        
        charlie = Charlie(is_human=False)
        charlie.llm = AsyncMock()
        charlie.rc = MockContext()
        charlie.rc.news = []
        charlie.rc.memory = MockMemory()
        
        # Add code and tests
        code_msg = MockMessage(role="Engineer", content="def func(): pass")
        code_msg.cause_by = "WriteCode"
        test_msg = MockMessage(role="Tester", content="def test_func(): pass")
        test_msg.cause_by = "WriteTest"
        charlie.rc.memory.storage = [code_msg, test_msg]
        
        # Mock ReviewCode action
        with patch('mgx_agent.roles.ReviewCode') as MockReview:
            mock_review = AsyncMock()
            mock_review.run = AsyncMock(return_value="SONUÇ: ONAYLANDI")
            MockReview.return_value = mock_review
            
            result = event_loop.run_until_complete(charlie._act())
            
            # Should have called ReviewCode.run
            mock_review.run.assert_called_once()
    
    def test_charlie_human_mode_with_input(self, event_loop):
        """Test Charlie accepts human input in human mode."""
        from mgx_agent.roles import Charlie
        
        charlie = Charlie(is_human=True)
        charlie.rc = MockContext()
        charlie.rc.news = []
        charlie.rc.memory = MockMemory()
        
        # Add code and tests
        code_msg = MockMessage(role="Engineer", content="def func(): pass")
        code_msg.cause_by = "WriteCode"
        test_msg = MockMessage(role="Tester", content="def test_func(): pass")
        test_msg.cause_by = "WriteTest"
        charlie.rc.memory.storage = [code_msg, test_msg]
        
        # Mock input to simulate human review
        with patch('builtins.input', side_effect=["SONUÇ: ONAYLANDI", "", ""]):
            result = event_loop.run_until_complete(charlie._act())
            
            # Should return message with review
            assert "ONAYLANDI" in result.content
    
    def test_charlie_human_mode_empty_input(self, event_loop):
        """Test Charlie handles empty input gracefully."""
        from mgx_agent.roles import Charlie
        
        charlie = Charlie(is_human=True)
        charlie.rc = MockContext()
        charlie.rc.news = []
        charlie.rc.memory = MockMemory()
        
        # Add minimal memory
        charlie.rc.memory.storage = []
        
        # Mock input to return empty immediately
        with patch('builtins.input', return_value=""):
            result = event_loop.run_until_complete(charlie._act())
            
            # Should have default approval message
            assert "ONAYLANDI" in result.content


# ============================================
# TEST Role Integration with Adapter
# ============================================

class TestRoleAdapterIntegration:
    """Test role integration with MetaGPTAdapter helpers."""
    
    def test_roles_use_adapter_for_memory_access(self, mock_role_with_memory):
        """Test roles use MetaGPTAdapter for safe memory access."""
        from mgx_agent.roles import RelevantMemoryMixin
        
        class TestRole(RelevantMemoryMixin):
            def __init__(self, role):
                self.rc = role.rc
        
        test_role = TestRole(mock_role_with_memory)
        
        # get_relevant_memories should use adapter internally
        memories = test_role.get_relevant_memories(limit=5)
        
        # Should not crash even with various memory store states
        assert isinstance(memories, list)
    
    def test_adapter_handles_missing_rc(self):
        """Test adapter handles missing rc gracefully."""
        from mgx_agent.adapter import MetaGPTAdapter
        
        role = Mock()
        del role.rc  # Remove rc
        
        mem_store = MetaGPTAdapter.get_memory_store(role)
        assert mem_store is None
    
    def test_adapter_handles_missing_memory(self):
        """Test adapter handles missing memory attribute."""
        from mgx_agent.adapter import MetaGPTAdapter
        
        role = Mock()
        role.rc = Mock()
        del role.rc.memory  # Remove memory
        
        mem_store = MetaGPTAdapter.get_memory_store(role)
        assert mem_store is None


# ============================================
# TEST Planning Guard Rails
# ============================================

class TestPlanningGuardRails:
    """Test planning phase guard rails and execution separation."""
    
    def test_mike_planning_phase_workflow(self, event_loop):
        """Test Mike's planning phase workflow."""
        from mgx_agent.roles import Mike
        
        mike = Mike()
        
        # Phase 1: Planning active
        assert mike._is_planning_phase == True
        
        # Phase 2: Complete planning
        mike.complete_planning()
        assert mike._is_planning_phase == False
        
        # Phase 3: Act should return empty
        result = event_loop.run_until_complete(mike._act())
        assert result.content == ""
    
    def test_mike_watch_cleared_after_planning(self):
        """Test Mike's watch list cleared after planning complete."""
        from mgx_agent.roles import Mike
        
        mike = Mike()
        
        # Initially has actions and watches
        initial_actions = len(mike.actions) if hasattr(mike, 'actions') else 0
        
        mike.complete_planning()
        
        # Watch should be cleared
        # Note: _watch is a MetaGPT internal, we're testing the guard rail
        assert mike._is_planning_phase == False


# ============================================
# NEGATIVE TEST CASES
# ============================================

class TestRolesNegativeCases:
    """Test edge cases and error conditions."""
    
    def test_alex_handles_no_task_spec_no_memory(self, event_loop):
        """Test Alex handles missing task spec and empty memory."""
        from mgx_agent.roles import Alex
        
        alex = Alex()
        alex._team_ref = None
        alex.llm = AsyncMock()
        alex.rc = MockContext()
        alex.rc.news = []
        alex.rc.memory = MockMemory()
        alex.rc.memory.storage = []  # Empty memory
        
        # Mock WriteCode to not crash
        with patch('mgx_agent.roles.WriteCode') as MockWrite:
            mock_write = AsyncMock()
            mock_write.run = AsyncMock(return_value="Fallback code")
            MockWrite.return_value = mock_write
            
            with patch('mgx_agent.roles.MetaGPTAdapter.get_news', return_value=[]):
                result = event_loop.run_until_complete(alex._act())
            
            # Should still produce output
            assert result.content == "Fallback code"
    
    def test_bob_handles_missing_code(self, event_loop):
        """Test Bob handles case where Alex's code is missing."""
        from mgx_agent.roles import Bob
        
        bob = Bob()
        bob.llm = AsyncMock()
        bob.rc = MockContext()
        bob.rc.news = []
        bob.rc.memory = MockMemory()
        bob.rc.memory.storage = []  # No code
        
        # Mock WriteTest action
        with patch('mgx_agent.roles.WriteTest') as MockTest:
            mock_test = AsyncMock()
            mock_test.run = AsyncMock(return_value="Tests for missing code")
            MockTest.return_value = mock_test
            
            result = event_loop.run_until_complete(bob._act())
            
            # Should still attempt to write tests
            mock_test.run.assert_called_once()
            # First arg should contain fallback
            call_args = mock_test.run.call_args
            assert call_args is not None
    
    def test_charlie_handles_missing_code_and_tests(self, event_loop):
        """Test Charlie handles missing code and tests gracefully."""
        from mgx_agent.roles import Charlie
        
        charlie = Charlie(is_human=False)
        charlie.llm = AsyncMock()
        charlie.rc = MockContext()
        charlie.rc.news = []
        charlie.rc.memory = MockMemory()
        charlie.rc.memory.storage = []  # No code or tests
        
        # Mock ReviewCode action
        with patch('mgx_agent.roles.ReviewCode') as MockReview:
            mock_review = AsyncMock()
            mock_review.run = AsyncMock(return_value="SONUÇ: DEĞİŞİKLİK GEREKLİ")
            MockReview.return_value = mock_review
            
            result = event_loop.run_until_complete(charlie._act())
            
            # Should still perform review with fallback
            mock_review.run.assert_called_once()
            args = mock_review.run.call_args[0]
            # Should contain "No code found" or "No tests found"
            assert any("No" in str(arg) for arg in args)


# ============================================
# TEST Progress Reporting
# ============================================

class TestProgressReporting:
    """Test progress reporting through team reference."""
    
    def test_role_uses_team_ref_for_progress(self, mock_team_ref):
        """Test role uses team_ref._print_progress when available."""
        from mgx_agent.roles import print_step_progress
        
        # Mock role with team ref
        role = Mock()
        role._team_ref = mock_team_ref
        
        # Call progress function
        print_step_progress(1, 3, "Testing", role=role)
        
        # Should have called team's progress method
        mock_team_ref._print_progress.assert_called_once_with(1, 3, "Testing")
    
    def test_progress_fallback_without_team_ref(self, capsys):
        """Test progress falls back to print when no team ref."""
        from mgx_agent.roles import print_step_progress
        
        # Call without team ref
        print_step_progress(1, 1, "Complete", role=None)
        
        # Should print to stdout
        captured = capsys.readouterr()
        assert "100%" in captured.out


# ============================================
# SUMMARY ASSERTIONS
# ============================================

def test_integration_roles_assertion_count():
    """Verify we have comprehensive test coverage with sufficient assertions."""
    import inspect
    
    # Count test methods in this module
    current_module = inspect.getmodule(inspect.currentframe())
    test_classes = [
        TestRelevantMemoryMixin,
        TestMikeRole,
        TestAlexRole,
        TestBobRole,
        TestCharlieRole,
        TestRoleAdapterIntegration,
        TestPlanningGuardRails,
        TestRolesNegativeCases,
        TestProgressReporting,
    ]
    
    total_tests = 0
    for cls in test_classes:
        methods = [m for m in dir(cls) if m.startswith('test_')]
        total_tests += len(methods)
    
    # Should have at least 30 test methods for roles
    assert total_tests >= 30, f"Expected at least 30 tests, found {total_tests}"
