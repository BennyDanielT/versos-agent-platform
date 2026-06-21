"""Model-provider layer — real NVIDIA NIM, behind a thin seam.

There is exactly one backend: NVIDIA NIM via `ChatNVIDIA`. No fakes, no mocks.

The seam (`get_structured_llm`) still exists for one reason: the orchestration
should depend on an *interface*, not a vendor SDK. Today that interface is backed
by NIM; swapping to OpenAI or a local model later is a change in this file only,
not in any specialist or graph code. That's the "evaluate many, retire
abstractions" posture — kept honest by actually having a seam, not by pretending
to have alternative backends that don't exist.

Requires `NVIDIA_API_KEY` (free at https://build.nvidia.com). Without it, calls
raise immediately with a clear message rather than silently degrading.
"""
from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from app.config import get_settings

TModel = TypeVar("TModel", bound=BaseModel)


def get_structured_llm(schema: type[TModel]):
    """Return a runnable that maps a prompt to an instance of `schema`.

    `.invoke(prompt)` returns a populated `schema` object — LangChain coerces the
    model's tool/JSON output into our Pydantic type via `with_structured_output`.
    """
    settings = get_settings()
    if not settings.nvidia_api_key:
        raise RuntimeError(
            "NVIDIA_API_KEY is not set. Get a free key at https://build.nvidia.com "
            "and put it in .env as NVIDIA_API_KEY=nvapi-..."
        )

    from langchain_nvidia_ai_endpoints import ChatNVIDIA

    chat = ChatNVIDIA(
        model=settings.nvidia_model,
        base_url=settings.nvidia_base_url,
        api_key=settings.nvidia_api_key,
        temperature=0,  # deterministic-ish: triage should be stable, not creative
    )
    return chat.with_structured_output(schema)
