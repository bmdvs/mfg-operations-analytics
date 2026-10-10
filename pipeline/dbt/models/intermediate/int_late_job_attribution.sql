-- Time-based attribution of late jobs. One row per late job, stage and cause.
-- Lost days at a stage are the stage days above the median of on-time jobs of the same routing class shipped in the same quarter.
-- A stage's lost days go to a cause when its rule matches; released-late days are allocated first, capped at days late; the remaining
-- days late are split across the matched and unmatched lost days in proportion; unmatched days are not attributable.
{{ late_job_attribution(0.7) }}
