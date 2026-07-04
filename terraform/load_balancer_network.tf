# Load Balancer Network Foundation — Phase 8b.1
#
# Static global IP and managed wildcard SSL certificate for the
# Global External HTTPS Load Balancer (ADR-0031). These resources
# have no dependencies on the LB, NEG, or backend service resources
# that follow in later sub-phases — they can be provisioned and DNS
# can be pointed at the IP before the LB itself exists.
#
# compute.googleapis.com and networksecurity.googleapis.com were
# enabled via gcloud in Phase 8b.1 and are documented in apis.tf.

# Static IPv4 address for the LB frontend. Reserving this first lets
# DNS be configured (*.slotsense.chandraailabs.com A record → this IP)
# before the full LB is wired, so DNS propagation runs in parallel
# with the remaining sub-phases.
resource "google_compute_global_address" "slotsense_lb_ip" {
  name         = "slotsense-lb-ip"
  project      = var.project_id
  description  = "Static global IP for the SlotSense wildcard subdomain LB (ADR-0031)"
  ip_version   = "IPV4"
  address_type = "EXTERNAL"

  labels = var.default_labels
}

# Managed wildcard SSL certificate for *.slotsense.chandraailabs.com.
# Google provisions and auto-renews this cert; provisioning completes
# only after the A record for the domain points at slotsense-lb-ip
# AND the LB forwarding rule referencing this cert is active.
# Status will remain PROVISIONING until those conditions are met.
resource "google_compute_managed_ssl_certificate" "slotsense_wildcard_cert" {
  name    = "slotsense-wildcard-cert"
  project = var.project_id

  managed {
    domains = ["*.slotsense.chandraailabs.com"]
  }
}
