#!/usr/bin/env python3
"""
MEV-INSPECT-PYREVM: Production Deployment Analysis
==================================================

Complete analysis of files, sizes, and deployment recommendations.
"""

import os
import json
from pathlib import Path
from collections import defaultdict

# Color codes
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def get_file_size(path):
    """Get file size in bytes"""
    try:
        return os.path.getsize(path)
    except:
        return 0

def get_line_count(path):
    """Count lines in a file"""
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return len(f.readlines())
    except:
        return 0

def analyze_directory(root_path):
    """Analyze all files in directory"""
    
    categories = {
        'production': {
            'paths': [
                'mev_inspect/*.py',
                'mev_inspect/detectors/*.py',
                'mev_inspect/dex/*.py',
                'mev_inspect/reporters/*.py',
            ],
            'files': [],
            'size': 0,
            'lines': 0
        },
        'config': {
            'paths': [
                'README.md',
                'pyproject.toml',
                '.env.example',
                '.gitignore'
            ],
            'files': [],
            'size': 0,
            'lines': 0
        },
        'docs_keep': {
            'paths': [
                'docs/PYREVM_INSTALL.md',
                'docs/DEPLOYMENT_SUMMARY.md',
                'PRODUCTION_GUIDE.md'
            ],
            'files': [],
            'size': 0,
            'lines': 0
        },
        'tests': {
            'paths': [
                'tests/*.py'
            ],
            'files': [],
            'size': 0,
            'lines': 0
        },
        'examples': {
            'paths': [
                'examples/*.py',
                'examples/*.md'
            ],
            'files': [],
            'size': 0,
            'lines': 0
        },
        'docs_remove': {
            'paths': [
                'docs/PHASE*.md',
                'docs/PHASE*.py',
                'PROJECT_COMPLETE.py'
            ],
            'files': [],
            'size': 0,
            'lines': 0
        }
    }
    
    # Scan files
    root = Path(root_path)
    
    # Production files
    for pattern in categories['production']['paths']:
        for file in root.glob(pattern):
            if file.is_file() and '__pycache__' not in str(file):
                categories['production']['files'].append(str(file))
                categories['production']['size'] += get_file_size(file)
                categories['production']['lines'] += get_line_count(file)
    
    # Config files
    for pattern in categories['config']['paths']:
        file = root / pattern
        if file.is_file():
            categories['config']['files'].append(str(file))
            categories['config']['size'] += get_file_size(file)
            categories['config']['lines'] += get_line_count(file)
    
    # Docs to keep
    for pattern in categories['docs_keep']['paths']:
        file = root / pattern
        if file.is_file():
            categories['docs_keep']['files'].append(str(file))
            categories['docs_keep']['size'] += get_file_size(file)
            categories['docs_keep']['lines'] += get_line_count(file)
    
    # Tests
    for pattern in categories['tests']['paths']:
        for file in root.glob(pattern):
            if file.is_file():
                categories['tests']['files'].append(str(file))
                categories['tests']['size'] += get_file_size(file)
                categories['tests']['lines'] += get_line_count(file)
    
    # Examples
    for pattern in categories['examples']['paths']:
        for file in root.glob(pattern):
            if file.is_file():
                categories['examples']['files'].append(str(file))
                categories['examples']['size'] += get_file_size(file)
                categories['examples']['lines'] += get_line_count(file)
    
    # Docs to remove
    for pattern in categories['docs_remove']['paths']:
        for file in root.glob(pattern):
            if file.is_file():
                categories['docs_remove']['files'].append(str(file))
                categories['docs_remove']['size'] += get_file_size(file)
                categories['docs_remove']['lines'] += get_line_count(file)
    
    return categories

def format_size(bytes_size):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

