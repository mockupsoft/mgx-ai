# -*- coding: utf-8 -*-
"""
Unit tests for roles.py helper functions and decorators.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from mgx_agent.roles import llm_retry, print_phase_header


class TestLLMRetryDecorator:
    """Test llm_retry decorator."""
    
    @pytest.mark.asyncio
    async def test_llm_retry_decorator_success(self):
        """Test llm_retry decorator with successful call."""
        from mgx_agent.roles import llm_retry
        
        @llm_retry()
        async def successful_function():
            return "success"
        
        result = await successful_function()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_llm_retry_decorator_retry_on_exception(self):
        """Test llm_retry decorator retries on exception."""
        from mgx_agent.roles import llm_retry
        
        call_count = [0]
        
        @llm_retry()
        async def failing_then_success():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Temporary error")
            return "success"
        
        result = await failing_then_success()
        assert result == "success"
        assert call_count[0] == 2
    
    @pytest.mark.asyncio
    async def test_llm_retry_decorator_max_attempts(self):
        """Test llm_retry decorator raises exception after max attempts."""
        from mgx_agent.roles import llm_retry
        from tenacity import RetryError
        
        call_count = [0]
        
        @llm_retry()
        async def always_failing():
            call_count[0] += 1
            raise Exception("Always fails")
        
        # Should raise RetryError after max attempts
        with pytest.raises(RetryError):
            await always_failing()
        
        # Should have tried 3 times (max attempts)
        assert call_count[0] == 3


class TestPrintPhaseHeader:
    """Test print_phase_header helper function."""
    
    def test_print_phase_header_basic(self):
        """Test print_phase_header with basic phase name."""
        from mgx_agent.roles import print_phase_header
        
        with patch('builtins.print') as mock_print:
            print_phase_header("Test Phase")
            
            # Should have called print 3 times (header lines)
            assert mock_print.call_count == 3
            
            # Check that phase name is in output
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("Test Phase" in str(call) for call in print_calls)
    
    def test_print_phase_header_custom_emoji(self):
        """Test print_phase_header with custom emoji."""
        from mgx_agent.roles import print_phase_header
        
        with patch('builtins.print') as mock_print:
            print_phase_header("Test Phase", emoji="🚀")
            
            # Should have called print 3 times
            assert mock_print.call_count == 3
            
            # Check that emoji is in output
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any("🚀" in str(call) for call in print_calls)
    
    def test_print_phase_header_long_phase(self):
        """Test print_phase_header with long phase name."""
        from mgx_agent.roles import print_phase_header
        
        long_phase_name = "A" * 100  # Very long phase name
        
        with patch('builtins.print') as mock_print:
            print_phase_header(long_phase_name)
            
            # Should have called print 3 times
            assert mock_print.call_count == 3
            
            # Check that long phase name is in output
            print_calls = [str(call) for call in mock_print.call_args_list]
            assert any(long_phase_name in str(call) for call in print_calls)

