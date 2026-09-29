"""Drift detection: compares what's actually configured in the gateway
against what the versioned config says should be there. Run periodically
(or in CI) to detect and surface manual edits made via the Control API
that diverge from the git-managed config.

The sync job converges state *toward* git, but it never deletes. So drift
report is what gives you visibility into the delta it deliberately leaves
behind: resources that exist in the gateway but not in the config file,
and resources declared in config that somehow don't exist in the gateway
(shouldn't happen post-sync, but worth detecting).
"""

import logging
from dataclasses import dataclass

import httpx

from gateway.gitops.schema import GatewayConfig

logger = logging.getLogger(__name__)


@dataclass
class DriftItem:
    kind: str
    name: str
    issue: str  # "missing_in_gateway" | "missing_in_config"


class DriftReport:
    def __init__(self) -> None:
        self.items: list[DriftItem] = []

    def add(self, kind: str, name: str, issue: str) -> None:
        self.items.append(DriftItem(kind=kind, name=name, issue=issue))
        logger.warning("drift detected: kind=%s name='%s' issue=%s", kind, name, issue)

    @property
    def has_drift(self) -> bool:
        return bool(self.items)

    def summary(self) -> dict:
        return {
            "drift_detected": self.has_drift,
            "total": len(self.items),
            "items": [{"kind": i.kind, "name": i.name, "issue": i.issue} for i in self.items],
        }


async def detect_drift(gateway_url: str, token: str, config: GatewayConfig) -> DriftReport:
    report = DriftReport()

    async with httpx.AsyncClient(
        base_url=gateway_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    ) as http:
        live_orgs_r = await http.get("/organizations")
        live_orgs_r.raise_for_status()
        live_orgs = live_orgs_r.json()

        config_org_slugs = {org.slug for org in config.organizations}
        live_org_slugs = {o["slug"] for o in live_orgs}

        for slug in config_org_slugs - live_org_slugs:
            report.add("organization", slug, "missing_in_gateway")

        for slug in live_org_slugs - config_org_slugs:
            report.add("organization", slug, "missing_in_config")

        for org_cfg in config.organizations:
            live_org = next((o for o in live_orgs if o.get("slug") == org_cfg.slug), None)
            if live_org is None:
                continue

            teams_r = await http.get(f"/organizations/{live_org['id']}/teams")
            teams_r.raise_for_status()
            live_teams = teams_r.json()

            config_team_slugs = {t.slug for t in org_cfg.teams}
            live_team_slugs = {t["slug"] for t in live_teams}

            for slug in config_team_slugs - live_team_slugs:
                report.add("team", f"{org_cfg.slug}/{slug}", "missing_in_gateway")

            for slug in live_team_slugs - config_team_slugs:
                report.add("team", f"{org_cfg.slug}/{slug}", "missing_in_config")

            for team_cfg in org_cfg.teams:
                live_team = next((t for t in live_teams if t.get("slug") == team_cfg.slug), None)
                if live_team is None:
                    continue

                projects_r = await http.get(f"/teams/{live_team['id']}/projects")
                projects_r.raise_for_status()
                live_projects = projects_r.json()

                config_project_slugs = {p.slug for p in team_cfg.projects}
                live_project_slugs = {p["slug"] for p in live_projects}

                for slug in config_project_slugs - live_project_slugs:
                    report.add(
                        "project", f"{org_cfg.slug}/{team_cfg.slug}/{slug}", "missing_in_gateway"
                    )

                for slug in live_project_slugs - config_project_slugs:
                    report.add(
                        "project", f"{org_cfg.slug}/{team_cfg.slug}/{slug}", "missing_in_config"
                    )

    return report
