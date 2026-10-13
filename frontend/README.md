# AI Gateway admin console

A Python-only web UI for the gateway's Control API, built with [Reflex](https://reflex.dev). Manage organizations, teams, projects, agents, providers, models, policies, and API keys, watch usage, and send real requests from the playground.

It calls the same Control API endpoints you'd hit from Postman. Nothing in the gateway needs to change.

## Run it

The gateway must already be running (default `http://localhost:8000`).

```bash
cd frontend

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

reflex run
```

Open **http://localhost:3000**.

The first `reflex run` downloads Node and installs the frontend dependencies, which takes a few minutes and needs an internet connection. Later runs start in seconds. Use Python 3.10 or newer.

Use a separate virtual environment from the gateway's. Reflex pulls in its own FastAPI and Pydantic versions, and you don't want them fighting the gateway's.

## Ports

| Service | Port |
|---|---|
| Gateway | 8000 |
| Console (browser) | 3000 |
| Console's own backend | 8001 |

Reflex normally uses 8000 for its backend, which is the gateway's port, so `rxconfig.py` moves it to 8001.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `GATEWAY_URL` | `http://localhost:8000` | Where the console finds the gateway |

```bash
GATEWAY_URL=http://localhost:8000 reflex run
```

The browser only talks to the console's own backend. The console calls the gateway from the server side, so you don't need CORS settings on the gateway.

## First use

1. Open the console. On the sign-in page, choose **First-time setup** to create the admin account. This only works while no users exist. Otherwise sign in.
2. **Workspace**: create an organization, a team, and a project.
3. **Providers and models**: add a provider (pick a preset), then add a model. The credential field is the *name* of a variable in the gateway's `.env`, like `GROQ_API_KEY`, never the key itself.
4. **API keys**: issue a key. The console fills it into the playground automatically.
5. **Playground**: pick a model and send a request.
6. **Policies**: add rules, then try the example messages in the playground to see a refusal.

## Pages

| Page | What it does |
|---|---|
| Dashboard | Requests, cost, tokens, success rate, provider health, rate limits, merged policy |
| Workspace | Create organizations, teams, projects, agents |
| Providers and models | Add providers and models, see circuit status |
| Policies | Allowed and denied models, budget, rate limit, injection blocking, PII redaction |
| API keys | Issue and revoke project keys |
| Playground | Send a request and see status, latency, reply, and raw JSON |

## Limits

- **No request log.** The Control API has no endpoint that lists individual usage records, so the dashboard shows totals only. A `GET /projects/{id}/usage/recent` endpoint on the gateway would unlock a recent-requests table.
- **Sign-in lives in server memory.** Restarting `reflex run` signs you out. Tokens last eight hours.
- **Playground is non-streaming.**
- **Read-only where the API is read-only.** There are no edit or disable endpoints for providers and models, so the console can't offer them.

## Troubleshooting

- **"Can't reach the gateway"**: start the gateway, or set `GATEWAY_URL`.
- **Port already in use**: change `frontend_port` or `backend_port` in `rxconfig.py`.
- **Blank page after an update**: stop the console, delete the `.web` folder, run `reflex run` again.
- **Errors on first run**: Reflex's API changes between versions. Paste the error with your `pip show reflex` version.
