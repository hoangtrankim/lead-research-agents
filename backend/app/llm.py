"""One helper that asks Claude for a validated, structured answer and reports token usage."""

from typing import TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    pass


class ClaudeLLM:
    def __init__(self, client: AsyncAnthropic, *, model: str, effort: str, max_tokens: int):
        self.client = client
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    async def structured(self, system: str, user: str, schema: type[T]) -> tuple[T, dict]:
        """Return (parsed answer, {"input_tokens", "output_tokens"})."""
        response = await self.client.beta.messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            output_config={"effort": self.effort},
            # If the model declines on safety grounds, the API retries on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise LLMError("Claude declined this request.")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise LLMError("Claude's answer was cut off or could not be read.")
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return response.parsed_output, usage


def estimate_cost(usage: list[dict], price_in: float, price_out: float) -> dict:
    tokens_in = sum(u["input_tokens"] for u in usage)
    tokens_out = sum(u["output_tokens"] for u in usage)
    return {
        "input_tokens": tokens_in,
        "output_tokens": tokens_out,
        "usd": round((tokens_in * price_in + tokens_out * price_out) / 1_000_000, 4),
    }
