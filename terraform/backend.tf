terraform {
  backend "gcs" {
    bucket = "sport-slot-dev-tfstate"
    prefix = "terraform/state"
  }
}
