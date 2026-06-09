# ADR-0003: Build Tooling Interface

**Status:** Accepted  
**Date:** 2026-06-09  
**Deciders:** Chandra Nakkalakunta

## Context

The project spans three separate runtimes — Python backend, TypeScript
frontend, and Terraform infrastructure — each with its own native
toolchain (`pip`/`pytest`, `npm`/`vite`, `terraform`). Developers and
CI pipelines need a single, stable entry point to run common tasks
(install, lint, test, build, deploy) without memorising the native
commands for each layer.

### Alternatives considered

| Option | Ruled out because |
|--------|------------------|
| Pure bash scripts | No discoverability (`make help`); harder to compose sub-tasks; no dependency tracking between targets |
| Just (casey/just) | Non-standard; requires separate install step; less universal than make on Linux/macOS CI images |
| Taskfile (go-task) | Same discoverability benefit as make but adds a Go binary dependency; team familiarity lower |
| npm scripts (package.json) | Backend/Terraform tasks don't belong in a Node file; coupling front-end tooling to all layers is wrong |
| Pure Python (invoke/nox) | Requires Python env to be active before you can run tooling — chicken-and-egg for bootstrap steps |

## Decision

Use a **Makefile + bash hybrid**:

- `Makefile` at repo root is the **single developer entry point** for
  all common tasks. Every target has a one-line `## comment` for
  `make help`.
- `scripts/` contains bash scripts (with `set -euo pipefail`) for
  operations too long or too complex to inline in a Makefile recipe.
  Makefile targets call these scripts; scripts are not called directly.
- Native toolchain commands (`pip`, `npm`, `terraform`) are **never
  invoked directly** in documentation or CI — always via `make <target>`.

### Standard Makefile target taxonomy

| Category | Targets |
|----------|---------|
| Bootstrap | `make install`, `make install-dev` |
| Code quality | `make lint`, `make format`, `make typecheck` |
| Testing | `make test`, `make test-unit`, `make test-integration`, `make test-e2e` |
| Build | `make build-backend`, `make build-frontend` |
| Infrastructure | `make tf-init`, `make tf-plan`, `make tf-apply` |
| Local dev | `make dev-backend`, `make dev-frontend`, `make dev` |
| CI helpers | `make ci-lint`, `make ci-test`, `make ci-build` |
| Operations | `make deploy`, `make rollback`, `make smoke-test` |

### Script conventions
- All scripts in `scripts/` must start with `#!/usr/bin/env bash` and
  `set -euo pipefail`.
- Scripts accept environment variables for configuration; never hardcode
  project IDs, regions, or service names.
- All scripts must be idempotent — safe to re-run without side effects.
- `chmod +x` all scripts; they are executable files, not sourced libs.

## Consequences

**Positive**
- Single `make help` gives a full task inventory — no documentation needed.
- CI YAML becomes thin (`make ci-test`) — details stay in the Makefile,
  not scattered across workflow files.
- Bash scripts in `scripts/` are version-controlled and code-reviewed
  like application code.
- Works on any Linux/macOS machine with no additional tooling beyond make and bash.

**Negative / risks**
- GNU Make syntax is quirky (tabs not spaces, variable scoping); onboarding
  cost for contributors unfamiliar with make.
- Makefile is not a task runner — complex dependency graphs or parallel
  execution require care.

**Mitigations**
- Keep Makefile targets shallow and delegate complexity to scripts.
- Add `.PHONY` declarations for all non-file targets to avoid stale-target surprises.
- `make help` auto-generates from `## comment` annotations — keep those current.
