# Local Development Setup Runbook

This document describes how to set up your local development
environment for SportSlotReservation.

## Prerequisites

Run the toolchain verification:

```bash
bash scripts/verify_toolchain.sh
```

All 13 checks must pass before proceeding.

## GCP Authentication for Local Development

### One-Time Setup

```bash
# 1. Authenticate gcloud CLI
gcloud auth login
# Follow browser prompts to authenticate

# 2. Set up Application Default Credentials (ADC)
# This is what Firebase Admin SDK and other libraries use
gcloud auth application-default login

# 3. Set the quota project for ADC
gcloud auth application-default set-quota-project sport-slot-dev

# 4. Set the default project for gcloud commands
gcloud config set project sport-slot-dev
```

### Verify Setup

```bash
# Verify accounts
gcloud auth list
# Should show your email as ACTIVE

# Verify ADC works
gcloud auth application-default print-access-token > /dev/null && \
  echo "✓ ADC working"

# Verify project
gcloud config get-value project
# Should print: sport-slot-dev

# Verify Firestore connectivity
gcloud firestore databases describe \
  --database='(default)' \
  --project=sport-slot-dev
# Should describe the database
```

## Python Environment

```bash
cd ~/Documents/Learning/Projects/sport-slot-reservation

# Activate the project virtual environment
source .venv/bin/activate

# Verify Python version
python --version
# Should print: Python 3.12.13

# Deactivate when done
deactivate
```

## Backend Code Uses ADC Automatically

No code changes needed for authentication. The Firebase Admin SDK
detects ADC automatically:

```python
import firebase_admin

# Auto-detects ADC — no path needed
firebase_admin.initialize_app()

from firebase_admin import firestore
db = firestore.client()

# All operations now use your developer identity
# via ADC, governed by your IAM permissions
```

## Frontend Configuration

Firebase web app config is in `infrastructure/firebase-web-config.json`
(not committed). For local development, the React app reads this
during build via Vite environment variables.

See `frontend/README.md` (created in Phase 2) for setup details.

## Troubleshooting

### "Default credentials not found"

Run: `gcloud auth application-default login`

### "Quota project not set"

Run: `gcloud auth application-default set-quota-project sport-slot-dev`

### "Permission denied" errors

Verify your identity has the necessary IAM roles:

```bash
gcloud projects get-iam-policy sport-slot-dev \
  --flatten="bindings[].members" \
  --filter="bindings.members:user:$(gcloud config get-value account)"
```

If you lack roles, contact admin@chandraailabs.com.

### Token Expired

ADC tokens auto-refresh. If issues persist:

```bash
gcloud auth application-default revoke
gcloud auth application-default login
```

## Related Runbooks

- `gcp-project-setup.md` — How the GCP project was created
- `iam-setup.md` — Service accounts and IAM details
