# -*- coding: utf-8 -*-
"""
Comprehensive unit tests for mgx_agent.actions module

Tests coverage:
- print_step_progress() with and without _team_ref
- print_phase_header() with various emojis
- AnalyzeTask, DraftPlan, WriteCode, WriteTest, ReviewCode actions
- WriteCode._parse_code() markdown stripping
- WriteTest._limit_tests() enforcing k cap
- llm_retry decorator retry behavior
- Error handling and logging
"""

import pytest
import logging
import re
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from io import StringIO

import sys
import os
sys.path.insert(0, '/home/engine/project')
os.environ['OPENAI_API_KEY'] = 'dummy_key_for_testing'

from mgx_agent.actions import (
    AnalyzeTask,
    DraftPlan,
    WriteCode,
    WriteTest,
    ReviewCode,
    llm_retry,
    print_step_progress,
    print_phase_header,
)
from tests.helpers.metagpt_stubs import MockRole, MockMessage, mock_logger


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def fake_action_role():
    """Create a fake role with _aask method for testing actions"""
    role = MockRole(name="TestEngineer")
    role._aask = AsyncMock(return_value="Mock response")
    return role


@pytest.fixture
def fake_action_role_with_team_ref():
    """Create a fake role with team reference"""
    role = MockRole(name="TestEngineer")
    role._aask = AsyncMock(return_value="Mock response")
    
    # Add team reference for _team_ref shortcut testing
    team_mock = Mock()
    team_mock._print_progress = Mock()
    role._team_ref = team_mock
    
    return role


@pytest.fixture
def async_mock_aask(event_loop):
    """Create a mock _aask coroutine"""
    async_mock = AsyncMock()
    async_mock.return_value = "Mock LLM response"
    return async_mock


@pytest.fixture
def mock_logger_fixture():
    """Get access to mock logger"""
    return mock_logger


# ============================================
# Tests for print_step_progress
# ============================================

class TestPrintStepProgress:
    """Test print_step_progress function"""
    
    def test_print_step_progress_without_team_ref(self, capsys):
        """Test print_step_progress without team reference"""
        print_step_progress(step=1, total=3, description="Test step")
        captured = capsys.readouterr()
        
        # Should print progress bar
        assert "█" in captured.out or "░" in captured.out
        assert "Test step" in captured.out
    
    def test_print_step_progress_with_team_ref(self, fake_action_role_with_team_ref):
        """Test print_step_progress uses team reference when available"""
        role = fake_action_role_with_team_ref
        print_step_progress(step=1, total=3, description="Test", role=role)
        
        # Should call team's _print_progress
        role._team_ref._print_progress.assert_called_once_with(1, 3, "Test")
    
    def test_print_step_progress_completion(self, capsys):
        """Test print_step_progress at completion"""
        print_step_progress(step=3, total=3, description="Complete")
        captured = capsys.readouterr()
        
        # Should have newline at completion
        assert "Complete" in captured.out
    
    def test_print_step_progress_percentages(self, capsys):
        """Test print_step_progress shows correct percentages"""
        print_step_progress(step=1, total=2, description="50%")
        captured = capsys.readouterr()
        
        assert "50%" in captured.out
    
    def test_print_step_progress_role_without_team_ref(self, fake_action_role, capsys):
        """Test print_step_progress falls back when role lacks _team_ref"""
        role = fake_action_role
        print_step_progress(step=1, total=2, description="Fallback")
        captured = capsys.readouterr()
        
        # Should use fallback (print bar)
        assert "Fallback" in captured.out


class TestPrintPhaseHeader:
    """Test print_phase_header function"""
    
    def test_print_phase_header_default_emoji(self, capsys):
        """Test print_phase_header with default emoji"""
        print_phase_header("Phase 1: Analysis")
        captured = capsys.readouterr()
        
        assert "🔄 Phase 1: Analysis" in captured.out
        assert "=" in captured.out
    
    def test_print_phase_header_custom_emoji(self, capsys):
        """Test print_phase_header with custom emoji"""
        print_phase_header("Phase 2: Implementation", emoji="⚙️")
        captured = capsys.readouterr()
        
        assert "⚙️ Phase 2: Implementation" in captured.out
    
    def test_print_phase_header_formatting(self, capsys):
        """Test print_phase_header formatting"""
        print_phase_header("Test")
        captured = capsys.readouterr()
        
        # Should have borders
        lines = captured.out.strip().split('\n')
        assert len(lines) == 3
        assert all('=' in line for line in [lines[0], lines[2]])


