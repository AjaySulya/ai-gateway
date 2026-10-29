import uuid

import pytest
from fastapi import HTTPException

from gateway.auth.dependencies import (
    check_scope_read_access,
    require_agent_member,
    require_org_member,
    require_project_member,
    require_provider_member,
    require_team_member,
)
from gateway.db.models import (
    Agent,
    Organization,
    OrganizationRole,
    PolicyScope,
    Project,
    Provider,
    ProviderType,
    Team,
    TeamRole,
    User,
)


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    """Minimal AsyncSession stand-in for dependency tests.

    `role_results` is consumed in query order: _org_role first, then
    _team_role when the org check fails.
    """

    def __init__(self, objects=None, role_results=None):
        self._objects = objects or {}
        self._role_results = list(role_results or [])

    async def get(self, model, ident):
        return self._objects.get((model, ident))

    async def execute(self, _stmt):
        value = self._role_results.pop(0) if self._role_results else None
        return _Result(value)


def _user(*, is_superuser: bool = False) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{uuid.uuid4()}@example.com",
        hashed_password="x",
        full_name="Test User",
        is_active=True,
        is_superuser=is_superuser,
    )


def _org() -> Organization:
    return Organization(id=uuid.uuid4(), name="Acme", slug=f"acme-{uuid.uuid4()}")


def _team(org: Organization) -> Team:
    return Team(id=uuid.uuid4(), organization_id=org.id, name="Platform", slug="platform")


def _project(team: Team) -> Project:
    return Project(id=uuid.uuid4(), team_id=team.id, name="Chatbot", slug="chatbot")


def _provider(project: Project) -> Provider:
    return Provider(
        id=uuid.uuid4(),
        project_id=project.id,
        name="openai",
        provider_type=ProviderType.openai,
        credential_ref="OPENAI_API_KEY",
        extra_config={},
        is_active=True,
    )


@pytest.mark.asyncio
async def test_superuser_can_read_org():
    user = _user(is_superuser=True)
    org = _org()
    db = _FakeDB({(Organization, org.id): org})

    assert await require_org_member(org.id, user, db) is user


@pytest.mark.asyncio
async def test_org_member_can_read_org_and_team():
    user = _user()
    org = _org()
    team = _team(org)
    db = _FakeDB(
        {(Organization, org.id): org, (Team, team.id): team},
        role_results=[OrganizationRole.member],
    )

    assert await require_org_member(org.id, user, db) is user
    # A second org-membership query for the team read.
    db._role_results = [OrganizationRole.member]
    assert await require_team_member(team.id, user, db) is user


@pytest.mark.asyncio
async def test_unrelated_user_cannot_read_org_or_team():
    user = _user()
    org = _org()
    team = _team(org)
    db = _FakeDB(
        {(Organization, org.id): org, (Team, team.id): team},
        role_results=[None],
    )

    with pytest.raises(HTTPException) as exc:
        await require_org_member(org.id, user, db)
    assert exc.value.status_code == 403

    db._role_results = [None, None]
    with pytest.raises(HTTPException) as exc:
        await require_team_member(team.id, user, db)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_team_member_can_read_project():
    user = _user()
    org = _org()
    team = _team(org)
    project = _project(team)
    db = _FakeDB(
        {(Project, project.id): project, (Team, team.id): team},
        role_results=[None, TeamRole.member],
    )

    assert await require_project_member(project.id, user, db) is user


@pytest.mark.asyncio
async def test_team_member_can_read_provider():
    user = _user()
    org = _org()
    team = _team(org)
    project = _project(team)
    provider = _provider(project)
    db = _FakeDB(
        {
            (Project, project.id): project,
            (Team, team.id): team,
            (Provider, provider.id): provider,
        },
        role_results=[None, TeamRole.member],
    )

    assert await require_provider_member(provider.id, user, db) is user


@pytest.mark.asyncio
async def test_unrelated_user_cannot_read_project():
    user = _user()
    org = _org()
    team = _team(org)
    project = _project(team)
    db = _FakeDB(
        {(Project, project.id): project, (Team, team.id): team},
        role_results=[None, None],
    )

    with pytest.raises(HTTPException) as exc:
        await require_project_member(project.id, user, db)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_missing_team_returns_404_even_for_superuser():
    user = _user(is_superuser=True)
    org = _org()
    team = _team(org)
    project = _project(team)
    db = _FakeDB({(Project, project.id): project})

    with pytest.raises(HTTPException) as exc:
        await require_project_member(project.id, user, db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_policy_listing_uses_read_scope_check():
    user = _user()
    org = _org()
    db = _FakeDB({(Organization, org.id): org}, role_results=[None])

    with pytest.raises(HTTPException) as exc:
        await check_scope_read_access(db, user, PolicyScope.organization, org.id)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_agent_read_access_uses_project():
    user = _user()
    org = _org()
    team = _team(org)
    project = _project(team)
    agent = Agent(id=uuid.uuid4(), project_id=project.id, name="Support", slug="support")
    db = _FakeDB(
        {
            (Agent, agent.id): agent,
            (Project, project.id): project,
            (Team, team.id): team,
        },
        role_results=[None, TeamRole.member],
    )

    assert await require_agent_member(agent.id, user, db) is user
