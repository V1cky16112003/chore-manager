# Kensal House Mama

A household chore & meal-planning tracker built with Flask, with round-robin
chore rotation and a companion **MCP server** so you can ask Claude about
your chores from mobile, web, or desktop.

## Features

- Chore board with drag-to-reorder tasks
- Round-robin rotation across household members per chore
- Weekly meal menu, with a cooked/not-cooked toggle per meal
- Admin panel (password-protected) to manage members, chores, and menus
- MCP server (`mcp_server.py`) exposing chore status as tools for Claude
- SQLite for local dev, Postgres-ready for production (`DATABASE_URL`)

## Tech stack

- **Backend:** Flask, Flask-SQLAlchemy
- **Database:** SQLite (local) / Postgres (production)
- **MCP server:** official Python MCP SDK (Streamable HTTP transport)
- **Deployment:** Vercel (serverless functions)

## Local setup

Requires Python 3.9+.

```bash
git clone https://github.com/<your-username>/chore_manager.git
cd chore_manager
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in SECRET_KEY / ADMIN_PASSWORD / MCP_AUTH_TOKEN
python app.py
```

Open `http://localhost:5000` in your browser. The app defaults to a local
SQLite file (`chores.db`) if `DATABASE_URL` is unset.

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Recommended | Flask session signing key |
| `ADMIN_PASSWORD` | Recommended | Password for the admin panel (`/login_page`) |
| `DATABASE_URL` | Optional | Postgres connection string; falls back to local SQLite |
| `MCP_AUTH_TOKEN` | Required for MCP server | Bearer token clients must send to use the MCP server |

Generate a strong random token/secret with:

```bash
openssl rand -hex 32
```

## Using the app

- **Chore board (`/`)** — see pending chores, who's currently assigned, and
  the weekly meal menu at a glance.
- **Complete a chore** — mark it done from the board (admin only); if the
  chore is recurring, it automatically rotates to the next person.
- **Admin panel** — log in at `/login_page` with `ADMIN_PASSWORD` to add/remove
  household members, add/delete chores, reorder chores or rotation order
  (drag-and-drop), and edit the weekly menu.
- **Ask Claude** — once the [MCP server](#mcp-server) is connected, ask things
  like "Who's next to clean the kitchen?" or "Mark dishes as done."

## Deployment

Configured for [Vercel](https://vercel.com) (see `vercel.json`) with two
serverless functions:

- `app.py` — the Flask web app (`/`)
- `mcp_server.py` — the MCP server (`/mcp`)

Set `DATABASE_URL` (Postgres/Neon), `SECRET_KEY`, `ADMIN_PASSWORD`, and
`MCP_AUTH_TOKEN` as Vercel environment variables.

## MCP server

`mcp_server.py` implements a remote [MCP](https://modelcontextprotocol.io)
server using the official Python SDK's Streamable HTTP transport, so Claude
(including the mobile app) can query and update chores directly. See
[`docs/mcp-architecture.md`](docs/mcp-architecture.md) for the full
architecture and data flow.

### Tools exposed

| Tool | Description |
|---|---|
| `list_chores` | List chores, optionally filtered by status |
| `get_chore_status` | Look up a chore's status/assignee/rotation by title |
| `get_next_assignee` | Who's next in a chore's rotation, without changing anything |
| `list_household_members` | List registered household members |
| `mark_chore_done` | Mark a chore done, advancing the rotation if recurring |
| `assign_chore` | Manually assign a chore to a specific rotation member |
| `add_household_member` | Add a new household member |
| `remove_household_member` | Remove a household member (reassigns their chores) |
| `add_chore` | Add a new recurring chore with a rotation |
| `remove_chore` | Delete a chore |

All tools are available to any client holding `MCP_AUTH_TOKEN` — there is no
separate read-only vs. admin scope. Treat the token as full admin access to
your household data.

### Run it locally

```bash
MCP_AUTH_TOKEN=my-local-token python mcp_server.py
```

This starts the server on `http://localhost:8001/mcp`.

### Connect it to Claude

The server authenticates every request with a bearer token, so you need it
publicly deployed and the token in hand before adding the connector.

**1. Deploy and set the token**

- Deploy the app (e.g. to Vercel — see [Deployment](#deployment)) so
  `https://<your-domain>/mcp` is publicly reachable. Claude connects from
  Anthropic's cloud, not your device, so `localhost` won't work here.
- Generate a token and set it as `MCP_AUTH_TOKEN` in your deployment's
  environment variables:

  ```bash
  openssl rand -hex 32
  ```

- Redeploy so the environment variable takes effect.

**2. Add the connector — Claude web/desktop app**

1. Go to **Settings → Connectors → Add custom connector**.
2. **Name:** anything you like (e.g. "Chore Manager").
3. **URL:** `https://<your-domain>/mcp`.
4. Under authentication, choose **Bearer token** (or equivalent) and paste
   your `MCP_AUTH_TOKEN` value. If the UI you're using only accepts a bare
   URL, append the token as a query parameter instead:
   `https://<your-domain>/mcp?token=<your-token>`.
5. Save, then enable the connector in a conversation via the tools/connector
   picker.

**3. Add the connector — Claude mobile app**

1. Open **Settings → Connectors → Add custom connector**.
2. Enter the same URL and token as above (mobile currently only supports the
   query-parameter form: `https://<your-domain>/mcp?token=<your-token>`).
3. Enable it for your conversation.

**4. Verify it works**

Ask Claude something like:

- "What chores are pending?"
- "Who's next to clean the kitchen?"
- "Mark dishes as done."

If Claude reports it can't reach the server, double-check the deployment is
live at `/mcp` (a bare `GET` should return `401 Unauthorized`, not `404`) and
that the token matches exactly what's set in your deployment's environment
variables.

> The bearer-token check here is a minimal starting point. For a public
> deployment, consider adding a full OAuth 2.1 flow per the
> [MCP authorization spec](https://modelcontextprotocol.io/docs/develop/build-server).

## Contributing

Issues and pull requests are welcome. For anything non-trivial, please open
an issue first to discuss what you'd like to change.

## License

[MIT](LICENSE)
