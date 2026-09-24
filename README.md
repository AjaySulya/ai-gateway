# AI Gateway

Internal LLM gateway — unified API, governance, and observability across LLM providers.

## Local setup

    uv sync
    docker compose up -d
    uv run alembic revision --autogenerate -m "init schema"
    uv run alembic upgrade head
    uv run uvicorn gateway.main:app --app-dir src --reload

Check it's alive:

    curl localhost:8000/health
    curl localhost:8000/health/db

## Project structure

The full intended layout, built phase by phase. Packages for phases not
built yet exist as placeholders (a docstring naming what belongs there) so
the shape of the whole project is visible now rather than discovered
one phase at a time - nothing in them is implemented until its phase says so.

    ai-gateway/
    ├── pyproject.toml, docker-compose.yml, alembic.ini,      Phase 0
    │   .env.example
    ├── alembic/                       migrations
    ├── .github/workflows/ci.yml       CI skeleton
    ├── config/example/                Phase 9 (placeholder) - versioned
    │                                  GitOps config, once the sync job reads it
    ├── tests/
    │   └── test_policy_merge.py       Phase 3 - more per phase as it lands
    └── src/gateway/
        ├── main.py                    registers every router below
        ├── config.py                  env-driven settings
        ├── db/                        Phase 0 - models, session, base
        │   └── models/                Organization, Team, Project, Agent,
        │                              Provider, Model, Policy, APIKey,
        │                              User, OrganizationMembership,
        │                              TeamMembership
        ├── auth/                      Phase 1 - Control API JWT auth,
        │                              password + API-key hashing
        ├── schemas/                   Phase 1+ - Pydantic request/response
        │                              shapes, one file per resource
        ├── api/                       Phase 1+ - route handlers, one file
        │                              per resource (chat.py is Phase 2)
        ├── data_plane/                Phase 2 - API-key auth, RequestContext,
        │                              model resolution, LiteLLM adapter
        ├── policy/                    Phase 3 - PolicyConfig/EffectivePolicy,
        │                              tighten-only merge, hierarchy walk
        ├── routing/                   Phase 4 (placeholder) - multi-provider
        │                              selection, health checks, circuit
        │                              breaker, Jev integration point
        ├── usage/                     Phase 5 (placeholder) - usage/cost
        │                              logging, budget enforcement
        ├── rate_limit/                Phase 6 (placeholder) - Redis-backed
        │                              request limiting
        ├── observability/             Phase 7 (placeholder) - OpenTelemetry
        │                              tracing and metrics
        ├── security/                  Phase 8 (placeholder) - request
        │                              analyzer, prompt-injection/PII checks
        └── gitops/                    Phase 9 (placeholder) - config-as-code
                                       sync into the Control API

## Phase 0 — foundations

- Org → Team → Project → Agent hierarchy, modeled and migratable
- Provider / Model catalog, scoped per project
- Policy table with polymorphic scope (org/team/project/agent) —
  resolution logic (effective policy merge) is Phase 3, not built yet
- API key table (hashed, prefix stored for display only)
- Alembic wired for autogenerate migrations against the models above
- CI skeleton: lint + test against real Postgres/Redis services

## Phase 1 — Control API

- `User` + `OrganizationMembership` / `TeamMembership` (org_admin / team_lead
  roles), JWT auth via `/auth/login`
- `POST /auth/bootstrap` creates the first superuser — only works once, while
  the `users` table is empty
- CRUD for organizations, teams, projects, agents, providers, models, policies
- `POST /projects/{id}/api-keys` issues a data-plane key — the raw key is
  returned exactly once, only its hash is stored

