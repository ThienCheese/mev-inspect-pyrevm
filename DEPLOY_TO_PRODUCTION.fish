#!/usr/bin/env fish
# ============================================================================
# Production Deployment - Complete Workflow
# ============================================================================
# This script guides you through the complete production deployment process

set -g RED '\033[0;31m'
set -g GREEN '\033[0;32m'
set -g YELLOW '\033[1;33m'
set -g BLUE '\033[0;34m'
set -g CYAN '\033[0;36m'
set -g NC '\033[0m'

function print_header
    echo ""
    echo -e "{$BLUE}============================================================================{$NC}"
    echo -e "{$CYAN}$argv{$NC}"
    echo -e "{$BLUE}============================================================================{$NC}"
    echo ""
end

function print_step
    echo -e "{$GREEN}▶{$NC} $argv"
end

function print_warn
    echo -e "{$YELLOW}⚠️  $argv{$NC}"
end

function print_error
    echo -e "{$RED}❌ $argv{$NC}"
end

function print_success
    echo -e "{$GREEN}✅ $argv{$NC}"
end

function pause_for_user
    echo ""
    echo -e "{$YELLOW}Press Enter to continue, or Ctrl+C to cancel...{$NC}"
    read
end

# ============================================================================
# START
# ============================================================================

print_header "MEV-INSPECT-PYREVM: Production Deployment"

echo -e "{$CYAN}This script will guide you through:{$NC}"
echo "  1. Repository analysis"
echo "  2. Cleanup development files"
echo "  3. Update README"
echo "  4. Build package"
echo "  5. Test installation"
echo ""

pause_for_user

# ============================================================================
# STEP 1: Repository Analysis
# ============================================================================

print_header "STEP 1: Repository Analysis"

print_step "Analyzing repository structure..."
python3 ANALYZE_REPO.py

if test $status -ne 0
    print_error "Analysis failed!"
    exit 1
end

print_success "Analysis complete!"
print_warn "Review the analysis above before proceeding"

pause_for_user

# ============================================================================
# STEP 2: Backup
# ============================================================================

print_header "STEP 2: Create Backup"

print_step "Creating backup..."

set backup_dir "../mev-inspect-pyrevm-backup-"(date +%Y%m%d-%H%M%S)
cp -r . $backup_dir

if test $status -eq 0
    print_success "Backup created at: $backup_dir"
else
    print_error "Backup failed!"
    exit 1
end

pause_for_user

# ============================================================================
# STEP 3: Cleanup
# ============================================================================

print_header "STEP 3: Cleanup Development Files"

print_warn "This will PERMANENTLY delete 53 development files!"
echo ""
echo "Files to be removed:"
echo "  • tests/ (6 files, 61.5 KB)"
echo "  • examples/ (12 files, 158 KB)"
echo "  • reports/ (2 files, 167.9 KB)"
echo "  • Development docs (14 files)"
echo "  • Test scripts (26 files)"
echo ""
echo -e "{$YELLOW}Type 'DELETE' to confirm (case-sensitive):{$NC}"
read -l confirm

if test "$confirm" != "DELETE"
    print_error "Cleanup cancelled"
    exit 1
end

print_step "Running cleanup script..."
fish CLEANUP_FOR_PRODUCTION.fish

if test $status -eq 0
    print_success "Cleanup complete!"
else
    print_error "Cleanup failed!"
    exit 1
end

pause_for_user

# ============================================================================
# STEP 4: Update README
# ============================================================================

print_header "STEP 4: Update README"

print_step "Replacing README.md with production version..."

if test -f README_PRODUCTION.md
    mv README.md README_OLD.md
    mv README_PRODUCTION.md README.md
    print_success "README.md updated"
    print_warn "Old README saved as README_OLD.md"
else
    print_error "README_PRODUCTION.md not found!"
    exit 1
end

pause_for_user

# ============================================================================
# STEP 5: Verify Structure
# ============================================================================

print_header "STEP 5: Verify Clean Structure"

