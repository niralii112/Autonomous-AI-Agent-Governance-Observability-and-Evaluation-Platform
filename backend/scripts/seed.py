"""Seed data for local development. Safe to run many times: existing rows are left alone.

Run from the backend folder:   python scripts/seed.py

Seeds: the four users, 8 tools, 2 agents (finance and support) and the permission matrix.
Policies are added in the next step. IT Operations is intentionally not seeded.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.core.database import get_session_factory  # noqa: E402
from app.core.enums import (  # noqa: E402
    ActionType, ActorType, AgentCategory, AuditEventName, AuditOutcome, ToolSensitivity, UserRole,
)
from app.core.security import hash_password  # noqa: E402
from app.models.agent import Agent  # noqa: E402
from app.models.agent_tool_permission import AgentToolPermission  # noqa: E402
from app.models.tool import Tool  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories import agent_repository, tool_repository, user_repository  # noqa: E402
from app.schemas import AuditEventCreate  # noqa: E402
from app.services.audit_service import record_audit_event  # noqa: E402

MIN_PASSWORD_LENGTH = 12  # spec section 18

# username, email, role, name of the Settings field that holds the password
SEED_USERS = [
    ("admin", "admin@example.test", UserRole.ADMIN, "seed_admin_password"),
    ("reviewer", "reviewer@example.test", UserRole.REVIEWER, "seed_reviewer_password"),
    ("operator", "operator@example.test", UserRole.OPERATOR, "seed_operator_password"),
    ("viewer", "viewer@example.test", UserRole.VIEWER, "seed_viewer_password"),
]


def _password_for(settings: Settings, username: str, field: str) -> str:
    value = getattr(settings, field)
    env_name = field.upper()
    if not value:
        raise SystemExit(f"{env_name} is not set. Put it in .env (see .env.example).")
    if len(value) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"{env_name} must be at least {MIN_PASSWORD_LENGTH} characters.")
    if "CHANGE_ME" in value and settings.app_env not in ("local", "test"):
        raise SystemExit(f"{env_name} still has the CHANGE_ME placeholder.")
    return value


async def seed_users(session: AsyncSession, settings: Settings) -> dict[str, str]:
    """Create the four users. Returns {username: 'created' | 'exists'}."""
    passwords = {name: _password_for(settings, name, field) for name, _, _, field in SEED_USERS}
    result: dict[str, str] = {}
    for username, email, role, _ in SEED_USERS:
        if await user_repository.get_by_username(session, username):
            result[username] = "exists"  # never overwrite an existing password
            continue
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(passwords[username]),
            role=role.value,
        )
        session.add(user)
        await session.flush()
        await record_audit_event(
            session,
            AuditEventCreate(
                event_name=AuditEventName.USER_CREATED,
                actor_type=ActorType.SYSTEM,
                entity_type="user",
                entity_id=user.user_id,
                outcome=AuditOutcome.SUCCESS,
                event_data={"username": username, "role": role.value, "source": "seed"},
            ),
        )
        result[username] = "created"
    return result


# tool_name, category, action type, sensitivity, description  (spec section 15, IT tools left out)
SEED_TOOLS = [
    ("finance_report_reader", AgentCategory.FINANCE, ActionType.FINANCE_GET_REPORT, ToolSensitivity.READ_ONLY,
     "Reads a finance report."),
    ("finance_summary_generator", AgentCategory.FINANCE, ActionType.FINANCE_GENERATE_SUMMARY, ToolSensitivity.READ_ONLY,
     "Generates a finance summary."),
    ("payment_processor_sim", AgentCategory.FINANCE, ActionType.FINANCE_PROPOSE_PAYMENT, ToolSensitivity.WRITE,
     "Simulated payment processor."),
    ("finance_records_vault", AgentCategory.FINANCE, ActionType.FINANCE_ACCESS_SENSITIVE_RECORDS,
     ToolSensitivity.SENSITIVE_READ, "Access to sensitive finance records."),
    ("ticket_reader", AgentCategory.CUSTOMER_SUPPORT, ActionType.SUPPORT_GET_TICKET, ToolSensitivity.READ_ONLY,
     "Reads a support ticket."),
    ("support_response_generator", AgentCategory.CUSTOMER_SUPPORT, ActionType.SUPPORT_GENERATE_RESPONSE,
     ToolSensitivity.READ_ONLY, "Drafts a support response."),
    ("refund_processor_sim", AgentCategory.CUSTOMER_SUPPORT, ActionType.SUPPORT_PROPOSE_REFUND, ToolSensitivity.WRITE,
     "Simulated refund processor."),
    ("customer_info_accessor", AgentCategory.CUSTOMER_SUPPORT, ActionType.SUPPORT_ACCESS_CUSTOMER_INFO,
     ToolSensitivity.SENSITIVE_READ, "Access to customer personal information."),
]

SEED_AGENTS = [
    ("finance-agent-01", AgentCategory.FINANCE, "Finance agent: reports, summaries, payments, sensitive records."),
    ("support-agent-01", AgentCategory.CUSTOMER_SUPPORT, "Customer support agent: tickets, responses, refunds, customer info."),
]


async def seed_registry(session: AsyncSession) -> dict[str, str]:
    """Create the 8 tools, the 2 agents and the permission matrix. Returns {name: 'created' | 'exists'}.

    Permissions are only written for an agent that is created in THIS run, so an admin's
    later changes through PUT /agents/{id}/tool-permissions are never undone by re-seeding.
    Each agent is allowed its own category's 4 tools and explicitly denied the other 4."""
    result: dict[str, str] = {}
    tools: dict[str, Tool] = {}
    for name, category, action_type, sensitivity, description in SEED_TOOLS:
        tool = await tool_repository.get_by_name(session, name)
        if tool is None:
            tool = Tool(tool_name=name, description=description, tool_sensitivity=sensitivity.value,
                        supported_action_type=action_type.value)
            session.add(tool)
            await session.flush()
            await record_audit_event(session, AuditEventCreate(
                event_name=AuditEventName.TOOL_REGISTERED, actor_type=ActorType.SYSTEM, entity_type="tool",
                entity_id=tool.tool_id, outcome=AuditOutcome.SUCCESS,
                event_data={"tool_name": name, "source": "seed"}))
            result[f"tool {name}"] = "created"
        else:
            result[f"tool {name}"] = "exists"
        tools[name] = tool

    category_of_tool = {name: category for name, category, *_ in SEED_TOOLS}
    for agent_name, category, description in SEED_AGENTS:
        if await agent_repository.get_by_name(session, agent_name):
            result[f"agent {agent_name}"] = "exists"
            continue
        agent = Agent(agent_name=agent_name, agent_category=category.value, description=description)
        session.add(agent)
        await session.flush()
        granted, denied = [], []
        for tool_name, tool in tools.items():
            allowed = category_of_tool[tool_name] == category
            session.add(AgentToolPermission(agent_id=agent.agent_id, tool_id=tool.tool_id, is_allowed=allowed))
            (granted if allowed else denied).append(tool_name)
        await session.flush()
        await record_audit_event(session, AuditEventCreate(
            event_name=AuditEventName.AGENT_REGISTERED, actor_type=ActorType.SYSTEM, agent_id=agent.agent_id,
            entity_type="agent", entity_id=agent.agent_id, outcome=AuditOutcome.SUCCESS,
            event_data={"agent_name": agent_name, "source": "seed"}))
        await record_audit_event(session, AuditEventCreate(
            event_name=AuditEventName.AGENT_UPDATED, actor_type=ActorType.SYSTEM, agent_id=agent.agent_id,
            entity_type="agent", entity_id=agent.agent_id, outcome=AuditOutcome.SUCCESS,
            event_data={"changed_fields": ["tool_permissions"], "granted": sorted(granted),
                        "denied": sorted(denied), "source": "seed"}))
        result[f"agent {agent_name}"] = "created"
    return result


async def main() -> None:
    settings = get_settings()
    async with get_session_factory()() as session:
        users = await seed_users(session, settings)
        registry = await seed_registry(session)
        await session.commit()
    for username, state in users.items():
        print(f"user {username}: {state}")
    for name, state in registry.items():
        print(f"{name}: {state}")


if __name__ == "__main__":
    asyncio.run(main())
