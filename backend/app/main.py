import json
from collections.abc import AsyncIterator

import anthropic
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import web
from .config import Settings, get_settings
from .graph import build_graph
from .llm import ClaudeLLM, LLMError, estimate_cost

app = FastAPI(title="Lead Research Agents", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_FOR_NODE = {"research": "researcher", "write": "writer", "review": "reviewer"}


class RunRequest(BaseModel):
    company_url: str = Field(min_length=3, max_length=300)
    offer: str = Field(min_length=10, max_length=2000)
    sender_name: str = Field(default="", max_length=100)
    language: str = Field(default="English", max_length=40)


def get_llm(settings: Settings = Depends(get_settings)):
    return ClaudeLLM(
        anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key),
        model=settings.claude_model,
        effort=settings.claude_effort,
        max_tokens=settings.max_output_tokens,
    )


def get_site_reader(settings: Settings = Depends(get_settings)):
    async def reader(url: str) -> list[dict]:
        return await web.read_site(
            url,
            max_pages=settings.max_pages,
            max_chars=settings.max_chars_per_page,
            timeout=settings.fetch_timeout_seconds,
        )

    return reader


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/runs")
async def run(
    body: RunRequest,
    settings: Settings = Depends(get_settings),
    llm=Depends(get_llm),
    read_site=Depends(get_site_reader),
) -> StreamingResponse:
    """Run the agent team. Streams SSE events: `step` (agent activity), `result`, or `error`."""
    graph = build_graph(
        llm, read_site, max_revisions=settings.max_revisions, approve_score=settings.approve_score
    )

    async def events() -> AsyncIterator[str]:
        state: dict = {"usage": []}
        try:
            async for mode, chunk in graph.astream(
                body.model_dump(), stream_mode=["custom", "updates"]
            ):
                if mode == "custom":
                    yield sse("step", chunk)
                    continue
                for node, update in chunk.items():
                    usage = update.pop("usage", [])
                    state["usage"] += usage
                    state.update(update)
                    yield sse(
                        "step",
                        {"agent": AGENT_FOR_NODE[node], "status": "finished", "output": update},
                    )
            yield sse(
                "result",
                {
                    "profile": state["profile"],
                    "email": state["draft"],
                    "review": state["review"],
                    "approved": state["approved"],
                    "revisions": state.get("revisions", 0),
                    "pages": state["pages"],
                    "cost": estimate_cost(
                        state["usage"], settings.price_input_per_mtok, settings.price_output_per_mtok
                    ),
                },
            )
        except web.FetchError as exc:
            yield sse("error", {"message": str(exc)})
        except LLMError as exc:
            yield sse("error", {"message": str(exc)})
        except anthropic.AuthenticationError:
            yield sse("error", {"message": "The Claude API key is missing or invalid."})
        except anthropic.RateLimitError:
            yield sse("error", {"message": "Too many requests right now. Please try again in a minute."})
        except anthropic.APIStatusError as exc:
            yield sse("error", {"message": f"Claude API error ({exc.status_code})."})
        except anthropic.APIConnectionError:
            yield sse("error", {"message": "Could not reach the Claude API."})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
