"""MCP server exposing Kensal House Mama chore data to MCP clients (e.g. Claude).

Built with the official Python MCP SDK (`mcp`) using the Streamable HTTP
transport, per https://modelcontextprotocol.io/docs/develop/build-server.

Run standalone for local testing:
    python mcp_server.py

Deployed on Vercel as a separate serverless function at /mcp (see vercel.json).
"""
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import app as flask_app
from models import Chore, User, ChoreParticipant, db

MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN")

mcp = FastMCP("kensal-house-mama")


@mcp.tool()
def list_chores(status: str = "pending") -> list[dict]:
    """List household chores, optionally filtered by status ('pending' or 'completed')."""
    with flask_app.app_context():
        query = Chore.query
        if status:
            query = query.filter_by(status=status)
        chores = query.order_by(Chore.display_order, Chore.id).all()
        return [
            {
                "id": c.id,
                "title": c.title,
                "status": c.status,
                "points": c.points,
                "assigned_to": c.assigned_to.name if c.assigned_to else None,
                "is_recurring": c.is_recurring,
            }
            for c in chores
        ]


@mcp.tool()
def get_chore_status(chore_title: str) -> dict:
    """Look up a single chore by (partial, case-insensitive) title and return its status and assignee."""
    with flask_app.app_context():
        chore = Chore.query.filter(Chore.title.ilike(f"%{chore_title}%")).first()
        if not chore:
            return {"error": f"No chore found matching '{chore_title}'"}
        return {
            "id": chore.id,
            "title": chore.title,
            "status": chore.status,
            "assigned_to": chore.assigned_to.name if chore.assigned_to else None,
            "rotation": [p.user.name for p in chore.participants_association],
        }


@mcp.tool()
def list_household_members() -> list[dict]:
    """List all household members registered in the app."""
    with flask_app.app_context():
        users = User.query.all()
        return [{"id": u.id, "name": u.name} for u in users]


def _find_chore(chore_title: str) -> Optional[Chore]:
    return Chore.query.filter(Chore.title.ilike(f"%{chore_title}%")).first()


def _find_user(name: str) -> Optional[User]:
    return User.query.filter(User.name.ilike(f"%{name}%")).first()


@mcp.tool()
def get_next_assignee(chore_title: str) -> dict:
    """Return who is next in the rotation for a recurring chore (the person after the current assignee), without changing anything."""
    with flask_app.app_context():
        chore = _find_chore(chore_title)
        if not chore:
            return {"error": f"No chore found matching '{chore_title}'"}
        if not chore.is_recurring or not chore.participants_association:
            return {"error": f"'{chore.title}' is not a recurring rotation chore"}

        assoc = chore.participants_association
        current_idx = next(
            (i for i, p in enumerate(assoc) if p.user_id == chore.assigned_to_id), -1
        )
        next_idx = (current_idx + 1) % len(assoc) if current_idx != -1 else 0
        return {
            "chore": chore.title,
            "current_assignee": chore.assigned_to.name if chore.assigned_to else None,
            "next_assignee": assoc[next_idx].user.name,
        }


@mcp.tool()
def mark_chore_done(chore_title: str) -> dict:
    """Mark a chore as completed by (partial, case-insensitive) title. Advances round-robin rotation if recurring."""
    with flask_app.app_context():
        chore = _find_chore(chore_title)
        if not chore:
            return {"error": f"No chore found matching '{chore_title}'"}

        if chore.is_recurring and chore.participants_association:
            assoc = chore.participants_association
            current_idx = next(
                (i for i, p in enumerate(assoc) if p.user_id == chore.assigned_to_id), -1
            )
            next_idx = (current_idx + 1) % len(assoc) if current_idx != -1 else 0
            chore.assigned_to = assoc[next_idx].user
            chore.status = "pending"
        else:
            chore.status = "completed"

        db.session.commit()
        return {
            "id": chore.id,
            "title": chore.title,
            "status": chore.status,
            "assigned_to": chore.assigned_to.name if chore.assigned_to else None,
        }


