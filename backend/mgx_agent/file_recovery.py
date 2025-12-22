# -*- coding: utf-8 -*-
"""
File recovery utilities for backup management.

Handles:
- Listing backup files
- Restoring from backups
- Cleaning up old backups
"""

import os
import re
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BackupInfo(BaseModel):
    """Information about a backup file."""
    original_file: str = Field(..., description="Path to the original file")
    backup_file: str = Field(..., description="Path to the backup file")
    timestamp: str = Field(..., description="Timestamp of the backup")
    size_bytes: int = Field(0, description="Size of backup file in bytes")
    exists: bool = Field(True, description="Whether the backup file still exists")


def list_backups(project_path: str, file_pattern: str = "*.mgx_bak.*") -> List[BackupInfo]:
    """
    List all backup files in a project directory.
    
    Args:
        project_path: Path to the project directory
        file_pattern: Glob pattern for backup files (default: *.mgx_bak.*)
    
    Returns:
        List of BackupInfo objects sorted by timestamp (newest first)
    """
    backups = []
    project_path_obj = Path(project_path)
    
    # Recursively find all backup files
    for backup_file in project_path_obj.rglob(file_pattern):
        if backup_file.is_file():
            # Extract timestamp from filename: file.ext.mgx_bak.20250114_153022
            match = re.search(r'\.mgx_bak\.(\d{8}_\d{6})$', str(backup_file))
            if match:
                timestamp = match.group(1)
                
                # Determine original file path
                original_file = str(backup_file).replace(f'.mgx_bak.{timestamp}', '')
                
                try:
                    size_bytes = backup_file.stat().st_size
                except Exception:
                    size_bytes = 0
                
                backups.append(BackupInfo(
                    original_file=original_file,
                    backup_file=str(backup_file),
                    timestamp=timestamp,
                    size_bytes=size_bytes,
                    exists=True
                ))
    
    # Sort by timestamp (newest first)
    backups.sort(key=lambda b: b.timestamp, reverse=True)
    
    return backups


def restore_from_backup(
    file_path: str,
    backup_timestamp: Optional[str] = None
) -> bool:
    """
    Restore a file from a backup.
    
    Args:
        file_path: Path to the file to restore
        backup_timestamp: Specific timestamp to restore from (default: latest)
    
    Returns:
        True if restore succeeded, False otherwise
    """
    try:
        # Find backup files
        backup_pattern = f"{file_path}.mgx_bak.*"
        backup_files = sorted(
            Path(os.path.dirname(file_path) or '.').glob(os.path.basename(backup_pattern)),
            reverse=True  # Latest first
        )
        
        if not backup_files:
            logger.error(f"No backup files found for: {file_path}")
            return False
        
        # Select backup to restore
        backup_to_restore = None
        if backup_timestamp:
            # Find specific backup
            for backup_file in backup_files:
                if backup_timestamp in str(backup_file):
                    backup_to_restore = backup_file
                    break
            
            if not backup_to_restore:
                logger.error(f"Backup with timestamp {backup_timestamp} not found")
                return False
        else:
            # Use latest backup
            backup_to_restore = backup_files[0]
        
        # Restore the file
        shutil.copy2(backup_to_restore, file_path)
        logger.info(f"Restored {file_path} from {backup_to_restore}")
        return True
    
    except Exception as e:
        logger.error(f"Failed to restore {file_path}: {e}")
        return False


