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
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# Google Beta provider for newer features (Firebase, etc.)
provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}
