# Kensal House Mama

A household chore & meal-planning tracker built with Flask, with round-robin
chore rotation and a companion **MCP server** so you can ask Claude about
your chores from mobile, web, or desktop.

## Features

- Chore board with drag-to-reorder tasks
- Round-robin rotation across household members per chore
- Weekly meal menu
- Admin panel (password-protected) to manage members, chores, and menus
- MCP server (`mcp_server.py`) exposing chore status as tools for Claude

## Local setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in SECRET_KEY / ADMIN_PASSWORD / MCP_AUTH_TOKEN
python app.py
```

The app defaults to a local SQLite file (`chores.db`) if `DATABASE_URL` is unset.

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

1. Deploy the app so `https://<your-domain>/mcp` is publicly reachable
   (Claude connects from Anthropic's cloud, not your device).
2. Set `MCP_AUTH_TOKEN` in your deployment's environment variables — every
   request must send `Authorization: Bearer <token>`.
3. In Claude, go to **Settings → Connectors → Add custom connector** and
   enter your server URL (`https://<your-domain>/mcp`).
4. Enable the connector in a conversation and ask Claude things like
   "What chores are pending?" or "Mark dishes as done."

> The bearer-token check here is a minimal starting point. For a public
> deployment, consider adding a full OAuth 2.1 flow per the
> [MCP authorization spec](https://modelcontextprotocol.io/docs/develop/build-server).

## License

[MIT](LICENSE)