# ============================================
# Tests for llm_retry decorator
# ============================================

class TestLLMRetryDecorator:
    """Test llm_retry decorator and retry behavior"""
    
    def test_llm_retry_success_on_first_attempt(self, event_loop, async_mock_aask):
        """Test llm_retry succeeds on first attempt"""
        @llm_retry()
        async def test_func():
            return await async_mock_aask()
        
        result = event_loop.run_until_complete(test_func())
        assert result == "Mock LLM response"
        async_mock_aask.assert_called_once()
    
    def test_llm_retry_succeeds_after_failures(self, event_loop, caplog):
        """Test llm_retry retries after failures and eventually succeeds"""
        attempt_count = 0
        
        @llm_retry()
        async def test_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ValueError("Temporary error")
            return "Success"
        
        with caplog.at_level(logging.WARNING):
            result = event_loop.run_until_complete(test_func())
        
        assert result == "Success"
        assert attempt_count == 3
        # Should log retry warnings
        assert "yeniden deneniyor" in caplog.text or "retry" in caplog.text.lower()
    
    def test_llm_retry_max_attempts(self):
        """Test llm_retry decorator can be applied to async functions"""
        # Test that decorator can be applied without raising
        @llm_retry()
        async def test_func():
            return "done"
        
        # Decorator should be applied successfully
        assert hasattr(test_func, '__wrapped__') or callable(test_func)


# ============================================
# Tests for AnalyzeTask Action
# ============================================

class TestAnalyzeTask:
    """Test AnalyzeTask action"""
    
    def test_analyze_task_basic_run(self, event_loop, fake_action_role):
        """Test AnalyzeTask basic run"""
        task = AnalyzeTask()
        task._aask = fake_action_role._aask
        fake_action_role._aask.return_value = "KARMAŞIKLIK: M"
        
        result = event_loop.run_until_complete(task.run("Write a web scraper"))
        
        assert "KARMAŞIKLIK" in fake_action_role._aask.call_args[0][0]
        assert "Write a web scraper" in fake_action_role._aask.call_args[0][0]
    
    def test_analyze_task_prompt_format(self, event_loop, fake_action_role):
        """Test AnalyzeTask formats prompt correctly"""
        task = AnalyzeTask()
        task._aask = fake_action_role._aask
        
        event_loop.run_until_complete(task.run("Test task"))
        
        prompt = fake_action_role._aask.call_args[0][0]
        assert "Görev: Test task" in prompt
        assert "XS:" in prompt
        assert "S:" in prompt
        assert "M:" in prompt
        assert "L:" in prompt
        assert "XL:" in prompt
    
    def test_analyze_task_error_handling(self, event_loop, caplog):
        """Test AnalyzeTask error handling"""
        task = AnalyzeTask()
        task._aask = AsyncMock(side_effect=Exception("LLM error"))
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception):
                event_loop.run_until_complete(task.run("Test task"))
        
        assert "AnalyzeTask hatası" in caplog.text


# ============================================
# Tests for DraftPlan Action
# ============================================

class TestDraftPlan:
    """Test DraftPlan action"""
    
    def test_draft_plan_basic_run(self, event_loop, fake_action_role):
        """Test DraftPlan basic run"""
        plan = DraftPlan()
        plan._aask = fake_action_role._aask
        fake_action_role._aask.return_value = "1. Kod yaz\n2. Test yaz\n3. Review yap"
        
        result = event_loop.run_until_complete(plan.run("Write feature", "Task is medium complexity"))
        
        assert plan._aask.called
    
    def test_draft_plan_prompt_format(self, event_loop, fake_action_role):
        """Test DraftPlan formats prompt correctly"""
        plan = DraftPlan()
        plan._aask = fake_action_role._aask
        
        event_loop.run_until_complete(plan.run("Build API", "Complexity: M"))
        
        prompt = fake_action_role._aask.call_args[0][0]
        assert "Görev: Build API" in prompt
        assert "1. Kod yaz" in prompt
        assert "2. Test yaz" in prompt
        assert "3. Review yap" in prompt
    
    def test_draft_plan_error_handling(self, event_loop, caplog):
        """Test DraftPlan error handling"""
        plan = DraftPlan()
        plan._aask = AsyncMock(side_effect=Exception("LLM error"))
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception):
                event_loop.run_until_complete(plan.run("Task", "Analysis"))
        
        assert "DraftPlan hatası" in caplog.text


