# -*- coding: utf-8 -*-
"""
Comprehensive unit tests for mgx_agent.adapter module

Tests coverage:
- MetaGPTAdapter.get_memory_store() with missing attributes
- MetaGPTAdapter.get_messages() with get() API, iterable fallback, storage fallback
- MetaGPTAdapter.add_message() with duplicate suppression, storage fallback
- MetaGPTAdapter.clear_memory() with three strategies (clear/add, storage, _memory)
- MetaGPTAdapter.get_messages_by_role() with get_by_role() and manual filter
- MetaGPTAdapter.get_news() with error handling and fallbacks
- Warning/error logging via caplog
"""

import pytest
import logging
from unittest.mock import Mock, MagicMock, patch

import sys
import os
sys.path.insert(0, '/home/engine/project')
os.environ['OPENAI_API_KEY'] = 'dummy_key_for_testing'

from mgx_agent.adapter import MetaGPTAdapter
from tests.helpers.metagpt_stubs import MockMessage, mock_logger


class TestMetaGPTAdapterGetMemoryStore:
    """Test MetaGPTAdapter.get_memory_store() method"""
    
    def test_get_memory_store_with_none_role(self):
        """Test get_memory_store with None role"""
        result = MetaGPTAdapter.get_memory_store(None)
        assert result is None
    
    def test_get_memory_store_role_without_rc(self):
        """Test get_memory_store when role has no rc attribute"""
        role = Mock()
        del role.rc  # Ensure rc doesn't exist
        result = MetaGPTAdapter.get_memory_store(role)
        assert result is None
    
    def test_get_memory_store_rc_without_memory(self):
        """Test get_memory_store when rc has no memory attribute"""
        role = Mock()
        role.rc = Mock(spec=[])  # Empty spec means no attributes
        result = MetaGPTAdapter.get_memory_store(role)
        assert result is None
    
    def test_get_memory_store_success(self):
        """Test get_memory_store returns memory successfully"""
        memory = Mock()
        role = Mock()
        role.rc = Mock()
        role.rc.memory = memory
        
        result = MetaGPTAdapter.get_memory_store(role)
        assert result is memory


class TestMetaGPTAdapterGetMessages:
    """Test MetaGPTAdapter.get_messages() method"""
    
    def test_get_messages_with_none_store(self):
        """Test get_messages with None memory store"""
        result = MetaGPTAdapter.get_messages(None)
        assert result == []
    
    def test_get_messages_with_get_api(self):
        """Test get_messages using get() API"""
        messages = [MockMessage("user", "msg1"), MockMessage("assistant", "msg2")]
        mem_store = Mock()
        mem_store.get.return_value = messages
        
        result = MetaGPTAdapter.get_messages(mem_store)
        assert len(result) == 2
        assert result[0].content == "msg1"
        assert result[1].content == "msg2"
        mem_store.get.assert_called_once()
    
    def test_get_messages_with_get_api_exception(self):
        """Test get_messages when get() raises exception"""
        mem_store = Mock()
        mem_store.get.side_effect = Exception("API error")
        mem_store.__iter__ = Mock(side_effect=TypeError())  # No fallback
        
        result = MetaGPTAdapter.get_messages(mem_store)
        assert result == []
    
    def test_get_messages_with_iterable_fallback(self):
        """Test get_messages falling back to iterable"""
        messages = [MockMessage("user", "msg1"), MockMessage("assistant", "msg2")]
        mem_store = MagicMock()
        del mem_store.get  # Remove get method
        mem_store.__iter__ = Mock(return_value=iter(messages))
        
        result = MetaGPTAdapter.get_messages(mem_store)
        assert len(result) == 2
    
    def test_get_messages_with_iterable_exception(self):
        """Test get_messages when iterable raises exception"""
        mem_store = MagicMock()
        del mem_store.get  # No get method
        mem_store.__iter__ = Mock(side_effect=Exception("Iteration error"))
        
        result = MetaGPTAdapter.get_messages(mem_store)
        assert result == []
    
    def test_get_messages_with_storage_fallback(self):
        """Test get_messages using storage attribute fallback"""
        messages = [MockMessage("user", "msg1")]
        mem_store = Mock(spec=['storage'])
        mem_store.storage = messages
        
        result = MetaGPTAdapter.get_messages(mem_store)
        assert len(result) == 1
        assert result[0].content == "msg1"
    
    def test_get_messages_with_storage_none(self):
        """Test get_messages when storage is None"""
        mem_store = Mock(spec=['storage'])
        mem_store.storage = None
        
        result = MetaGPTAdapter.get_messages(mem_store)
        assert result == []
    
    def test_get_messages_no_applicable_api(self):
        """Test get_messages when no API is available"""
        mem_store = Mock(spec=[])  # No get, iter, or storage
        
        result = MetaGPTAdapter.get_messages(mem_store)
        assert result == []


