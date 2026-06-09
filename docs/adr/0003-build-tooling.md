# ADR-0003: Build Tooling Interface

## Status

Accepted — 2026-06-09

## Context

SportBook development involves many recurring operations: installing dependencies, running tests, building Docker images, deploying to GCP environments, running database seeds, tailing logs, and more. Throughout development and operations, these commands will be executed thousands of times by the engineer (and potentially future team members).

Without a unified interface for these tasks:

- Developers must memorize 30+ commands with varying syntax
- Each command may require different arguments and flags
- New contributors cannot easily discover what commands are available
- Easy to forget critical flags or run commands in the wrong order
- No central place to enforce safety checks on dangerous operations

A clean, discoverable interface for common operations is essential for developer velocity and operational safety.

### Requirements

1. **Discoverability:** Single command to list all available operations
2. **Consistency:** Uniform command syntax across all tasks
3. **Simplicity:** Short, memorable commands for daily use
4. **Safety:** Guardrails for destructive or production-affecting operations
5. **Maintainability:** Easy to add new commands as the system grows
6. **Portability:** Must work on Mac (development) and Linux (CI/CD)
7. **Zero installation friction:** Should not require team members to install exotic tools

## Options Considered

### Option A — Makefile (Hybrid with Bash)

GNU Make as the top-level command interface, with complex logic delegated to bash scripts under `scripts/`.

**Architecture:**

```
Makefile (discovery layer):
  install:
      bash scripts/install.sh

  test:
      bash scripts/test.sh

  deploy-dev:
      bash scripts/deploy.sh dev

scripts/install.sh (implementation):
  Complex multi-step logic with error handling,
  verification, and fail-fast principle
```

**Strengths:**

- Make is pre-installed on every Mac and Linux distribution — zero setup friction
- Universally understood by developers across all backgrounds
- Self-documenting via `make help` target
- Composable — targets can depend on other targets
- Industry standard since 1976, used by virtually every open-source project
- Standard pattern in Anthropic, OpenAI, Stripe, GitHub, and most senior engineering shops
- CI/CD systems support Make out of the box
- Bash implementation layer provides full flexibility for complex logic
- Easy to test bash scripts independently

**Weaknesses:**

- Make syntax is quirky (tab-sensitive whitespace)
- Variables work differently than expected by newcomers
- Originally designed for C compilation (we use it differently)
- Error messages can be cryptic

### Option B — Direct Bash Scripts Only

All operations as separate bash scripts in `scripts/` directory, invoked directly.

**Architecture:**

```
scripts/
  install.sh
  test.sh
  deploy.sh
  seed.sh
```

Used as: `bash scripts/install.sh`, `bash scripts/test.sh`, etc.

**Strengths:**

- Most flexible — pure bash with no abstraction
- No syntax surprises or quirks
- Direct mapping to underlying commands
- Easy to debug (just bash)
- What old SportBook used (familiar pattern)

**Weaknesses:**

- Long commands: `bash scripts/test.sh` versus `make test`
- No built-in dependency chain (must manually invoke install before test)
- No central discoverability — must `ls scripts/` to find available commands
- Each script needs duplicated help text
- Easy to forget which scripts exist
- Less polished developer experience

### Option C — Just

Modern command runner written in Rust, inspired by Make but designed for current developer needs.

**Architecture:**

```
justfile:
  install:
      uv sync
      pnpm install

  test:
      pytest tests/ --cov=app

  deploy env:
      bash scripts/deploy.sh {{env}}
```

Used as: `just install`, `just test`, `just deploy dev`.

**Strengths:**

- Cleaner syntax than Make
- Better error messages
- No tab/space sensitivity
- Native argument support
- Built-in `--list` (no help target needed)
- Cross-platform consistent
- Growing adoption in modern Rust/Python projects

**Weaknesses:**

- Not installed by default — requires `brew install just` (Mac) or equivalent
- New team members need to install before contributing
- Newer (released 2017) — less established than Make
- Smaller community and ecosystem
- CI/CD Docker images may need just installed first (extra build step)
- Less Stack Overflow / online documentation than Make

### Option D — Task (Go-based)

YAML-based task runner.

**Architecture:**

```yaml
version: '3'
tasks:
  install:
    cmds:
      - uv sync
      - pnpm install
```

Used as: `task install`, `task test`.

**Strengths:**

