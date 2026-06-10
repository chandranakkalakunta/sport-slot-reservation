#!/usr/bin/env bash
# Verifies that all required tools are installed and at correct versions.
# Returns exit 0 if all checks pass, 1 if any fail.

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0

print_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

print_fail() {
    echo -e "${RED}✗${NC} $1"
    FAILED=$((FAILED + 1))
}

print_info() {
    echo -e "${YELLOW}→${NC} $1"
}

echo "═════════════════════════════════════════════════════════"
echo "SportSlotReservation — Toolchain Verification"
echo "═════════════════════════════════════════════════════════"
echo ""

# Check Homebrew
if command -v brew &> /dev/null; then
    VERSION=$(brew --version 2>/dev/null | sed -n '1p')
    print_pass "Homebrew: $VERSION"
else
    print_fail "Homebrew: NOT INSTALLED"
fi

# Check uv
if command -v uv &> /dev/null; then
    VERSION=$(uv --version)
    print_pass "uv: $VERSION"
else
    print_fail "uv: NOT INSTALLED"
fi

# Check Python 3.12 via uv
if uv python find 3.12 &> /dev/null; then
    PYTHON_PATH=$(uv python find 3.12)
    PYTHON_VERSION=$("$PYTHON_PATH" --version)
    print_pass "Python 3.12 (uv): $PYTHON_VERSION at $PYTHON_PATH"
else
    print_fail "Python 3.12: NOT INSTALLED via uv"
fi

# Check project .venv
if [ -f ".venv/bin/python" ]; then
    VENV_VERSION=$(.venv/bin/python --version)
    print_pass "Project .venv: $VENV_VERSION"
else
    print_fail "Project .venv: NOT CREATED"
fi

# Check Node
if command -v node &> /dev/null; then
    VERSION=$(node --version)
    if [[ "$VERSION" == v22.* ]]; then
        print_pass "Node.js: $VERSION (matches ADR-0001)"
    else
        print_info "Node.js: $VERSION (ADR-0001 expects v22.x)"
    fi
else
    print_fail "Node.js: NOT INSTALLED"
fi

# Check pnpm
if command -v pnpm &> /dev/null; then
    VERSION=$(pnpm --version)
    print_pass "pnpm: $VERSION"
else
    print_fail "pnpm: NOT INSTALLED"
fi

# Check PNPM_HOME
if [ -n "${PNPM_HOME:-}" ] && [ -d "$PNPM_HOME" ]; then
    print_pass "PNPM_HOME: $PNPM_HOME"
else
    print_info "PNPM_HOME: not set in current shell (may need new terminal)"
fi

# Check Firebase CLI
if command -v firebase &> /dev/null; then
    FIREBASE_PATH=$(which firebase)
    VERSION=$(firebase --version 2>&1)
    if [[ "$FIREBASE_PATH" == *"npm-global"* ]]; then
        print_info "Firebase CLI: $VERSION (at $FIREBASE_PATH — should be in pnpm location)"
    else
        print_pass "Firebase CLI: $VERSION at $FIREBASE_PATH"
    fi
else
    print_fail "Firebase CLI: NOT INSTALLED"
fi

# Check Terraform
if command -v terraform &> /dev/null; then
    VERSION=$(terraform --version 2>/dev/null | sed -n '1p')
    print_pass "Terraform: $VERSION"
else
    print_fail "Terraform: NOT INSTALLED"
fi

# Check ShellCheck
if command -v shellcheck &> /dev/null; then
    VERSION=$(shellcheck --version 2>/dev/null | sed -n '1p')
    print_pass "ShellCheck: $VERSION"
else
    print_fail "ShellCheck: NOT INSTALLED"
fi

# Check gcloud
if command -v gcloud &> /dev/null; then
    VERSION=$(gcloud --version 2>/dev/null | sed -n '1p')
    print_pass "gcloud: $VERSION"
else
    print_fail "gcloud: NOT INSTALLED"
fi

# Check Git
if command -v git &> /dev/null; then
    VERSION=$(git --version)
    print_pass "Git: $VERSION"
else
    print_fail "Git: NOT INSTALLED"
fi

# Check gh CLI
if command -v gh &> /dev/null; then
    VERSION=$(gh --version 2>/dev/null | sed -n '1p')
    print_pass "gh CLI: $VERSION"
else
    print_fail "gh CLI: NOT INSTALLED"
fi

echo ""
echo "═════════════════════════════════════════════════════════"
if [ "$FAILED" -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TOOLCHAIN CHECKS PASSED${NC}"
    echo "═════════════════════════════════════════════════════════"
    exit 0
else
    echo -e "${RED}✗ $FAILED TOOLCHAIN CHECK(S) FAILED${NC}"
    echo "═════════════════════════════════════════════════════════"
    exit 1
fi