Quickstart, after `alembic upgrade head`:

    # 1. bootstrap the first superuser
    curl -X POST localhost:8000/auth/bootstrap -H 'Content-Type: application/json' \
      -d '{"email":"you@company.com","password":"changeme","full_name":"You"}'

    # 2. log in
    curl -X POST localhost:8000/auth/login \
      -d 'username=you@company.com&password=changeme'
    # -> {"access_token": "...", "token_type": "bearer"}
    export TOKEN=<access_token from above>

    # 3. create an org, a team, a project
    curl -X POST localhost:8000/organizations -H "Authorization: Bearer $TOKEN" \
      -H 'Content-Type: application/json' -d '{"name":"Acme","slug":"acme"}'
    # -> use the returned id as {org_id} below
    curl -X POST localhost:8000/organizations/{org_id}/teams -H "Authorization: Bearer $TOKEN" \
      -H 'Content-Type: application/json' -d '{"name":"Platform","slug":"platform"}'
    curl -X POST localhost:8000/teams/{team_id}/projects -H "Authorization: Bearer $TOKEN" \
      -H 'Content-Type: application/json' -d '{"name":"Chatbot","slug":"chatbot"}'

    # 4. issue a data-plane API key for that project
    curl -X POST localhost:8000/projects/{project_id}/api-keys -H "Authorization: Bearer $TOKEN" \
      -H 'Content-Type: application/json' -d '{"name":"local-dev"}'

New tables mean a new migration:

    uv run alembic revision --autogenerate -m "add users and memberships"
    uv run alembic upgrade head

Still outstanding from Phase 1: the GitOps sync job (versioned config →
applied idempotently through this Control API → Postgres).

## Phase 2 — data-plane proxy (current)

- `POST /v1/chat/completions`, OpenAI-compatible body, sync and streaming (SSE)
- Auth via `Authorization: Bearer <api key>` (the raw key from Phase 1's
  `/projects/{id}/api-keys`, not a JWT) → resolves to a `RequestContext`
  (org/team/project/agent ids, request id) via `data_plane/auth.py`
- Optional `X-Agent-Id` header attributes the call to a specific agent
- Model resolution: the requested `model` must match an active `Model` under
  an active `Provider` on that project (Phase 1 Control API is how those get
  created) - this is the seam Phase 4's multi-provider router replaces
- `Provider.credential_ref` is read as an **environment variable name** at
  call time (e.g. a provider row with `credential_ref=ANTHROPIC_API_KEY`
  reads `os.environ["ANTHROPIC_API_KEY"]`) - a stand-in for a real secrets
  manager, swapped in later without touching call sites

Set up one provider + model, export its credential, then call it:

    export ANTHROPIC_API_KEY=sk-ant-...

    curl -X POST localhost:8000/projects/{project_id}/providers \
      -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
      -d '{"name":"anthropic-prod","provider_type":"anthropic","credential_ref":"ANTHROPIC_API_KEY"}'

    curl -X POST localhost:8000/providers/{provider_id}/models \
      -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
      -d '{"model_name":"claude-sonnet-4-6","display_name":"Claude Sonnet 4.6"}'

    # sync
    curl localhost:8000/v1/chat/completions \
      -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
      -d '{"model":"claude-sonnet-4-6","messages":[{"role":"user","content":"hi"}]}'

    # streaming
    curl -N localhost:8000/v1/chat/completions \
      -H "Authorization: Bearer $API_KEY" -H 'Content-Type: application/json' \
      -d '{"model":"claude-sonnet-4-6","messages":[{"role":"user","content":"hi"}],"stream":true}'

`$API_KEY` is the raw key from Phase 1's `POST /projects/{id}/api-keys` -
distinct from `$TOKEN`, the Control API JWT used for the calls above it.

Not yet built (untested against a live provider in this environment, since
the sandbox that generated this scaffold has no network access - worth a
real smoke test before relying on it): retries, timeouts, and provider-specific
parameter quirks (e.g. Azure needing `api_base`/`api_version`) that
`litellm.acompletion`'s defaults may not cover for every provider.

## Phase 3 — effective policy resolution (current)

- `Policy.config` now validates against a real shape (`PolicyConfig`):
  `allowed_models`, `denied_models`, `budget_limit_usd`, `rate_limit_rpm`,
  `allowed_regions` - not an arbitrary dict