class TestMetaGPTAdapterAddMessage:
    """Test MetaGPTAdapter.add_message() method"""
    
    def test_add_message_with_none_store(self):
        """Test add_message with None memory store"""
        message = MockMessage("user", "test")
        result = MetaGPTAdapter.add_message(None, message)
        assert result is False
    
    def test_add_message_using_add_api(self):
        """Test add_message using add() API"""
        message = MockMessage("user", "test")
        mem_store = Mock()
        mem_store.add = Mock()
        
        result = MetaGPTAdapter.add_message(mem_store, message)
        assert result is True
        mem_store.add.assert_called_once_with(message)
    
    def test_add_message_add_api_exception(self, caplog):
        """Test add_message when add() raises exception"""
        message = MockMessage("user", "test")
        mem_store = Mock()
        mem_store.add.side_effect = Exception("Add error")
        mem_store.storage = None  # No storage fallback
        
        with caplog.at_level(logging.WARNING):
            result = MetaGPTAdapter.add_message(mem_store, message)
        
        assert result is False
        assert "⚠️ Mesaj eklenirken hata" in caplog.text
    
    def test_add_message_storage_fallback_no_duplicate(self):
        """Test add_message using storage fallback without duplicate"""
        message = MockMessage("user", "test")
        mem_store = Mock()
        del mem_store.add  # No add method
        mem_store.storage = []
        
        result = MetaGPTAdapter.add_message(mem_store, message)
        assert result is True
        assert len(mem_store.storage) == 1
        assert mem_store.storage[0] == message
    
    def test_add_message_storage_fallback_duplicate_suppression(self):
        """Test add_message suppresses duplicate messages in storage"""
        message = MockMessage("user", "test")
        mem_store = Mock()
        del mem_store.add
        mem_store.storage = [message]  # Already exists
        
        result = MetaGPTAdapter.add_message(mem_store, message)
        assert result is True
        assert len(mem_store.storage) == 1  # Not added again
    
    def test_add_message_no_storage_api(self):
        """Test add_message when no API is available"""
        message = MockMessage("user", "test")
        mem_store = Mock(spec=[])
        
        result = MetaGPTAdapter.add_message(mem_store, message)
        assert result is False


