# -*- coding: utf-8 -*-
"""backend.tests.test_database_migrations

Comprehensive tests for database migration system including creation, application, rollback, and safety features.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import text, event

from backend.db.models.entities import DatabaseMigration, MigrationRun
from backend.db.models.enums import MigrationStatus, MigrationType
from backend.services.migrations.migration_manager import (
    MigrationManager,
    MigrationCreateRequest,
    MigrationRunRequest,
    MigrationSafetyCheck
)
from backend.services.migrations.backup_manager import BackupManager
from backend.services.migrations.dry_runner import MigrationDryRunner
from backend.services.pipeline.builders.migration_planner import MigrationPlanner


class TestMigrationManager:
    """Test cases for database migration management."""

    @pytest.fixture
    def mock_session(self):
        """Mock async session."""
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def migration_manager(self, mock_session):
        """Create migration manager with mock session."""
        return MigrationManager(mock_session)

    @pytest.fixture
    def sample_migration_request(self):
        """Sample migration creation request."""
        return MigrationCreateRequest(
            name="add_user_preferences_table",
            description="Add user preferences table for settings",
            sql_up="""
                CREATE TABLE user_preferences (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36) NOT NULL,
                    settings JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );
            """,
            sql_down="""
                DROP TABLE user_preferences;
            """,
            estimated_duration=30,
            risk_level="low",
            preflight_checks=[
                "Verify database connectivity",
                "Check current schema version"
            ],
            rollback_plan="Drop user_preferences table and any related indexes"
        )

    def test_migration_create_request_validation(self, sample_migration_request):
        """Test migration creation request validation."""
        # Valid request should pass
        assert sample_migration_request.name == "add_user_preferences_table"
        assert "CREATE TABLE" in sample_migration_request.sql_up
        assert "DROP TABLE" in sample_migration_request.sql_down
        assert sample_migration_request.estimated_duration == 30
        assert sample_migration_request.risk_level == "low"

    @pytest.mark.asyncio
    async def test_create_migration_success(self, migration_manager, mock_session, sample_migration_request):
        """Test successful migration creation."""
        # Mock workspace check
        mock_workspace = MagicMock()
        mock_workspace.id = "workspace123"
        mock_session.get = AsyncMock(return_value=mock_workspace)
        
        # Mock existing migration check
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result
        
        # Mock the async session add and commit
        mock_session.add = AsyncMock()
        
        # Create migration
        migration = await migration_manager.create_migration(
            workspace_id="workspace123",
            request=sample_migration_request,
            user_id="user123"
        )
        
        # Verify migration properties
        assert migration.name == "add_user_preferences_table"
        assert migration.description == "Add user preferences table for settings"
        assert migration.status == MigrationStatus.PENDING
        assert migration.created_by_user_id == "user123"
        assert migration.workspace_id == "workspace123"
        
        # Verify session operations
        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_migration_duplicate_name(self, migration_manager, mock_session, sample_migration_request):
        """Test migration creation with duplicate name."""
        # Mock existing migration with same name
        mock_existing = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = mock_existing
        mock_session.execute.return_value = mock_result
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="already exists"):
            await migration_manager.create_migration(
                workspace_id="workspace123",
                request=sample_migration_request
            )

    @pytest.mark.asyncio
    async def test_get_migration_by_id(self, migration_manager, mock_session):
        """Test getting migration by ID."""
        # Mock migration
        mock_migration = MagicMock()
        mock_migration.id = "migration123"
        mock_migration.name = "test_migration"
        mock_migration.workspace_id = "workspace123"
        mock_migration.status = MigrationStatus.PENDING
        
        mock_session.get = AsyncMock(return_value=mock_migration)
        
        # Get migration
        migration = await migration_manager.get_migration(
            workspace_id="workspace123",
            migration_id="migration123"
        )
        
        # Verify
        assert migration == mock_migration
        mock_session.get.assert_called_once_with(DatabaseMigration, "migration123")

    @pytest.mark.asyncio
    async def test_get_migration_wrong_workspace(self, migration_manager, mock_session):
        """Test getting migration from wrong workspace."""
        # Mock migration from different workspace
        mock_migration = MagicMock()
        mock_migration.workspace_id = "different_workspace"
        
        mock_session.get = AsyncMock(return_value=mock_migration)
        
        with pytest.raises(ValueError, match="does not belong to workspace"):
            await migration_manager.get_migration(
                workspace_id="workspace123",
                migration_id="migration123"
            )

    @pytest.mark.asyncio
    async def test_list_migrations(self, migration_manager, mock_session):
        """Test listing migrations."""
        # Mock migrations query result
        mock_migrations = [
            MagicMock(
                id="migration1",
                name="add_users_table",
                description="Add users table",
                status=MigrationStatus.COMPLETED,
                created_at=datetime.now(timezone.utc),
                created_by_user_id="user123",
                workspace_id="workspace123"
            ),
            MagicMock(
                id="migration2",
                name="add_projects_table",
                description="Add projects table",
                status=MigrationStatus.PENDING,
                created_at=datetime.now(timezone.utc),
                created_by_user_id="user123",
                workspace_id="workspace123"
            )
        ]
        
        # Mock query execution
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_migrations
        mock_session.execute.return_value = mock_result
        
        # List migrations
        migrations = await migration_manager.list_migrations(
            workspace_id="workspace123",
            status_filter=None
        )
        
        # Verify
        assert len(migrations) == 2
        assert migrations[0].id == "migration1"
        assert migrations[1].id == "migration2"

    @pytest.mark.asyncio
    async def test_list_migrations_by_status(self, migration_manager, mock_session):
        """Test listing migrations by status."""
        # Mock migrations with specific status
        mock_migrations = [
            MagicMock(
                id="migration1",
                name="completed_migration",
                status=MigrationStatus.COMPLETED
            )
        ]
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_migrations
        mock_session.execute.return_value = mock_result
        
        # List completed migrations
        migrations = await migration_manager.list_migrations(
            workspace_id="workspace123",
            status_filter=MigrationStatus.COMPLETED
        )
        
        assert len(migrations) == 1
        assert migrations[0].status == MigrationStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_get_migration_history(self, migration_manager, mock_session):
        """Test getting migration history."""
        # Mock migration runs
        mock_runs = [
            MagicMock(
                id="run1",
                migration_id="migration123",
                status=MigrationStatus.COMPLETED,
                started_at=datetime.now(timezone.utc) - timedelta(minutes=10),
                completed_at=datetime.now(timezone.utc),
                error_message=None,
                affected_rows=100
            ),
            MagicMock(
                id="run2",
                migration_id="migration123",
                status=MigrationStatus.FAILED,
                started_at=datetime.now(timezone.utc) - timedelta(days=1),
                completed_at=datetime.now(timezone.utc) - timedelta(days=1, minutes=5),
                error_message="Connection timeout",
                affected_rows=0
            )
        ]
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_runs
        mock_session.execute.return_value = mock_result
        
        # Get history
        history = await migration_manager.get_migration_history("migration123")
        
        # Verify
        assert len(history) == 2
        assert history[0].status == MigrationStatus.COMPLETED
        assert history[1].status == MigrationStatus.FAILED

    @pytest.mark.asyncio
    async def test_update_migration_status(self, migration_manager, mock_session):
        """Test updating migration status."""
        # Mock migration
        mock_migration = MagicMock()
        mock_migration.status = MigrationStatus.PENDING
        
        mock_session.get = AsyncMock(return_value=mock_migration)
        
        # Update status
        await migration_manager.update_migration_status(
            migration_id="migration123",
            new_status=MigrationStatus.IN_PROGRESS
        )
        
        # Verify status and session operations
        assert mock_migration.status == MigrationStatus.IN_PROGRESS
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_migration(self, migration_manager, mock_session):
        """Test deleting migration."""
        # Mock pending migration
        mock_migration = MagicMock()
        mock_migration.status = MigrationStatus.PENDING
        mock_migration.workspace_id = "workspace123"
        mock_migration.name = "test_migration"
        
        mock_session.get = AsyncMock(return_value=mock_migration)
        
        # Delete migration
        result = await migration_manager.delete_migration(
            workspace_id="workspace123",
            migration_id="migration123"
        )
        
        # Verify
        assert result is True
        mock_session.delete.assert_called_once_with(mock_migration)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_migration_in_progress(self, migration_manager, mock_session):
        """Test deleting migration that's in progress."""
        # Mock in-progress migration
        mock_migration = MagicMock()
        mock_migration.status = MigrationStatus.IN_PROGRESS
        
        mock_session.get = AsyncMock(return_value=mock_migration)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Cannot delete migration in progress"):
            await migration_manager.delete_migration(
                workspace_id="workspace123",
                migration_id="migration123"
            )