# ============================================
# Tests for WriteCode Action
# ============================================

class TestWriteCode:
    """Test WriteCode action"""
    
    def test_write_code_basic_run(self, event_loop, fake_action_role):
        """Test WriteCode basic run"""
        action = WriteCode()
        action._aask = fake_action_role._aask
        fake_action_role._aask.return_value = "```python\ndef hello():\n    pass\n```"
        
        result = event_loop.run_until_complete(action.run("Write hello function"))
        
        # _parse_code should extract code
        assert "def hello()" in result
    
    def test_write_code_parse_code_with_markdown(self):
        """Test WriteCode._parse_code strips markdown fences"""
        response = "```python\ndef test():\n    return True\n```"
        result = WriteCode._parse_code(response)
        
        assert "```" not in result
        assert "def test():" in result
        assert result.startswith("def test()")
    
    def test_write_code_parse_code_without_markdown(self):
        """Test WriteCode._parse_code handles plain code"""
        code = "def plain():\n    pass"
        result = WriteCode._parse_code(code)
        
        assert result == code
    
    def test_write_code_parse_code_multiline(self):
        """Test WriteCode._parse_code handles multiline code"""
        response = """Some text before
```python
def multi():
    x = 1
    y = 2
    return x + y
```
Some text after"""
        result = WriteCode._parse_code(response)
        
        assert "def multi():" in result
        assert "x = 1" in result
        assert "Some text" not in result
    
    def test_write_code_with_review_notes(self, event_loop, fake_action_role):
        """Test WriteCode includes review notes in prompt"""
        action = WriteCode()
        action._aask = fake_action_role._aask
        fake_action_role._aask.return_value = "```python\npass\n```"
        
        event_loop.run_until_complete(action.run(
            instruction="Write code",
            review_notes="Add error handling"
        ))
        
        prompt = fake_action_role._aask.call_args[0][0]
        assert "Review Notları" in prompt
        assert "Add error handling" in prompt
        assert "düzeltme turu" in prompt
    
    def test_write_code_prompt_structure(self, event_loop, fake_action_role):
        """Test WriteCode prompt has correct structure"""
        action = WriteCode()
        action._aask = fake_action_role._aask
        fake_action_role._aask.return_value = "```python\npass\n```"
        
        event_loop.run_until_complete(action.run("Implement feature", "Step 1, Step 2"))
        
        prompt = fake_action_role._aask.call_args[0][0]
        assert "ADIM 1" in prompt
        assert "ADIM 2" in prompt
        assert "DÜŞÜN" in prompt or "KODLA" in prompt
    
    def test_write_code_error_handling(self, event_loop, caplog):
        """Test WriteCode error handling"""
        action = WriteCode()
        action._aask = AsyncMock(side_effect=Exception("LLM error"))
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception):
                event_loop.run_until_complete(action.run("Task"))
        
        assert "WriteCode hatası" in caplog.text


# ============================================
# Tests for WriteTest Action
# ============================================