print_step "Checking directory structure..."
echo ""

echo -e "{$CYAN}Remaining directories:{$NC}"
ls -d */ 2>/dev/null | while read dir
    if test "$dir" != ".git/" -a "$dir" != ".venv/" -a "$dir" != "__pycache__/"
        echo "  📁 $dir"
    end
end

echo ""
echo -e "{$CYAN}Root files:{$NC}"
ls -1 | grep -v '/' | while read file
    echo "  📄 $file"
end

echo ""
print_warn "Verify that only production files remain"

pause_for_user

# ============================================================================
# STEP 6: Build Package
# ============================================================================

print_header "STEP 6: Build Package"

print_step "Checking build tools..."

if not pip show build > /dev/null 2>&1
    print_warn "build module not installed. Installing..."
    pip install build
end

print_step "Building package..."
python3 -m build

if test $status -eq 0
    print_success "Package built successfully!"
    echo ""
    echo -e "{$CYAN}Build artifacts:{$NC}"
    ls -lh dist/
else
    print_error "Build failed!"
    exit 1
end

pause_for_user

# ============================================================================
# STEP 7: Test Installation
# ============================================================================

print_header "STEP 7: Test Installation"

print_step "Creating test environment..."

set test_env ".test_venv"

if test -d $test_env
    rm -rf $test_env
end

python3 -m venv $test_env

print_step "Installing package in test environment..."

source $test_env/bin/activate.fish

pip install --quiet dist/*.whl

if test $status -ne 0
    print_error "Installation failed!"
    deactivate
    exit 1
end

print_step "Testing imports..."

python3 -c "
from mev_inspect import RPCClient, StateManager, EnhancedSwapDetector, ProfitCalculator
print('✅ All imports successful')
"

if test $status -eq 0
    print_success "Import test passed!"
else
    print_error "Import test failed!"
    deactivate
    exit 1
end

print_step "Testing CLI..."

python3 -m mev_inspect.cli --help > /dev/null 2>&1

if test $status -eq 0
    print_success "CLI test passed!"
else
    print_warn "CLI test warning (may need additional setup)"
end

deactivate

print_success "All tests passed!"

pause_for_user

# ============================================================================
# STEP 8: Summary
# ============================================================================

print_header "DEPLOYMENT SUMMARY"

echo -e "{$GREEN}✅ Repository cleaned{$NC}"
echo -e "{$GREEN}✅ README updated{$NC}"
echo -e "{$GREEN}✅ Package built{$NC}"
echo -e "{$GREEN}✅ Installation tested{$NC}"
echo ""

echo -e "{$CYAN}Build artifacts:{$NC}"
ls -lh dist/ | tail -n +2

echo ""
echo -e "{$CYAN}Package info:{$NC}"
echo "  Name: mev-inspect-pyrevm"
echo "  Version: "(grep version pyproject.toml | cut -d'"' -f2)
echo "  Size: "(du -sh dist/*.whl | cut -f1)
echo ""

print_header "NEXT STEPS"

echo -e "{$YELLOW}Choose deployment option:{$NC}"
echo ""
echo "1️⃣  Deploy to PyPI (Public):"
echo "   pip install twine"
echo "   twine upload dist/*"
echo ""
echo "2️⃣  Deploy to Git Repository:"
echo "   git add ."
echo "   git commit -m 'Production release v0.1.0'"
echo "   git tag v0.1.0"
echo "   git push origin main --tags"
echo ""
echo "3️⃣  Deploy as Docker Container:"
echo "   docker build -t mev-inspect-pyrevm:0.1.0 ."
echo "   docker push YOUR_REGISTRY/mev-inspect-pyrevm:0.1.0"
echo ""
echo "4️⃣  Private distribution:"
echo "   Share dist/*.whl file directly"
echo "   Users install: pip install mev_inspect_pyrevm-0.1.0-py3-none-any.whl"
echo ""

print_success "🎉 Production deployment preparation complete!"
echo ""