class TestMigrationApplication:
    """Test cases for migration application and execution."""

    @pytest.fixture
    def mock_session(self):
        """Mock async session."""
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def migration_manager(self, mock_session):
        """Create migration manager with mock session."""
        return MigrationManager(mock_session)

    @pytest.mark.asyncio
    async def test_apply_migration_success(self, migration_manager, mock_session):
        """Test successful migration application."""
        # Mock migration
        mock_migration = MagicMock()
        mock_migration.id = "migration123"
        mock_migration.status = MigrationStatus.PENDING
        mock_migration.sql_up = "CREATE TABLE test (id INT PRIMARY KEY);"
        mock_migration.name = "test_migration"
        
        mock_session.get = AsyncMock(return_value=mock_migration)
        
        # Mock successful execution
        mock_execute_result = MagicMock()
        mock_session.execute.return_value = mock_execute_result
        
        # Mock create migration run
        mock_run = MagicMock()
        mock_run.id = "run123"
        mock_run.status = MigrationStatus.COMPLETED
        
        with patch.object(migration_manager, 'create_migration_run', return_value=mock_run):
            # Apply migration
            result = await migration_manager.apply_migration(
                migration_id="migration123",
                user_id="user123"
            )
            
            # Verify
            assert result.status == MigrationStatus.COMPLETED
            assert mock_migration.status == MigrationStatus.COMPLETED
            mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_apply_migration_sql_error(self, migration_manager, mock_session):
        """Test migration application with SQL error."""
        # Mock migration
        mock_migration = MagicMock()
        mock_migration.id = "migration123"
        mock_migration.status = MigrationStatus.PENDING
        mock_migration.sql_up = "INVALID SQL STATEMENT;"
        
        mock_session.get = AsyncMock(return_value=mock_migration)
        
        # Mock SQL error
        mock_session.execute.side_effect = Exception("SQL syntax error")
        
        # Mock create migration run
        mock_run = MagicMock()
        mock_run.id = "run123"
        mock_run.status = MigrationStatus.FAILED
        mock_run.error_message = "SQL syntax error"
        
        with patch.object(migration_manager, 'create_migration_run', return_value=mock_run):
            # Apply migration should fail
            result = await migration_manager.apply_migration(
                migration_id="migration123",
                user_id="user123"
            )
            
            # Verify failure
            assert result.status == MigrationStatus.FAILED
            assert "SQL syntax error" in result.error_message
            mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_apply_migration_transaction_rollback(self, migration_manager, mock_session):
        """Test migration transaction rollback on failure."""
        # Mock migration that will fail
        mock_migration = MagicMock()
        mock_migration.id = "migration123"
        mock_migration.status = MigrationStatus.PENDING
        
        mock_session.get = AsyncMock(return_value=mock_migration)
        mock_session.execute.side_effect = Exception("Connection lost")
        
        # Apply migration should rollback
        with pytest.raises(Exception, match="Connection lost"):
            await migration_manager.apply_migration(
                migration_id="migration123",
                user_id="user123"
            )
        
        # Verify rollback was called
        mock_session.rollback.assert_called()

    @pytest.mark.asyncio
    async def test_batch_apply_migrations(self, migration_manager, mock_session):
        """Test applying multiple migrations in batch."""
        # Mock migrations
        mock_migrations = [
            MagicMock(id="migration1", status=MigrationStatus.PENDING, sql_up="CREATE TABLE a (id INT);"),
            MagicMock(id="migration2", status=MigrationStatus.PENDING, sql_up="CREATE TABLE b (id INT);"),
            MagicMock(id="migration3", status=MigrationStatus.PENDING, sql_up="CREATE TABLE c (id INT);")
        ]
        
        def get_migration_side_effect(migration_class, migration_id):
            return next(m for m in mock_migrations if m.id == migration_id)
        
        mock_session.get.side_effect = get_migration_side_effect
        mock_session.execute = AsyncMock()
        
        # Mock migration runs
        mock_runs = [MagicMock(status=MigrationStatus.COMPLETED) for _ in mock_migrations]
        
        with patch.object(migration_manager, 'create_migration_run', side_effect=mock_runs):
            # Apply migrations in batch
            results = await migration_manager.batch_apply_migrations(
                migration_ids=["migration1", "migration2", "migration3"],
                user_id="user123"
            )
            
            # Verify
            assert len(results) == 3
            assert all(result.status == MigrationStatus.COMPLETED for result in results)