class TestMetaGPTAdapterClearMemory:
    """Test MetaGPTAdapter.clear_memory() method"""
    
    def test_clear_memory_with_none_store(self):
        """Test clear_memory with None store"""
        result = MetaGPTAdapter.clear_memory(None, keep_last_n=2)
        assert result is False
    
    def test_clear_memory_within_limit(self):
        """Test clear_memory when already within limit"""
        mem_store = Mock()
        mem_store.get = Mock(return_value=[
            MockMessage("user", "msg1"),
            MockMessage("assistant", "msg2")
        ])
        
        result = MetaGPTAdapter.clear_memory(mem_store, keep_last_n=5)
        assert result is True  # No clearing needed
    
    def test_clear_memory_strategy_clear_and_add(self):
        """Test clear_memory using clear() + add() strategy"""
        messages = [
            MockMessage("user", "msg1"),
            MockMessage("assistant", "msg2"),
            MockMessage("user", "msg3"),
            MockMessage("assistant", "msg4"),
        ]
        mem_store = Mock()
        mem_store.get = Mock(return_value=messages)
        mem_store.clear = Mock()
        mem_store.add = Mock()
        
        result = MetaGPTAdapter.clear_memory(mem_store, keep_last_n=2)
        assert result is True
        mem_store.clear.assert_called_once()
        # Should have added the last 2 messages
        assert mem_store.add.call_count == 2
    
    def test_clear_memory_strategy_storage_reassignment(self):
        """Test clear_memory using storage reassignment strategy"""
        messages = [
            MockMessage("user", "msg1"),
            MockMessage("assistant", "msg2"),
            MockMessage("user", "msg3"),
        ]
        mem_store = Mock()
        mem_store.get = Mock(return_value=messages)
        del mem_store.clear  # No clear method
        mem_store.storage = list(messages)
        del mem_store.index  # No index
        
        result = MetaGPTAdapter.clear_memory(mem_store, keep_last_n=1)
        assert result is True
        # Should keep only last 1 message
        assert len(mem_store.storage) == 1
        assert mem_store.storage[0].content == "msg3"
    
    def test_clear_memory_strategy_storage_with_index(self):
        """Test clear_memory updating index when present"""
        messages = [
            MockMessage("user", "msg1"),
            MockMessage("assistant", "msg2"),
            MockMessage("user", "msg3"),
        ]
        msg1 = messages[0]
        msg1.cause_by = "Action1"
        msg3 = messages[2]
        msg3.cause_by = "Action3"
        
        mem_store = Mock()
        mem_store.get = Mock(return_value=messages)
        del mem_store.clear
        mem_store.storage = list(messages)
        mem_store.index = {}  # Use real dict
        
        result = MetaGPTAdapter.clear_memory(mem_store, keep_last_n=1)
        assert result is True
        # Index should be cleared and repopulated
        assert isinstance(mem_store.index, dict)
    
    def test_clear_memory_strategy_private_memory_attribute(self, caplog):
        """Test clear_memory using _memory private attribute (fallback)"""
        messages = [
            MockMessage("user", "msg1"),
            MockMessage("assistant", "msg2"),
            MockMessage("user", "msg3"),
        ]
        mem_store = Mock()
        mem_store.get = Mock(return_value=messages)
        del mem_store.clear
        del mem_store.storage
        mem_store._memory = list(messages)
        
        with caplog.at_level(logging.WARNING):
            result = MetaGPTAdapter.clear_memory(mem_store, keep_last_n=1)
        
        assert result is True
        assert len(mem_store._memory) == 1
        assert "UYARI: MetaGPT private attribute" in caplog.text
    
    def test_clear_memory_no_strategy_available(self, caplog):
        """Test clear_memory when no strategy is available"""
        mem_store = Mock()
        messages = [MockMessage("user", f"msg{i}") for i in range(5)]
        mem_store.get = Mock(return_value=messages)
        # Remove all strategies
        del mem_store.clear
        del mem_store.storage
        del mem_store._memory
        
        with caplog.at_level(logging.WARNING):
            result = MetaGPTAdapter.clear_memory(mem_store, keep_last_n=2)
        
        assert result is False
        assert "Memory temizliği yapılamadı" in caplog.text
    
    def test_clear_memory_exception_handling(self, caplog):
        """Test clear_memory error handling when clear strategies fail"""
        mem_store = Mock()
        messages = [MockMessage("user", f"msg{i}") for i in range(5)]
        mem_store.get = Mock(return_value=messages)
        mem_store.clear = Mock(side_effect=Exception("Clear error"))
        mem_store.storage = None  # No storage fallback
        mem_store._memory = None  # No _memory fallback
        
        with caplog.at_level(logging.ERROR):
            result = MetaGPTAdapter.clear_memory(mem_store, keep_last_n=2)
        
        assert result is False
        assert "Memory temizliği hatası" in caplog.text


class TestMetaGPTAdapterGetMessagesByRole:
    """Test MetaGPTAdapter.get_messages_by_role() method"""
    
    def test_get_messages_by_role_with_none_store(self):
        """Test get_messages_by_role with None store"""
        result = MetaGPTAdapter.get_messages_by_role(None, "Engineer")
        assert result == []
    
    def test_get_messages_by_role_using_get_by_role_api(self):
        """Test get_messages_by_role using get_by_role() API"""
        messages = [
            MockMessage("assistant", "msg1"),
            MockMessage("assistant", "msg2"),
        ]
        mem_store = Mock()
        mem_store.get_by_role = Mock(return_value=messages)
        
        result = MetaGPTAdapter.get_messages_by_role(mem_store, "Engineer")
        assert len(result) == 2
        mem_store.get_by_role.assert_called_once_with("Engineer")
    
    def test_get_messages_by_role_manual_filter(self):
        """Test get_messages_by_role using manual filter fallback"""
        msg1 = MockMessage("assistant", "msg1")
        msg1.role = "Engineer"
        msg2 = MockMessage("assistant", "msg2")
        msg2.role = "Tester"
        msg3 = MockMessage("assistant", "msg3")
        msg3.role = "Engineer"
        
        mem_store = MagicMock()
        del mem_store.get_by_role  # No get_by_role API
        mem_store.get = Mock(return_value=[msg1, msg2, msg3])
        mem_store.__iter__ = Mock(side_effect=TypeError())
        
        result = MetaGPTAdapter.get_messages_by_role(mem_store, "Engineer")
        assert len(result) == 2
        assert all(msg.role == "Engineer" for msg in result)
    
    def test_get_messages_by_role_no_matching_messages(self):
        """Test get_messages_by_role with no matching messages"""
        msg1 = MockMessage("assistant", "msg1")
        msg1.role = "Engineer"
        
        mem_store = MagicMock()
        del mem_store.get_by_role
        mem_store.get = Mock(return_value=[msg1])
        mem_store.__iter__ = Mock(side_effect=TypeError())
        
        result = MetaGPTAdapter.get_messages_by_role(mem_store, "Tester")
        assert result == []
    
    def test_get_messages_by_role_messages_without_role_attr(self):
        """Test get_messages_by_role with messages lacking role attribute"""
        messages = [
            MockMessage("assistant", "msg1"),
            MockMessage("assistant", "msg2"),
        ]
        # Remove role attribute from messages
        for msg in messages:
            del msg.role
        
        mem_store = MagicMock()
        del mem_store.get_by_role
        mem_store.get = Mock(return_value=messages)
        mem_store.__iter__ = Mock(side_effect=TypeError())
        
        result = MetaGPTAdapter.get_messages_by_role(mem_store, "Engineer")
        assert result == []
    
    def test_get_messages_by_role_exception_handling(self, caplog):
        """Test get_messages_by_role error handling"""
        mem_store = Mock()
        mem_store.get_by_role.side_effect = Exception("API error")
        
        with caplog.at_level(logging.WARNING):
            result = MetaGPTAdapter.get_messages_by_role(mem_store, "Engineer")
        
        assert result == []
        assert "Role mesajları alınırken hata" in caplog.text


