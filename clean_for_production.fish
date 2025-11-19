#!/usr/bin/env fish
# Clean Project for Production Deployment
# ========================================
# Remove development files and prepare for production

set -g GREEN '\033[0;32m'
set -g RED '\033[0;31m'
set -g YELLOW '\033[1;33m'
set -g BLUE '\033[0;34m'
set -g NC '\033[0m' # No Color

echo "=========================================="
echo "MEV-INSPECT-PYREVM: Production Cleanup"
echo "=========================================="
echo ""

# Safety check
echo -e "{$YELLOW}⚠️  WARNING: This will remove development files!{$NC}"
echo ""
echo "Files to be removed:"
echo "  - tests/ (unit tests)"
echo "  - examples/ (demo scripts)"
echo "  - docs/PHASE*.* (progress reports)"
echo "  - PROJECT_COMPLETE.py (completion report)"
echo "  - .pytest_cache/ (test cache)"
echo "  - __pycache__/ (Python cache)"
echo "  - *.egg-info/ (build artifacts)"
echo "  - reports/ (test reports)"
echo ""

read -P "Continue? [y/N] " -n 1 confirm

if test "$confirm" != "y" -a "$confirm" != "Y"
    echo ""
    echo "Cancelled."
    exit 0
end

echo ""
echo ""
echo "=========================================="
echo "Starting cleanup..."
echo "=========================================="
echo ""

set FILES_REMOVED 0
set DIRS_REMOVED 0
set BYTES_SAVED 0

# Function to remove file/directory with size tracking
function remove_item
    set item $argv[1]
    
    if test -e $item
        # Get size before removing
        if test -d $item
            set size (du -sb $item 2>/dev/null | awk '{print $1}')
            rm -rf $item
            echo -e "{$GREEN}✅ Removed directory: $item ($size bytes){$NC}"
            set -g DIRS_REMOVED (math $DIRS_REMOVED + 1)
        else
            set size (stat -f%z $item 2>/dev/null || stat -c%s $item 2>/dev/null)
            rm -f $item
            echo -e "{$GREEN}✅ Removed file: $item ($size bytes){$NC}"
            set -g FILES_REMOVED (math $FILES_REMOVED + 1)
        end
        set -g BYTES_SAVED (math $BYTES_SAVED + $size)
    else
        echo -e "{$YELLOW}⚠️  Not found: $item{$NC}"
    end
end

# Remove test directories
echo "Removing test files..."
remove_item "tests/"
remove_item ".pytest_cache/"

# Remove example directories
echo ""
echo "Removing example scripts..."
remove_item "examples/"

# Remove development documentation
echo ""
echo "Removing development docs..."
remove_item "docs/PHASE1_SUMMARY.md"
remove_item "docs/PHASE2_PROGRESS.md"
remove_item "docs/PHASE3_PROGRESS.py"
remove_item "docs/PHASE4_COMPLETE.py"
remove_item "PROJECT_COMPLETE.py"

# Remove cache directories
echo ""
echo "Removing cache files..."
remove_item "__pycache__/"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
remove_item ".pytest_cache/"

# Remove build artifacts
echo ""
echo "Removing build artifacts..."
remove_item "*.egg-info/"
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null
remove_item "build/"
remove_item "dist/"
remove_item "reports/"

# Remove Python cache files
echo ""
echo "Removing Python cache files..."
find . -type f -name "*.pyc" -delete 2>/dev/null
find . -type f -name "*.pyo" -delete 2>/dev/null

# Remove temporary files
echo ""
echo "Removing temporary files..."
remove_item "basic.json"
remove_item ".env" # Keep .env.example
find . -type f -name "*.tmp" -delete 2>/dev/null
find . -type f -name "*~" -delete 2>/dev/null

echo ""
echo "=========================================="
echo "Cleanup Summary"
echo "=========================================="
echo -e "Files removed:       {$GREEN}$FILES_REMOVED{$NC}"
echo -e "Directories removed: {$GREEN}$DIRS_REMOVED{$NC}"

# Convert bytes to human readable
set MB (math $BYTES_SAVED / 1024 / 1024)
echo -e "Space saved:         {$GREEN}$MB MB{$NC}"

echo ""
echo "=========================================="
echo "Production Files Remaining"
echo "=========================================="
echo ""

# List production files
echo -e "{$BLUE}Core Package:{$NC}"
ls -lh mev_inspect/*.py 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'

echo ""
echo -e "{$BLUE}Configuration:{$NC}"
test -f README.md && echo "  README.md"
test -f pyproject.toml && echo "  pyproject.toml"
test -f .env.example && echo "  .env.example"
test -f .gitignore && echo "  .gitignore"

echo ""
echo -e "{$BLUE}Documentation:{$NC}"
test -f docs/PYREVM_INSTALL.md && echo "  docs/PYREVM_INSTALL.md"
test -f docs/DEPLOYMENT_SUMMARY.md && echo "  docs/DEPLOYMENT_SUMMARY.md"
test -f PRODUCTION_GUIDE.md && echo "  PRODUCTION_GUIDE.md"

echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo ""
echo "1. Verify files:"
echo "   ls -la"
echo ""
echo "2. Run production tests:"
echo "   ./TEST_PRODUCTION.fish"
echo ""
echo "3. Build package:"
echo "   python3 -m build"
echo ""
echo "4. Test installation:"
echo "   pip install dist/*.whl"
echo ""
echo "5. Deploy to production!"
echo ""
echo -e "{$GREEN}✅ Cleanup complete - Ready for production!{$NC}"
