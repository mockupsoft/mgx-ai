# -*- coding: utf-8 -*-
"""
Unit tests for patch/diff writer and file recovery.

Tests:
- Unified diff parsing
- Diff application (create, modify, delete)
- Backup creation and restoration
- Line drift detection
- Fallback mechanism (.mgx_new files)
- Multi-file patch sets
- Dry-run mode
"""

import os
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from mgx_agent.diff_writer import (
    parse_unified_diff,
    validate_diff,
    apply_diff,
    apply_patch_set,
    DiffOperation,
    DiffHunk,
    ApplyResult,
    PatchSetResult
)
from mgx_agent.file_recovery import (
    list_backups,
    restore_from_backup,
    cleanup_old_backups,
    get_backup_for_file,
    list_mgx_artifacts,
    cleanup_mgx_artifacts,
    BackupInfo
)


@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    temp_dir = tempfile.mkdtemp(prefix="mgx_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_file(temp_project):
    """Create a sample file for testing."""
    file_path = os.path.join(temp_project, "test.py")
    content = """def hello():
    print("Hello")
    return True

def world():
    print("World")
    return False
"""
    with open(file_path, 'w') as f:
        f.write(content)
    return file_path


class TestUnifiedDiffParsing:
    """Tests for parse_unified_diff()."""
    
    def test_parse_unified_diff_single_hunk(self):
        """Test parsing a single hunk modification."""
        diff = """--- a/src/test.py
+++ b/src/test.py
@@ -10,5 +10,7 @@
 existing line
-removed line
+added line
+another added line
 context line
"""
        hunks = parse_unified_diff(diff)
        
        assert len(hunks) == 1
        assert hunks[0].file_path == "src/test.py"
        assert hunks[0].operation == DiffOperation.MODIFY
        assert hunks[0].line_start == 10
        assert hunks[0].lines_added == 2
        assert hunks[0].lines_removed == 1
    
    def test_parse_unified_diff_multiple_hunks(self):
        """Test parsing multiple hunks."""
        diff = """--- a/src/test.py
+++ b/src/test.py
@@ -5,3 +5,4 @@
 line 1
+line 2
 line 3
@@ -15,2 +16,3 @@
 line 15
+line 16
 line 17
"""
        hunks = parse_unified_diff(diff)
        
        assert len(hunks) == 2
        assert hunks[0].line_start == 5
        assert hunks[1].line_start == 15
    
    def test_parse_unified_diff_new_file(self):
        """Test parsing a new file creation."""
        diff = """--- /dev/null
+++ b/src/new_file.py
@@ -0,0 +1,3 @@
+def new_function():
+    pass
+    return True
"""
        hunks = parse_unified_diff(diff)
        
        assert len(hunks) == 1
        assert hunks[0].file_path == "src/new_file.py"
        assert hunks[0].operation == DiffOperation.CREATE
        assert hunks[0].lines_added == 3
    
    def test_parse_unified_diff_deleted_file(self):
        """Test parsing a file deletion."""
        diff = """--- a/src/old_file.py
+++ /dev/null
"""
        hunks = parse_unified_diff(diff)
        
        assert len(hunks) == 1
        assert hunks[0].file_path == "src/old_file.py"
        assert hunks[0].operation == DiffOperation.DELETE


class TestDiffApplication:
    """Tests for apply_diff()."""
    
    def test_apply_diff_to_existing_file_success(self, sample_file):
        """Test successfully applying a diff to an existing file."""
        diff = """--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
+    print("Bonjour")
     print("Hello")
     return True
"""
        result = apply_diff(sample_file, diff, backup=True)
        
        assert result.success
        assert result.backup_file is not None
        assert os.path.exists(result.backup_file)
        
        # Check file was modified
        with open(sample_file, 'r') as f:
            content = f.read()
            assert 'Bonjour' in content
    
    def test_apply_diff_creates_backup_with_timestamp(self, sample_file):
        """Test that backup files have timestamp format."""
        diff = """--- a/test.py
+++ b/test.py
@@ -1,2 +1,3 @@
 def hello():
+    # Comment
     print("Hello")
"""
        result = apply_diff(sample_file, diff, backup=True)
        
        assert result.backup_file is not None
        # Check timestamp format: YYYYMMDD_HHMMSS
        assert '.mgx_bak.' in result.backup_file
        timestamp_part = result.backup_file.split('.mgx_bak.')[-1]
        assert len(timestamp_part) == 15  # YYYYMMDD_HHMMSS
        assert '_' in timestamp_part
    
    def test_apply_diff_restores_from_backup_on_failure(self, sample_file):
        """Test that file is restored from backup on failure."""
        # Create a malformed diff that will fail
        original_content = open(sample_file, 'r').read()
        
        diff = """--- a/test.py
+++ b/test.py
@@ -1000,2 +1000,3 @@
 nonexistent line
+added line
"""
        result = apply_diff(sample_file, diff, backup=True)
        
        # Should fail but not corrupt file
        assert not result.success
        
        # Original file should be unchanged
        current_content = open(sample_file, 'r').read()
        assert current_content == original_content
    
    def test_apply_diff_writes_mgx_new_on_failure(self, sample_file):
        """Test that .mgx_new file is created on failure."""
        diff = """--- a/test.py
+++ b/test.py
@@ -1000,2 +1000,3 @@
 nonexistent line
+added line
"""
        result = apply_diff(sample_file, diff, backup=True)
        
        assert not result.success
        assert result.new_file_created is not None
        assert os.path.exists(result.new_file_created)
        assert result.new_file_created.endswith('.mgx_new')
    
    def test_apply_diff_detects_line_drift_warns(self, sample_file):
        """Test that line drift is detected and warned."""
        # Create a diff with line numbers that don't quite match
        diff = """--- a/test.py
+++ b/test.py
@@ -100,2 +100,3 @@
 def world():
+    # New comment
     print("World")
"""
        result = apply_diff(sample_file, diff, backup=True)
        
        # Should detect line drift
        assert len(result.line_drift_warnings) > 0
    
    def test_apply_diff_invalid_syntax_rejected(self, temp_project):
        """Test that invalid diff syntax is rejected."""
        file_path = os.path.join(temp_project, "test.py")
        
        # Invalid diff (missing +++ line)
        diff = """--- a/test.py
this is not a valid diff
"""
        result = apply_diff(file_path, diff, backup=True)
        
        assert not result.success
        assert "validation failed" in result.message.lower()
    
    def test_apply_diff_creates_new_file(self, temp_project):
        """Test creating a new file with diff."""
        file_path = os.path.join(temp_project, "new_file.py")
        
        diff = """--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,4 @@
+def new_function():
+    print("New")
+    return 42
+
"""
        result = apply_diff(file_path, diff, backup=False)
        
        assert result.success
        assert os.path.exists(file_path)
        
        with open(file_path, 'r') as f:
            content = f.read()
            assert 'new_function' in content
            assert 'return 42' in content
    
    def test_apply_diff_deletes_file(self, sample_file):
        """Test deleting a file with diff."""
        diff = """--- a/test.py
+++ /dev/null
"""
        result = apply_diff(sample_file, diff, backup=True)
        
        assert result.success
        assert not os.path.exists(sample_file)
        assert result.backup_file is not None
        assert os.path.exists(result.backup_file)


class TestPatchSets:
    """Tests for apply_patch_set()."""
    
    def test_apply_patch_set_all_or_nothing(self, temp_project):
        """Test all_or_nothing mode rolls back on failure."""
        # Create files
        file1 = os.path.join(temp_project, "file1.py")
        file2 = os.path.join(temp_project, "file2.py")
        
        with open(file1, 'w') as f:
            f.write("content1\n")
        with open(file2, 'w') as f:
            f.write("content2\n")
        
        # Create diffs (second one will fail)
        diff1 = """--- a/file1.py
+++ b/file1.py
@@ -1 +1,2 @@
 content1
+added line
"""
        diff2 = """--- a/file2.py
+++ b/file2.py
@@ -1000,2 +1000,3 @@
 nonexistent line
+will fail
"""
        
        diffs = [("file1.py", diff1), ("file2.py", diff2)]
        result = apply_patch_set(diffs, temp_project, mode="all_or_nothing")
        
        assert not result.success
        assert result.rollback_performed
        
        # file1 should be rolled back
        with open(file1, 'r') as f:
            content = f.read()
            assert content == "content1\n"
    
    def test_apply_patch_set_best_effort_mode(self, temp_project):
        """Test best_effort mode applies what it can."""
        # Create files
        file1 = os.path.join(temp_project, "file1.py")
        file2 = os.path.join(temp_project, "file2.py")
        
        with open(file1, 'w') as f:
            f.write("content1\n")
        with open(file2, 'w') as f:
            f.write("content2\n")
        
        # Create diffs (second one will fail)
        diff1 = """--- a/file1.py
+++ b/file1.py
@@ -1 +1,2 @@
 content1
+added line
"""
        diff2 = """--- a/file2.py
+++ b/file2.py
@@ -1000,2 +1000,3 @@
 nonexistent line
+will fail
"""
        
        diffs = [("file1.py", diff1), ("file2.py", diff2)]
        result = apply_patch_set(diffs, temp_project, mode="best_effort")
        
        assert not result.success  # Overall failure
        assert result.applied_count == 1
        assert result.failed_count == 1
        assert not result.rollback_performed
        
        # file1 should be modified
        with open(file1, 'r') as f:
            content = f.read()
            assert 'added line' in content
    
    def test_apply_patch_set_dry_run_doesnt_modify(self, temp_project):
        """Test dry_run mode doesn't modify files."""
        file1 = os.path.join(temp_project, "file1.py")
        
        with open(file1, 'w') as f:
            f.write("original\n")
        
        original_content = open(file1, 'r').read()
        
        diff1 = """--- a/file1.py
+++ b/file1.py
@@ -1 +1,2 @@
 original
+added line
"""
        
        diffs = [("file1.py", diff1)]
        result = apply_patch_set(diffs, temp_project, dry_run=True)
        
        assert result.success
        
        # File should be unchanged
        current_content = open(file1, 'r').read()
        assert current_content == original_content


class TestLoggingAndContext:
    """Tests for logging and context information."""
    
    def test_patch_apply_failure_logs_context(self, sample_file):
        """Test that failure logs contain useful context."""
        diff = """--- a/test.py
+++ b/test.py
@@ -1000,2 +1000,3 @@
 nonexistent line
+will fail
"""
        result = apply_diff(sample_file, diff, backup=True)
        
        assert not result.success
        assert result.log_file is not None
        assert os.path.exists(result.log_file)
        
        # Check log file contains useful info
        with open(result.log_file, 'r') as f:
            log_content = f.read()
            assert 'Patch apply failed' in log_content
            assert 'Failed hunks' in log_content
    
    def test_mgx_new_file_readable_for_manual_review(self, sample_file):
        """Test that .mgx_new file is readable for manual review."""
        diff = """--- a/test.py
+++ b/test.py
@@ -1000,2 +1000,3 @@
 nonexistent line
+manual review needed
"""
        result = apply_diff(sample_file, diff, backup=True)
        
        assert not result.success
        assert result.new_file_created is not None
        
        # Should be readable
        with open(result.new_file_created, 'r') as f:
            content = f.read()
            assert len(content) > 0


class TestFileRecovery:
    """Tests for file_recovery module."""
    
    def test_list_backups(self, temp_project, sample_file):
        """Test listing backup files."""
        import time
        
        # Create some backups
        diff1 = """--- a/test.py
+++ b/test.py
@@ -1 +1,2 @@
 def hello():
+    # v1
"""
        apply_diff(sample_file, diff1, backup=True)
        
        # Small delay to ensure different timestamps
        time.sleep(1.1)
        
        diff2 = """--- a/test.py
+++ b/test.py
@@ -1 +1,2 @@
 def hello():
+    # v2
"""
        apply_diff(sample_file, diff2, backup=True)
        
        backups = list_backups(temp_project)
        
        assert len(backups) >= 2
        assert all(isinstance(b, BackupInfo) for b in backups)
        assert all('.mgx_bak.' in b.backup_file for b in backups)
    
    def test_restore_from_backup(self, sample_file):
        """Test restoring from a backup."""
        original_content = open(sample_file, 'r').read()
        
        # Modify file
        diff = """--- a/test.py
+++ b/test.py
@@ -1 +1,2 @@
 def hello():
+    # modified
"""
        result = apply_diff(sample_file, diff, backup=True)
        assert result.success
        
        # Restore from backup
        success = restore_from_backup(sample_file)
        
        assert success
        restored_content = open(sample_file, 'r').read()
        assert restored_content == original_content
    
    def test_cleanup_old_backups(self, temp_project, sample_file):
        """Test cleaning up old backups."""
        # Manually create backup files with different timestamps
        base_content = "test content"
        timestamps = [
            "20250101_120000",
            "20250102_120000",
            "20250103_120000",
            "20250104_120000",
            "20250105_120000",
            "20250106_120000",
            "20250107_120000",
            "20250108_120000",
        ]
        
        for ts in timestamps:
            backup_path = f"{sample_file}.mgx_bak.{ts}"
            with open(backup_path, 'w') as f:
                f.write(base_content)
        
        # Verify we have 8 backups
        backups_before = list_backups(temp_project)
        assert len(backups_before) == 8
        
        # Keep only 3 latest
        removed = cleanup_old_backups(temp_project, keep_latest=3)
        
        assert removed == 5  # Should remove 8 - 3 = 5 backups
        
        # Check only 3 remain
        backups = list_backups(temp_project)
        assert len(backups) == 3
        
        # Verify the 3 remaining are the latest ones
        remaining_timestamps = [b.timestamp for b in backups]
        assert "20250108_120000" in remaining_timestamps
        assert "20250107_120000" in remaining_timestamps
        assert "20250106_120000" in remaining_timestamps
    
    def test_backup_timestamp_format_correct(self, sample_file):
        """Test that backup timestamp format is correct."""
        diff = """--- a/test.py
+++ b/test.py
@@ -1 +1,2 @@
 def hello():
+    # test
"""
        result = apply_diff(sample_file, diff, backup=True)
        
        assert result.backup_file is not None
        
        # Extract timestamp
        timestamp_part = result.backup_file.split('.mgx_bak.')[-1]
        
        # Should be in format: YYYYMMDD_HHMMSS
        assert len(timestamp_part) == 15
        assert timestamp_part[8] == '_'
        
        # Should be parseable as datetime
        try:
            datetime.strptime(timestamp_part, "%Y%m%d_%H%M%S")
            valid_timestamp = True
        except ValueError:
            valid_timestamp = False
        
        assert valid_timestamp
    
    def test_list_mgx_artifacts(self, temp_project, sample_file):
        """Test listing all MGX artifacts."""
        # Create various artifacts
        diff = """--- a/test.py
+++ b/test.py
@@ -1000 +1000,2 @@
 fail
+test
"""
        apply_diff(sample_file, diff, backup=True)
        
        artifacts = list_mgx_artifacts(temp_project)
        
        assert 'backups' in artifacts
        assert 'new_files' in artifacts
        assert 'apply_logs' in artifacts
        assert 'failed_diffs' in artifacts
        
        # Should have at least some artifacts
        total_artifacts = sum(len(v) for v in artifacts.values())
        assert total_artifacts > 0
    
    def test_cleanup_mgx_artifacts(self, temp_project, sample_file):
        """Test cleaning up MGX artifacts."""
        # Create various artifacts
        diff = """--- a/test.py
+++ b/test.py
@@ -1000 +1000,2 @@
 fail
+test
"""
        apply_diff(sample_file, diff, backup=True)
        
        # Cleanup all artifacts
        removed = cleanup_mgx_artifacts(temp_project)
        
        assert removed > 0
        
        # Check artifacts are gone
        artifacts = list_mgx_artifacts(temp_project)
        total_remaining = sum(len(v) for v in artifacts.values())
        assert total_remaining == 0
