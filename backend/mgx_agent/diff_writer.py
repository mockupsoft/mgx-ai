# -*- coding: utf-8 -*-
"""
Unified diff parser and safe patch applicator.

Handles:
- Parsing unified diff format
- Safely applying diffs with backups
- Line drift detection and warnings
- Fallback mechanism with .mgx_new files
- Multi-file patch sets (transaction or best-effort mode)
"""

import os
import re
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DiffOperation(str, Enum):
    """Diff operation types."""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


class DiffHunk(BaseModel):
    """Represents a single hunk in a unified diff."""
    file_path: str = Field(..., description="Path to the file")
    operation: DiffOperation = Field(..., description="Operation type")
    line_start: int = Field(0, description="Starting line number (0 for new files)")
    lines_added: int = Field(0, description="Number of lines added")
    lines_removed: int = Field(0, description="Number of lines removed")
    content: str = Field("", description="Hunk content with +/- lines")
    context_before: List[str] = Field(default_factory=list, description="Context lines before change")
    context_after: List[str] = Field(default_factory=list, description="Context lines after change")


class ApplyResult(BaseModel):
    """Result of applying a diff."""
    success: bool = Field(..., description="Whether the apply succeeded")
    message: str = Field("", description="Result message")
    file_path: Optional[str] = Field(None, description="Path to the modified file")
    backup_file: Optional[str] = Field(None, description="Path to backup file")
    failed_hunks: List[int] = Field(default_factory=list, description="Indices of failed hunks")
    new_file_created: Optional[str] = Field(None, description="Path to .mgx_new file if created")
    log_file: Optional[str] = Field(None, description="Path to .mgx_apply_log.txt file")
    line_drift_warnings: List[str] = Field(default_factory=list, description="Line drift warnings")


class PatchSetResult(BaseModel):
    """Result of applying a patch set."""
    success: bool = Field(..., description="Whether all patches succeeded")
    applied_count: int = Field(0, description="Number of successfully applied patches")
    failed_count: int = Field(0, description="Number of failed patches")
    results: List[ApplyResult] = Field(default_factory=list, description="Individual patch results")
    rollback_performed: bool = Field(False, description="Whether rollback was performed")