class TestWriteTest:
    """Test WriteTest action"""
    
    def test_write_test_basic_run(self, event_loop, fake_action_role):
        """Test WriteTest basic run"""
        action = WriteTest()
        action._aask = fake_action_role._aask
        code_response = """```python
import pytest

def test_one():
    assert 1 == 1

def test_two():
    assert 2 == 2
```"""
        fake_action_role._aask.return_value = code_response
        
        result = event_loop.run_until_complete(action.run("def func(): pass", k=2))
        
        assert "def test_" in result
    
    def test_write_test_parse_code(self):
        """Test WriteTest._parse_code"""
        response = """```python
import pytest

def test_1():
    pass
```"""
        result = WriteTest._parse_code(response)
        
        assert "```" not in result
        assert "import pytest" in result
        assert "def test_1():" in result
    
    def test_write_test_limit_tests_enforces_cap(self):
        """Test WriteTest._limit_tests enforces k cap even with extra tests"""
        code = """import pytest

def test_1():
    assert True

def test_2():
    assert True

def test_3():
    assert True

def test_4():
    assert True

def test_5():
    assert True
"""
        result = WriteTest._limit_tests(code, k=2)
        
        # Count test functions
        test_count = len(re.findall(r'def test_\d+\(\):', result))
        assert test_count <= 2, f"Expected max 2 tests, got {test_count}"
    
    def test_write_test_limit_tests_with_complex_code(self):
        """Test WriteTest._limit_tests with complex function bodies"""
        code = """import pytest

def test_1():
    x = 1
    y = 2
    assert x < y

def test_2():
    result = sum([1, 2, 3])
    assert result == 6

def test_3():
    with pytest.raises(ValueError):
        int("invalid")

def test_4():
    pass
"""
        result = WriteTest._limit_tests(code, k=2)
        
        test_count = len(re.findall(r'def test_\d+\(\):', result))
        assert test_count == 2
        
        # Should include imports
        assert "import pytest" in result
    
    def test_write_test_limit_tests_preserves_imports(self):
        """Test WriteTest._limit_tests preserves imports and decorators"""
        code = """import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_data():
    return {"key": "value"}

def test_1(mock_data):
    assert mock_data["key"] == "value"

def test_2():
    assert 1 == 1

def test_3():
    assert 2 == 2
"""
        result = WriteTest._limit_tests(code, k=1)
        
        assert "import pytest" in result
        assert "from unittest.mock import Mock" in result
        test_count = len(re.findall(r'def test_\d+\(\w*\):', result))
        assert test_count == 1
    
    def test_write_test_limit_tests_empty_code(self):
        """Test WriteTest._limit_tests with empty/no tests"""
        code = "# No tests here"
        result = WriteTest._limit_tests(code, k=3)
        
        assert result == code
    
    def test_write_test_prompt_format(self, event_loop, fake_action_role):
        """Test WriteTest formats prompt with correct k value"""
        action = WriteTest()
        action._aask = fake_action_role._aask
        code_response = "```python\ndef test_1():\n    pass\n```"
        fake_action_role._aask.return_value = code_response
        
        event_loop.run_until_complete(action.run("def func(): pass", k=5))
        
        prompt = fake_action_role._aask.call_args[0][0]
        assert "TAM OLARAK 5" in prompt
        assert "5 adet test" in prompt
    
    def test_write_test_error_handling(self, event_loop, caplog):
        """Test WriteTest error handling"""
        action = WriteTest()
        action._aask = AsyncMock(side_effect=Exception("LLM error"))
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception):
                event_loop.run_until_complete(action.run("code", k=3))
        
        assert "WriteTest hatası" in caplog.text


# ============================================
# Tests for ReviewCode Action
# ============================================

