# -*- coding: utf-8 -*-
"""Enhanced Actions with Knowledge Base Integration.

Provides enhanced versions of existing actions that integrate with the knowledge base
for RAG (Retrieval-Augmented Generation) functionality.
"""

import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_async_session
from backend.services.knowledge.factory import create_knowledge_base_services, cleanup_knowledge_base_services

logger = logging.getLogger(__name__)


class RAGEnhancedAction:
    """Mixin for actions enhanced with RAG functionality."""
    
    def __init__(self):
        self._knowledge_services: Dict[str, Any] = {}
        self._workspace_id: Optional[str] = None
        self._enable_rag: bool = True
        self._rag_max_examples: int = 3
    
    async def initialize_knowledge_base(self, workspace_id: str, db_session: Optional[AsyncSession] = None):
        """Initialize knowledge base services for this action.
        
        Args:
            workspace_id: Workspace ID for knowledge base operations
            db_session: Database session (optional, will create if not provided)
        """
        try:
            if not db_session:
                from backend.db.session import get_async_session
                async with get_async_session() as session:
                    db_session = session
            
            self._workspace_id = workspace_id
            self._knowledge_services = await create_knowledge_base_services(db_session)
            
        except Exception as e:
            logger.warning(f"Failed to initialize knowledge base services: {e}")
            self._enable_rag = False
    
    async def enhance_prompt_with_knowledge(
        self,
        base_prompt: str,
        query: str,
        category_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
        max_examples: Optional[int] = None
    ) -> str:
        """Enhance prompt with relevant knowledge from the knowledge base.
        
        Args:
            base_prompt: Original prompt
            query: Search query for finding relevant knowledge
            category_filter: Filter by knowledge category
            language_filter: Filter by programming language
            max_examples: Maximum number of examples to include
            
        Returns:
            Enhanced prompt with knowledge examples
        """
        if not self._enable_rag or not self._workspace_id or not self._knowledge_services:
            return base_prompt
        
        try:
            enhanced = await self._knowledge_services['rag_service'].enhance_prompt(
                base_prompt=base_prompt,
                query=query,
                workspace_id=self._workspace_id,
                num_examples=max_examples or self._rag_max_examples,
                category_filter=category_filter,
                language_filter=language_filter
            )
            
            return enhanced.enhanced_prompt
            
        except Exception as e:
            logger.warning(f"Failed to enhance prompt with knowledge: {e}")
            return base_prompt
    
    async def search_knowledge(
        self,
        query: str,
        category_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Search knowledge base for relevant information.
        
        Args:
            query: Search query
            category_filter: Filter by knowledge category
            language_filter: Filter by programming language
            max_results: Maximum number of results
            
        Returns:
            List of search results
        """
        if not self._enable_rag or not self._workspace_id or not self._knowledge_services:
            return []
        
        try:
            from backend.services.knowledge.rag_service import KnowledgeSearchRequest
            from backend.db.models.enums import KnowledgeCategory
            
            category = KnowledgeCategory(category_filter) if category_filter else None
            
            search_request = KnowledgeSearchRequest(
                query=query,
                workspace_id=self._workspace_id,
                top_k=max_results,
                category_filter=category,
                language_filter=language_filter
            )
            
            search_result = await self._knowledge_services['retriever'].search_knowledge(search_request)
            
            return [
                {
                    'id': item.id,
                    'title': item.title,
                    'content_preview': item.content[:200] + "..." if len(item.content) > 200 else item.content,
                    'category': item.category.value,
                    'language': item.language,
                    'tags': item.tags,
                    'author': item.author,
                    'relevance_score': item.relevance_score,
                    'source': item.source.value,
                    'file_path': item.file_path
                }
                for item in search_result.items
            ]
            
        except Exception as e:
            logger.warning(f"Failed to search knowledge: {e}")
            return []
    
    async def get_code_patterns(
        self,
        language: str,
        pattern_type: str = "function",
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Get code patterns for a specific language and pattern type.
        
        Args:
            language: Programming language
            pattern_type: Type of code pattern (function, class, etc.)
            max_results: Maximum number of patterns
            
        Returns:
            List of code patterns
        """
        query = f"{pattern_type} pattern {language}"
        return await self.search_knowledge(
            query=query,
            category_filter="code_pattern",
            language_filter=language,
            max_results=max_results
        )
    
    async def get_best_practices(
        self,
        topic: str,
        language: Optional[str] = None,
        max_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Get best practices for a specific topic.
        
        Args:
            topic: Topic or area (e.g., "authentication", "testing")
            language: Programming language (optional)
            max_results: Maximum number of best practices
            
        Returns:
            List of best practices
        """
        query = f"best practice {topic}"
        return await self.search_knowledge(
            query=query,
            category_filter="best_practice",
            language_filter=language,
            max_results=max_results
        )
    
    async def get_architecture_standards(
        self,
        topic: str,
        max_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Get architecture standards and patterns.
        
        Args:
            topic: Architecture topic
            max_results: Maximum number of standards
            
        Returns:
            List of architecture standards
        """
        return await self.search_knowledge(
            query=f"architecture standard {topic}",
            category_filter="architecture",
            max_results=max_results
        )
    
    async def get_security_guidelines(
        self,
        topic: str,
        language: Optional[str] = None,
        max_results: int = 3
    ) -> List[Dict[str, Any]]:
        """Get security guidelines for a specific topic.
        
        Args:
            topic: Security topic
            language: Programming language (optional)
            max_results: Maximum number of guidelines
            
        Returns:
            List of security guidelines
        """
        return await self.search_knowledge(
            query=f"security guideline {topic}",
            category_filter="security_guideline",
            language_filter=language,
            max_results=max_results
        )
    
    async def track_knowledge_usage(self, knowledge_item_id: str, usage_type: str = "reference"):
        """Track usage of a knowledge item.
        
        Args:
            knowledge_item_id: ID of the knowledge item
            usage_type: Type of usage (search, reference, etc.)
        """
        if not self._enable_rag or not self._workspace_id or not self._knowledge_services:
            return
        
        try:
            await self._knowledge_services['rag_service'].track_usage(
                knowledge_item_id=knowledge_item_id,
                usage_type=usage_type,
                action_type=self.__class__.__name__
            )
        except Exception as e:
            logger.warning(f"Failed to track knowledge usage: {e}")
    
    async def cleanup_knowledge_services(self):
        """Clean up knowledge base services."""
        if self._knowledge_services:
            await cleanup_knowledge_base_services(list(self._knowledge_services.values())[0]['db_session'])
            self._knowledge_services.clear()


class EnhancedAnalyzeTask(RAGEnhancedAction):
    """Enhanced AnalyzeTask with knowledge base integration."""
    
    def __init__(self):
        super().__init__()
        self.original_class = None  # Will be set when enhancing the original class
    
    async def run_enhanced(self, task: str, target_stack: str = None, workspace_id: str = None) -> str:
        """Enhanced run method with knowledge integration."""
        try:
            # Initialize knowledge base if workspace_id provided
            if workspace_id:
                await self.initialize_knowledge_base(workspace_id)
            
            # Enhance the prompt with relevant knowledge
            knowledge_query = f"{task} {target_stack or 'development'} best practices patterns"
            
            enhanced_prompt = await self.enhance_prompt_with_knowledge(
                base_prompt=f"Analyze the following task: {task}",
                query=knowledge_query,
                category_filter="best_practice",
                language_filter=target_stack.lower() if target_stack else None
            )
            
            # Call the original analyze task logic
            # This would integrate with the existing AnalyzeTask implementation
            if self.original_class:
                result = await self.original_class.run(self, task, target_stack)
                
                # If we have relevant patterns, add them to the result
                patterns = await self.get_code_patterns(
                    language=target_stack.lower() if target_stack else "python",
                    max_results=3
                )
                
                if patterns:
                    enhanced_result = result + "\n\nRelevant Patterns Found:\n"
                    for pattern in patterns:
                        enhanced_result += f"- {pattern['title']}: {pattern['content_preview']}\n"
                    
                    # Track usage of these patterns
                    for pattern in patterns:
                        await self.track_knowledge_usage(pattern['id'], "reference")
                    
                    return enhanced_result
                
                return result
            
            # Fallback if no original class available
            return f"Analysis for task: {task}"
            
        except Exception as e:
            logger.error(f"Enhanced AnalyzeTask failed: {e}")
            # Fallback to basic analysis
            return f"Analysis for task: {task}"


class EnhancedWriteCode(RAGEnhancedAction):
    """Enhanced WriteCode with knowledge base integration."""
    
    def __init__(self):
        super().__init__()
        self.original_class = None
    
    async def run_enhanced(
        self,
        instruction: str,
        plan: str,
        target_stack: str = None,
        workspace_id: str = None,
        **kwargs
    ) -> str:
        """Enhanced run method with code patterns and best practices."""
        try:
            # Initialize knowledge base if workspace_id provided
            if workspace_id:
                await self.initialize_knowledge_base(workspace_id)
            
            # Get relevant code patterns and best practices
            language = target_stack.lower() if target_stack else "python"
            
            code_patterns = await self.get_code_patterns(language, "function", 5)
            best_practices = await self.get_best_practices("development", language, 3)
            
            # Build enhanced prompt
            enhanced_instruction = instruction
            if code_patterns:
                enhanced_instruction += "\n\nRelevant Code Patterns:\n"
                for pattern in code_patterns:
                    enhanced_instruction += f"- {pattern['title']}: {pattern['content_preview']}\n"
            
            if best_practices:
                enhanced_instruction += "\n\nBest Practices:\n"
                for practice in best_practices:
                    enhanced_instruction += f"- {practice['title']}: {practice['content_preview']}\n"
            
            # Call original write code logic
            if self.original_class:
                result = await self.original_class.run(self, instruction, plan, **kwargs)
                
                # Track usage of referenced patterns and practices
                for pattern in code_patterns:
                    await self.track_knowledge_usage(pattern['id'], "reference")
                for practice in best_practices:
                    await self.track_knowledge_usage(practice['id'], "reference")
                
                return result
            
            # Fallback implementation
            return f"Generated code for: {instruction}"
            
        except Exception as e:
            logger.error(f"Enhanced WriteCode failed: {e}")
            return f"Generated code for: {instruction}"


class EnhancedReviewCode(RAGEnhancedAction):
    """Enhanced ReviewCode with knowledge base integration."""
    
    def __init__(self):
        super().__init__()
        self.original_class = None
    
    async def run_enhanced(
        self,
        code: str,
        tests: str,
        target_stack: str = None,
        workspace_id: str = None,
        **kwargs
    ) -> str:
        """Enhanced run method with security and quality guidelines."""
        try:
            # Initialize knowledge base if workspace_id provided
            if workspace_id:
                await self.initialize_knowledge_base(workspace_id)
            
            # Get relevant security and quality guidelines
            language = target_stack.lower() if target_stack else "python"
            
            security_guidelines = await self.get_security_guidelines("code review", language, 3)
            quality_standards = await self.get_best_practices("code quality", language, 3)
            
            # Build enhanced review prompt
            enhanced_context = f"Code Review for {language} code"
            if security_guidelines:
                enhanced_context += "\n\nSecurity Guidelines:\n"
                for guideline in security_guidelines:
                    enhanced_context += f"- {guideline['title']}: {guideline['content_preview']}\n"
            
            if quality_standards:
                enhanced_context += "\n\nQuality Standards:\n"
                for standard in quality_standards:
                    enhanced_context += f"- {standard['title']}: {standard['content_preview']}\n"
            
            # Call original review code logic
            if self.original_class:
                result = await self.original_class.run(self, code, tests, **kwargs)
                
                # Track usage of referenced guidelines
                for guideline in security_guidelines:
                    await self.track_knowledge_usage(guideline['id'], "reference")
                for standard in quality_standards:
                    await self.track_knowledge_usage(standard['id'], "reference")
                
                return result
            
            # Fallback implementation
            return f"Code review for: {code[:100]}..."
            
        except Exception as e:
            logger.error(f"Enhanced ReviewCode failed: {e}")
            return f"Code review for: {code[:100]}..."


def enhance_existing_action(original_action_class):
    """Enhance an existing action class with RAG functionality.
    
    Args:
        original_action_class: The original action class to enhance
        
    Returns:
        Enhanced action class
    """
    # Determine which enhanced class to use based on the original class name
    enhancement_map = {
        'AnalyzeTask': EnhancedAnalyzeTask,
        'WriteCode': EnhancedWriteCode,
        'ReviewCode': EnhancedReviewCode,
    }
    
    original_name = original_action_class.__name__
    if original_name in enhancement_map:
        enhanced_class = enhancement_map[original_name]
        
        # Create a new enhanced class
        class EnhancedAction(enhanced_class):
            def __init__(self):
                super().__init__()
                enhanced_class.__init__(self)
                enhanced_class.original_class.__init__(self)
        
        # Set the original class reference
        EnhancedAction.__bases__[1].original_class = original_action_class
        
        return EnhancedAction
    
    # Return the original class if no enhancement available
    return original_action_class