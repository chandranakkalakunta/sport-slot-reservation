# "SlotSense Ops" Dashboard — ADR-0041 D17 (PR-3)
#
# One Terraform-managed Monitoring dashboard so on-call doesn't have
# to reconstruct filters in Metrics Explorer — a single bookmarkable
# URL. This is an ops panel, not the deferred SLO-burn-rate dashboard
# (D14 explicitly defers Monitoring SLO API resources to
# SLO-LOAD-TEST).
#
# Widget approach (lesson a from PR-2: plan/validate don't validate
# Monitoring payload semantics — only apply does, so plain metric
# filters are preferred over MQL wherever the schema supports it
# directly):
#   - voice_turns, agent_text_turns, p95 latency, edge uptime,
#     instance count: xyChart + timeSeriesFilter (plain filter +
#     aggregation) — same filter/aggregation shape already proven in
#     the ADR-0040 alert policies (observability.tf).
#   - 5xx ratio: xyChart + timeSeriesFilterRatio (native
#     numerator/denominator construct) rather than reusing the
#     error_rate policy's MQL string — this keeps the widget entirely
#     in plain-filter form (no MQL parsing risk at apply) while
#     expressing the identical sum(5xx)/sum(all) logic as the proven
#     alert policy.

resource "google_monitoring_dashboard" "slotsense_ops" {
  project = var.project_id

  dashboard_json = jsonencode({
    displayName = "SlotSense Ops"
    mosaicLayout = {
      columns = 48
      tiles = [
        {
          xPos = 0, yPos = 0, width = 24, height = 16
          widget = {
            title = "Voice turns/day"
            xyChart = {
              dataSets = [{
                plotType = "STACKED_BAR"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.voice_turns.name}\" AND resource.type=\"cloud_run_revision\""
                    aggregation = {
                      alignmentPeriod    = "86400s"
                      perSeriesAligner   = "ALIGN_SUM"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos = 24, yPos = 0, width = 24, height = 16
          widget = {
            title = "Agent text turns/day"
            xyChart = {
              dataSets = [{
                plotType = "STACKED_BAR"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.agent_text_turns.name}\" AND resource.type=\"cloud_run_revision\""
                    aggregation = {
                      alignmentPeriod    = "86400s"
                      perSeriesAligner   = "ALIGN_SUM"
                      crossSeriesReducer = "REDUCE_SUM"
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos = 0, yPos = 16, width = 24, height = 16
          widget = {
            title = "5xx error ratio"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilterRatio = {
                    numerator = {
                      filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"sport-slot-api\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.labels.response_code_class=\"5xx\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                      }
                    }
                    denominator = {
                      filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"sport-slot-api\" AND metric.type=\"run.googleapis.com/request_count\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                      }
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos = 24, yPos = 16, width = 24, height = 16
          widget = {
            title = "p95 latency (ms)"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"sport-slot-api\" AND metric.type=\"run.googleapis.com/request_latencies\""
                    aggregation = {
                      alignmentPeriod    = "900s"
                      perSeriesAligner   = "ALIGN_PERCENTILE_95"
                      crossSeriesReducer = "REDUCE_MEAN"
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos = 0, yPos = 32, width = 24, height = 16
          widget = {
            title = "Edge uptime (check passed)"
            xyChart = {
              dataSets = [{
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"uptime_url\" AND metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.labels.check_id=\"${google_monitoring_uptime_check_config.edge_health.uptime_check_id}\""
                    aggregation = {
                      alignmentPeriod    = "300s"
                      perSeriesAligner   = "ALIGN_FRACTION_TRUE"
                      crossSeriesReducer = "REDUCE_MEAN"
                      groupByFields      = ["resource.label.host"]
                    }
                  }
                }
              }]
            }
          }
        },
        {
          xPos = 24, yPos = 32, width = 24, height = 16
          widget = {
            title = "Cloud Run instance count"
            xyChart = {
              dataSets = [{
                plotType = "STACKED_AREA"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"sport-slot-api\" AND metric.type=\"run.googleapis.com/container/instance_count\""
                    aggregation = {
                      alignmentPeriod    = "300s"
                      perSeriesAligner   = "ALIGN_MEAN"
                      crossSeriesReducer = "REDUCE_SUM"
                      groupByFields      = ["metric.label.state"]
                    }
                  }
                }
              }]
            }
          }
        },
      ]
    }
  })
}
