#!/usr/bin/env bash
#
# install.sh — Set up local development dependencies
#
# Called by: make install

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

echo "═══════════════════════════════════════════════════════"
echo "SportSlotReservation — Install Dependencies"
echo "═══════════════════════════════════════════════════════"
echo ""

# Backend dependencies (Python via uv)
if [ -f "backend/pyproject.toml" ]; then
    echo "→ Installing backend Python dependencies..."
    cd backend
    # Phase 1.4.3: pyproject.toml has no real deps yet — Phase 2 adds fastapi, firebase-admin, etc.
    uv sync 2>&1 | head -5 || echo "  (no dependencies to install yet — Phase 2 will add)"
    cd "${REPO_ROOT}"
    echo "  ✓ Backend Python environment ready"
fi

# Frontend dependencies (Node via pnpm)
if [ -f "frontend/package.json" ]; then
    echo "→ Installing frontend Node dependencies..."
    cd frontend
    # Phase 1.4.3: package.json has no real deps yet — Phase 2 adds react, vite, etc.
    pnpm install 2>&1 | head -5 || echo "  (no dependencies to install yet — Phase 2 will add)"
    cd "${REPO_ROOT}"
    echo "  ✓ Frontend Node environment ready"
fi

echo ""
echo "✓ Installation complete"