def cleanup_old_backups(
    project_path: str,
    keep_latest: int = 5,
    file_pattern: str = "*.mgx_bak.*"
) -> int:
    """
    Clean up old backup files, keeping only the N latest for each file.
    
    Args:
        project_path: Path to the project directory
        keep_latest: Number of latest backups to keep per file
        file_pattern: Glob pattern for backup files
    
    Returns:
        Number of backup files removed
    """
    removed_count = 0
    
    try:
        # Group backups by original file
        backups_by_file = {}
        all_backups = list_backups(project_path, file_pattern)
        
        for backup in all_backups:
            original = backup.original_file
            if original not in backups_by_file:
                backups_by_file[original] = []
            backups_by_file[original].append(backup)
        
        # Remove old backups for each file
        for original_file, backups in backups_by_file.items():
            # Sort by timestamp (newest first)
            backups.sort(key=lambda b: b.timestamp, reverse=True)
            
            # Remove old backups beyond keep_latest
            for backup in backups[keep_latest:]:
                try:
                    os.remove(backup.backup_file)
                    logger.info(f"Removed old backup: {backup.backup_file}")
                    removed_count += 1
                except Exception as e:
                    logger.warning(f"Failed to remove {backup.backup_file}: {e}")
        
        logger.info(f"Cleaned up {removed_count} old backup files")
        return removed_count
    
    except Exception as e:
        logger.error(f"Failed to cleanup backups: {e}")
        return 0


def get_backup_for_file(file_path: str, timestamp: Optional[str] = None) -> Optional[str]:
    """
    Get the path to a backup file.
    
    Args:
        file_path: Path to the original file
        timestamp: Specific timestamp (default: latest)
    
    Returns:
        Path to the backup file, or None if not found
    """
    try:
        backup_pattern = f"{file_path}.mgx_bak.*"
        backup_files = sorted(
            Path(os.path.dirname(file_path) or '.').glob(os.path.basename(backup_pattern)),
            reverse=True  # Latest first
        )
        
        if not backup_files:
            return None
        
        if timestamp:
            for backup_file in backup_files:
                if timestamp in str(backup_file):
                    return str(backup_file)
            return None
        else:
            return str(backup_files[0])
    
    except Exception as e:
        logger.error(f"Failed to get backup for {file_path}: {e}")
        return None


def list_mgx_artifacts(project_path: str) -> Dict[str, List[str]]:
    """
    List all MGX-related artifacts (.mgx_new, .mgx_apply_log.txt, etc.).
    
    Args:
        project_path: Path to the project directory
    
    Returns:
        Dictionary mapping artifact type to list of file paths
    """
    artifacts = {
        'backups': [],
        'new_files': [],
        'apply_logs': [],
        'failed_diffs': []
    }
    
    project_path_obj = Path(project_path)
    
    # Find all artifacts
    for item in project_path_obj.rglob('*'):
        if item.is_file():
            name = str(item)
            if '.mgx_bak.' in name:
                artifacts['backups'].append(name)
            elif name.endswith('.mgx_new'):
                artifacts['new_files'].append(name)
            elif name.endswith('.mgx_apply_log.txt'):
                artifacts['apply_logs'].append(name)
            elif name.endswith('.mgx_failed_diff.txt'):
                artifacts['failed_diffs'].append(name)
    
    return artifacts


def cleanup_mgx_artifacts(
    project_path: str,
    artifact_types: Optional[List[str]] = None
) -> int:
    """
    Clean up MGX-related artifacts.
    
    Args:
        project_path: Path to the project directory
        artifact_types: List of artifact types to clean (default: all)
            Options: 'backups', 'new_files', 'apply_logs', 'failed_diffs'
    
    Returns:
        Number of files removed
    """
    if artifact_types is None:
        artifact_types = ['backups', 'new_files', 'apply_logs', 'failed_diffs']
    
    removed_count = 0
    artifacts = list_mgx_artifacts(project_path)
    
    for artifact_type in artifact_types:
        if artifact_type not in artifacts:
            continue
        
        for file_path in artifacts[artifact_type]:
            try:
                os.remove(file_path)
                logger.info(f"Removed artifact: {file_path}")
                removed_count += 1
            except Exception as e:
                logger.warning(f"Failed to remove {file_path}: {e}")
    
    logger.info(f"Cleaned up {removed_count} MGX artifacts")
    return removed_count