@mcp.tool()
def assign_chore(chore_title: str, member_name: str) -> dict:
    """Manually assign a chore to a specific household member. The member must already be in the chore's rotation."""
    with flask_app.app_context():
        chore = _find_chore(chore_title)
        if not chore:
            return {"error": f"No chore found matching '{chore_title}'"}

        user = _find_user(member_name)
        if not user:
            return {"error": f"No household member found matching '{member_name}'"}

        if chore.is_recurring and not any(
            p.user_id == user.id for p in chore.participants_association
        ):
            return {"error": f"'{user.name}' is not in the rotation for '{chore.title}'"}

        chore.assigned_to = user
        db.session.commit()
        return {"chore": chore.title, "assigned_to": user.name}


@mcp.tool()
def add_household_member(name: str, color: str = "#FF6B6B") -> dict:
    """Add a new household member."""
    with flask_app.app_context():
        if _find_user(name):
            return {"error": f"A member matching '{name}' already exists"}
        user = User(name=name, color=color)
        db.session.add(user)
        db.session.commit()
        return {"id": user.id, "name": user.name, "color": user.color}


@mcp.tool()
def remove_household_member(name: str) -> dict:
    """Remove a household member. Any chores currently assigned to them fall to the next person in their rotation."""
    with flask_app.app_context():
        user = _find_user(name)
        if not user:
            return {"error": f"No household member found matching '{name}'"}

        ChoreParticipant.query.filter_by(user_id=user.id).delete()

        chores = Chore.query.filter_by(assigned_to_id=user.id).all()
        for chore in chores:
            chore.assigned_to = chore.participants_association[0].user if chore.participants_association else None

        removed_name = user.name
        db.session.delete(user)
        db.session.commit()
        return {"removed": removed_name}


@mcp.tool()
def add_chore(title: str, participant_names: list[str], points: int = 10) -> dict:
    """Add a new recurring chore with a round-robin rotation across the given household members (in order)."""
    with flask_app.app_context():
        users = []
        for name in participant_names:
            user = _find_user(name)
            if not user:
                return {"error": f"No household member found matching '{name}'"}
            users.append(user)

        if not users:
            return {"error": "At least one participant is required"}

        max_order = db.session.query(db.func.max(Chore.display_order)).scalar() or 0
        chore = Chore(
            title=title,
            points=points,
            assigned_to=users[0],
            is_recurring=True,
            display_order=max_order + 1,
        )
        db.session.add(chore)
        db.session.flush()

        for idx, user in enumerate(users):
            db.session.add(ChoreParticipant(chore_id=chore.id, user_id=user.id, rotation_order=idx))

        db.session.commit()
        return {"id": chore.id, "title": chore.title, "rotation": [u.name for u in users]}


@mcp.tool()
def remove_chore(chore_title: str) -> dict:
    """Delete a chore by (partial, case-insensitive) title."""
    with flask_app.app_context():
        chore = _find_chore(chore_title)
        if not chore:
            return {"error": f"No chore found matching '{chore_title}'"}
        removed_title = chore.title
        db.session.delete(chore)
        db.session.commit()
        return {"removed": removed_title}


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Requires the configured token via `Authorization: Bearer <token>` header
    OR a `?token=<token>` query parameter.

    The query-param fallback exists because Claude's mobile/web custom
    connector UI only supports OAuth, not a raw bearer-token field - so the
    token is embedded directly in the connector URL instead:
    https://<your-domain>/mcp?token=<token>

    Skipped entirely if MCP_AUTH_TOKEN is unset (local dev convenience) - always
    set it in production so the server isn't open to the public internet.
    """

    async def dispatch(self, request: Request, call_next):
        if MCP_AUTH_TOKEN:
            auth_header = request.headers.get("authorization", "")
            token_param = request.query_params.get("token", "")
            if auth_header != f"Bearer {MCP_AUTH_TOKEN}" and token_param != MCP_AUTH_TOKEN:
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await call_next(request)


# Streamable HTTP ASGI app. Deployed behind /mcp on Vercel (see vercel.json),
# so the public URL clients use is https://<your-domain>/mcp
app = mcp.streamable_http_app()
app.add_middleware(BearerAuthMiddleware)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8001)))
