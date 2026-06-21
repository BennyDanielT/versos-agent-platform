"""NAT workflow embedding: build workflows once, run them in-process per request.

This is the seam between FastAPI and NAT. The agentic routes (triage, ask) call
`run_workflow`; everything else is plain SQL and never touches NAT.
"""
from contextlib import AsyncExitStack

from fastapi import Request

from nat.runtime.loader import load_workflow


class NatWorkflows:
    """Holds the long-lived session managers for our workflows (built once at startup)."""

    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self.triage = None
        self.agent = None

    async def startup(self, triage_config: str, agent_config: str) -> None:
        self.triage = await self._stack.enter_async_context(load_workflow(triage_config))
        self.agent = await self._stack.enter_async_context(load_workflow(agent_config))

    async def shutdown(self) -> None:
        await self._stack.aclose()


async def run_workflow(session_manager, message: str) -> str:
    """Run a NAT workflow in-process and return its string output."""
    async with session_manager.session() as session:
        async with session.run(message) as runner:
            return await runner.result(to_type=str)


# Dependencies: hand routers the right session manager from app.state.
def get_triage(request: Request):
    return request.app.state.nat.triage


def get_agent(request: Request):
    return request.app.state.nat.agent
