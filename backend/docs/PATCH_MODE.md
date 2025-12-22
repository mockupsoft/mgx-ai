# Patch Mode - Safe Diff Application

## Overview

Patch Mode allows MGX Agent to safely apply unified diffs to existing projects with guaranteed backups and fallback mechanisms. This mode is essential for modifying existing codebases without risking data loss.

## Features

- ✅ **Automatic Backups**: Every file modification creates a timestamped backup
- ✅ **Line Drift Detection**: Warns when diff line numbers don't match file
- ✅ **Fallback Mechanism**: Creates `.mgx_new` files on failure for manual review
- ✅ **Transaction Support**: All-or-nothing or best-effort patch application
- ✅ **Dry-Run Mode**: Test patches without modifying files
- ✅ **Comprehensive Logging**: Detailed logs of what succeeded and failed

## Patch Mode vs. Generate New Mode

| Feature | Patch Mode | Generate New Mode |
|---------|------------|-------------------|
| Use Case | Modify existing files | Create new project |
| Safety | Backups + rollback | N/A |
| Line Numbers | Critical | Not needed |
| Conflict Handling | Fallback to .mgx_new | N/A |
| Best For | Bug fixes, features | Greenfield projects |

## Usage

### Basic Patch Application

```python
from mgx_agent.diff_writer import apply_diff

# Apply a single diff
diff_str = """--- a/src/app.py
+++ b/src/app.py
@@ -10,5 +10,7 @@
 def hello():
-    print("Hello")
+    print("Hello World")
+    return True
"""

result = apply_diff(
    file_path="src/app.py",
    diff=diff_str,
    backup=True  # Create backup (default)
)

if result.success:
    print(f"✅ Patch applied successfully")
    print(f"Backup: {result.backup_file}")
else:
    print(f"❌ Patch failed: {result.message}")
    print(f"Review: {result.new_file_created}")
    print(f"Log: {result.log_file}")
```

### Multi-File Patch Set

```python
from mgx_agent.diff_writer import apply_patch_set

diffs = [
    ("src/app.py", diff1),
    ("src/utils.py", diff2),
    ("tests/test_app.py", diff3)
]

# All-or-nothing mode (rollback on any failure)
result = apply_patch_set(
    diffs=diffs,
    project_path="/path/to/project",
    mode="all_or_nothing"
)

# Best-effort mode (apply what you can)
result = apply_patch_set(
    diffs=diffs,
    project_path="/path/to/project",
    mode="best_effort"
)

print(f"Applied: {result.applied_count}/{len(diffs)}")
print(f"Failed: {result.failed_count}")
```

### Dry-Run Mode

```python
# Test without modifying files
result = apply_diff(
    file_path="src/app.py",
    diff=diff_str,
    dry_run=True
)

print(f"Would apply: {result.message}")
for warning in result.line_drift_warnings:
    print(f"⚠️ {warning}")
```

## Backup Management

### List Backups

```python
from mgx_agent.file_recovery import list_backups

backups = list_backups("/path/to/project")

for backup in backups:
    print(f"Original: {backup.original_file}")
    print(f"Backup: {backup.backup_file}")
    print(f"Timestamp: {backup.timestamp}")
    print(f"Size: {backup.size_bytes} bytes")
```

### Restore from Backup

```python
from mgx_agent.file_recovery import restore_from_backup

# Restore from latest backup
success = restore_from_backup("src/app.py")

# Restore from specific timestamp
success = restore_from_backup(
    "src/app.py",
    backup_timestamp="20250114_153022"
)
```

### Cleanup Old Backups

```python
from mgx_agent.file_recovery import cleanup_old_backups

# Keep only 5 latest backups per file
removed = cleanup_old_backups(
    project_path="/path/to/project",
    keep_latest=5
)

print(f"Removed {removed} old backups")
```

## Handling .mgx_new Files

When a patch fails to apply, MGX Agent creates several files for manual review:

- **`file.mgx_new`**: Attempted changes that couldn't be applied
- **`file.mgx_apply_log.txt`**: Detailed log of what went wrong
- **`file.mgx_failed_diff.txt`**: The diff that failed

### Manual Review Workflow

1. **Review the Log**:
   ```bash
   cat src/app.py.mgx_apply_log.txt
   ```

2. **Compare Files**:
   ```bash
   diff src/app.py src/app.py.mgx_new
   ```

