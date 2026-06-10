# SportSlotReservation — Makefile
#
# Discovery layer for common operations.
# Implementation details live in scripts/ per ADR-0003.

.DEFAULT_GOAL := help

# ═══════════════════════════════════════════════════════════════
# Setup & Verification
# ═══════════════════════════════════════════════════════════════

.PHONY: install
install: ## Install all dependencies (backend + frontend)
	@bash scripts/install.sh

.PHONY: verify-env
verify-env: ## Verify all required tools are installed
	@bash scripts/verify_toolchain.sh

# ═══════════════════════════════════════════════════════════════
# Terraform
# ═══════════════════════════════════════════════════════════════

.PHONY: tf-init
tf-init: ## Initialize Terraform with remote state
	@bash scripts/tf-init.sh

.PHONY: tf-plan
tf-plan: ## Show Terraform execution plan
	@bash scripts/tf-plan.sh

.PHONY: tf-apply-dev
tf-apply-dev: ## Apply Terraform changes to DEV (GUARDED)
	@bash scripts/tf-apply-dev.sh

.PHONY: tf-destroy-dev
tf-destroy-dev: ## Destroy DEV Terraform resources (DOUBLE-GUARDED)
	@bash scripts/tf-destroy-dev.sh

.PHONY: tf-fmt
tf-fmt: ## Format Terraform files
	@cd terraform && terraform fmt -recursive

.PHONY: tf-validate
tf-validate: ## Validate Terraform syntax
	@cd terraform && terraform validate

# ═══════════════════════════════════════════════════════════════
# GCP
# ═══════════════════════════════════════════════════════════════

.PHONY: gcp-whoami
gcp-whoami: ## Show current gcloud authentication state
	@bash scripts/gcp-whoami.sh

.PHONY: gcp-set-dev
gcp-set-dev: ## Switch to sport-slot-dev project
	@bash scripts/gcp-set-dev.sh

# ═══════════════════════════════════════════════════════════════
# Help
# ═══════════════════════════════════════════════════════════════

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "SportSlotReservation — Available Commands"
	@echo "═══════════════════════════════════════════════════════════"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Run any command with: make <command>"
	@echo ""
