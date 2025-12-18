# -*- coding: utf-8 -*-
"""Knowledge Ingester Service.

Provides document ingestion and processing functionality for the knowledge base.
Automatically extracts patterns, standards, and best practices from various sources.
"""

import logging
import hashlib
import re
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4, UUID
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from backend.db.models.entities import KnowledgeItem, Workspace
from backend.db.models.enums import (
    KnowledgeCategory,
    KnowledgeSourceType, 
    KnowledgeItemStatus,
    EmbeddingModel
)
from .vector_db import VectorDB, VectorDBError
from .rag_service import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class IngestionJob:
    """Represents an ingestion job."""
    
    id: str
    workspace_id: str
    source_type: KnowledgeSourceType
    source_path: str
    status: str = "pending"
    progress: float = 0.0
    items_processed: int = 0
    items_created: int = 0
    items_updated: int = 0
    error_message: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at


@dataclass
class IngestionResult:
    """Result of an ingestion operation."""
    
    job_id: str
    items_created: int
    items_updated: int
    items_failed: int
    processing_time_ms: float
    errors: List[str]


class DocumentProcessor:
    """Processes different document types for knowledge extraction."""
    
    def __init__(self):
        self.supported_extensions = {
            '.py': self._process_python,
            '.js': self._process_javascript,
            '.ts': self._process_typescript,
            '.java': self._process_java,
            '.php': self._process_php,
            '.go': self._process_go,
            '.rs': self._process_rust,
            '.md': self._process_markdown,
            '.rst': self._process_rst,
            '.txt': self._process_text,
            '.json': self._process_json,
            '.yaml': self._process_yaml,
            '.yml': self._process_yaml,
            '.sql': self._process_sql,
        }
    
    async def process_file(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process a file and extract knowledge items.
        
        Args:
            file_path: Path to the file
            content: File content
            workspace_id: Workspace ID
            source_type: Source type
            
        Returns:
            List of extracted knowledge items
        """
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext in self.supported_extensions:
            processor = self.supported_extensions[file_ext]
            return await processor(file_path, content, workspace_id, source_type)
        else:
            # Default to text processing
            return await self._process_text(file_path, content, workspace_id, source_type)
    
    async def _process_python(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process Python files."""
        items = []
        
        # Extract classes and functions
        class_pattern = r'class\s+(\w+).*?:'
        function_pattern = r'def\s+(\w+)\s*\('
        docstring_pattern = r'"""(.*?)"""'
        
        lines = content.split('\n')
        current_function = None
        current_class = None
        current_docstring = []
        in_docstring = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Check for classes
            class_match = re.match(class_pattern, line)
            if class_match:
                class_name = class_match.group(1)
                current_class = {
                    'name': class_name,
                    'start_line': i + 1,
                    'docstring': ' '.join(current_docstring) if current_docstring else None
                }
                current_docstring = []
                continue
            
            # Check for functions
            function_match = re.match(function_pattern, line)
            if function_match:
                function_name = function_match.group(1)
                
                # Create knowledge item for function
                if current_docstring:
                    item = self._create_code_pattern_item(
                        f"Function: {function_name}",
                        ' '.join(current_docstring),
                        file_path,
                        i + 1,
                        workspace_id,
                        'python',
                        source_type,
                        'function'
                    )
                    items.append(item)
                
                current_function = function_name
                current_docstring = []
                continue
            
            # Extract docstrings
            if '"""' in line:
                if not in_docstring:
                    in_docstring = True
                    # Extract docstring content
                    docstring_match = re.search(r'"""(.*?)"""', line, re.DOTALL)
                    if docstring_match:
                        docstring_content = docstring_match.group(1).strip()
                        if docstring_content:
                            current_docstring.append(docstring_content)
                    in_docstring = False
                else:
                    in_docstring = False
            elif in_docstring and line:
                current_docstring.append(line)
        
        return items
    
    async def _process_javascript(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process JavaScript files."""
        items = []
        
        # Extract functions and classes
        function_pattern = r'(?:function\s+(\w+)|const\s+(\w+)\s*=|(\w+)\s*:\s*function)'
        class_pattern = r'class\s+(\w+)'
        comment_pattern = r'/\*\*(.*?)\*/'
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Extract JSDoc comments
            comment_match = re.search(comment_pattern, line, re.DOTALL)
            if comment_match:
                doc_content = comment_match.group(1).strip()
                if doc_content:
                    item = self._create_code_pattern_item(
                        f"JavaScript Pattern",
                        doc_content,
                        file_path,
                        i + 1,
                        workspace_id,
                        'javascript',
                        source_type,
                        'pattern'
                    )
                    items.append(item)
            
            # Extract function definitions
            function_match = re.search(function_pattern, line)
            if function_match:
                function_name = function_match.group(1) or function_match.group(2) or function_match.group(3)
                if function_name:
                    item = self._create_code_pattern_item(
                        f"Function: {function_name}",
                        f"JavaScript function definition from {Path(file_path).name}",
                        file_path,
                        i + 1,
                        workspace_id,
                        'javascript',
                        source_type,
                        'function'
                    )
                    items.append(item)
        
        return items
    
    async def _process_typescript(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process TypeScript files."""
        return await self._process_javascript(file_path, content, workspace_id, source_type)
    
    async def _process_java(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process Java files."""
        items = []
        
        # Extract classes, methods, and Javadoc
        class_pattern = r'(?:public|private|protected)?\s*class\s+(\w+)'
        method_pattern = r'(?:public|private|protected)?\s*(?:static\s+)?[\w<>\[\]\.\s]+\s+(\w+)\s*\('
        javadoc_pattern = r'/\*\*(.*?)\*/'
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Extract Javadoc comments
            javadoc_match = re.search(javadoc_pattern, line, re.DOTALL)
            if javadoc_match:
                javadoc_content = javadoc_match.group(1).strip()
                if javadoc_content:
                    item = self._create_code_pattern_item(
                        f"Java Pattern",
                        javadoc_content,
                        file_path,
                        i + 1,
                        workspace_id,
                        'java',
                        source_type,
                        'pattern'
                    )
                    items.append(item)
            
            # Extract method definitions
            method_match = re.search(method_pattern, line)
            if method_match:
                method_name = method_match.group(1)
                if method_name:
                    item = self._create_code_pattern_item(
                        f"Method: {method_name}",
                        f"Java method definition from {Path(file_path).name}",
                        file_path,
                        i + 1,
                        workspace_id,
                        'java',
                        source_type,
                        'method'
                    )
                    items.append(item)
        
        return items
    
    async def _process_php(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process PHP files."""
        items = []
        
        # Extract functions, classes, and comments
        function_pattern = r'function\s+(\w+)\s*\('
        class_pattern = r'class\s+(\w+)'
        comment_pattern = r'/\*\*(.*?)\*/'
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Extract PHPDoc comments
            comment_match = re.search(comment_pattern, line, re.DOTALL)
            if comment_match:
                doc_content = comment_match.group(1).strip()
                if doc_content:
                    item = self._create_code_pattern_item(
                        f"PHP Pattern",
                        doc_content,
                        file_path,
                        i + 1,
                        workspace_id,
                        'php',
                        source_type,
                        'pattern'
                    )
                    items.append(item)
        
        return items
    
    async def _process_go(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process Go files."""
        items = []
        
        # Extract functions, structs, and comments
        function_pattern = r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\('
        struct_pattern = r'type\s+(\w+)\s+struct'
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Extract comments
            if line.startswith('//'):
                comment_content = line[2:].strip()
                if comment_content and len(comment_content) > 10:
                    item = self._create_code_pattern_item(
                        f"Go Pattern",
                        comment_content,
                        file_path,
                        i + 1,
                        workspace_id,
                        'go',
                        source_type,
                        'pattern'
                    )
                    items.append(item)
        
        return items
    
    async def _process_rust(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process Rust files."""
        items = []
        
        # Extract functions, structs, and comments
        function_pattern = r'fn\s+(\w+)\s*\('
        struct_pattern = r'struct\s+(\w+)'
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Extract comments
            if line.startswith('///') or line.startswith('//'):
                comment_content = line[3:] if line.startswith('///') else line[2:]
                comment_content = comment_content.strip()
                if comment_content and len(comment_content) > 10:
                    item = self._create_code_pattern_item(
                        f"Rust Pattern",
                        comment_content,
                        file_path,
                        i + 1,
                        workspace_id,
                        'rust',
                        source_type,
                        'pattern'
                    )
                    items.append(item)
        
        return items
    
    async def _process_markdown(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process Markdown files."""
        items = []
        
        lines = content.split('\n')
        current_section = None
        current_content = []
        
        for i, line in enumerate(lines):
            # Check for headers
            if line.startswith('#'):
                # Save previous section
                if current_section and current_content:
                    item = self._create_documentation_item(
                        current_section,
                        '\n'.join(current_content),
                        file_path,
                        i,
                        workspace_id,
                        source_type,
                        'markdown'
                    )
                    items.append(item)
                
                # Start new section
                current_section = line.lstrip('#').strip()
                current_content = []
            else:
                if line.strip():
                    current_content.append(line)
        
        # Save last section
        if current_section and current_content:
            item = self._create_documentation_item(
                current_section,
                '\n'.join(current_content),
                file_path,
                len(lines),
                workspace_id,
                source_type,
                'markdown'
            )
            items.append(item)
        
        return items
    
    async def _process_rst(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process reStructuredText files."""
        return await self._process_markdown(file_path, content, workspace_id, source_type)
    
    async def _process_text(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process plain text files."""
        items = []
        
        # Split content into sections based on blank lines or patterns
        sections = re.split(r'\n\s*\n', content)
        
        for i, section in enumerate(sections):
            section = section.strip()
            if section and len(section) > 20:  # Only process substantial sections
                item = self._create_documentation_item(
                    f"Text Section {i+1}",
                    section,
                    file_path,
                    i * 2,  # Approximate line number
                    workspace_id,
                    source_type,
                    'text'
                )
                items.append(item)
        
        return items
    
    async def _process_json(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process JSON files."""
        items = []
        
        try:
            import json
            data = json.loads(content)
            
            # Create a knowledge item for the JSON structure
            item = self._create_code_pattern_item(
                f"JSON Configuration: {Path(file_path).stem}",
                f"JSON configuration structure:\n{json.dumps(data, indent=2)}",
                file_path,
                1,
                workspace_id,
                'json',
                source_type,
                'configuration'
            )
            items.append(item)
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON file {file_path}: {e}")
        
        return items
    
    async def _process_yaml(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process YAML files."""
        items = []
        
        try:
            import yaml
            
            # Try to parse as YAML
            data = yaml.safe_load(content)
            if data:
                item = self._create_code_pattern_item(
                    f"YAML Configuration: {Path(file_path).stem}",
                    f"YAML configuration structure:\n{yaml.dump(data, default_flow_style=False)}",
                    file_path,
                    1,
                    workspace_id,
                    'yaml',
                    source_type,
                    'configuration'
                )
                items.append(item)
                
        except ImportError:
            # Fallback to treating as text
            return await self._process_text(file_path, content, workspace_id, source_type)
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse YAML file {file_path}: {e}")
        
        return items
    
    async def _process_sql(
        self,
        file_path: str,
        content: str,
        workspace_id: str,
        source_type: KnowledgeSourceType
    ) -> List[Dict[str, Any]]:
        """Process SQL files."""
        items = []
        
        # Split SQL into statements
        statements = re.split(r';\s*\n', content)
        
        for i, statement in enumerate(statements):
            statement = statement.strip()
            if statement and len(statement) > 20:
                item = self._create_code_pattern_item(
                    f"SQL Query {i+1}",
                    statement,
                    file_path,
                    i * 10,  # Approximate line number
                    workspace_id,
                    'sql',
                    source_type,
                    'query'
                )
                items.append(item)
        
        return items
    
    def _create_code_pattern_item(
        self,
        title: str,
        content: str,
        file_path: str,
        line_number: int,
        workspace_id: str,
        language: str,
        source_type: KnowledgeSourceType,
        pattern_type: str
    ) -> Dict[str, Any]:
        """Create a code pattern knowledge item."""
        return {
            'title': title,
            'content': content,
            'category': KnowledgeCategory.CODE_PATTERN,
            'language': language,
            'tags': [pattern_type, f'from_{source_type.value}'],
            'source': source_type,
            'file_path': file_path,
            'line_start': line_number,
            'line_end': line_number + content.count('\n'),
            'chunk_hash': self._generate_content_hash(content),
        }
    
    def _create_documentation_item(
        self,
        title: str,
        content: str,
        file_path: str,
        line_number: int,
        workspace_id: str,
        source_type: KnowledgeSourceType,
        doc_type: str
    ) -> Dict[str, Any]:
        """Create a documentation knowledge item."""
        return {
            'title': title,
            'content': content,
            'category': KnowledgeCategory.BEST_PRACTICE,
            'language': None,
            'tags': [doc_type, f'from_{source_type.value}'],
            'source': source_type,
            'file_path': file_path,
            'line_start': line_number,
            'line_end': line_number + content.count('\n'),
            'chunk_hash': self._generate_content_hash(content),
        }
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()


class KnowledgeIngester:
    """Service for ingesting and processing knowledge items."""
    
    def __init__(
        self,
        db_session: AsyncSession,
        vector_db: VectorDB,
        embedding_service: EmbeddingService
    ):
        """Initialize knowledge ingester.
        
        Args:
            db_session: Database session
            vector_db: Vector database instance
            embedding_service: Embedding service
        """
        self.db_session = db_session
        self.vector_db = vector_db
        self.embedding_service = embedding_service
        self.document_processor = DocumentProcessor()
        
        logger.info("Knowledge Ingester initialized")
    
    async def create_ingestion_job(
        self,
        workspace_id: str,
        source_type: KnowledgeSourceType,
        source_path: str,
        **kwargs
    ) -> IngestionJob:
        """Create a new ingestion job.
        
        Args:
            workspace_id: Workspace ID
            source_type: Type of source to ingest
            source_path: Path to the source
            **kwargs: Additional job parameters
            
        Returns:
            Created ingestion job
        """
        job = IngestionJob(
            id=str(uuid4()),
            workspace_id=workspace_id,
            source_type=source_type,
            source_path=source_path,
            **kwargs
        )
        
        # TODO: Store job in database for tracking
        logger.info(f"Created ingestion job {job.id} for workspace {workspace_id}")
        return job
    
    async def ingest_repository(
        self,
        workspace_id: str,
        repo_url: str,
        branch: str = "main",
        auto_update: bool = False
    ) -> IngestionJob:
        """Ingest knowledge from a repository.
        
        Args:
            workspace_id: Workspace ID
            repo_url: Repository URL
            branch: Repository branch
            auto_update: Whether to auto-update existing items
            
        Returns:
            Created ingestion job
        """
        job = await self.create_ingestion_job(
            workspace_id=workspace_id,
            source_type=KnowledgeSourceType.INTERNAL_REPOSITORY,
            source_path=repo_url,
            branch=branch,
            auto_update=auto_update
        )
        
        # TODO: Clone repository and process files
        # This is a placeholder implementation
        job.status = "completed"
        job.progress = 1.0
        
        logger.info(f"Repository ingestion job {job.id} completed")
        return job
    
    async def ingest_documentation(
        self,
        workspace_id: str,
        doc_paths: List[str],
        auto_update: bool = False
    ) -> IngestionJob:
        """Ingest knowledge from documentation files.
        
        Args:
            workspace_id: Workspace ID
            doc_paths: List of documentation file paths
            auto_update: Whether to auto-update existing items
            
        Returns:
            Created ingestion job
        """
        job = await self.create_ingestion_job(
            workspace_id=workspace_id,
            source_type=KnowledgeSourceType.DOCUMENTATION,
            source_path=','.join(doc_paths),
            auto_update=auto_update
        )
        
        try:
            total_files = len(doc_paths)
            processed_files = 0
            created_items = 0
            updated_items = 0
            
            for doc_path in doc_paths:
                # Process documentation file
                items = await self._process_documentation_file(doc_path, workspace_id)
                created, updated = await self._save_knowledge_items(
                    items, workspace_id, job.id, auto_update
                )
                
                created_items += created
                updated_items += updated
                processed_files += 1
                
                job.progress = processed_files / total_files
                job.items_processed = processed_files
                job.items_created = created_items
                job.items_updated = updated_items
            
            job.status = "completed"
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            logger.error(f"Documentation ingestion job {job.id} failed: {e}")
        
        logger.info(f"Documentation ingestion job {job.id} completed")
        return job
    
    async def ingest_adr_records(self, workspace_id: str) -> IngestionJob:
        """Ingest knowledge from Architecture Decision Records.
        
        Args:
            workspace_id: Workspace ID
            
        Returns:
            Created ingestion job
        """
        job = await self.create_ingestion_job(
            workspace_id=workspace_id,
            source_type=KnowledgeSourceType.ARCHITECTURE_DECISION,
            source_path="adrs"
        )
        
        try:
            # Get ADR records from database
            from backend.db.models.entities import ADR
            
            stmt = select(ADR).where(ADR.workspace_id == workspace_id)
            result = await self.db_session.execute(stmt)
            adrs = result.scalars().all()
            
            total_adrs = len(adrs)
            processed_adrs = 0
            created_items = 0
            
            for adr in adrs:
                # Convert ADR to knowledge item
                item_data = {
                    'title': f"ADR: {adr.title}",
                    'content': f"Context: {adr.context}\n\nDecision: {adr.decision}\n\nConsequences: {adr.consequences}",
                    'category': KnowledgeCategory.ARCHITECTURE,
                    'language': None,
                    'tags': ['adr', adr.status.value, *adr.tags],
                    'source': KnowledgeSourceType.ARCHITECTURE_DECISION,
                    'author': adr.created_by,
                    'file_path': f"adrs/{adr.id}.md",
                    'chunk_hash': self._generate_content_hash(adr.content),
                }
                
                items = [item_data]
                created, _ = await self._save_knowledge_items(items, workspace_id, job.id)
                created_items += created
                
                processed_adrs += 1
                job.progress = processed_adrs / total_adrs
                job.items_processed = processed_adrs
                job.items_created = created_items
            
            job.status = "completed"
            
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            logger.error(f"ADR ingestion job {job.id} failed: {e}")
        
        logger.info(f"ADR ingestion job {job.id} completed")
        return job
    
    async def ingest_examples(
        self,
        workspace_id: str,
        example_paths: List[str]
    ) -> IngestionJob:
        """Ingest knowledge from code examples.
        
        Args:
            workspace_id: Workspace ID
            example_paths: List of example file paths
            
        Returns:
            Created ingestion job
        """
        job = await self.create_ingestion_job(
            workspace_id=workspace_id,
            source_type=KnowledgeSourceType.MANUAL_ENTRY,
            source_path=','.join(example_paths)
        )
        
        # TODO: Implement example ingestion
        job.status = "completed"
        job.progress = 1.0
        
        logger.info(f"Example ingestion job {job.id} completed")
        return job
    
    async def _process_documentation_file(
        self,
        file_path: str,
        workspace_id: str
    ) -> List[Dict[str, Any]]:
        """Process a single documentation file.
        
        Args:
            file_path: Path to the documentation file
            workspace_id: Workspace ID
            
        Returns:
            List of extracted knowledge items
        """
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Process file using document processor
            items = await self.document_processor.process_file(
                file_path=file_path,
                content=content,
                workspace_id=workspace_id,
                source_type=KnowledgeSourceType.DOCUMENTATION
            )
            
            return items
            
        except Exception as e:
            logger.error(f"Failed to process documentation file {file_path}: {e}")
            return []
    
    async def _save_knowledge_items(
        self,
        items_data: List[Dict[str, Any]],
        workspace_id: str,
        job_id: str,
        auto_update: bool = False
    ) -> Tuple[int, int]:
        """Save knowledge items to database and vector store.
        
        Args:
            items_data: List of knowledge item data
            workspace_id: Workspace ID
            job_id: Ingestion job ID
            auto_update: Whether to auto-update existing items
            
        Returns:
            Tuple of (created_count, updated_count)
        """
        created_count = 0
        updated_count = 0
        
        for item_data in items_data:
            try:
                # Check if item already exists
                existing_item = await self._find_existing_item(
                    workspace_id, item_data.get('chunk_hash'), item_data.get('title')
                )
                
                if existing_item and not auto_update:
                    continue
                
                if existing_item:
                    # Update existing item
                    await self._update_knowledge_item(existing_item, item_data, job_id)
                    updated_count += 1
                else:
                    # Create new item
                    await self._create_knowledge_item(item_data, workspace_id, job_id)
                    created_count += 1
                
            except Exception as e:
                logger.error(f"Failed to save knowledge item: {e}")
        
        return created_count, updated_count
    
    async def _find_existing_item(
        self,
        workspace_id: str,
        chunk_hash: Optional[str],
        title: str
    ) -> Optional[KnowledgeItem]:
        """Find existing knowledge item by hash or title.
        
        Args:
            workspace_id: Workspace ID
            chunk_hash: Content hash
            title: Item title
            
        Returns:
            Existing knowledge item or None
        """
        # Try to find by hash first
        if chunk_hash:
            stmt = select(KnowledgeItem).where(
                KnowledgeItem.workspace_id == workspace_id,
                KnowledgeItem.chunk_hash == chunk_hash
            )
            result = await self.db_session.execute(stmt)
            item = result.scalar_one_or_none()
            if item:
                return item
        
        # Try to find by title
        stmt = select(KnowledgeItem).where(
            KnowledgeItem.workspace_id == workspace_id,
            KnowledgeItem.title == title
        )
        result = await self.db_session.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _create_knowledge_item(
        self,
        item_data: Dict[str, Any],
        workspace_id: str,
        job_id: str
    ) -> KnowledgeItem:
        """Create a new knowledge item.
        
        Args:
            item_data: Knowledge item data
            workspace_id: Workspace ID
            job_id: Ingestion job ID
            
        Returns:
            Created knowledge item
        """
        # Create knowledge item
        item = KnowledgeItem(
            workspace_id=workspace_id,
            title=item_data['title'],
            content=item_data['content'],
            category=item_data['category'],
            language=item_data.get('language'),
            tags=item_data.get('tags', []),
            source=item_data['source'],
            status=KnowledgeItemStatus.ACTIVE,
            file_path=item_data.get('file_path'),
            line_start=item_data.get('line_start'),
            line_end=item_data.get('line_end'),
            chunk_hash=item_data.get('chunk_hash'),
            content_hash=item_data.get('chunk_hash'),
            embedding_model=EmbeddingModel.OPENAI_TEXT_EMBEDDING_3_SMALL
        )
        
        # Generate embedding
        try:
            embedding = await self.embedding_service.embed_text(
                f"{item.title}\n{item.content}"
            )
            item.vector_dimension = len(embedding)
            
            # Store in vector database
            embedding_id = self.vector_db._generate_embedding_id(
                f"{item.title}\n{item.content}", workspace_id
            )
            
            success = await self.vector_db.store_embedding(
                text_id=embedding_id,
                embedding=embedding,
                metadata={
                    'title': item.title,
                    'category': item.category.value,
                    'language': item.language,
                    'tags': item.tags,
                    'workspace_id': workspace_id,
                    'knowledge_item_id': item.id if hasattr(item, 'id') else 'temp'
                },
                collection_name=self.vector_db._get_collection_name(workspace_id)
            )
            
            if success:
                item.embedding_id = embedding_id
            else:
                logger.warning(f"Failed to store embedding for item {item.title}")
                
        except Exception as e:
            logger.error(f"Failed to generate or store embedding: {e}")
        
        # Save to database
        self.db_session.add(item)
        await self.db_session.flush()  # Get the ID
        
        return item
    
    async def _update_knowledge_item(
        self,
        item: KnowledgeItem,
        item_data: Dict[str, Any],
        job_id: str
    ) -> None:
        """Update an existing knowledge item.
        
        Args:
            item: Existing knowledge item
            item_data: New knowledge item data
            job_id: Ingestion job ID
        """
        # Update basic fields
        item.title = item_data['title']
        item.content = item_data['content']
        item.tags = item_data.get('tags', [])
        item.updated_at = datetime.now()
        
        # Update embedding if content changed
        if item.content_hash != item_data.get('chunk_hash'):
            await self._update_embedding(item, item_data, job_id)
    
    async def _update_embedding(
        self,
        item: KnowledgeItem,
        item_data: Dict[str, Any],
        job_id: str
    ) -> None:
        """Update embedding for a knowledge item.
        
        Args:
            item: Knowledge item
            item_data: Knowledge item data
            job_id: Ingestion job ID
        """
        try:
            # Generate new embedding
            embedding = await self.embedding_service.embed_text(
                f"{item_data['title']}\n{item_data['content']}"
            )
            
            # Update in vector database
            if item.embedding_id:
                await self.vector_db.delete(item.embedding_id)
            
            embedding_id = self.vector_db._generate_embedding_id(
                f"{item_data['title']}\n{item_data['content']}", item.workspace_id
            )
            
            success = await self.vector_db.store_embedding(
                text_id=embedding_id,
                embedding=embedding,
                metadata={
                    'title': item_data['title'],
                    'category': item_data['category'].value,
                    'language': item_data.get('language'),
                    'tags': item_data.get('tags', []),
                    'workspace_id': item.workspace_id,
                    'knowledge_item_id': item.id
                },
                collection_name=self.vector_db._get_collection_name(item.workspace_id)
            )
            
            if success:
                item.embedding_id = embedding_id
                item.embedding_model = EmbeddingModel.OPENAI_TEXT_EMBEDDING_3_SMALL
                item.vector_dimension = len(embedding)
                item.content_hash = item_data.get('chunk_hash')
                
        except Exception as e:
            logger.error(f"Failed to update embedding: {e}")
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate hash for content deduplication."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()