class TestMigrationRollback:
    """Test cases for migration rollback functionality."""

    @pytest.fixture
    def mock_session(self):
        """Mock async session."""
        session = AsyncMock(spec=AsyncSession)
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def migration_manager(self, mock_session):
        """Create migration manager with mock session."""
        return MigrationManager(mock_session)

    @pytest.mark.asyncio
    async def test_rollback_migration_success(self, migration_manager, mock_session):
        """Test successful migration rollback."""
        # Mock completed migration with rollback SQL
        mock_migration = MagicMock()
        mock_migration.id = "migration123"
        mock_migration.status = MigrationStatus.COMPLETED
        mock_migration.sql_down = "DROP TABLE test;"
        mock_migration.name = "test_migration"
        
        mock_session.get = AsyncMock(return_value=mock_migration)
        mock_session.execute = AsyncMock()
        
        # Mock create migration run
        mock_run = MagicMock()
        mock_run.id = "run123"
        mock_run.status = MigrationStatus.COMPLETED
        
        with patch.object(migration_manager, 'create_migration_run', return_value=mock_run):
            # Rollback migration
            result = await migration_manager.rollback_migration(
                migration_id="migration123",
                user_id="user123"
            )
            
            # Verify
            assert result.status == MigrationStatus.COMPLETED
            assert mock_migration.status == MigrationStatus.ROLLED_BACK
            mock_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_rollback_migration_no_rollback_sql(self, migration_manager, mock_session):
        """Test rollback without rollback SQL."""
        # Mock migration without rollback SQL
        mock_migration = MagicMock()
        mock_migration.id = "migration123"
        mock_migration.status = MigrationStatus.COMPLETED
        mock_migration.sql_down = None
        
        mock_session.get = AsyncMock(return_value=mock_migration)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="No rollback SQL defined"):
            await migration_manager.rollback_migration(
                migration_id="migration123",
                user_id="user123"
            )

    @pytest.mark.asyncio
    async def test_rollback_irreversible_migration(self, migration_manager, mock_session):
        """Test rollback of irreversible migration."""
        # Mock migration marked as irreversible
        mock_migration = MagicMock()
        mock_migration.id = "migration123"
        mock_migration.status = MigrationStatus.COMPLETED
        mock_migration.irreversible = True
        mock_migration.sql_down = "DROP TABLE test;"
        
        mock_session.get = AsyncMock(return_value=mock_migration)
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Migration marked as irreversible"):
            await migration_manager.rollback_migration(
                migration_id="migration123",
                user_id="user123"
            )