3. **Decide**:
   - **Accept Changes**: `mv src/app.py.mgx_new src/app.py`
   - **Reject Changes**: `rm src/app.py.mgx_new`
   - **Manual Merge**: Use editor to selectively apply changes

4. **Cleanup**:
   ```bash
   rm src/app.py.mgx_apply_log.txt
   rm src/app.py.mgx_failed_diff.txt
   ```

## Line Drift Detection

Patch Mode detects when diff line numbers don't match the current file state:

```python
result = apply_diff(file_path, diff)

for warning in result.line_drift_warnings:
    print(f"⚠️ {warning}")
```

**Tolerance**: Drift > 2 lines triggers a warning but doesn't block application.

**What to do**:
- Check if file was modified since diff was generated
- Regenerate diff against current file state
- Manually review `.mgx_new` file

## Integration with TaskExecutor

Patch mode is automatically used when `output_mode == 'patch_existing'`:

```python
# In TaskExecutor.execute_task()
if output_mode == 'patch_existing':
    # Extract diffs from generated output
    diffs = extract_diffs_from_output(result)
    
    # Apply patch set
    patch_result = apply_patch_set(
        diffs=diffs,
        project_path=project_path,
        mode="best_effort"
    )
    
    if not patch_result.success:
        # Emit event with .mgx_new file references
        await broadcaster.publish(PatchApplyFailedEvent(
            task_id=task_id,
            run_id=run_id,
            data={
                "failed_count": patch_result.failed_count,
                "results": patch_result.results
            }
        ))
```

## Safety Guarantees

1. **Non-Destructive**: Original files are never lost
2. **Atomic Operations**: File modification is atomic (write to temp, then rename)
3. **Rollback on Failure**: All-or-nothing mode rolls back all changes
4. **Manual Fallback**: Failed changes written to `.mgx_new` for review

## Troubleshooting

### "Patch apply failed: No hunks found"

**Cause**: Invalid diff format

**Solution**: Check diff syntax, ensure it follows unified diff format

### "Line drift: hunk starts at line 100, but file has only 50 lines"

**Cause**: File was modified since diff was generated

**Solution**: Regenerate diff against current file state

### "File does not exist for modification"

**Cause**: Diff tries to modify non-existent file

**Solution**: Change operation to CREATE or ensure file exists

### ".mgx_new files accumulating"

**Cause**: Failed patches not cleaned up

**Solution**: Use `cleanup_mgx_artifacts()` to remove all MGX files

```python
from mgx_agent.file_recovery import cleanup_mgx_artifacts

removed = cleanup_mgx_artifacts("/path/to/project")
```

## Best Practices

1. **Always Enable Backups**: Never disable backup creation in production
2. **Use Dry-Run First**: Test patches before applying to critical files
3. **Monitor Line Drift**: Regenerate diffs if drift warnings appear
4. **Regular Cleanup**: Remove old backups periodically (keep 5-10 latest)
5. **Review .mgx_new Files**: Don't ignore failed patches, review manually
6. **Transaction Mode for Critical**: Use "all_or_nothing" for production deployments

## Example: Complete Workflow

```python
from mgx_agent.diff_writer import apply_patch_set
from mgx_agent.file_recovery import list_backups, cleanup_old_backups

# 1. Apply patches
diffs = [
    ("src/app.py", diff1),
    ("src/utils.py", diff2)
]

result = apply_patch_set(
    diffs=diffs,
    project_path="/path/to/project",
    mode="all_or_nothing"
)

# 2. Handle results
if result.success:
    print("✅ All patches applied successfully")
    
    # List backups
    backups = list_backups("/path/to/project")
    print(f"Created {len(backups)} backups")
else:
    print(f"❌ {result.failed_count} patches failed")
    
    # Review failures
    for r in result.results:
        if not r.success:
            print(f"Failed: {r.file_path}")
            print(f"Review: {r.new_file_created}")
            print(f"Log: {r.log_file}")

# 3. Cleanup old backups
removed = cleanup_old_backups("/path/to/project", keep_latest=5)
print(f"Cleaned up {removed} old backups")
```

## Related Documentation

- [DIFF_FORMAT.md](./DIFF_FORMAT.md) - Unified diff format specification
- [OUTPUT_VALIDATION.md](./OUTPUT_VALIDATION.md) - Output validation guardrails
- [GIT_AWARE_EXECUTION.md](./GIT_AWARE_EXECUTION.md) - Git integration
