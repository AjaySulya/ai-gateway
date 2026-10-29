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

    async def _update(
        self, url: str, existing: dict, desired: dict, kind: str, name: str
    ) -> dict:
        """PATCH only the fields that differ from the live resource."""
        changed = {key: value for key, value in desired.items() if existing.get(key) != value}
        if not changed:
            logger.debug("%s '%s' is already up to date", kind, name)
            return existing

        r = await self._http.patch(url, json=changed)
        r.raise_for_status()
        data = r.json()
        self._audit.record("update", kind, name, data.get("id", existing.get("id")))
        logger.info("updated %s '%s' (id=%s)", kind, name, data.get("id"))
        return data

    def _find_by_slug(self, items: list[dict], slug: str) -> dict | None:
        return next((i for i in items if i.get("slug") == slug), None)

    def _find_by_name(self, items: list[dict], name: str) -> dict | None:
        return next((i for i in items if i.get("name") == name), None)

    # ------------------------------------------------------------------ #
    # Org                                                                   #
    # ------------------------------------------------------------------ #

    async def sync_org(self, cfg: OrgConfig) -> str:
        orgs = await self._get_list("/organizations")
        existing = self._find_by_slug(orgs, cfg.slug)
        if existing:
            existing = await self._update(
                f"/organizations/{existing['id']}",
                existing,
                {"name": cfg.name},
                "organization",
                cfg.slug,
            )
            org_id = existing["id"]
        else:
            data = await self._create(
                "/organizations", {"name": cfg.name, "slug": cfg.slug}, "organization", cfg.slug
            )
            org_id = data["id"]

        team_ids: dict[str, str] = {}
        for team_cfg in cfg.teams:
            team_ids[team_cfg.slug] = await self.sync_team(org_id, team_cfg)

        await self._sync_policies(cfg.policies, org_id=org_id, team_ids=team_ids)

        return org_id

    # ------------------------------------------------------------------ #
    # Team                                                                  #
    # ------------------------------------------------------------------ #

    async def sync_team(self, org_id: str, cfg: TeamConfig) -> str:
        teams = await self._get_list(f"/organizations/{org_id}/teams")
        existing = self._find_by_slug(teams, cfg.slug)
        if existing:
            existing = await self._update(
                f"/teams/{existing['id']}",
                existing,
                {"name": cfg.name},
                "team",
                cfg.slug,
            )
            team_id = existing["id"]
        else:
            data = await self._create(
                f"/organizations/{org_id}/teams",
                {"name": cfg.name, "slug": cfg.slug},
                "team",
                cfg.slug,
            )
            team_id = data["id"]

        project_ids: dict[str, str] = {}
        for project_cfg in cfg.projects:
            project_ids[project_cfg.slug] = await self.sync_project(team_id, project_cfg)

        await self._sync_policies(
            cfg.policies,
            org_id=org_id,
            team_id=team_id,
            project_ids=project_ids,
        )

        return team_id

    # ------------------------------------------------------------------ #
    # Project                                                               #
    # ------------------------------------------------------------------ #

    async def sync_project(self, team_id: str, cfg: ProjectConfig) -> str:
        projects = await self._get_list(f"/teams/{team_id}/projects")
        existing = self._find_by_slug(projects, cfg.slug)
        if existing:
            existing = await self._update(
                f"/projects/{existing['id']}",
                existing,
                {"name": cfg.name},
                "project",
                cfg.slug,
            )
            project_id = existing["id"]
        else:
            data = await self._create(
                f"/teams/{team_id}/projects",
                {"name": cfg.name, "slug": cfg.slug},
                "project",
                cfg.slug,
            )
            project_id = data["id"]

        # Agents must exist before agent-scoped policies can be attached.
        agent_ids: dict[str, str] = {}
        for agent_cfg in cfg.agents:
            agent_ids[agent_cfg.slug] = await self.sync_agent(project_id, agent_cfg)

        for provider_cfg in cfg.providers:
            await self.sync_provider(project_id, provider_cfg)

        await self._sync_policies(
            cfg.policies,
            team_id=team_id,
            project_id=project_id,
            agents=agent_ids,
        )

        return project_id

    # ------------------------------------------------------------------ #
    # Agent                                                                 #
    # ------------------------------------------------------------------ #

    async def sync_agent(self, project_id: str, cfg: AgentConfig) -> str:
        agents = await self._get_list(f"/projects/{project_id}/agents")
        existing = self._find_by_slug(agents, cfg.slug)
        if existing:
            existing = await self._update(
                f"/agents/{existing['id']}",
                existing,
                {"name": cfg.name},
                "agent",
                cfg.slug,
            )
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
        existing = self._find_by_name(providers, cfg.name)
        if existing:
            existing = await self._update(
                f"/providers/{existing['id']}",
                existing,
                {
                    "provider_type": cfg.provider_type.value,
                    "credential_ref": cfg.credential_ref,
                    "extra_config": cfg.extra_config,
                },
                "provider",
                cfg.name,
            )
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
            existing = await self._update(
                f"/models/{existing['id']}",
                existing,
                {"display_name": cfg.display_name, "priority": cfg.priority},
                "model",
                cfg.model_name,
            )
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

    async def _sync_policies(
        self,
        policies: list[PolicyConfigEntry],
        *,
        org_id: str | None = None,
        team_id: str | None = None,
        project_id: str | None = None,
        team_ids: dict[str, str] | None = None,
        project_ids: dict[str, str] | None = None,
        agents: dict[str, str] | None = None,
    ) -> None:
        for policy_cfg in policies:
            scopes = self._resolve_policy_scopes(
                policy_cfg.scope,
                org_id=org_id,
                team_id=team_id,
                project_id=project_id,
                team_ids=team_ids or {},
                project_ids=project_ids or {},
                agents=agents or {},
            )
            for scope_type, scope_id in scopes:
                await self._sync_one_policy(policy_cfg, scope_type, scope_id)

    @staticmethod
    def _resolve_policy_scopes(
        scope: str,
        *,
        org_id: str | None,
        team_id: str | None,
        project_id: str | None,
        team_ids: dict[str, str],
        project_ids: dict[str, str],
        agents: dict[str, str],
    ) -> list[tuple[str, str]]:
        """Turn a config scope into concrete (scope_type, scope_id) pairs.

        The scope field is authoritative - it is never inferred from the
        resource whose config block the policy happens to be nested under.
        Supported values are organization, team, project, agent,
        agent:<slug>, plus team:<slug> and project:<slug> qualifiers.
        A bare "agent" applies the policy to every agent in the project.
        """
        kind, _, qualifier = scope.strip().partition(":")
        kind = kind.strip().lower()
        qualifier = qualifier.strip()

        if kind in {"organization", "org"}:
            if org_id is None:
                raise ValueError("policy scope 'organization' requires an organization context")
            return [("organization", org_id)]

        if kind == "team":
            if qualifier:
                resolved = team_ids.get(qualifier)
                if resolved is None:
                    raise ValueError(f"policy scope references unknown team '{qualifier}'")
                return [("team", resolved)]
            if team_id is None:
                raise ValueError("policy scope 'team' requires a team context")
            return [("team", team_id)]

        if kind == "project":
            if qualifier:
                resolved = project_ids.get(qualifier)
                if resolved is None:
                    raise ValueError(f"policy scope references unknown project '{qualifier}'")
                return [("project", resolved)]
            if project_id is None:
                raise ValueError("policy scope 'project' requires a project context")
            return [("project", project_id)]

        if kind == "agent":
            if qualifier:
                resolved = agents.get(qualifier)
                if resolved is None:
                    raise ValueError(f"policy scope references unknown agent '{qualifier}'")
                return [("agent", resolved)]
            if not agents:
                raise ValueError("policy scope 'agent' requires an agent context")
            return [("agent", agent_id) for agent_id in agents.values()]

        raise ValueError(
            f"unknown policy scope '{scope}' "
            "(expected organization, team, project, agent, or agent:<slug>)"
        )

    async def _sync_one_policy(
        self, policy_cfg: PolicyConfigEntry, scope_type: str, scope_id: str
    ) -> None:
        existing = await self._get_list(
            f"/policies?scope_type={scope_type}&scope_id={scope_id}"
        )
        current = self._find_by_name(existing, policy_cfg.name)
        desired_config = policy_cfg.config.model_dump(exclude_none=True)

        if current is None:
            await self._create(
                "/policies",
                {
                    "name": policy_cfg.name,
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    "config": desired_config,
                    "enabled": True,
                },
                "policy",
                policy_cfg.name,
            )
            return

        # PolicyRead serializes unset fields as nulls; strip them so the
        # comparison is against the restrictions that are actually set.
        existing_config = {
            key: value
            for key, value in (current.get("config") or {}).items()
            if value is not None
        }
        comparable = dict(current)
        comparable["config"] = existing_config

        await self._update(
            f"/policies/{current['id']}",
            comparable,
            {"config": desired_config, "enabled": True},
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
