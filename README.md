# AI Gateway

An OpenAI-compatible gateway that sits between your applications and LLM providers. One endpoint for every app, with centralized API keys, per-team policies, budgets, rate limits, automatic failover, and observability.

> **Status: alpha.** Feature-complete for its V1 scope (internal teams, single deployment) but not production-hardened. Read [Known limitations](#known-limitations) and [Security notes](#security-notes) before putting it in front of real traffic.

```
Your apps ──► AI Gateway ──► Anthropic
(OpenAI SDK,                 OpenAI
 curl, LangChain, ...)       Gemini / Groq / OpenRouter / Ollama
                             HuggingFace, Bedrock, Vertex, ... (anything LiteLLM supports)
```

## Why

When several teams build LLM apps independently, the same problems appear every time:

- Provider API keys scattered across codebases
- No visibility into who is spending what, on which models
- Apps break when one provider has an outage
- No way to say "this team may only use these models" or "this project has a $100 cap"
- Switching providers means changing application code

The gateway centralizes all of that behind one OpenAI-compatible URL. Applications change their `base_url` and API key, nothing else.

## Features

- **OpenAI-compatible** `POST /v1/chat/completions`, synchronous and streaming (SSE)
- **Multi-tenancy**: Organization → Team → Project → Agent, each project with its own API keys, providers, and models
- **Hierarchical policies**: allowed/denied models, budgets, rate limits, and security toggles attached at any level and resolved into one effective policy. A lower level can only tighten what a parent set, never loosen it
- **Budgets**: per-level spend caps (`402` when exceeded) backed by a usage log
- **Rate limiting**: per-level requests-per-minute in Redis (`429` with `Retry-After`)
- **Routing and reliability**: priority-ordered fallback across providers, retries with exponential backoff, per-provider circuit breaker
- **Security (opt-in per policy)**: prompt-injection detection and PII redaction
- **Observability**: OpenTelemetry traces (one span per pipeline stage), metrics, and trace-correlated logs
- **GitOps**: manage config as YAML in git, with an idempotent sync, drift detection, and an audit log
- **Provider-agnostic** via [LiteLLM](https://github.com/BerriAI/litellm)

## How a request flows

```
POST /v1/chat/completions
  │
  ├─ 1. Authenticate       project API key → project → team → org
  ├─ 2. Rate limit         Redis fixed-window counters, checked at each hierarchy level
  ├─ 3. Policy             effective policy resolved org → team → project → agent
  ├─ 4. Budget             each level's own cap vs. that level's own cumulative spend
  ├─ 5. Request analyzer   message count and size validation
  ├─ 6. Security engine    injection detection, PII redaction (opt-in)
  ├─ 7. Model router       candidates by priority → circuit breaker → retries → fallback
  ├─ 8. LiteLLM            provider call (sync or streaming)
  └─ 9. Usage tracking     usage row in Postgres + OpenTelemetry metrics
```

Tenancy hierarchy:

```
Organization
 └─ Team
     └─ Project        owns API keys, providers, models
         └─ Agent      optional; attribute calls with the X-Agent-Id header
```

The **Control API** (REST, JWT-authenticated) manages all of this. **PostgreSQL** is the source of truth; **Redis** holds rate-limit counters and circuit-breaker state.

## Quickstart

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), Docker.

```bash
git clone https://github.com/AjaySulya/ai-gateway.git
cd ai-gateway

uv sync
cp .env.example .env          # then edit: set SECRET_KEY and your provider key(s)

docker compose up -d          # Postgres (host port 5433) + Redis (6379)
uv run alembic upgrade head   # create tables
uv run uvicorn gateway.main:app --app-dir src --reload
```

Check it is up: `curl localhost:8000/health` and `curl localhost:8000/health/db`.
Interactive API docs are at `http://localhost:8000/docs`.

### Two kinds of credentials

| | Control API token | Project API key |
|---|---|---|
| Obtained from | `POST /auth/login` (JWT, 8 hours) | `POST /projects/{id}/api-keys` (shown once) |
| Used for | Managing orgs, teams, projects, providers, policies | `POST /v1/chat/completions` |
| Header | `Authorization: Bearer <jwt>` | `Authorization: Bearer sk-proj-...` |

### First request (Groq free tier as the example)

Get a free key at [console.groq.com](https://console.groq.com) and put `GROQ_API_KEY=...` in `.env`, then restart the gateway.

```bash
# 1. Create the first admin (works once, while no users exist)
curl -X POST localhost:8000/auth/bootstrap -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"change-me","full_name":"Admin"}'

# 2. Log in, then export the access_token
curl -X POST localhost:8000/auth/login -d 'username=admin@example.com&password=change-me'
export TOKEN=<access_token>

# 3. Create org → team → project (use each returned "id" in the next call)
curl -X POST localhost:8000/organizations -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"Acme","slug":"acme"}'
curl -X POST localhost:8000/organizations/<org_id>/teams -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"Platform","slug":"platform"}'
curl -X POST localhost:8000/teams/<team_id>/projects -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"Chatbot","slug":"chatbot"}'

# 4. Add a provider and a model
curl -X POST localhost:8000/projects/<project_id>/providers -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"groq","provider_type":"openai","credential_ref":"GROQ_API_KEY",
       "extra_config":{"api_base":"https://api.groq.com/openai/v1"}}'
curl -X POST localhost:8000/providers/<provider_id>/models -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"model_name":"llama-3.1-8b-instant","display_name":"Llama 3.1 8B Instant","priority":10}'

# 5. Issue a project API key (the raw key is returned once)
curl -X POST localhost:8000/projects/<project_id>/api-keys -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"local-dev"}'
export API_KEY=<api_key>

# 6. Call the gateway
curl localhost:8000/v1/chat/completions -H "Authorization: Bearer $API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":"Hello!"}]}'
```

Any OpenAI SDK works by pointing it at the gateway:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="sk-proj-...")  # project API key
response = client.chat.completions.create(
    model="llama-3.1-8b-instant",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
```

A ready-made Postman collection, `ai-gateway.postman_collection.json`, is in the repo root. It walks through the same flow and saves IDs and tokens into collection variables automatically. You can also provision everything from YAML instead, see [GitOps](#gitops).

## Providers

`credential_ref` is the **name of an environment variable** the gateway reads at call time (for example `GROQ_API_KEY`). Raw keys are never stored in the database. `model_name` must be exactly what the provider expects.

| Provider | `provider_type` | `extra_config` |
|---|---|---|
| OpenAI | `openai` | `{}` |
| Anthropic | `anthropic` | `{}` |
| Gemini (OpenAI-compatible endpoint) | `openai` | `{"api_base": "https://generativelanguage.googleapis.com/v1beta/openai"}` |
| Groq | `openai` | `{"api_base": "https://api.groq.com/openai/v1"}` |
| OpenRouter | `openai` | `{"api_base": "https://openrouter.ai/api/v1"}` |
| Ollama (local) | `openai` | `{"api_base": "http://localhost:11434/v1"}` (set any value for the key) |
| HuggingFace endpoint | `huggingface` | `{"api_base": "https://<endpoint>.endpoints.huggingface.cloud"}` |
| Azure OpenAI, Bedrock, Vertex AI | `azure_openai`, `bedrock`, `vertex_ai` | provider-specific extras (`api_version`, region, ...) |

`extra_config` is passed through to LiteLLM, so provider quirks never need a new column. Don't use `provider_type: other`: LiteLLM receives `other/<model>` and can't route it. For anything OpenAI-compatible, use `openai` plus `api_base`.

The OpenAI-compatible route (Gemini, Groq) is the most exercised path so far. Native Anthropic, OpenAI, HuggingFace, Azure, Bedrock, and Vertex support is implemented through LiteLLM but is less battle-tested, and issues are welcome.

**Fallback chains:** register the same `model_name` under two providers with different `priority` (lower is tried first). If the first provider fails or its circuit is open, the router moves to the next.

## Policies

Attach a policy to an organization, team, project, or agent with `POST /policies`:

```json
{
  "name": "chatbot-limits",
  "scope_type": "project",
  "scope_id": "<project_id>",
  "config": {
    "allowed_models": ["llama-3.1-8b-instant"],
    "budget_limit_usd": 10.0,
    "rate_limit_rpm": 60,
    "block_prompt_injection": true,
    "redact_pii": true
  }
}
```

| Field | Behavior |
|---|---|
| `allowed_models` / `denied_models` | Enforced. Requests for a disallowed model get `403` |
| `budget_limit_usd` | Enforced per level against cumulative spend. `402` when exceeded |
| `rate_limit_rpm` | Enforced per level, fixed one-minute window. `429` with `Retry-After` |
| `block_prompt_injection` | Rejects requests matching injection patterns (`400`). Off by default, so matches are only logged |
| `redact_pii` | Masks emails, phone numbers, SSNs, and card-like numbers before the provider sees them. Off by default |
| `allowed_regions` | Accepted and merged, **not enforced yet** |

**Merge rules:** allowlists intersect, denylists union, numeric caps take the minimum, and security flags stay on once any level enables them. Budgets and rate limits are enforced at each level against that level's own totals (an org cap against org-wide spend, a project cap against project spend), not via the merged value. Inspect the result with `GET /projects/{id}/effective-policy`.

## GitOps

Manage orgs, teams, projects, providers, models, agents, and policies as YAML. See [`config/example/acme.yaml`](config/example/acme.yaml) for the full shape.

```bash
export GATEWAY_URL=http://localhost:8000
export GATEWAY_TOKEN=<control-api-jwt>   # a superuser token (creating orgs is superuser-only)

uv run python -m gateway.gitops.cli validate --config config/example/acme.yaml   # schema only, no network
uv run python -m gateway.gitops.cli sync     --config config/example/acme.yaml   # apply
uv run python -m gateway.gitops.cli drift    --config config/example/acme.yaml   # exits 2 if live state differs
```

The sync is idempotent (create if missing) and **never deletes**, so a typo in a config file can't remove production resources. Every change is written to an audit log (`--audit-log path.json` to save it). CI validates any config change (`.github/workflows/validate-config.yml`).

## Observability

By default, spans and metrics print to stdout, so nothing extra is needed to see them. Set `OTEL_EXPORTER_OTLP_ENDPOINT` (for example `http://localhost:4318`) to export via OTLP/HTTP to a collector, Tempo, Honeycomb, and so on.

- **Traces:** a child span per stage (`rate_limit`, `policy_engine`, `budget_check`, `request_analyzer`, `security_engine`, `model_router`)
- **Metrics:** `gateway.requests`, `gateway.request.duration`, `gateway.tokens`, `gateway.cost`, labeled by org, team, project, model, provider, and status
- **Logs:** every line carries the active `trace_id` and `span_id`

Metric labels include raw org and project IDs, which is high-cardinality. That's fine for most OTLP backends, but reconsider before sending to Prometheus.

Debug endpoints: `GET /projects/{id}/usage`, `/effective-policy`, `/rate-limit-status`, and `GET /providers/{id}/health` (circuit-breaker state).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://gateway:gateway@localhost:5433/ai_gateway` | Postgres connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key. **Must be overridden** |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | unset | OTLP collector URL. Unset means console export |
| *provider keys* | | Whatever names you use in `credential_ref` (`GROQ_API_KEY`, `OPENAI_API_KEY`, ...) |

## Project structure

```
src/gateway/
├── api/            route handlers (Control API + /v1/chat/completions)
├── auth/           JWT auth, password and API-key hashing
├── data_plane/     API-key auth, RequestContext, LiteLLM adapter
├── db/             SQLAlchemy models and session
├── policy/         policy schema, tighten-only merge, hierarchy resolution
├── rate_limit/     Redis fixed-window limiter and per-level enforcement
├── routing/        candidate selection, circuit breaker, retries and fallback
├── security/       request analyzer, injection detection, PII redaction
├── usage/          usage records and per-level budget enforcement
├── observability/  OpenTelemetry setup, instruments, trace-correlated logging
├── gitops/         config schema, sync, drift detection, audit log, CLI
└── schemas/        Pydantic request/response models
alembic/            migrations
config/example/     example GitOps config
tests/
```

## Development

```bash
uv sync --all-extras
uv run pytest                                   # policy-merge unit tests
uv run ruff check .                             # lint
uv run alembic revision --autogenerate -m "..." # after changing models
```

Adding a value to an existing Postgres enum (for example a new `ProviderType`) isn't detected by Alembic's autogenerate. Add `op.execute("ALTER TYPE provider_type ADD VALUE IF NOT EXISTS '<value>'")` to the migration by hand.

## Security notes

- **Set `SECRET_KEY`** to a long random value. The default is public.
- **Run `/auth/bootstrap` immediately.** It's unauthenticated until the first user exists, so whoever calls it first becomes superuser. Don't expose a fresh instance publicly before bootstrapping.
- Put the gateway behind TLS. Tokens and API keys travel in headers.
- Provider credentials live in the gateway's process environment. Treat that environment as sensitive.
- Injection detection and PII redaction are small regex rule sets. They reduce accidents, they are **not** a security boundary.

## Known limitations

- **Alpha quality.** Only the policy-merge logic has automated tests. There is no integration test suite yet.
- **Minimal user management.** The only way to create a user is `/auth/bootstrap`. Org-admin and team-lead roles and membership tables exist, but there are no endpoints to invite users or assign roles, so in practice the bootstrap superuser manages everything.
- **Read endpoints aren't membership-scoped.** Any logged-in user can read org, team, project, provider, and policy metadata (writes are scoped correctly). Fine for a single internal deployment, not for multi-tenant use. There's no read-only role.
- **Streaming:** cost is never recorded, tokens only when the provider includes usage in a chunk, and failover only happens before the first chunk is sent.
- **Budgets:** cumulative all-time with no reset window. Cost comes from LiteLLM's pricing table, so models it doesn't know count as $0. Checks aren't atomic, so concurrent requests can overshoot a cap slightly.
- **Rate limiting** uses fixed windows, so bursts of up to about 2x the limit are possible across a minute boundary.
- **`allowed_regions`** is merged but not enforced.
- **Scope of the API:** chat completions only (no embeddings or `/v1/models`), and text-only message content (no multimodal parts or multi-turn tool-call messages).
- **Secrets:** no vault integration; `credential_ref` is an environment variable name.
- **Detectors:** the PII patterns (phone, card-like digits) can produce false positives.

## Roadmap

- Admin UI on top of the existing Control API
- User and membership endpoints, a read-only role, membership-scoped reads
- Time-windowed budgets (daily and monthly) and atomic budget accounting
- Sliding-window or token-bucket rate limiting
- Streaming usage and cost accounting
- Cost, latency, and quality-aware routing on top of the current priority-based router (integration with TypeSafe AI's Jev is planned)
- Integration tests, and a secrets-manager backend for provider credentials

## Contributing

Issues and pull requests are welcome. For anything larger than a small fix, please open an issue first to discuss the approach. Before submitting, run `uv run ruff check .` and `uv run pytest`, and add tests for policy or routing logic changes.

## License

[MIT](LICENSE)

## Acknowledgements

Built on [LiteLLM](https://github.com/BerriAI/litellm), [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy](https://www.sqlalchemy.org/), and [OpenTelemetry](https://opentelemetry.io/).
