"""Phase 9 - GitOps config sync.

- schema.py     Pydantic models for YAML config files (GatewayConfig,
                OrgConfig, TeamConfig, ProjectConfig, etc.) - validated
                before any sync job call touches the gateway
- sync.py       Idempotent sync engine: reads GatewayConfig, drives the
                Control API to converge toward it. Never deletes (see
                sync.py's module docstring for why)
- audit.py      Records every create/update the sync job makes, with a
                timestamp; written to stdout as structured JSON and
                optionally to a file
- drift.py      Compares live gateway state to config; surfaces resources
                that exist in the gateway but not in the config (manual
                edits) and vice versa
- cli.py        Standalone CLI: `validate`, `sync`, `drift` subcommands;
                runs as a script, a Kubernetes CronJob, a GitHub Actions
                step, etc.

Config files live under config/ (see config/example/acme.yaml for the
full shape). CI validates them on every push that touches config/**
(.github/workflows/validate-config.yml).

RBAC on Control API endpoints (a read-only role below org_admin/team_lead)
is noted as the remaining gap, not built here - it requires changing every
Depends(require_*) in the API routers and a new membership table column,
which is a Phase 9 follow-on rather than the core sync plumbing.
"""
