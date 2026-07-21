terraform {
  required_version = "~> 1.15"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
  }
}

# Standard Google provider for stable APIs
# user_project_override + billing_project: required for user ADC against
# APIs like billingbudgets.googleapis.com that demand a quota project
# (otherwise requests hit Google's default consumer 764086051850 → 403).
provider "google" {
  project               = var.project_id
  region                = var.region
  zone                  = var.zone
  user_project_override = true
  billing_project       = var.project_id
}

# Google Beta provider for newer features (Firebase, etc.)
provider "google-beta" {
  project               = var.project_id
  region                = var.region
  zone                  = var.zone
  user_project_override = true
  billing_project       = var.project_id
}