- YAML is familiar to most developers
- Built-in dependency management
- Cross-platform consistent

**Weaknesses:**

- Not installed by default — requires separate installation
- YAML can be verbose for simple tasks
- Smaller community than Make
- Less industry presence

## Decision

**Makefile (hybrid pattern) — Option A**

Makefile serves as the discoverable command interface. Complex logic, error handling, and multi-step operations live in bash scripts under `scripts/`. Make targets are typically one-liners that invoke the appropriate bash script.

## Rationale

### Why Hybrid Over Pure Approaches

**Pure Makefile (everything in Make):**
- Make syntax struggles with complex multi-step logic
- Error handling becomes painful with Make's quirks
- Long Makefile becomes unreadable
- Hard to test individual steps in isolation

**Pure Bash (no Make):**
- Loses the discoverability of `make help`
- Longer commands every day (`bash scripts/test.sh` versus `make test`)
- No central command catalog
- This is what Old SportBook used — caused friction

**Hybrid (Make + Bash):**
- Make provides the menu and discoverability
- Bash provides the implementation flexibility
- Best of both worlds without compromise
- Pattern used by every senior engineering shop

### Why Make Over Just

Although `just` has cleaner syntax and better error messages, two factors decided in favour of Make:

1. **Zero installation friction:** Make is pre-installed on every Mac, every Linux distribution, every CI/CD runner. `just` requires explicit installation as a prerequisite step in development setup and CI pipelines. For an early-stage product where reducing setup friction is critical, this matters.

2. **Universality and longevity:** Make has been the industry standard since 1976. Every developer has seen it. Documentation is everywhere. `just` is excellent but newer (2017) — for a project intended to last 5+ years, the proven option is safer.

The `just` advantages (cleaner syntax, better errors) are minor compared to these factors. Make's quirks are well-documented and easy to work around with the hybrid pattern (push complexity into bash).

### Why Bash Scripts Underneath

Bash is the universal shell on Mac and Linux. Every developer can read and modify bash scripts. CI/CD environments execute bash natively. For complex logic, bash provides full programming capability while remaining transparent and debuggable.

Alternative scripting languages (Python scripts for tooling) were considered but rejected because:

- Bash is faster to start (no Python interpreter overhead)
- No virtual environment activation needed for tooling
- Universal availability — every Unix system has bash
- Standard for DevOps tooling across the industry

## Safety Guardrails — Mandatory for Destructive Operations

Daily operations should be fast and frictionless. Destructive or production-affecting operations require explicit safety checks.

### Operations Requiring Confirmation

The following Make targets must prompt for explicit confirmation before proceeding:

```
make deploy-prod         → Type "yes deploy to production"
make deploy-test         → Type "yes deploy to test"
make migrate-prod        → Type "yes migrate production database"
make clean-all           → Type "yes clean all artifacts"
make destroy-test-env    → Type "yes destroy test environment"
make destroy-prod-env    → Type "yes destroy production environment"
                           (followed by typing the project name)
```

### Confirmation Pattern

Each guardrail script follows this pattern:

```
echo "⚠️  You are about to deploy to PRODUCTION"
echo "    Project: sportbook-prod-india"
echo "    Region: asia-south1"
echo ""
echo "Type exactly: 'yes deploy to production'"
read -r CONFIRMATION
[ "$CONFIRMATION" = "yes deploy to production" ] || {
    echo "❌ Confirmation failed. Aborting."
    exit 1
}
echo "Proceeding with deployment..."
```

### Why This Pattern

- **Explicit phrase:** Cannot be triggered accidentally by hitting Enter
- **Cannot be aliased:** Users must consciously type the full phrase
- **Project name in confirmation:** Forces user to verify which project
- **Visible in shell history:** Audit trail of who confirmed what
- **No CI bypass:** CI/CD deployments use different commands that don't require interactive input (they use explicit credentials and authorization)

## Naming Conventions

To keep the Makefile readable and predictable:

```
Format: action-target

Examples:
  install                Install all dependencies
  install-backend        Install only backend
  test                   Run all tests
  test-backend           Run only backend tests
  build                  Build all images
  build-backend          Build only backend image
  deploy-dev             Deploy to DEV
  deploy-test            Deploy to TEST (guarded)
  deploy-prod            Deploy to PROD (guarded)
  seed-dev               Seed DEV database
  logs-dev               Tail DEV logs
  health-dev             Check DEV health
  clean                  Quick cleanup
  clean-all              Deep cleanup (guarded)
```