class TestMigrationPlannerIntegration:
    """Test integration between migration planner and migration manager."""

    @pytest.mark.asyncio
    async def test_planner_generates_migration_files(self):
        """Test MigrationPlanner generates proper migration files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = MigrationPlanner()
            
            # Generate migration plan
            result = await planner.generate_plan(
                from_version="1.0.0",
                to_version="1.1.0",
                changes={
                    "db_migrations_sql": "ALTER TABLE users ADD COLUMN preferences JSON;",
                    "rollback_sql": "ALTER TABLE users DROP COLUMN preferences;",
                    "estimated_downtime": "2-5 minutes",
                    "preflight_checks": [
                        "Backup database",
                        "Verify current schema version",
                        "Check database connectivity"
                    ],
                    "post_deploy_validation": [
                        "Test user preference functionality",
                        "Verify data integrity",
                        "Check application startup"
                    ]
                },
                output_dir=temp_dir
            )
            
            # Verify migration plan was generated
            assert Path(result.file_path).exists()
            content = Path(result.file_path).read_text()
            
            # Verify content structure
            assert "Migration Plan: 1.0.0 → 1.1.0" in content
            assert "ALTER TABLE users ADD COLUMN preferences JSON;" in content
            assert "ALTER TABLE users DROP COLUMN preferences;" in content
            assert "2-5 minutes" in content
            assert "Backup database" in content

    @pytest.mark.asyncio
    async def test_planner_handles_missing_sections(self):
        """Test MigrationPlanner handles missing optional sections."""
        with tempfile.TemporaryDirectory() as temp_dir:
            planner = MigrationPlanner()
            
            # Generate minimal migration plan
            result = await planner.generate_plan(
                from_version="1.0.0",
                to_version="1.0.1",
                changes={},
                output_dir=temp_dir
            )
            
            # Verify default sections included
            content = Path(result.file_path).read_text()
            assert "Migration Plan: 1.0.0 → 1.0.1" in content
            assert "Pre-flight Checks" in content
            assert "Deployment Steps" in content
            assert "Rollback Steps" in content


class TestMigrationModels:
    """Test database models for migrations."""

    def test_database_migration_model(self):
        """Test DatabaseMigration model properties."""
        migration = DatabaseMigration(
            id="migration123",
            workspace_id="workspace123",
            name="test_migration",
            description="Test migration",
            sql_up="CREATE TABLE test (id INT);",
            sql_down="DROP TABLE test;",
            status=MigrationStatus.PENDING,
            created_by_user_id="user123",
            estimated_duration=30,
            risk_level="low",
            irreversible=False
        )
        
        # Test model properties
        assert migration.id == "migration123"
        assert migration.name == "test_migration"
        assert migration.status == MigrationStatus.PENDING
        assert migration.irreversible is False

    def test_migration_run_model(self):
        """Test MigrationRun model properties."""
        run = MigrationRun(
            id="run123",
            migration_id="migration123",
            status=MigrationStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            executed_by_user_id="user123",
            affected_rows=100,
            backup_id="backup123",
            dry_run=False
        )
        
        # Test model properties
        assert run.id == "run123"
        assert run.status == MigrationStatus.COMPLETED
        assert run.affected_rows == 100
        assert run.dry_run is False

    def test_migration_repr(self):
        """Test model string representation."""
        migration = DatabaseMigration(
            id="migration123",
            workspace_id="workspace123",
            name="test_migration",
            status=MigrationStatus.PENDING
        )
        
        expected = "<DatabaseMigration(id=migration123, name=test_migration, status=pending)>"
        assert repr(migration) == expected

    def test_migration_run_repr(self):
        """Test MigrationRun string representation."""
        run = MigrationRun(
            id="run123",
            migration_id="migration123",
            status=MigrationStatus.COMPLETED
        )
        
        expected = "<MigrationRun(id=run123, migration_id=migration123, status=completed)>"
        assert repr(run) == expected


# Helper function for timezone-aware datetime
def timezone():
    import pytz
    return pytz.UTC