- `resolve_effective_policy()` walks org → team → project → agent, folding
  in every enabled policy at each level. The merge is **tighten-only**:
  allowlists intersect, denylists union, numeric caps take the min - a
  child can never loosen what a parent already restricted. See
  `src/gateway/policy/merge.py` and `tests/test_policy_merge.py` (11 tests
  covering exactly this invariant - written before wiring it into the
  request path, per the plan)
- Wired into `/v1/chat/completions`: the Policy Engine runs before the
  Model Router, matching the architecture diagram's pipeline order. A
  model not in the effective allowlist (or present in the denylist) gets
  rejected with 403 before any provider is touched
- `GET /projects/{project_id}/effective-policy?agent_id=...` (Control API,
  requires project access) - shows exactly what the data plane computes,
  without needing an API key or a provider call
- **Not yet enforced**: `budget_limit_usd` and `rate_limit_rpm` are resolved
  correctly but nothing checks against them yet - that's Phase 5 (usage
  tracking) and Phase 6 (Redis rate limiter) respectively. The fields exist
  now so those phases have something to read instead of inventing it later

Run the new tests:

    uv run pytest tests/test_policy_merge.py -v

(Not run in this environment - the sandbox that built this scaffold has no
network, so dependencies were never installed here. Worth doing before you
trust the merge logic.)

Try it end to end: create a project-level policy restricting to one model,
then check the debug endpoint and a real call.

    curl -X POST localhost:8000/policies -H "Authorization: Bearer $TOKEN" \
      -H 'Content-Type: application/json' \
      -d '{"name":"project-default","scope_type":"project","scope_id":"{project_id}","config":{"allowed_models":["claude-sonnet-4-6"]}}'

    curl localhost:8000/projects/{project_id}/effective-policy -H "Authorization: Bearer $TOKEN"
    # -> {"allowed_models":["claude-sonnet-4-6"],"denied_models":[],...}

    curl localhost:8000/v1/chat/completions -H "Authorization: Bearer $API_KEY" \
      -H 'Content-Type: application/json' \
      -d '{"model":"gpt-4o","messages":[{"role":"user","content":"hi"}]}'
    # -> 403, "Model 'gpt-4o' is not permitted by policy"

## HuggingFace as a provider

`ProviderType` now includes `huggingface`. Two setup shapes:

- **Serverless Inference API**: `credential_ref` pointing at an env var with
  your HF token; no `extra_config` needed for models that support it.
- **Dedicated Inference Endpoint**: same, plus
  `extra_config={"api_base": "https://<your-endpoint>.endpoints.huggingface.cloud"}` -
  `extra_config` is a generic JSONB column on `Provider` for exactly this
  kind of provider-specific extra (Azure's `api_version` would go the same
  way), so adding another provider quirk later never needs a new column.

    export HF_TOKEN=hf_...

    curl -X POST localhost:8000/projects/{project_id}/providers \
      -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
      -d '{"name":"hf-endpoint","provider_type":"huggingface","credential_ref":"HF_TOKEN","extra_config":{"api_base":"https://xyz.endpoints.huggingface.cloud"}}'

**Migration gotcha**: adding `huggingface` to a Postgres native enum is not
something Alembic's autogenerate detects on its own - it will pick up the
new `extra_config` column, but not the enum value. After running

    uv run alembic revision --autogenerate -m "add extra_config and huggingface provider type"

open the generated file and add this line at the top of `upgrade()`:

    op.execute("ALTER TYPE provider_type ADD VALUE IF NOT EXISTS 'huggingface'")

(Safe as a single statement pre-Postgres-12; on 16, as used here, it can
also run in the same transaction as the column change autogenerate already
wrote - no special ordering needed beyond putting it first for clarity.)
Postgres has no matching "remove a value" operation, so leave `downgrade()`
as the autogenerated column-drop only, with a comment that the enum value
removal is intentionally not reversed.

## Next: Phase 4

Model Router: multiple providers/models per project (HuggingFace now among
them), the static priority-fallback strategy, health checks, and retries -
with TypeSafe Jev slotted in afterward as described earlier in this project's
planning, once the deterministic router underneath it is solid.
