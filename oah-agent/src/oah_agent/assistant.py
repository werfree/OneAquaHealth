"""Natural-language One Health assistant over the OAH FHIR repository.

Runs an OpenAI tool-calling loop against the typed FHIR tools in `tools.py`.
The model never writes a FHIR URL; it chooses a tool and arguments, and this
code builds and issues the query. Every tool result carries the `fhir_url` it
called, and the assistant is instructed to cite those, so any claim it makes is
checkable against the server.

Two things keep the output honest, and they are different in kind:
  - the system prompt, which *asks* the model not to invent figures, and
  - `grounding.check`, which *verifies* mechanically that it didn't.

Only the second is evidence. Every answer carries its grounding verdict.

Credentials come from `OPENAI_API_KEY` in the environment (the repo's `.env` is
gitignored). Nothing here embeds a key.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Callable, Dict, List, Optional

from . import grounding
from .tools import TOOL_IMPLEMENTATIONS, TOOL_SCHEMAS

logger = logging.getLogger("OAH_Assistant")

DEFAULT_MODEL = "gpt-4o"
MAX_TOOL_ROUNDS = 8

SYSTEM_PROMPT = """You are the OneAquaHealth One Health analyst. You answer questions about urban stream \
ecosystems and the health of the communities living beside them, using a HL7 FHIR repository that holds \
data conforming to the OneAquaHealth Implementation Guide.

The repository holds three kinds of Observation:
  - observation-indicators-oah: single sensor readings and citizen-science survey answers
  - observation-with-component-oah: readings carrying average/minimum/maximum statistics
  - observation-health-measure-oah: population health and risk measures, each tied to a demographic cohort (Group)

Rules you must follow:
1. Never state a number you did not get from a tool call. If the data is not there, say so plainly.
1a. Thresholds and "safe levels" are numbers too. Call get_thresholds before judging any reading as high,
    safe, or exceeding a limit, and quote the basis it returns. A filter value you chose for a search is NOT
    a threshold - never present it as one.
2. Always call a tool before answering a factual question. Do not answer from memory.
3. When a question links stream condition to human health, use get_site_profile - that is the cross-domain join.
4. Do NOT write URLs, links, or a "Source queries" list. The harness records the exact queries that ran
    and prints them beneath your answer; a URL you compose yourself is a guess and may not exist. Refer to
    data by site id and indicator code instead.
5. Be precise about uncertainty. This is a prototype dataset with few readings; do not describe a single \
reading as a trend, and do not imply causation from co-location. Environmental and health measures sharing \
a site is an association worth investigating, not a causal finding.
6. Keep answers brief and concrete. Lead with the direct answer.
7. In a follow-up question, "it", "there" and "that site" refer to whatever the previous turn was about. \
Reuse what you already retrieved rather than re-querying unchanged facts."""


def _client():
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("The assistant needs the OpenAI SDK: pip install openai") from exc

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to .env (gitignored) or export it before running the assistant."
        )
    return OpenAI()


def _run_tool(name: str, arguments: str) -> dict:
    implementation: Optional[Callable] = TOOL_IMPLEMENTATIONS.get(name)
    if implementation is None:
        return {"error": f"unknown tool {name!r}"}
    try:
        kwargs = json.loads(arguments or "{}")
    except json.JSONDecodeError as exc:
        return {"error": f"could not parse arguments for {name}: {exc}"}
    try:
        return implementation(**kwargs)
    except TypeError as exc:
        return {"error": f"bad arguments for {name}: {exc}"}
    except Exception as exc:  # a tool failure is data for the model, not a crash
        logger.exception("Tool %s failed", name)
        return {"error": f"{type(exc).__name__}: {exc}"}


class Conversation:
    """A multi-turn session. Tool results accumulate so follow-ups stay grounded.

    The grounding check for a follow-up runs against every tool result retrieved
    so far in the conversation, not just this turn's -- "and what about the
    cohort there?" legitimately reuses figures fetched two turns ago.
    """

    def __init__(self, *, model: Optional[str] = None, client=None):
        self.model = model or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
        self._client = client
        self.messages: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.tool_results: List[object] = []

    @property
    def client(self):
        if self._client is None:
            self._client = _client()
        return self._client

    def ask(self, question: str, *, verbose: bool = False) -> Dict[str, object]:
        self.messages.append({"role": "user", "content": question})
        trace: List[dict] = []

        for _ in range(MAX_TOOL_ROUNDS):
            response = self.client.chat.completions.create(
                model=self.model, messages=self.messages, tools=TOOL_SCHEMAS, tool_choice="auto"
            )
            choice = response.choices[0].message
            self.messages.append(choice.model_dump(exclude_none=True))

            if not choice.tool_calls:
                answer = choice.content or ""
                return {
                    "answer": answer,
                    "trace": trace,
                    "model": self.model,
                    "grounding": grounding.check(answer, self.tool_results),
                }

            for call in choice.tool_calls:
                name = call.function.name
                if verbose:
                    print(f"  -> {name}({call.function.arguments})")
                result = _run_tool(name, call.function.arguments)
                self.tool_results.append(result)
                # Some tools issue several queries and report `fhir_urls`;
                # recording only `fhir_url` left the cross-domain join -- the
                # step that queries most -- looking like it touched nothing.
                urls = result.get("fhir_urls") or ([result["fhir_url"]] if result.get("fhir_url") else [])
                trace.append(
                    {
                        "tool": name,
                        "arguments": call.function.arguments,
                        "fhir_url": result.get("fhir_url"),
                        "fhir_urls": [u for u in urls if u],
                    }
                )
                self.messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result, default=str)[:12000]}
                )

        answer = "Stopped after the maximum number of tool rounds without reaching an answer."
        return {"answer": answer, "trace": trace, "model": self.model, "grounding": grounding.check(answer, [])}


def ask(question: str, *, model: Optional[str] = None, verbose: bool = False) -> Dict[str, object]:
    """Answer one standalone question."""

    return Conversation(model=model).ask(question, verbose=verbose)