def print_analysis(categories):
    """Print detailed analysis"""
    
    print("=" * 80)
    print("MEV-INSPECT-PYREVM: Production Deployment Analysis")
    print("=" * 80)
    print()
    
    # Production files
    print(f"{GREEN}✅ PRODUCTION FILES (Must Deploy){NC}")
    print("-" * 80)
    print(f"Files:  {len(categories['production']['files'])}")
    print(f"Size:   {format_size(categories['production']['size'])}")
    print(f"Lines:  {categories['production']['lines']:,}")
    print()
    print("Files:")
    for f in sorted(categories['production']['files'])[:10]:
        size = format_size(get_file_size(f))
        lines = get_line_count(f)
        print(f"  • {f.replace('/home/cheese/Documents/Vault/Blockchain/Project/mev-inspect-pyrevm/', ''):<50s} {size:>8s} ({lines:>4,} lines)")
    if len(categories['production']['files']) > 10:
        print(f"  ... and {len(categories['production']['files']) - 10} more files")
    print()
    
    # Config files
    print(f"{GREEN}✅ CONFIGURATION FILES (Must Deploy){NC}")
    print("-" * 80)
    print(f"Files:  {len(categories['config']['files'])}")
    print(f"Size:   {format_size(categories['config']['size'])}")
    print(f"Lines:  {categories['config']['lines']:,}")
    print()
    for f in sorted(categories['config']['files']):
        size = format_size(get_file_size(f))
        lines = get_line_count(f)
        print(f"  • {f.replace('/home/cheese/Documents/Vault/Blockchain/Project/mev-inspect-pyrevm/', ''):<50s} {size:>8s} ({lines:>4,} lines)")
    print()
    
    # Docs to keep
    print(f"{YELLOW}⚠️  DOCUMENTATION (Optional - Recommended){NC}")
    print("-" * 80)
    print(f"Files:  {len(categories['docs_keep']['files'])}")
    print(f"Size:   {format_size(categories['docs_keep']['size'])}")
    print(f"Lines:  {categories['docs_keep']['lines']:,}")
    print()
    for f in sorted(categories['docs_keep']['files']):
        size = format_size(get_file_size(f))
        lines = get_line_count(f)
        print(f"  • {f.replace('/home/cheese/Documents/Vault/Blockchain/Project/mev-inspect-pyrevm/', ''):<50s} {size:>8s} ({lines:>4,} lines)")
    print()
    
    # Tests
    print(f"{RED}❌ TEST FILES (Exclude from Production){NC}")
    print("-" * 80)
    print(f"Files:  {len(categories['tests']['files'])}")
    print(f"Size:   {format_size(categories['tests']['size'])}")
    print(f"Lines:  {categories['tests']['lines']:,}")
    print()
    for f in sorted(categories['tests']['files']):
        size = format_size(get_file_size(f))
        lines = get_line_count(f)
        print(f"  • {f.replace('/home/cheese/Documents/Vault/Blockchain/Project/mev-inspect-pyrevm/', ''):<50s} {size:>8s} ({lines:>4,} lines)")
    print()
    
    # Examples
    print(f"{RED}❌ EXAMPLE SCRIPTS (Exclude from Production){NC}")
    print("-" * 80)
    print(f"Files:  {len(categories['examples']['files'])}")
    print(f"Size:   {format_size(categories['examples']['size'])}")
    print(f"Lines:  {categories['examples']['lines']:,}")
    print()
    for f in sorted(categories['examples']['files']):
        size = format_size(get_file_size(f))
        lines = get_line_count(f)
        print(f"  • {f.replace('/home/cheese/Documents/Vault/Blockchain/Project/mev-inspect-pyrevm/', ''):<50s} {size:>8s} ({lines:>4,} lines)")
    print()
    
    # Docs to remove
    print(f"{RED}❌ DEVELOPMENT DOCS (Exclude from Production){NC}")
    print("-" * 80)
    print(f"Files:  {len(categories['docs_remove']['files'])}")
    print(f"Size:   {format_size(categories['docs_remove']['size'])}")
    print(f"Lines:  {categories['docs_remove']['lines']:,}")
    print()
    for f in sorted(categories['docs_remove']['files']):
        size = format_size(get_file_size(f))
        lines = get_line_count(f)
        print(f"  • {f.replace('/home/cheese/Documents/Vault/Blockchain/Project/mev-inspect-pyrevm/', ''):<50s} {size:>8s} ({lines:>4,} lines)")
    print()
    
    # Summary
    print("=" * 80)
    print("DEPLOYMENT SUMMARY")
    print("=" * 80)
    print()
    
    production_total = (
        categories['production']['size'] + 
        categories['config']['size'] + 
        categories['docs_keep']['size']
    )
    production_lines = (
        categories['production']['lines'] + 
        categories['config']['lines'] + 
        categories['docs_keep']['lines']
    )
    production_files = (
        len(categories['production']['files']) + 
        len(categories['config']['files']) + 
        len(categories['docs_keep']['files'])
    )
    
    exclude_total = (
        categories['tests']['size'] + 
        categories['examples']['size'] + 
        categories['docs_remove']['size']
    )
    exclude_lines = (
        categories['tests']['lines'] + 
        categories['examples']['lines'] + 
        categories['docs_remove']['lines']
    )
    exclude_files = (
        len(categories['tests']['files']) + 
        len(categories['examples']['files']) + 
        len(categories['docs_remove']['files'])
    )
    
    print(f"{GREEN}Production Package:{NC}")
    print(f"  Files:  {production_files}")
    print(f"  Size:   {format_size(production_total)}")
    print(f"  Lines:  {production_lines:,}")
    print()
    
    print(f"{RED}Excluded from Production:{NC}")
    print(f"  Files:  {exclude_files}")
    print(f"  Size:   {format_size(exclude_total)}")
    print(f"  Lines:  {exclude_lines:,}")
    print()
    
    reduction_pct = (exclude_total / (production_total + exclude_total) * 100)
    print(f"{GREEN}Size Reduction: {reduction_pct:.1f}% ({format_size(exclude_total)} saved){NC}")
    print()
    
    # Deployment command
    print("=" * 80)
    print("DEPLOYMENT COMMANDS")
    print("=" * 80)
    print()
    print("1. Clean for production:")
    print(f"   {BLUE}chmod +x clean_for_production.fish{NC}")
    print(f"   {BLUE}./clean_for_production.fish{NC}")
    print()
    print("2. Test production readiness:")
    print(f"   {BLUE}chmod +x TEST_PRODUCTION.fish{NC}")
    print(f"   {BLUE}./TEST_PRODUCTION.fish{NC}")
    print()
    print("3. Build package:")
    print(f"   {BLUE}python3 -m build{NC}")
    print()
    print("4. Deploy:")
    print(f"   {BLUE}python3 -m twine upload dist/*{NC}")
    print()
    
    # Export to JSON
    summary = {
        'production': {
            'files': production_files,
            'size_bytes': production_total,
            'size_human': format_size(production_total),
            'lines': production_lines
        },
        'excluded': {
            'files': exclude_files,
            'size_bytes': exclude_total,
            'size_human': format_size(exclude_total),
            'lines': exclude_lines
        },
        'reduction_percent': reduction_pct
    }
    
    with open('deployment_analysis.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"{GREEN}✅ Analysis saved to: deployment_analysis.json{NC}")
    print()

if __name__ == '__main__':
    root_path = '/home/cheese/Documents/Vault/Blockchain/Project/mev-inspect-pyrevm'
    categories = analyze_directory(root_path)
    print_analysis(categories)
