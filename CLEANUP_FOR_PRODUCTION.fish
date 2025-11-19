#!/usr/bin/env fish
# ============================================================================
# Production Cleanup Script
# ============================================================================
# Removes all development files, keeping only production-ready code
# Run this before deploying to production

set -g RED '\033[0;31m'
set -g GREEN '\033[0;32m'
set -g YELLOW '\033[1;33m'
set -g BLUE '\033[0;34m'
set -g NC '\033[0m'

echo -e "{$BLUE}============================================================================{$NC}"
echo -e "{$BLUE}MEV-INSPECT-PYREVM: Production Cleanup{$NC}"
echo -e "{$BLUE}============================================================================{$NC}"
echo ""

# Safety check
echo -e "{$YELLOW}⚠️  WARNING: This will delete development files!{$NC}"
echo ""
echo "Files/directories to be removed:"
echo "  • tests/ - All unit tests"
echo "  • examples/ - All demo scripts"
echo "  • docs/PHASE*.* - Development phase documentation"
echo "  • docs/CONTEXT.md - Development context"
echo "  • docs/UPGRADE_PLAN.md - Development planning"
echo "  • docs/PYREVM_INSTALL.md - Installation notes"
echo "  • docs/DEPLOYMENT_SUMMARY.md - Deployment draft"
echo "  • reports/ - Test reports"
echo "  • *.txt - Test output files"
echo "  • check_*.py - Debugging scripts"
echo "  • quick_test.py - Quick test script"
echo "  • analyze_deployment.py - Analysis script"
echo "  • TEST_PRODUCTION.fish - Test suite"
echo "  • clean_for_production.fish - Old cleanup script"
echo "  • deployment_analysis.json - Analysis output"
echo "  • __pycache__/ directories"
echo "  • .pytest_cache/"
echo ""

echo -e "{$YELLOW}Type 'yes' to continue or anything else to cancel:{$NC}"
read -l confirm

if test "$confirm" != "yes"
    echo -e "{$RED}❌ Cancelled{$NC}"
    exit 1
end

echo ""
echo -e "{$GREEN}Starting cleanup...{$NC}"
echo ""

set removed_count 0
set space_saved 0

# Function to remove and track
function remove_item
    set item $argv[1]
    if test -e $item
        set size (du -sb $item 2>/dev/null | awk '{print $1}')
        rm -rf $item
        if test $status -eq 0
            echo -e "  {$GREEN}✓{$NC} Removed: $item"
            set -g removed_count (math $removed_count + 1)
            set -g space_saved (math $space_saved + $size)
        else
            echo -e "  {$RED}✗{$NC} Failed to remove: $item"
        end
    else
        echo -e "  {$YELLOW}⊘{$NC} Not found: $item"
    end
end

# Remove directories
echo -e "{$BLUE}Removing directories...{$NC}"
remove_item "tests"
remove_item "examples"
remove_item "reports"
remove_item ".pytest_cache"

# Remove phase documentation
echo ""
echo -e "{$BLUE}Removing development documentation...{$NC}"
remove_item "docs/PHASE1_COMPLETE.md"
remove_item "docs/PHASE1_QUICKREF.md"
remove_item "docs/PHASE1_SUMMARY.md"
remove_item "docs/PHASE2_COMPLETE.py"
remove_item "docs/PHASE2_PROGRESS.md"
remove_item "docs/PHASE2_SUMMARY.md"
remove_item "docs/PHASE3_COMPLETE.py"
remove_item "docs/PHASE4_COMPLETE.py"
remove_item "docs/PRODUCTION_GUIDE.py"
remove_item "docs/PROJECT_COMPLETE.py"
remove_item "docs/CONTEXT.md"
remove_item "docs/UPGRADE_PLAN.md"
remove_item "docs/PYREVM_INSTALL.md"
remove_item "docs/DEPLOYMENT_SUMMARY.md"

# Remove test/debug files
echo ""
echo -e "{$BLUE}Removing test and debug files...{$NC}"
remove_item "test_output.txt"
remove_item "test_output2.txt"
remove_item "test_output_fixed.txt"
remove_item "test_final.txt"
remove_item "final_test.txt"
remove_item "full_test_result.txt"
remove_item "api_check.txt"
remove_item "pyrevm_check.txt"
remove_item "pyrevm_api.txt"
remove_item "check_pyrevm.py"
remove_item "check_api.py"
remove_item "quick_test.py"
remove_item "analyze_deployment.py"
remove_item "deployment_analysis.json"
remove_item "TEST_PRODUCTION.fish"
remove_item "clean_for_production.fish"
remove_item "SUMMARY.txt"

# Remove __pycache__ directories
echo ""
echo -e "{$BLUE}Removing cache directories...{$NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
echo -e "  {$GREEN}✓{$NC} Removed all __pycache__ directories"

# Remove .egg-info
echo ""
echo -e "{$BLUE}Removing build artifacts...{$NC}"
remove_item "mev_inspect_pyrevm.egg-info"
remove_item "build"
remove_item "dist"

echo ""
echo -e "{$BLUE}============================================================================{$NC}"
echo -e "{$GREEN}Cleanup Complete!{$NC}"
echo -e "{$BLUE}============================================================================{$NC}"
echo ""
echo "Statistics:"
echo -e "  Files/directories removed: {$GREEN}$removed_count{$NC}"
set space_mb (math $space_saved / 1024 / 1024)
echo -e "  Space saved: {$GREEN}$space_mb MB{$NC}"
echo ""
echo "Remaining production files:"
echo "  • mev_inspect/ - Core production code"
echo "  • docs/PRODUCTION_GUIDE.md - Production documentation"
echo "  • docs/DEPLOYMENT_QUICK_START.md - Quick start guide"
echo "  • README.md - User documentation"
echo "  • pyproject.toml - Package configuration"
echo "  • .gitignore"
echo "  • .env.example"
echo ""
echo -e "{$GREEN}✅ Ready for production deployment!{$NC}"
echo ""
echo "Next steps:"
echo "  1. Review README.md"
echo "  2. Build package: python3 -m build"
echo "  3. Test installation: pip install dist/*.whl"
echo "  4. Deploy to production"
echo ""
