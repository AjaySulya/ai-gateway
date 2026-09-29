"""Standalone CLI for the GitOps sync job. Runs as a script, a Kubernetes
CronJob, a GitHub Actions step, or anything else that can exec a command.

Usage:
    uv run python -m gateway.gitops.cli sync --config config/acme.yaml
    uv run python -m gateway.gitops.cli validate --config config/acme.yaml
    uv run python -m gateway.gitops.cli drift --config config/acme.yaml
"""

import asyncio
import json
import logging
import os
import sys

import yaml
from pydantic import ValidationError

from gateway.gitops.drift import detect_drift
from gateway.gitops.schema import GatewayConfig
from gateway.gitops.sync import run_sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("gitops")


def _load_config(path: str) -> GatewayConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    try:
        return GatewayConfig(**raw)
    except ValidationError as exc:
        logger.error("config validation failed:\n%s", exc)
        sys.exit(1)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        logger.error("environment variable %s is required but not set", name)
        sys.exit(1)
    return value


# ------------------------------------------------------------------ #
# Commands                                                              #
# ------------------------------------------------------------------ #


def cmd_validate(args) -> None:
    """Validates config against the schema only; doesn't touch the gateway."""
    config = _load_config(args.config)
    orgs = len(config.organizations)
    teams = sum(len(o.teams) for o in config.organizations)
    projects = sum(len(t.projects) for o in config.organizations for t in o.teams)
    logger.info("config valid: %d org(s), %d team(s), %d project(s)", orgs, teams, projects)


def cmd_sync(args) -> None:
    """Validates config, then syncs it to the gateway."""
    config = _load_config(args.config)
    gateway_url = _require_env("GATEWAY_URL")
    token = _require_env("GATEWAY_TOKEN")

    async def _run():
        audit = await run_sync(gateway_url, token, config)
        logger.info("sync complete: %s", audit.summary())
        if args.audit_log:
            audit.write_to_file(args.audit_log)
        if audit.summary()["total"] == 0:
            logger.info("no changes - gateway already matches config")

    asyncio.run(_run())


def cmd_drift(args) -> None:
    """Compares live gateway state to config; exits non-zero if drift is found.
    Useful as a CI gate - run on a schedule to catch manual edits."""
    config = _load_config(args.config)
    gateway_url = _require_env("GATEWAY_URL")
    token = _require_env("GATEWAY_TOKEN")

    async def _run():
        report = await detect_drift(gateway_url, token, config)
        print(json.dumps(report.summary(), indent=2))
        if report.has_drift:
            logger.warning("drift detected - gateway state diverges from config")
            sys.exit(2)
        else:
            logger.info("no drift detected")

    asyncio.run(_run())


# ------------------------------------------------------------------ #
# Argparse                                                              #
# ------------------------------------------------------------------ #


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="AI Gateway GitOps CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("validate", "sync", "drift"):
        p = sub.add_parser(name)
        p.add_argument("--config", required=True, help="path to gateway config YAML")

    sync_p = sub.parsers["sync"] if hasattr(sub, "parsers") else sub.choices["sync"]
    sync_p.add_argument("--audit-log", default=None, help="write audit log to this file path")

    args = parser.parse_args()
    {"validate": cmd_validate, "sync": cmd_sync, "drift": cmd_drift}[args.command](args)


if __name__ == "__main__":
    main()