Composite targets exist for common workflows:

```
ci                       Run lint + test (what CI runs)
release                  Build + push images + deploy
ship-dev                 Test + build + deploy to dev
```

## Standard Sections in Every Makefile

The SportBook Makefile is organized into clear sections:

```
# Setup & Installation
install, verify-env, install-backend, install-frontend

# Development
dev, dev-backend, dev-frontend

# Testing
test, test-backend, test-frontend, test-e2e, coverage

# Code Quality
lint, format, type-check, security-scan

# Building
build, build-backend, build-frontend

# Deployment (DEV / TEST / PROD)
deploy-dev, deploy-test, deploy-prod
rollback-dev, rollback-test, rollback-prod

# Database Operations
seed-dev, seed-test
migrate-dev, migrate-test, migrate-prod

# Operations
logs-dev, logs-test, logs-prod
health-dev, health-test, health-prod
status

# Documentation
docs, docs-serve, docs-build

# Cleanup
clean, clean-all

# Help
help (default target, lists all commands)
```

## Help Target Pattern

Every Makefile target has a comment describing it. The `help` target parses these comments to generate documentation:

```
install: ## Install all dependencies (backend + frontend)
test: ## Run full test suite with coverage
deploy-dev: ## Deploy to DEV environment

help: ## Show this help message
    @grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
        awk 'BEGIN {FS = ":.*?## "}; \
             {printf "  %-20s %s\n", $$1, $$2}'
```

Result of `make help`:

```
$ make help
  install              Install all dependencies (backend + frontend)
  test                 Run full test suite with coverage
  deploy-dev           Deploy to DEV environment
  ...
```

This makes the Makefile self-documenting — adding a new command means adding a new line, and it automatically appears in `make help`.

## Consequences

### Positive

- **Single discoverable interface** for all operations (`make help`)
- **Short, memorable commands** for daily use
- **Zero installation friction** for new contributors
- **Safety guardrails** prevent accidental destructive operations
- **Hybrid pattern** keeps Makefile clean while allowing complex logic
- **Self-documenting** — new commands automatically appear in help
- **CI/CD friendly** — same commands work in pipelines
- **Industry-standard pattern** — recognizable to all developers

### Negative

- **Make syntax quirks** (tab-sensitive, variable scoping) must be learned
- **Cryptic error messages** when Make syntax is wrong
- **Hybrid pattern adds indirection** (Make target → bash script)
- **Make's age** means it has accumulated quirks over decades

### Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Developer accidentally runs `make deploy-prod` | High | Guarded with explicit confirmation phrase |
| Tab vs space confusion breaks Makefile | Medium | Editor configured to preserve tabs; CI lints Makefile |
| Bash script fails silently | Medium | `set -euo pipefail` mandatory in every script |
| New developer cannot find a command | Low | `make help` shows all commands, README documents |

## Alternatives Rejected

### Just

**Why rejected:** Requires installation as prerequisite. For a project where reducing onboarding friction matters, Make's pre-installed availability wins. The syntax improvements of `just` are not significant enough to justify the additional setup step.

### Task (Go-based)

**Why rejected:** Same installation friction as `just` plus less established. No clear advantage over the Make+Bash hybrid for our use case.

### Pure Bash Scripts

**Why rejected:** Used by Old SportBook and caused friction. Long commands every day, no discoverability, no central catalog. The discoverability of `make help` alone justifies the small overhead of Make.

### Python Scripts for Tooling

**Why rejected:** Adds virtual environment activation overhead, slower startup, dependency on Python toolchain working. Bash is universally available and faster for tooling scripts.

## References

- GNU Make manual: https://www.gnu.org/software/make/manual/
- The Hybrid Makefile pattern: well-documented in many open-source projects
- Anthropic, Stripe, GitHub: all use Makefile + bash hybrid for their public repositories
- ShellCheck (for bash script linting): https://www.shellcheck.net/
- Standard pattern documented in Google's engineering practices

## Related ADRs

- ADR-0001: Tech Stack & Software Versions (defines Python and Node toolchain that Makefile invokes)
- ADR-0002: Database Technology (Make targets will include database operations)
- Future ADR: CI/CD Pipeline Design (will reference Makefile targets)