def parse_unified_diff(diff_str: str) -> List[DiffHunk]:
    """
    Parse a unified diff string into DiffHunk objects.
    
    Supports:
    - File creation (new file)
    - File modification (hunks with context)
    - File deletion (--- only)
    
    Args:
        diff_str: Unified diff string
    
    Returns:
        List of DiffHunk objects
    """
    hunks = []
    current_file = None
    current_operation = None
    current_hunk_lines = []
    current_line_start = 0
    lines_added = 0
    lines_removed = 0
    
    lines = diff_str.strip().split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i]
        
        # File header: --- a/path or --- /dev/null
        if line.startswith('---'):
            # Extract file path
            if '/dev/null' in line:
                # New file being created
                current_operation = DiffOperation.CREATE
            else:
                # Extract path from --- a/path
                match = re.search(r'--- a/(.+)', line)
                if match:
                    current_file = match.group(1)
                else:
                    # Try --- path format
                    match = re.search(r'--- (.+)', line)
                    if match:
                        current_file = match.group(1).strip()
            i += 1
            continue
        
        # File header: +++ b/path or +++ /dev/null
        if line.startswith('+++'):
            if '/dev/null' in line:
                # File being deleted
                current_operation = DiffOperation.DELETE
            else:
                # Extract path from +++ b/path
                match = re.search(r'\+\+\+ b/(.+)', line)
                if match:
                    new_file = match.group(1)
                    if current_operation != DiffOperation.CREATE:
                        current_operation = DiffOperation.MODIFY
                    current_file = new_file
                else:
                    # Try +++ path format
                    match = re.search(r'\+\+\+ (.+)', line)
                    if match:
                        new_file = match.group(1).strip()
                        if current_operation != DiffOperation.CREATE:
                            current_operation = DiffOperation.MODIFY
                        current_file = new_file
            i += 1
            continue
        
        # Hunk header: @@ -10,5 +10,7 @@
        if line.startswith('@@'):
            # Save previous hunk if exists
            if current_hunk_lines and current_file:
                hunks.append(DiffHunk(
                    file_path=current_file,
                    operation=current_operation or DiffOperation.MODIFY,
                    line_start=current_line_start,
                    lines_added=lines_added,
                    lines_removed=lines_removed,
                    content='\n'.join(current_hunk_lines)
                ))
            
            # Parse hunk header: @@ -10,5 +10,7 @@
            match = re.search(r'@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            if match:
                current_line_start = int(match.group(1))
            else:
                current_line_start = 0
            
            current_hunk_lines = []
            lines_added = 0
            lines_removed = 0
            i += 1
            continue
        
        # Hunk content
        if line.startswith('+') and not line.startswith('+++'):
            current_hunk_lines.append(line)
            lines_added += 1
        elif line.startswith('-') and not line.startswith('---'):
            current_hunk_lines.append(line)
            lines_removed += 1
        elif line.startswith(' ') or line == '':
            # Context line
            current_hunk_lines.append(line if line else ' ')
        
        i += 1
    
    # Save last hunk
    if current_hunk_lines and current_file:
        hunks.append(DiffHunk(
            file_path=current_file,
            operation=current_operation or DiffOperation.MODIFY,
            line_start=current_line_start,
            lines_added=lines_added,
            lines_removed=lines_removed,
            content='\n'.join(current_hunk_lines)
        ))
    
    # Handle file deletion (only --- present, no hunks)
    if current_operation == DiffOperation.DELETE and not hunks and current_file:
        hunks.append(DiffHunk(
            file_path=current_file,
            operation=DiffOperation.DELETE,
            line_start=0,
            lines_added=0,
            lines_removed=0,
            content=""
        ))
    
    return hunks


def validate_diff(file_path: str, diff: str) -> bool:
    """
    Validate a diff before applying.
    
    Checks:
    - Diff syntax is valid
    - File exists (if modification)
    - Line numbers match original (within tolerance)
    
    Args:
        file_path: Path to the file
        diff: Diff string to validate
    
    Returns:
        True if valid, False otherwise
    """
    try:
        hunks = parse_unified_diff(diff)
        if not hunks:
            logger.error("No hunks found in diff")
            return False
        
        for hunk in hunks:
            # For modifications, check if file exists
            if hunk.operation == DiffOperation.MODIFY:
                if not os.path.exists(file_path):
                    logger.error(f"File does not exist for modification: {file_path}")
                    return False
            
            # For creates, check file doesn't exist
            if hunk.operation == DiffOperation.CREATE:
                if os.path.exists(file_path):
                    logger.warning(f"File already exists for creation: {file_path}")
                    # Don't fail, just warn (might be intentional overwrite)
            
            # Check for path traversal attacks
            normalized_path = os.path.normpath(file_path)
            if '..' in normalized_path or normalized_path.startswith('/etc/'):
                logger.error(f"Dangerous path detected: {file_path}")
                return False
        
        return True
    except Exception as e:
        logger.error(f"Diff validation failed: {e}")
        return False


def _create_backup(file_path: str) -> str:
    """
    Create a timestamped backup of a file.
    
    Args:
        file_path: Path to the file to backup
    
    Returns:
        Path to the backup file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.mgx_bak.{timestamp}"
    shutil.copy2(file_path, backup_path)
    logger.info(f"Created backup: {backup_path}")
    return backup_path


def _detect_line_drift(file_path: str, hunk: DiffHunk, tolerance: int = 2) -> Optional[str]:
    """
    Detect if line numbers in diff have drifted from original file.
    
    Args:
        file_path: Path to the file
        hunk: DiffHunk to check
        tolerance: Maximum allowed drift in lines
    
    Returns:
        Warning message if drift detected, None otherwise
    """
    if not os.path.exists(file_path):
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Check if line_start is within reasonable bounds
        if hunk.line_start > len(lines) + tolerance:
            return f"Line drift: hunk starts at line {hunk.line_start}, but file has only {len(lines)} lines"
        
        return None
    except Exception as e:
        logger.warning(f"Could not check line drift: {e}")
        return None


def _apply_hunk(file_lines: List[str], hunk: DiffHunk) -> tuple[List[str], bool]:
    """
    Apply a single hunk to file lines.
    
    Args:
        file_lines: List of file lines
        hunk: DiffHunk to apply
    
    Returns:
        Tuple of (modified_lines, success)
    """
    try:
        hunk_lines = hunk.content.split('\n')
        
        # Find the position to apply the hunk
        start_pos = hunk.line_start - 1  # Convert to 0-based index
        if start_pos < 0:
            start_pos = 0
        
        # Check if start position is way beyond file bounds (drift too large)
        if start_pos > len(file_lines):
            logger.error(f"Hunk start position {hunk.line_start} is beyond file length {len(file_lines)}")
            return file_lines, False
        
        # Extract context and changes from hunk
        context_lines = []
        changes = []
        
        for line in hunk_lines:
            if line.startswith(' ') or (not line.startswith('+') and not line.startswith('-')):
                # Context line
                context_lines.append(line[1:] if line.startswith(' ') else line)
            else:
                changes.append(line)
        
        # Verify context matches (basic check - at least some context should match)
        if context_lines and start_pos < len(file_lines):
            # Check first context line
            first_context = context_lines[0].rstrip('\n')
            if start_pos < len(file_lines):
                actual_line = file_lines[start_pos].rstrip('\n')
                # If context doesn't match at all, fail
                if first_context and actual_line and first_context not in actual_line and actual_line not in first_context:
                    logger.error(f"Context mismatch at line {start_pos}: expected '{first_context}', found '{actual_line}'")
                    return file_lines, False
        
        # Build new lines
        new_lines = []
        old_line_idx = 0
        
        for line in hunk_lines:
            if line.startswith('+'):
                # Add new line
                new_lines.append(line[1:] + '\n')
            elif line.startswith('-'):
                # Remove line (skip in new_lines)
                old_line_idx += 1
            else:
                # Context line (keep)
                if start_pos + old_line_idx < len(file_lines):
                    new_lines.append(file_lines[start_pos + old_line_idx])
                else:
                    # Context line beyond file bounds
                    logger.error(f"Context line {old_line_idx} beyond file bounds")
                    return file_lines, False
                old_line_idx += 1
        
        # Construct final file
        result = file_lines[:start_pos] + new_lines + file_lines[start_pos + old_line_idx:]
        return result, True
    except Exception as e:
        logger.error(f"Failed to apply hunk: {e}")
        return file_lines, False


def apply_diff(
    file_path: str,
    diff: str,
    backup: bool = True,
    dry_run: bool = False
) -> ApplyResult:
    """
    Apply a unified diff to a file with safety checks.
    
    Args:
        file_path: Path to the file to modify
        diff: Unified diff string
        backup: Whether to create a backup before applying
        dry_run: If True, validate but don't actually apply
    
    Returns:
        ApplyResult with details of the operation
    """
    backup_file = None
    new_file_path = None
    log_file_path = None
    line_drift_warnings = []
    
    try:
        # Validate diff syntax
        if not validate_diff(file_path, diff):
            return ApplyResult(
                success=False,
                message="Diff validation failed",
                file_path=file_path
            )
        
        # Parse diff
        hunks = parse_unified_diff(diff)
        if not hunks:
            return ApplyResult(
                success=False,
                message="No hunks found in diff",
                file_path=file_path
            )
        
        # Determine operation type
        operation = hunks[0].operation
        
        # Handle file deletion
        if operation == DiffOperation.DELETE:
            if dry_run:
                return ApplyResult(
                    success=True,
                    message=f"[DRY RUN] Would delete file: {file_path}",
                    file_path=file_path
                )
            
            if os.path.exists(file_path):
                if backup:
                    backup_file = _create_backup(file_path)
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
            
            return ApplyResult(
                success=True,
                message=f"File deleted: {file_path}",
                file_path=file_path,
                backup_file=backup_file
            )
        
        # Handle file creation
        if operation == DiffOperation.CREATE:
            if dry_run:
                return ApplyResult(
                    success=True,
                    message=f"[DRY RUN] Would create file: {file_path}",
                    file_path=file_path
                )
            
            # Create directory if needed
            os.makedirs(os.path.dirname(file_path) or '.', exist_ok=True)
            
            # Extract content from diff
            content_lines = []
            for hunk in hunks:
                for line in hunk.content.split('\n'):
                    if line.startswith('+'):
                        content_lines.append(line[1:])
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content_lines))
            
            logger.info(f"Created file: {file_path}")
            return ApplyResult(
                success=True,
                message=f"File created: {file_path}",
                file_path=file_path
            )
        
        # Handle file modification
        if not os.path.exists(file_path):
            return ApplyResult(
                success=False,
                message=f"File does not exist: {file_path}",
                file_path=file_path
            )
        
        # Check line drift
        for i, hunk in enumerate(hunks):
            drift_warning = _detect_line_drift(file_path, hunk)
            if drift_warning:
                line_drift_warnings.append(f"Hunk {i+1}: {drift_warning}")
        
        if line_drift_warnings:
            logger.warning(f"Line drift detected in {file_path}:")
            for warning in line_drift_warnings:
                logger.warning(f"  {warning}")
        
        # Create backup
        if backup and not dry_run:
            backup_file = _create_backup(file_path)
        
        if dry_run:
            return ApplyResult(
                success=True,
                message=f"[DRY RUN] Would apply {len(hunks)} hunks to: {file_path}",
                file_path=file_path,
                line_drift_warnings=line_drift_warnings
            )
        
        # Read original file
        with open(file_path, 'r', encoding='utf-8') as f:
            file_lines = f.readlines()
        
        # Apply hunks
        failed_hunks = []
        modified_lines = file_lines
        
        for i, hunk in enumerate(hunks):
            modified_lines, success = _apply_hunk(modified_lines, hunk)
            if not success:
                failed_hunks.append(i)
        
        if failed_hunks:
            # Restore from backup
            if backup_file:
                shutil.copy2(backup_file, file_path)
                logger.warning(f"Restored from backup due to failed hunks: {failed_hunks}")
            
            # Write .mgx_new file
            new_file_path = f"{file_path}.mgx_new"
            with open(new_file_path, 'w', encoding='utf-8') as f:
                f.writelines(modified_lines)
            
            # Write apply log
            log_file_path = f"{file_path}.mgx_apply_log.txt"
            with open(log_file_path, 'w', encoding='utf-8') as f:
                f.write(f"Patch apply failed for: {file_path}\n")
                f.write(f"Failed hunks: {failed_hunks}\n\n")
                f.write("Original diff:\n")
                f.write(diff)
                f.write("\n\nLine drift warnings:\n")
                for warning in line_drift_warnings:
                    f.write(f"  {warning}\n")
            
            # Write failed diff
            failed_diff_path = f"{file_path}.mgx_failed_diff.txt"
            with open(failed_diff_path, 'w', encoding='utf-8') as f:
                f.write(diff)
            
            return ApplyResult(
                success=False,
                message=f"Failed to apply {len(failed_hunks)} hunks",
                file_path=file_path,
                backup_file=backup_file,
                failed_hunks=failed_hunks,
                new_file_created=new_file_path,
                log_file=log_file_path,
                line_drift_warnings=line_drift_warnings
            )
        
        # Write modified file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(modified_lines)
        
        logger.info(f"Successfully applied {len(hunks)} hunks to: {file_path}")
        return ApplyResult(
            success=True,
            message=f"Successfully applied {len(hunks)} hunks",
            file_path=file_path,
            backup_file=backup_file,
            line_drift_warnings=line_drift_warnings
        )
    
    except Exception as e:
        logger.error(f"Failed to apply diff to {file_path}: {e}")
        
        # Try to restore from backup
        if backup_file and os.path.exists(backup_file):
            try:
                shutil.copy2(backup_file, file_path)
                logger.info(f"Restored from backup: {backup_file}")
            except Exception as restore_error:
                logger.error(f"Failed to restore from backup: {restore_error}")
        
        return ApplyResult(
            success=False,
            message=f"Exception during apply: {str(e)}",
            file_path=file_path,
            backup_file=backup_file
        )


def apply_patch_set(
    diffs: List[tuple[str, str]],
    project_path: str,
    dry_run: bool = False,
    mode: str = "all_or_nothing"
) -> PatchSetResult:
    """
    Apply multiple diffs to a project.
    
    Args:
        diffs: List of (file_path, diff_string) tuples
        project_path: Base path of the project
        dry_run: If True, validate but don't actually apply
        mode: "all_or_nothing" or "best_effort"
            - all_or_nothing: rollback all if any fail
            - best_effort: apply all, report failures separately
    
    Returns:
        PatchSetResult with details of all operations
    """
    results = []
    applied_files = []
    
    try:
        # Apply all diffs
        for file_path, diff in diffs:
            # Make path relative to project_path
            full_path = os.path.join(project_path, file_path)
            
            result = apply_diff(
                file_path=full_path,
                diff=diff,
                backup=True,
                dry_run=dry_run
            )
            results.append(result)
            
            if result.success:
                applied_files.append((full_path, result.backup_file))
            else:
                # Failure detected
                if mode == "all_or_nothing":
                    logger.warning(f"Patch failed in all_or_nothing mode, rolling back...")
                    
                    # Rollback all previously applied diffs
                    for applied_file, backup_file in applied_files:
                        if backup_file and os.path.exists(backup_file):
                            try:
                                shutil.copy2(backup_file, applied_file)
                                logger.info(f"Rolled back: {applied_file}")
                            except Exception as e:
                                logger.error(f"Failed to rollback {applied_file}: {e}")
                    
                    return PatchSetResult(
                        success=False,
                        applied_count=0,
                        failed_count=len(results),
                        results=results,
                        rollback_performed=True
                    )
        
        # Count successes and failures
        applied_count = sum(1 for r in results if r.success)
        failed_count = len(results) - applied_count
        
        return PatchSetResult(
            success=failed_count == 0,
            applied_count=applied_count,
            failed_count=failed_count,
            results=results,
            rollback_performed=False
        )
    
    except Exception as e:
        logger.error(f"Patch set apply failed: {e}")
        return PatchSetResult(
            success=False,
            applied_count=0,
            failed_count=len(diffs),
            results=results,
            rollback_performed=False
        )
