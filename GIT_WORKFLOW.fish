#!/usr/bin/env fish
# ============================================================================
# Git Workflow: Preserve Dev Files in 'dev' Branch
# ============================================================================

set -g GREEN '\033[0;32m'
set -g YELLOW '\033[1;33m'
set -g BLUE '\033[0;34m'
set -g NC '\033[0m'

echo -e "{$BLUE}============================================================================{$NC}"
echo -e "{$BLUE}Git Workflow: Creating 'dev' branch with all development files{$NC}"
echo -e "{$BLUE}============================================================================{$NC}"
echo ""

# Step 1: Commit current state to main
echo -e "{$GREEN}Step 1: Commit all current files to main branch{$NC}"
echo "Commands:"
echo "  git add ."
echo "  git commit -m 'Complete: All 4 phases + tests + examples + docs'"
echo "  git push origin main"
echo ""

# Step 2: Create dev branch
echo -e "{$GREEN}Step 2: Create 'dev' branch from current state{$NC}"
echo "Commands:"
echo "  git checkout -b dev"
echo "  git push -u origin dev"
echo ""
echo "✅ Branch 'dev' will contain:"
echo "   • All tests/"
echo "   • All examples/"
echo "   • All development docs"
echo "   • Test scripts"
echo "   • Phase documentation"
echo ""

# Step 3: Switch back to main
echo -e "{$GREEN}Step 3: Switch back to main and cleanup{$NC}"
echo "Commands:"
echo "  git checkout main"
echo ""

# Step 4: Cleanup main branch
echo -e "{$GREEN}Step 4: Cleanup production (main branch){$NC}"
echo "Commands:"
echo "  fish CLEANUP_FOR_PRODUCTION.fish"
echo "  mv README.md README_OLD.md"
echo "  mv README_PRODUCTION.md README.md"
echo ""

# Step 5: Commit production version
echo -e "{$GREEN}Step 5: Commit production-ready main branch{$NC}"
echo "Commands:"
echo "  git add ."
echo "  git commit -m 'Production release v0.1.0 - cleaned for deployment'"
echo "  git tag v0.1.0"
echo "  git push origin main"
echo "  git push origin v0.1.0"
echo ""

# Summary
echo -e "{$BLUE}============================================================================{$NC}"
echo -e "{$YELLOW}After this workflow:{$NC}"
echo ""
echo -e "{$GREEN}main branch{$NC} (production):"
echo "  • Clean production code only"
echo "  • No tests, no examples"
echo "  • Ready for deployment"
echo "  • Tagged as v0.1.0"
echo ""
echo -e "{$BLUE}dev branch{$NC} (development):"
echo "  • All tests preserved"
echo "  • All examples preserved"
echo "  • All development docs preserved"
echo "  • Full development environment"
echo ""
echo -e "{$YELLOW}To switch between branches:{$NC}"
echo "  git checkout dev    # Work on features"
echo "  git checkout main   # Production code"
echo ""
echo -e "{$BLUE}============================================================================{$NC}"