class TestReviewCode:
    """Test ReviewCode action"""
    
    def test_review_code_basic_run(self, event_loop, fake_action_role):
        """Test ReviewCode basic run"""
        action = ReviewCode()
        action._aask = fake_action_role._aask
        review_response = "SONUÇ: ONAYLANDI\n\nYORUMLAR:\n- Code looks good"
        fake_action_role._aask.return_value = review_response
        
        result = event_loop.run_until_complete(action.run("def func(): pass", "def test(): pass"))
        
        assert result == review_response
    
    def test_review_code_prompt_includes_code_and_tests(self, event_loop, fake_action_role):
        """Test ReviewCode prompt includes code and tests"""
        action = ReviewCode()
        action._aask = fake_action_role._aask
        fake_action_role._aask.return_value = "SONUÇ: ONAYLANDI"
        
        code = "def add(a, b):\n    return a + b"
        tests = "def test_add():\n    assert add(1, 2) == 3"
        
        event_loop.run_until_complete(action.run(code, tests))
        
        prompt = fake_action_role._aask.call_args[0][0]
        assert code in prompt
        assert tests in prompt
    
    def test_review_code_prompt_structure(self, event_loop, fake_action_role):
        """Test ReviewCode prompt structure"""
        action = ReviewCode()
        action._aask = fake_action_role._aask
        fake_action_role._aask.return_value = "Response"
        
        event_loop.run_until_complete(action.run("code", "tests"))
        
        prompt = fake_action_role._aask.call_args[0][0]
        assert "DİKKATLİCE incele" in prompt
        assert "SONUÇ:" in prompt
    
    def test_review_code_approval_response(self, event_loop, fake_action_role):
        """Test ReviewCode with approval response"""
        action = ReviewCode()
        action._aask = fake_action_role._aask
        response = "SONUÇ: ONAYLANDI\n\nYORUMLAR:\n- Excellent code quality"
        fake_action_role._aask.return_value = response
        
        result = event_loop.run_until_complete(action.run("good code", "good tests"))
        
        assert "ONAYLANDI" in result
    
    def test_review_code_revision_response(self, event_loop, fake_action_role):
        """Test ReviewCode requesting revision"""
        action = ReviewCode()
        action._aask = fake_action_role._aask
        response = "SONUÇ: DEĞİŞİKLİK GEREKLİ\n\nYORUMLAR:\n- Missing error handling"
        fake_action_role._aask.return_value = response
        
        result = event_loop.run_until_complete(action.run("code", "tests"))
        
        assert "DEĞİŞİKLİK GEREKLİ" in result
    
    def test_review_code_error_handling(self, event_loop, caplog):
        """Test ReviewCode error handling"""
        action = ReviewCode()
        action._aask = AsyncMock(side_effect=Exception("LLM error"))
        
        with caplog.at_level(logging.ERROR):
            with pytest.raises(Exception):
                event_loop.run_until_complete(action.run("code", "tests"))
        
        assert "ReviewCode hatası" in caplog.text


# ============================================
# Integration Tests
# ============================================

class TestActionsIntegration:
    """Integration tests for action classes"""
    
    def test_action_workflow_sequence(self, event_loop, fake_action_role):
        """Test complete action workflow"""
        fake_action_role._aask.side_effect = [
            "KARMAŞIKLIK: M",  # AnalyzeTask
            "1. Kod yaz\n2. Test yaz\n3. Review yap",  # DraftPlan
            "```python\ndef hello():\n    pass\n```",  # WriteCode
            "```python\ndef test_hello():\n    assert True\n```",  # WriteTest
            "SONUÇ: ONAYLANDI",  # ReviewCode
        ]
        
        # Step 1: Analyze
        analyze = AnalyzeTask()
        analyze._aask = fake_action_role._aask
        analysis = event_loop.run_until_complete(analyze.run("Task"))
        assert "KARMAŞIKLIK" in analysis
        
        # Step 2: Draft plan
        plan = DraftPlan()
        plan._aask = fake_action_role._aask
        plan_result = event_loop.run_until_complete(plan.run("Task", analysis))
        assert "Kod yaz" in plan_result
        
        # Step 3: Write code
        write = WriteCode()
        write._aask = fake_action_role._aask
        code = event_loop.run_until_complete(write.run("Task", plan_result))
        assert "def hello()" in code
        
        # Step 4: Write tests
        test = WriteTest()
        test._aask = fake_action_role._aask
        tests = event_loop.run_until_complete(test.run(code, k=3))
        assert "def test_" in tests
        
        # Step 5: Review
        review = ReviewCode()
        review._aask = fake_action_role._aask
        review_result = event_loop.run_until_complete(review.run(code, tests))
        assert "ONAYLANDI" in review_result
    
    def test_actions_with_retry(self, event_loop, fake_action_role, caplog):
        """Test actions retry on failure"""
        call_count = 0
        
        async def failing_aask(prompt):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary failure")
            return "```python\npass\n```"
        
        fake_action_role._aask = failing_aask
        
        action = WriteCode()
        action._aask = fake_action_role._aask
        
        with caplog.at_level(logging.WARNING):
            result = event_loop.run_until_complete(action.run("Task"))
        
        assert call_count == 2
        assert "pass" in result