class TestMetaGPTAdapterGetNews:
    """Test MetaGPTAdapter.get_news() method"""
    
    def test_get_news_with_none_role(self):
        """Test get_news with None role"""
        result = MetaGPTAdapter.get_news(None)
        assert result == []
    
    def test_get_news_role_without_rc(self):
        """Test get_news when role has no rc attribute"""
        role = Mock()
        del role.rc
        result = MetaGPTAdapter.get_news(role)
        assert result == []
    
    def test_get_news_rc_without_news(self):
        """Test get_news when rc has no news attribute"""
        role = Mock()
        role.rc = Mock(spec=[])
        result = MetaGPTAdapter.get_news(role)
        assert result == []
    
    def test_get_news_success(self):
        """Test get_news returns news successfully"""
        news = [MockMessage("user", "news1"), MockMessage("assistant", "news2")]
        role = Mock()
        role.rc = Mock()
        role.rc.news = news
        
        result = MetaGPTAdapter.get_news(role)
        assert len(result) == 2
    
    def test_get_news_with_none_news(self):
        """Test get_news when news is None"""
        role = Mock()
        role.rc = Mock()
        role.rc.news = None
        
        result = MetaGPTAdapter.get_news(role)
        assert result == []
    
    def test_get_news_with_non_iterable_news(self):
        """Test get_news when news is not iterable"""
        role = Mock()
        role.rc = Mock()
        role.rc.news = 123  # Not iterable
        
        result = MetaGPTAdapter.get_news(role)
        assert result == []
    
    def test_get_news_exception_handling(self, caplog):
        """Test get_news error handling"""
        role = Mock()
        role.rc = Mock()
        role.rc.news = MagicMock()
        role.rc.news.__iter__ = Mock(side_effect=Exception("Iteration error"))
        
        with caplog.at_level(logging.WARNING):
            result = MetaGPTAdapter.get_news(role)
        
        assert result == []
        assert "News alınırken hata" in caplog.text
    
    def test_get_news_with_generator(self):
        """Test get_news with generator"""
        def news_generator():
            yield MockMessage("user", "news1")
            yield MockMessage("assistant", "news2")
        
        role = Mock()
        role.rc = Mock()
        role.rc.news = news_generator()
        
        result = MetaGPTAdapter.get_news(role)
        assert len(result) == 2


class TestMetaGPTAdapterIntegration:
    """Integration tests for MetaGPTAdapter"""
    
    def test_adapter_full_workflow(self):
        """Test complete adapter workflow"""
        # Create a realistic role structure
        role = Mock()
        memory = Mock()
        
        # Setup memory with messages
        messages = [
            MockMessage("user", "task"),
            MockMessage("assistant", "response"),
        ]
        memory.get = Mock(return_value=messages)
        memory.add = Mock()
        
        # Setup role
        role.rc = Mock()
        role.rc.memory = memory
        role.rc.news = []
        
        # Test get_memory_store
        mem_store = MetaGPTAdapter.get_memory_store(role)
        assert mem_store is memory
        
        # Test get_messages
        msgs = MetaGPTAdapter.get_messages(mem_store)
        assert len(msgs) == 2
        
        # Test add_message
        new_msg = MockMessage("user", "new")
        added = MetaGPTAdapter.add_message(mem_store, new_msg)
        assert added is True
        
        # Test get_news
        news = MetaGPTAdapter.get_news(role)
        assert news == []
    
    def test_adapter_fallback_chain(self):
        """Test adapter uses fallbacks in correct order"""
        # Create memory that only supports storage
        mem_store = Mock(spec=['storage'])
        mem_store.storage = [MockMessage("user", "msg")]
        
        # Should use storage fallback
        result = MetaGPTAdapter.get_messages(mem_store)
        assert len(result) == 1
