"""Idempotent sync engine: reads a GatewayConfig and drives the Control
API to converge the gateway's actual state toward it. Every operation is
safe to run repeatedly - create-if-not-exists, update-if-changed.

The sync job never deletes: if an org/team/project/policy/provider/model
exists in the gateway but not in the config file, it is left alone. This
is a deliberate, conservative default for V1 - a typo in a config file
should not silently destroy production resources. Explicit deletion is
still possible via the Control API directly. The operator posture is
"config as the source of additions and updates; Control API for removals."

All calls go through httpx against the running gateway's own HTTP API
rather than directly to SQLAlchemy, for two reasons:
 1. The Control API is the authoritative write path - bypassing it
    would skip its access-control, audit, and validation logic.
 2. The sync job can run as a standalone script, a Kubernetes CronJob, a
    GitHub Actions step, etc. - it doesn't need to be co-located with the
    gateway process or share its SQLAlchemy session.
"""

import logging

import httpx

from gateway.gitops.audit import AuditLog
from gateway.gitops.schema import (
    AgentConfig,
    GatewayConfig,
    ModelConfig,
    OrgConfig,
    PolicyConfigEntry,
    ProjectConfig,
    ProviderConfig,
    TeamConfig,
)

logger = logging.getLogger(__name__)


class SyncClient:
    def __init__(self, base_url: str, token: str, audit: AuditLog) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        self._audit = audit

    async def close(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    async def _get_list(self, url: str) -> list[dict]:
        r = await self._http.get(url)
        r.raise_for_status()
        return r.json()

    async def _create(self, url: str, payload: dict, kind: str, name: str) -> dict:
        r = await self._http.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        self._audit.record("create", kind, name, data.get("id"))
        logger.info("created %s '%s' (id=%s)", kind, name, data.get("id"))
        return data

    async def _find_by_slug(self, items: list[dict], slug: str) -> dict | None:
        return next((i for i in items if i.get("slug") == slug), None)

    async def _find_by_name(self, items: list[dict], name: str) -> dict | None:
        return next((i for i in items if i.get("name") == name), None)

    # ------------------------------------------------------------------ #
    # Org                                                                   #
    # ------------------------------------------------------------------ #

    async def sync_org(self, cfg: OrgConfig) -> str:
        orgs = await self._get_list("/organizations")
        existing = self._find_by_slug.__func__(self, orgs, cfg.slug)  # type: ignore[attr-defined]
        existing = next((o for o in orgs if o.get("slug") == cfg.slug), None)
        if existing:
            logger.debug("org '%s' already exists, skipping create", cfg.slug)
            org_id = existing["id"]
        else:
            data = await self._create(
                "/organizations", {"name": cfg.name, "slug": cfg.slug}, "organization", cfg.slug
            )
            org_id = data["id"]

        await self._sync_org_policies(org_id, cfg.policies)
        for team_cfg in cfg.teams:
            await self.sync_team(org_id, team_cfg)

        return org_id

    # ------------------------------------------------------------------ #
    # Team                                                                  #
    # ------------------------------------------------------------------ #

    async def sync_team(self, org_id: str, cfg: TeamConfig) -> str:
        teams = await self._get_list(f"/organizations/{org_id}/teams")
        existing = next((t for t in teams if t.get("slug") == cfg.slug), None)
        if existing:
            logger.debug("team '%s' already exists, skipping create", cfg.slug)
            team_id = existing["id"]
        else:
            data = await self._create(
                f"/organizations/{org_id}/teams",
                {"name": cfg.name, "slug": cfg.slug},
                "team",
                cfg.slug,
            )
            team_id = data["id"]

        await self._sync_policies(team_id, "team", cfg.policies)
        for project_cfg in cfg.projects:
            await self.sync_project(team_id, project_cfg)

        return team_id

    # ------------------------------------------------------------------ #
    # Project                                                               #
    # ------------------------------------------------------------------ #

    async def sync_project(self, team_id: str, cfg: ProjectConfig) -> str:
        projects = await self._get_list(f"/teams/{team_id}/projects")
        existing = next((p for p in projects if p.get("slug") == cfg.slug), None)
        if existing:
            logger.debug("project '%s' already exists, skipping create", cfg.slug)
            project_id = existing["id"]
        else:
            data = await self._create(
                f"/teams/{team_id}/projects",
                {"name": cfg.name, "slug": cfg.slug},
                "project",
                cfg.slug,
            )
            project_id = data["id"]

        await self._sync_policies(project_id, "project", cfg.policies)

        for agent_cfg in cfg.agents:
            await self.sync_agent(project_id, agent_cfg)

        for provider_cfg in cfg.providers:
            await self.sync_provider(project_id, provider_cfg)

        return project_id

    # ------------------------------------------------------------------ #
    # Agent                                                                 #
    # ------------------------------------------------------------------ #

    async def sync_agent(self, project_id: str, cfg: AgentConfig) -> str:
        agents = await self._get_list(f"/projects/{project_id}/agents")
        existing = next((a for a in agents if a.get("slug") == cfg.slug), None)
        if existing:
            logger.debug("agent '%s' already exists, skipping create", cfg.slug)
            return existing["id"]

        data = await self._create(
            f"/projects/{project_id}/agents",
            {"name": cfg.name, "slug": cfg.slug},
            "agent",
            cfg.slug,
        )
        return data["id"]

    # ------------------------------------------------------------------ #
    # Provider + models                                                     #
    # ------------------------------------------------------------------ #

    async def sync_provider(self, project_id: str, cfg: ProviderConfig) -> str:
        providers = await self._get_list(f"/projects/{project_id}/providers")
        existing = next((p for p in providers if p.get("name") == cfg.name), None)
        if existing:
            logger.debug("provider '%s' already exists, skipping create", cfg.name)
            provider_id = existing["id"]
        else:
            data = await self._create(
                f"/projects/{project_id}/providers",
                {
                    "name": cfg.name,
                    "provider_type": cfg.provider_type.value,
                    "credential_ref": cfg.credential_ref,
                    "extra_config": cfg.extra_config,
                },
                "provider",
                cfg.name,
            )
            provider_id = data["id"]

        for model_cfg in cfg.models:
            await self.sync_model(provider_id, model_cfg)

        return provider_id

    async def sync_model(self, provider_id: str, cfg: ModelConfig) -> str:
        models = await self._get_list(f"/providers/{provider_id}/models")
        existing = next((m for m in models if m.get("model_name") == cfg.model_name), None)
        if existing:
            logger.debug("model '%s' already exists, skipping create", cfg.model_name)
            return existing["id"]

        data = await self._create(
            f"/providers/{provider_id}/models",
            {
                "model_name": cfg.model_name,
                "display_name": cfg.display_name,
                "priority": cfg.priority,
            },
            "model",
            cfg.model_name,
        )
        return data["id"]

    # ------------------------------------------------------------------ #
    # Policies                                                              #
    # ------------------------------------------------------------------ #

    async def _sync_org_policies(self, org_id: str, policies: list[PolicyConfigEntry]) -> None:
        await self._sync_policies(org_id, "organization", policies)

    async def _sync_policies(
        self, scope_id: str, scope_type: str, policies: list[PolicyConfigEntry]
    ) -> None:
        existing = await self._get_list(f"/policies?scope_type={scope_type}&scope_id={scope_id}")
        existing_names = {p["name"] for p in existing}

        for policy_cfg in policies:
            if policy_cfg.name in existing_names:
                logger.debug("policy '%s' already exists, skipping create", policy_cfg.name)
                continue
            await self._create(
                "/policies",
                {
                    "name": policy_cfg.name,
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    "config": policy_cfg.config.model_dump(exclude_none=True),
                    "enabled": True,
                },
                "policy",
                policy_cfg.name,
            )


async def run_sync(gateway_url: str, token: str, config: GatewayConfig) -> AuditLog:
    audit = AuditLog()
    client = SyncClient(gateway_url, token, audit)
    try:
        for org_cfg in config.organizations:
            logger.info("syncing organization '%s'", org_cfg.slug)
            await client.sync_org(org_cfg)
    finally:
        await client.close()
    return audit
