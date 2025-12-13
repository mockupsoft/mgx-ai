# Unified Diff Format Specification

## Overview

This document describes the unified diff format supported by MGX Agent's patch system. Understanding this format is essential for generating diffs that can be safely applied to existing projects.

## Basic Format

A unified diff consists of:
1. **File headers** (`---` and `+++` lines)
2. **Hunk headers** (`@@` lines)
3. **Hunk content** (context, additions, deletions)

## Format Components

### File Headers

```diff
--- a/path/to/original/file.ext
+++ b/path/to/modified/file.ext
```

- `--- a/`: Original file path (prefix `a/` is conventional but optional)
- `+++ b/`: Modified file path (prefix `b/` is conventional but optional)

### Hunk Header

```diff
@@ -10,5 +10,7 @@
```

Format: `@@ -<start>,<count> +<start>,<count> @@`

- `-10,5`: Original file starts at line 10, shows 5 lines
- `+10,7`: Modified file starts at line 10, shows 7 lines
- Difference (7-5=2): Net 2 lines added

### Hunk Content

```diff
 context line (unchanged)
-removed line
+added line
 another context line
```

- Lines starting with ` ` (space): Context (unchanged)
- Lines starting with `-`: Removed from original
- Lines starting with `+`: Added in modified

## Operations

### 1. File Modification

Modify an existing file by adding/removing/changing lines.

**Example: Add logging to a function**

```diff
--- a/src/app.py
+++ b/src/app.py
@@ -10,5 +10,8 @@
 def process_data(data):
+    import logging
+    logging.info(f"Processing {len(data)} items")
     result = []
     for item in data:
         result.append(item * 2)
     return result
```

**Result**: Adds 2 lines (import and logging) to the function.

### 2. File Creation

Create a new file from scratch.

**Format**:
```diff
--- /dev/null
+++ b/path/to/new/file.ext
@@ -0,0 +1,N @@
+line 1 of new file
+line 2 of new file
+...
+line N of new file
```

**Example: Create a new utility module**

```diff
--- /dev/null
+++ b/src/utils/helper.py
@@ -0,0 +1,5 @@
+def format_name(name):
+    """Format a name to title case."""
+    return name.strip().title()
+
+# End of file
```

### 3. File Deletion

Delete an existing file.

**Format**:
```diff
--- a/path/to/file.ext
+++ /dev/null
```

**Example: Remove deprecated module**

```diff
--- a/src/deprecated/old_utils.py
+++ /dev/null
```

**Note**: No hunk content needed for deletion.

## Multiple Hunks

Multiple hunks in the same file are separated by new `@@` headers.

**Example: Modify two separate sections**

```diff
--- a/src/app.py
+++ b/src/app.py
@@ -5,3 +5,4 @@
 import os
 import sys
+import logging

@@ -15,2 +16,3 @@
 def main():
+    logging.basicConfig(level=logging.INFO)
     run_app()
```

## Context Lines

Context lines help identify where changes should be applied:

- **Minimum**: 3 lines of context before and after changes
- **Purpose**: Uniquely identify location in file
- **Line Drift**: More context = better drift detection

**Example with context**

```diff
--- a/src/app.py
+++ b/src/app.py
@@ -10,7 +10,8 @@
 # Context before
 def calculate(x, y):
     result = x + y
-    return result
+    # Added validation
+    return result if result > 0 else 0
 # Context after
```

## Advanced Patterns

### Replace Multiple Lines

```diff
--- a/config.py
+++ b/config.py
@@ -5,4 +5,3 @@
 CONFIG = {
-    'host': 'localhost',
-    'port': 8080,
+    'server': 'localhost:8080',
 }
```

**Result**: Replaces 2 lines with 1 line (net -1 line).

### Insert Block of Code

```diff
--- a/src/app.py
+++ b/src/app.py
@@ -20,0 +21,5 @@
+def new_function():
+    """New utility function."""
+    pass
+
+
```

**Note**: `@@ -20,0 +21,5 @@` means insert at line 21 (after line 20).

### Modify Multiple Files

Separate diffs for different files with blank line:

```diff
--- a/src/app.py
+++ b/src/app.py
@@ -10,1 +10,2 @@
 import sys
+import logging

--- a/src/utils.py
+++ b/src/utils.py
@@ -5,1 +5,2 @@
 def helper():
+    logging.info("Called helper")
     pass
```

## How TEM Agent Should Format Diffs

When generating diffs, TEM Agent should:

