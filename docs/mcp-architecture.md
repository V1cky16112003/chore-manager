# Kensal House Mama — MCP Server Architecture

Remote MCP server exposing chore/household data to Claude (web, desktop, mobile) via a custom connector, per the [MCP Streamable HTTP transport spec](https://modelcontextprotocol.io/docs/develop/build-server) and [Claude custom connector docs](https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp).

```mermaid
flowchart TB
    subgraph ClaudeSide["Anthropic Cloud"]
        User["User<br/>(Claude mobile / web / desktop)"]
        ClaudeApp["Claude"]
        Connector["Custom Connector<br/>(OAuth client)"]
        User --> ClaudeApp --> Connector
    end

    subgraph Vercel["Vercel Deployment (public HTTPS)"]
        subgraph MCPServer["MCP Server (/mcp route)"]
            Transport["Streamable HTTP transport"]
            OAuth["OAuth 2.1 handler<br/>(token issuance/validation)"]
            Tools["Tool handlers:<br/>list_chores<br/>get_chore_status<br/>list_household_members<br/>mark_chore_done (optional)"]
            Transport --> OAuth
            OAuth --> Tools
        end

        FlaskApp["Existing Flask App<br/>(app.py, models.py)"]
        Tools --> FlaskApp
    end

    subgraph DataLayer["Data Layer"]
        DB[("Postgres / Neon DB<br/>Chore, User, ChoreParticipant")]
    end

    Connector <-->|"HTTPS POST/GET<br/>JSON-RPC over Streamable HTTP"| Transport
    FlaskApp --> DB

    classDef cloud fill:#eef2ff,stroke:#6366f1
    classDef server fill:#ecfdf5,stroke:#10b981
    classDef data fill:#fff7ed,stroke:#f97316
    class ClaudeSide cloud
    class MCPServer,Vercel server
    class DataLayer data
```

## Flow

1. **User asks Claude** (any surface, including mobile) about chore status.
2. **Claude** determines the custom connector's tool (e.g. `list_chores`) is relevant and calls it.
3. **Connector** sends an authenticated JSON-RPC request over **Streamable HTTP** to the MCP server's public `/mcp` endpoint — reachable from Anthropic's cloud, not the user's device.
4. **OAuth handler** validates the bearer token/session before allowing tool execution (per MCP auth spec — no shared static secrets over the open internet).
5. **Tool handlers** query existing `models.py` (Chore, User, ChoreParticipant) through the current Flask/SQLAlchemy app.
6. **Postgres (Neon)** returns chore/assignment data, which flows back through the same path to Claude, which renders a natural-language answer.

## Key constraints from official docs

- Must use **Streamable HTTP** (not stdio) since Claude mobile/web only supports remote MCP servers.
- Server must be reachable over the **public internet** — no VPN/firewall-gated access, since requests originate from Anthropic's servers.
- Requires **OAuth 2.1** (or equivalent token auth) — Claude connects on the user's behalf without exposing a password.
- Configured once as a **custom connector** in Claude settings (Customize → Connectors), then toggled on per conversation.
