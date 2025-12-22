#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Demo script showing Phase 8.1 Output Validation Guardrails in action

This demonstrates:
1. Valid output passing validation
2. Invalid output failing validation with clear errors
3. Auto-revision flow (simulated)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from mgx_agent.guardrails import validate_output_constraints, build_revision_prompt
from mgx_agent.stack_specs import get_stack_spec


def demo_valid_express_output():
    """Example 1: Valid Express TypeScript output"""
    print("\n" + "="*70)
    print("EXAMPLE 1: Valid Express TypeScript Output")
    print("="*70)
    
    content = """
FILE: package.json
{
  "name": "my-api",
  "version": "1.0.0",
  "dependencies": {
    "express": "^4.18.0",
    "dotenv": "^16.0.0"
  },
  "scripts": {
    "dev": "ts-node src/index.ts",
    "build": "tsc",
    "test": "jest"
  }
}

FILE: tsconfig.json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "commonjs",
    "outDir": "./dist",
    "strict": true
  }
}

FILE: src/index.ts
import express from 'express';
import dotenv from 'dotenv';

dotenv.config();

const app = express();
app.use(express.json());

app.get('/', (req, res) => {
  res.json({ message: 'Hello World' });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
"""
    
    spec = get_stack_spec("express-ts")
    result = validate_output_constraints(content, spec, strict_mode=False)
    
    print(f"\n✅ Validation Result: {result.summary()}")
    if result.warnings:
        print(f"\n⚠️  Warnings:")
        for warning in result.warnings:
            print(f"   - {warning}")


def demo_invalid_express_output():
    """Example 2: Invalid Express output (missing files, wrong imports)"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Invalid Express Output (Missing Files + Forbidden Imports)")
    print("="*70)
    
    content = """
FILE: src/index.ts
import express from 'express';
from fastapi import FastAPI  // ❌ Wrong! This is Python

const app = express();
app.listen(3000);
"""
    
    spec = get_stack_spec("express-ts")
    result = validate_output_constraints(content, spec, strict_mode=False)
    
    print(f"\n❌ Validation Result: {result.summary()}")
    print(f"\nErrors ({len(result.errors)}):")
    for i, error in enumerate(result.errors, 1):
        print(f"   {i}. {error}")


def demo_path_traversal_attack():
    """Example 3: Path traversal attack prevention"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Path Traversal Attack Prevention")
    print("="*70)
    
    content = """
FILE: ../../../etc/passwd
root:x:0:0:root:/root:/bin/bash

FILE: src/main.py
def hello():
    pass
"""
    
    spec = get_stack_spec("fastapi")
    result = validate_output_constraints(content, spec)
    
    print(f"\n❌ Validation Result: {result.summary()}")
    print(f"\nErrors ({len(result.errors)}):")
    for i, error in enumerate(result.errors, 1):
        print(f"   {i}. {error}")


def demo_constraint_validation():
    """Example 4: Constraint enforcement - no extra libraries"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Constraint Enforcement - 'No Extra Libraries'")
    print("="*70)
    
    content = """
FILE: main.py
from fastapi import FastAPI
import requests  # ❌ Not in common deps
import numpy as np  # ❌ Not in common deps
import os  # ✅ Built-in, OK

app = FastAPI()
"""
    
    spec = get_stack_spec("fastapi")
    constraints = ["no extra libraries"]
    result = validate_output_constraints(content, spec, constraints=constraints)
    
    print(f"\n❌ Validation Result: {result.summary()}")
    print(f"\nErrors ({len(result.errors)}):")
    for i, error in enumerate(result.errors, 1):
        print(f"   {i}. {error}")


def demo_strict_mode():
    """Example 5: Strict mode - no prose allowed"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Strict Mode - FILE-Only Format")
    print("="*70)
    
    content = """
Here's my solution to the problem:

FILE: main.py
def hello():
    pass

This implements the feature as requested.
"""
    
    spec = get_stack_spec("fastapi")
    result = validate_output_constraints(content, spec, strict_mode=True)
    
    print(f"\n❌ Validation Result: {result.summary()}")
    print(f"\nErrors ({len(result.errors)}):")
    for i, error in enumerate(result.errors, 1):
        print(f"   {i}. {error}")


def demo_revision_prompt():
    """Example 6: Auto-revision prompt generation"""
    print("\n" + "="*70)
    print("EXAMPLE 6: Auto-Revision Prompt Generation")
    print("="*70)
    
    # Simulate a failed validation
    content = """
FILE: src/index.ts
import express from 'express';
"""
    
    spec = get_stack_spec("express-ts")
    result = validate_output_constraints(content, spec)
    
    if not result.is_valid:
        print("\n⚠️  Validation failed. Generating revision prompt...\n")
        revision_prompt = build_revision_prompt(result, "Create an Express TypeScript REST API")
        print("="*70)
        print("REVISION PROMPT:")
        print("="*70)
        print(revision_prompt)


def demo_mixed_stack_warning():
    """Example 7: Mixed stack detection"""
    print("\n" + "="*70)
    print("EXAMPLE 7: Mixed Stack Detection")
    print("="*70)
    
    content = """
FILE: package.json
{
  "name": "mixed"
}

FILE: requirements.txt
fastapi==0.104.0

FILE: src/index.ts
import express from 'express';

FILE: main.py
from fastapi import FastAPI
"""
    
    spec = get_stack_spec("express-ts")
    result = validate_output_constraints(content, spec)
    
    print(f"\n⚠️  Validation Result: {result.summary()}")
    if result.warnings:
        print(f"\nWarnings ({len(result.warnings)}):")
        for i, warning in enumerate(result.warnings, 1):
            print(f"   {i}. {warning}")


def main():
    """Run all demos"""
    print("\n" + "🛡️ "*35)
    print("   PHASE 8.1: OUTPUT VALIDATION GUARDRAILS - DEMO")
    print("🛡️ "*35)
    
    demo_valid_express_output()
    demo_invalid_express_output()
    demo_path_traversal_attack()
    demo_constraint_validation()
    demo_strict_mode()
    demo_revision_prompt()
    demo_mixed_stack_warning()
    
    print("\n" + "="*70)
    print("✅ Demo Complete!")
    print("="*70)
    print("\nSee docs/OUTPUT_VALIDATION.md for complete documentation.")
    print()


if __name__ == "__main__":
    main()
