#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simple demo showing Phase 8.1 Output Validation Guardrails

This demonstrates validation rules without requiring MetaGPT config.
"""

def print_example(title, content, errors, warnings=None):
    """Print example output"""
    print(f"\n{'='*70}")
    print(f"EXAMPLE: {title}")
    print(f"{'='*70}")
    print("\nContent Preview:")
    print("-" * 70)
    lines = content.strip().split('\n')
    for line in lines[:10]:
        print(line)
    if len(lines) > 10:
        print(f"... ({len(lines) - 10} more lines)")
    print("-" * 70)
    
    if errors:
        print(f"\n❌ VALIDATION FAILED - {len(errors)} Errors:")
        for i, error in enumerate(errors, 1):
            print(f"   {i}. {error}")
    else:
        print(f"\n✅ VALIDATION PASSED")
    
    if warnings:
        print(f"\n⚠️  {len(warnings)} Warnings:")
        for i, warning in enumerate(warnings, 1):
            print(f"   {i}. {warning}")


def main():
    print("\n" + "🛡️ " * 35)
    print("   PHASE 8.1: OUTPUT VALIDATION GUARDRAILS - DEMO")
    print("🛡️ " * 35)
    
    # Example 1: Valid Express TypeScript
    print_example(
        "Valid Express TypeScript Output",
        """
FILE: package.json
{"name": "my-api", "dependencies": {"express": "^4.18.0"}}

FILE: tsconfig.json
{"compilerOptions": {"target": "ES2020"}}

FILE: src/index.ts
import express from 'express';
const app = express();
app.listen(3000);
""",
        errors=[],
        warnings=["Stack 'express-ts' typically uses command: npm run dev (not found)"]
    )
    
    # Example 2: Missing Required Files
    print_example(
        "Missing Required Files (Express TS)",
        """
FILE: src/index.ts
import express from 'express';
const app = express();
""",
        errors=[
            "Stack 'express-ts' requires file: package.json",
            "Stack 'express-ts' requires file: tsconfig.json"
        ]
    )
    
    # Example 3: Forbidden Imports
    print_example(
        "Forbidden Imports (FastAPI with Express)",
        """
FILE: main.py
from fastapi import FastAPI
import express  # ❌ Wrong framework!

app = FastAPI()
""",
        errors=[
            "Forbidden import/usage in stack 'fastapi': 'import express'"
        ]
    )
    
    # Example 4: Path Traversal Attack
    print_example(
        "Path Traversal Attack Prevention",
        """
FILE: ../../../etc/passwd
root:x:0:0:root:/root:/bin/bash

FILE: src/main.py
def hello():
    pass
""",
        errors=[
            "Path traversal detected: ../../../etc/passwd"
        ]
    )
    
    # Example 5: Strict Mode Violation
    print_example(
        "Strict Mode - Prose Outside FILE Blocks",
        """
Here's my solution:

FILE: main.py
def hello():
    pass

This implements the feature.
""",
        errors=[
            "Strict mode: Found 2 lines of prose/explanation outside FILE blocks"
        ]
    )
    
    # Example 6: Duplicate Files
    print_example(
        "Duplicate File Definitions",
        """
FILE: main.py
def hello():
    pass

FILE: routes.py
def route():
    pass

FILE: main.py
def goodbye():
    pass
""",
        errors=[
            "Duplicate file definition: main.py (defined 2 times)"
        ]
    )
    
    # Example 7: Constraint Violation - Extra Libraries
    print_example(
        "Constraint Violation: 'No Extra Libraries'",
        """
FILE: main.py
from fastapi import FastAPI
import requests  # ❌ Not in common deps
import numpy as np  # ❌ Not in common deps
""",
        errors=[
            "Constraint 'no extra libraries': Found import 'requests' which is not in common dependencies",
            "Constraint 'no extra libraries': Found import 'numpy' which is not in common dependencies"
        ]
    )
    
    # Example 8: Mixed Stack Warning
    print_example(
        "Mixed Stack Detection (Monorepo Warning)",
        """
FILE: package.json
{"name": "frontend"}

FILE: requirements.txt
fastapi==0.104.0

FILE: src/index.ts
import express from 'express';

FILE: main.py
from fastapi import FastAPI
""",
        errors=[],
        warnings=[
            "Mixed stack detected: Expected 'nodejs' (based on express-ts) but also found indicators for: python. This might be intentional (monorepo) or a mistake."
        ]
    )
    
    print("\n" + "="*70)
    print("✅ VALIDATION FEATURES DEMONSTRATED:")
    print("="*70)
    print("""
✓ Stack-Specific File Requirements
✓ Forbidden Library Detection
✓ Path Security (Traversal Prevention)
✓ FILE Manifest Format Compliance
✓ Duplicate File Detection
✓ User Constraint Enforcement
✓ Mixed Stack Detection
✓ Clear, Actionable Error Messages

📚 Full Documentation: docs/OUTPUT_VALIDATION.md
🧪 Unit Tests: tests/unit/test_output_validation.py (46 tests)
🔧 Integration: mgx_agent/actions.py (WriteCode with auto-revision)
""")
    
    print("="*70)
    print()


if __name__ == "__main__":
    main()
