#!/usr/bin/env python3
"""
Validation script for enterprise test implementations.
Checks syntax, imports, and basic structure without running tests.
"""

import ast
import os
import sys
from pathlib import Path

def check_python_syntax(file_path):
    """Check if Python file has valid syntax."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        ast.parse(content)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error reading file: {str(e)}"

def analyze_test_file(file_path):
    """Analyze test file structure."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        classes = []
        test_methods = []
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith('test_'):
                        test_methods.append(f"{node.name}::{item.name}")
            
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        
        return {
            'file': file_path,
            'classes': classes,
            'test_methods': test_methods,
            'imports': imports,
            'total_classes': len(classes),
            'total_tests': len(test_methods),
            'syntax_valid': True
        }
    
    except Exception as e:
        return {
            'file': file_path,
            'error': str(e),
            'syntax_valid': False
        }

def main():
    """Main validation function."""
    print("=== Enterprise Test Implementation Validation ===\n")
    
    # Test files to validate
    test_files = [
        'backend/tests/test_secrets.py',
        'backend/tests/test_rbac_audit.py',
        'backend/tests/test_project_generator.py',
        'backend/tests/test_artifact_pipeline.py',
        'backend/tests/test_database_migrations.py',  # NEW
        'backend/tests/test_enterprise_scenarios.py',  # NEW
    ]
    
    all_results = []
    total_tests = 0
    
    for test_file in test_files:
        file_path = Path(test_file)
        if not file_path.exists():
            print(f"❌ {test_file}: File not found")
            continue
        
        print(f"📋 Validating {test_file}...")
        
        # Check syntax
        syntax_valid, syntax_error = check_python_syntax(file_path)
        if not syntax_valid:
            print(f"   ❌ Syntax error: {syntax_error}")
            continue
        
        # Analyze structure
        analysis = analyze_test_file(file_path)
        
        if 'error' in analysis:
            print(f"   ❌ Analysis error: {analysis['error']}")
            continue
        
        # Display results
        print(f"   ✅ Syntax valid")
        print(f"   📊 Classes: {analysis['total_classes']}")
        print(f"   🧪 Test methods: {analysis['total_tests']}")
        
        # Show test classes
        for class_name in analysis['classes']:
            if class_name.startswith('Test'):
                print(f"      • {class_name}")
        
        # Show first few test methods
        for test_method in analysis['test_methods'][:5]:
            print(f"      • {test_method}")
        
        if len(analysis['test_methods']) > 5:
            print(f"      ... and {len(analysis['test_methods']) - 5} more tests")
        
        all_results.append(analysis)
        total_tests += analysis['total_tests']
        
        # Show file size
        file_size = file_path.stat().st_size
        print(f"   📁 File size: {file_size:,} bytes")
        print()
    
    # Summary
    print("=== VALIDATION SUMMARY ===")
    print(f"📁 Files validated: {len(all_results)}")
    print(f"🧪 Total test methods: {total_tests}")
    print(f"📄 Total lines of test code: {sum(r['file'].stat().st_size for r in all_results):,}")
    
    # Coverage analysis
    print("\n=== COVERAGE BREAKDOWN ===")
    
    coverage_areas = {
        'test_secrets.py': 'Secret Management',
        'test_rbac_audit.py': 'RBAC & Audit',
        'test_project_generator.py': 'Project Scaffolding',
        'test_artifact_pipeline.py': 'Artifact Pipeline',
        'test_database_migrations.py': 'Database Migrations (NEW)',
        'test_enterprise_scenarios.py': 'Enterprise Integration (NEW)',
    }
    
    for result in all_results:
        file_name = Path(result['file']).name
        area = coverage_areas.get(file_name, 'Unknown')
        print(f"✅ {area}: {result['total_classes']} classes, {result['total_tests']} tests")
    
    # Check documentation
    docs_file = Path('docs/ENTERPRISE_TESTING.md')
    if docs_file.exists():
        print(f"\n✅ Documentation created: {docs_file}")
        docs_size = docs_file.stat().st_size
        print(f"📚 Documentation size: {docs_size:,} bytes")
    else:
        print("\n❌ Documentation not found")
    
    print(f"\n=== VALIDATION COMPLETE ===")
    
    # Return success if all files are valid
    all_valid = all(r['syntax_valid'] for r in all_results)
    return 0 if all_valid else 1

if __name__ == '__main__':
    sys.exit(main())