1. **Use Standard Format**: Follow unified diff format exactly
2. **Include Context**: Minimum 3 lines before/after changes
3. **Use Relative Paths**: Paths relative to project root
4. **One Operation Per Diff**: Don't mix create/modify/delete in same diff
5. **Clear Intent**: Make it obvious what changed and why

### Good Diff Example

```diff
--- a/src/middleware/auth.py
+++ b/src/middleware/auth.py
@@ -15,6 +15,8 @@
 def authenticate_user(token):
     """Authenticate user by token."""
+    if not token:
+        raise ValueError("Token is required")
+    
     user = decode_token(token)
     if not user:
         raise AuthenticationError("Invalid token")
```

**Why Good**:
- Clear context (function definition)
- Obvious change (added validation)
- Proper formatting (spaces, indentation)

### Bad Diff Example

```diff
--- a/src/middleware/auth.py
+++ b/src/middleware/auth.py
@@ -15,1 +15,2 @@
+    if not token:
+        raise ValueError("Token is required")
```

**Why Bad**:
- No context (can't determine where to insert)
- Missing surrounding code
- Ambiguous location

## Line Number Handling

### Absolute Line Numbers

Line numbers in hunk headers are **absolute** (1-based):

```diff
@@ -10,5 +10,7 @@
```

- Original file: lines 10-14 (5 lines)
- Modified file: lines 10-16 (7 lines)

### Sequential Application

When applying multiple hunks, line numbers adjust after each hunk:

```diff
# Hunk 1: Insert at line 10
@@ -10,0 +10,2 @@
+new line 1
+new line 2

# Hunk 2: Line numbers shifted by +2
@@ -20,1 +22,1 @@
-old line
+new line
```

**Note**: Second hunk line numbers account for first hunk's changes.

## Special Cases

### Empty File Creation

```diff
--- /dev/null
+++ b/new_file.py
@@ -0,0 +1,1 @@
+# Empty file with comment
```

### Complete File Replacement

```diff
--- a/old_file.py
+++ b/new_file.py
@@ -1,5 +0,0 @@
-old line 1
-old line 2
-old line 3
-old line 4
-old line 5
@@ -0,0 +1,3 @@
+new line 1
+new line 2
+new line 3
```

**Note**: Remove all old content, then add new content.

### Binary Files

Binary files are detected but not supported:

```diff
--- a/image.png
+++ b/image.png
Binary files differ
```

**MGX Behavior**: Skip with warning, don't corrupt binary files.

## Diff Generation Tips

### Use Git

```bash
# Single file
git diff src/app.py > app.patch

# Multiple files
git diff src/ > changes.patch

# Staged changes
git diff --staged > staged.patch
```

### Use Diff Command

```bash
# Single file
diff -u original.py modified.py > file.patch

# Directory
diff -ur original_dir/ modified_dir/ > dir.patch
```

### Python Generation

```python
import difflib

with open('original.py') as f:
    original = f.readlines()

with open('modified.py') as f:
    modified = f.readlines()

diff = difflib.unified_diff(
    original,
    modified,
    fromfile='a/original.py',
    tofile='b/modified.py',
    lineterm=''
)

print('\n'.join(diff))
```

## Validation

MGX Agent validates diffs before applying:

1. **Syntax Check**: Valid unified diff format
2. **Path Security**: No path traversal (`../`, `/etc/`)
3. **File Existence**: Modification target exists
4. **Line Bounds**: Line numbers within file range
5. **Context Match**: Context lines match file content

## Common Errors

### Missing File Headers

```diff
@@ -10,1 +10,2 @@
 line 1
+line 2
```

**Fix**: Add `---` and `+++` headers.

### Wrong Line Numbers

```diff
@@ -1000,2 +1000,3 @@
 line at position 1000
```

**Fix**: Ensure line numbers match actual file.

### Missing Context

```diff
@@ -10,0 +10,1 @@
+new line
```

**Fix**: Add at least 3 lines of context before/after.

### Mixed Operations

```diff
--- /dev/null
+++ b/new_file.py
@@ -10,1 +10,2 @@
```

**Fix**: Don't mix create with modify hunks.

## Testing Diffs

Before applying to production:

```python
from mgx_agent.diff_writer import apply_diff

# Dry-run test
result = apply_diff(
    file_path="src/app.py",
    diff=diff_string,
    dry_run=True
)

if result.success:
    print("✅ Diff is valid")
else:
    print(f"❌ Error: {result.message}")
```

## Related Documentation

- [PATCH_MODE.md](./PATCH_MODE.md) - Safe patch application
- [OUTPUT_VALIDATION.md](./OUTPUT_VALIDATION.md) - Output validation
