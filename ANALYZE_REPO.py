#!/usr/bin/env python3
"""
Repository Analysis for Production Deployment
==============================================
Analyzes all files in the repository and categorizes them as:
- Production code (deploy)
- Development files (remove)
- Configuration files (keep)
"""

import os
import json
from pathlib import Path
from collections import defaultdict

def get_file_size(filepath):
    """Get file size in bytes."""
    try:
        return os.path.getsize(filepath)
    except:
        return 0

def count_lines(filepath):
    """Count lines in a file."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return len(f.readlines())
    except:
        return 0

def analyze_repo():
    """Analyze repository structure."""
    
    base_path = Path('.')
    
    # Categories
    production_files = []  # Files to deploy
    dev_files = []         # Files to remove before deploy
    config_files = []      # Config files (keep but don't count)
    
    # Patterns for development files
    dev_patterns = [
        'test_', 'demo_', 'check_', 'verify_', 'validate_',
        'PHASE', 'PROJECT_COMPLETE', 'PRODUCTION_GUIDE.py',
        'analyze_deployment', 'quick_test', 'TEST_PRODUCTION',
        'clean_for_production', 'SUMMARY.txt', 'CONTEXT.md',
        'UPGRADE_PLAN', 'PYREVM_INSTALL', 'DEPLOYMENT_SUMMARY',
    ]
    
    dev_extensions = ['.txt', '.json']  # Only if in root
    
    # Scan all files
    for root, dirs, files in os.walk('.'):
        # Skip hidden and cache directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        
        for filename in files:
            filepath = Path(root) / filename
            rel_path = str(filepath.relative_to('.'))
            
            # Skip hidden files and cache
            if filename.startswith('.') or '__pycache__' in str(filepath):
                continue
            
            file_info = {
                'path': rel_path,
                'size': get_file_size(filepath),
                'lines': count_lines(filepath) if filepath.suffix in ['.py', '.md', '.fish', '.toml'] else 0
            }
            
            # Categorize
            if 'tests/' in rel_path:
                dev_files.append({**file_info, 'category': 'tests'})
            elif 'examples/' in rel_path:
                dev_files.append({**file_info, 'category': 'examples'})
            elif 'reports/' in rel_path:
                dev_files.append({**file_info, 'category': 'reports'})
            elif any(pattern in filename for pattern in dev_patterns):
                dev_files.append({**file_info, 'category': 'dev_scripts'})
            elif rel_path.startswith('docs/PHASE'):
                dev_files.append({**file_info, 'category': 'dev_docs'})
            elif filename in ['CONTEXT.md', 'UPGRADE_PLAN.md', 'PYREVM_INSTALL.md', 'DEPLOYMENT_SUMMARY.md'] and 'docs/' in rel_path:
                dev_files.append({**file_info, 'category': 'dev_docs'})
            elif rel_path.endswith(tuple(dev_extensions)) and '/' not in rel_path.replace('./', ''):
                # Root .txt, .json files (test outputs)
                dev_files.append({**file_info, 'category': 'test_output'})
            elif filename in ['.gitignore', '.env', '.env.example', 'pyproject.toml']:
                config_files.append({**file_info, 'category': 'config'})
            elif 'mev_inspect/' in rel_path and filepath.suffix == '.py':
                production_files.append({**file_info, 'category': 'production_code'})
            elif filename in ['README.md', 'README_PRODUCTION.md']:
                production_files.append({**file_info, 'category': 'documentation'})
            elif rel_path.startswith('docs/') and filename in ['PRODUCTION_GUIDE.md', 'DEPLOYMENT_QUICK_START.md']:
                production_files.append({**file_info, 'category': 'production_docs'})
            else:
                # Unknown - default to production
                production_files.append({**file_info, 'category': 'other'})
    
    return {
        'production': production_files,
        'development': dev_files,
        'config': config_files
    }

def print_summary(analysis):
    """Print analysis summary."""
    
    print("="*80)
    print("REPOSITORY ANALYSIS FOR PRODUCTION DEPLOYMENT")
    print("="*80)
    print()
    
    # Production files
    print("📦 PRODUCTION FILES (Deploy these)")
    print("-"*80)
    prod_by_cat = defaultdict(list)
    for f in analysis['production']:
        prod_by_cat[f['category']].append(f)
    
    total_prod_size = 0
    total_prod_lines = 0
    
    for cat in sorted(prod_by_cat.keys()):
        files = prod_by_cat[cat]
        cat_size = sum(f['size'] for f in files)
        cat_lines = sum(f['lines'] for f in files)
        total_prod_size += cat_size
        total_prod_lines += cat_lines
        
        print(f"\n{cat.upper().replace('_', ' ')}:")
        print(f"  Files: {len(files)}")
        print(f"  Size: {cat_size/1024:.1f} KB")
        print(f"  Lines: {cat_lines}")
        
        for f in files:
            if f['lines'] > 0:
                print(f"    • {f['path']} ({f['lines']} lines)")
            else:
                print(f"    • {f['path']}")
    
    print(f"\n📊 Production Total: {len(analysis['production'])} files, {total_prod_size/1024:.1f} KB, {total_prod_lines} lines")
    
    # Development files
    print()
    print("🗑️  DEVELOPMENT FILES (Remove before deploy)")
    print("-"*80)
    dev_by_cat = defaultdict(list)
    for f in analysis['development']:
        dev_by_cat[f['category']].append(f)
    
    total_dev_size = 0
    total_dev_lines = 0
    
    for cat in sorted(dev_by_cat.keys()):
        files = dev_by_cat[cat]
        cat_size = sum(f['size'] for f in files)
        cat_lines = sum(f['lines'] for f in files)
        total_dev_size += cat_size
        total_dev_lines += cat_lines
        
        print(f"\n{cat.upper().replace('_', ' ')}:")
        print(f"  Files: {len(files)}")
        print(f"  Size: {cat_size/1024:.1f} KB")
        print(f"  Lines: {cat_lines}")
        
        # Show first 5 files as examples
        for f in files[:5]:
            if f['lines'] > 0:
                print(f"    • {f['path']} ({f['lines']} lines)")
            else:
                print(f"    • {f['path']}")
        
        if len(files) > 5:
            print(f"    ... and {len(files) - 5} more files")
    
    print(f"\n📊 Development Total: {len(analysis['development'])} files, {total_dev_size/1024:.1f} KB, {total_dev_lines} lines")
    
    # Config files
    print()
    print("⚙️  CONFIGURATION FILES (Keep)")
    print("-"*80)
    for f in analysis['config']:
        print(f"  • {f['path']}")
    print(f"\n📊 Config Total: {len(analysis['config'])} files")
    
    # Summary
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    total_size = total_prod_size + total_dev_size
    reduction = (total_dev_size / total_size * 100) if total_size > 0 else 0
    
    print(f"Current size: {total_size/1024:.1f} KB ({total_prod_lines + total_dev_lines} lines)")
    print(f"Production size: {total_prod_size/1024:.1f} KB ({total_prod_lines} lines)")
    print(f"Development size: {total_dev_size/1024:.1f} KB ({total_dev_lines} lines)")
    print(f"Size reduction: {reduction:.1f}%")
    print()
    print(f"✅ Deploy: {len(analysis['production'])} files")
    print(f"🗑️  Remove: {len(analysis['development'])} files")
    print(f"⚙️  Config: {len(analysis['config'])} files")
    print()
    print("="*80)
    print()
    print("Next steps:")
    print("  1. Run: fish CLEANUP_FOR_PRODUCTION.fish")
    print("  2. Replace README.md with README_PRODUCTION.md")
    print("  3. Build: python3 -m build")
    print("  4. Deploy to production")
    print()

def main():
    """Main function."""
    analysis = analyze_repo()
    print_summary(analysis)
    
    # Save to JSON
    output_file = 'PRODUCTION_ANALYSIS.json'
    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"💾 Detailed analysis saved to: {output_file}")
    print()

if __name__ == '__main__':
    main()
