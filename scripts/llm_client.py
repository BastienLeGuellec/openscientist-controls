"""LLM client used to code the reports (scripts/audit_reports.py uses OpenRouterBackend).

Verbatim copy of an LLM-client module written earlier by the first author; only this docstring, the OpenRouter
app title and the load_dotenv helper at the end were changed, so the coding calls behave exactly as when the reports were coded.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

# $ per million tokens: (input, output, cache_read). Cache writes (5-minute TTL)
# cost 1.25x input. Prices from the Claude API docs as of 2026-10; approximate.
PRICES = {
    "claude-fable-5-1": (10.0, 50.0, 0.25),
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
    "scripted": (0.0, 0.0, 0.0),
}
# Models for which we opt into server-side refusal fallbacks ("default" routing).
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class BudgetExceeded(RuntimeError):
    pass


class FatalLLMError(RuntimeError):
    """Configuration or request bug (auth, model access, invalid request): stop the run."""


class TransientLLMError(RuntimeError):
    """Overload, rate limit or network failure that survived the SDK's retries: fail this agent."""


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    content: list            # blocks to append verbatim as the assistant turn
    stop_reason: str
    model: str
    usage: dict = field(default_factory=dict)

    @property
    def tool_calls(self) -> list[ToolCall]:
        out = []
        for b in self.content:
            t = b.get("type") if isinstance(b, dict) else getattr(b, "type", None)
            if t == "tool_use":
                if isinstance(b, dict):
                    out.append(ToolCall(b["id"], b["name"], b["input"]))
                else:
                    out.append(ToolCall(b.id, b.name, b.input))
        return out

    @property
    def text(self) -> str:
        parts = []
        for b in self.content:
            t = b.get("type") if isinstance(b, dict) else getattr(b, "type", None)
            if t == "text":
                parts.append(b["text"] if isinstance(b, dict) else b.text)
        return "\n".join(parts)


class CostTracker:
    def __init__(self, max_cost: float | None, log_path: Path | None):
        self.max_cost = max_cost
        self.total = 0.0
        self.tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
        self.calls = 0
        self._lock = threading.Lock()
        self._log = log_path
        self.stopped: str | None = None    # set on SIGTERM: every agent stops at its next call

    def check(self) -> None:
        if self.stopped:
            raise BudgetExceeded(self.stopped)
        if self.max_cost is not None and self.total >= self.max_cost:
            raise BudgetExceeded(f"spent ${self.total:.2f} >= max_cost ${self.max_cost:.2f}")

    def add(self, model: str, usage: dict, meta: dict) -> float:
        if usage.get("cost") is not None:  # provider-reported (OpenRouter)
            cost = float(usage["cost"])
        else:
            pin, pout, pread = PRICES.get(model, PRICES["claude-opus-5-5"])
            cost = (usage.get("input_tokens", 0) * pin
                    + usage.get("cache_creation_input_tokens", 0) * pin * 1.25
                    + usage.get("cache_read_input_tokens", 0) * pread
                    + usage.get("output_tokens", 0) * pout) / 1e6
        with self._lock:
            self.total += cost
            self.calls += 1
            self.tokens["input"] += usage.get("input_tokens", 0)
            self.tokens["output"] += usage.get("output_tokens", 0)
            self.tokens["cache_read"] += usage.get("cache_read_input_tokens", 0)
            self.tokens["cache_write"] += usage.get("cache_creation_input_tokens", 0)
            if self._log:
                with self._log.open("a") as f:
                    f.write(json.dumps({**meta, "model": model, "usage": usage,
                                        "cost": round(cost, 6), "t": time.time()}) + "\n")
        return cost


class Backend(Protocol):
    name: str

    def create(self, *, role: str, conv_id: str, system: list[dict], tools: list[dict],
               messages: list[dict], max_tokens: int, effort: str, hints: dict) -> LLMResponse: ...


class AnthropicBackend:
    def __init__(self, model: str, max_retries: int = 6):
        import anthropic  # imported lazily so the mock path has no SDK dependency

        self.anthropic = anthropic
        self.client = anthropic.Anthropic(max_retries=max_retries, timeout=600.0)
        self.model = model
        self.name = model

    def create(self, *, role, conv_id, system, tools, messages, max_tokens, effort, hints):
        kwargs: dict[str, Any] = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
            output_config={"effort": effort},
            cache_control={"type": "ephemeral"},  # auto-cache the growing prefix
        )
        if self.model in FALLBACK_MODELS:
            kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        resp = self._call(**kwargs)
        usage = {
            "input_tokens": resp.usage.input_tokens or 0,
            "output_tokens": resp.usage.output_tokens or 0,
            "cache_read_input_tokens": getattr(resp.usage, "cache_read_input_tokens", 0) or 0,
            "cache_creation_input_tokens": getattr(resp.usage, "cache_creation_input_tokens", 0) or 0,
        }
        return LLMResponse(content=list(resp.content), stop_reason=resp.stop_reason or "",
                           model=resp.model, usage=usage)


    def _call(self, **kwargs):
        a = self.anthropic
        try:
            return self.client.beta.messages.create(**kwargs)
        except (a.AuthenticationError, a.PermissionDeniedError, a.NotFoundError, a.BadRequestError) as exc:
            raise FatalLLMError(f"{type(exc).__name__}: {exc}") from exc
        except (a.RateLimitError, a.InternalServerError, a.APIConnectionError, a.APIStatusError) as exc:
            raise TransientLLMError(f"{type(exc).__name__}: {exc}") from exc

    def ping(self) -> None:
        """Cheap request that fails fast on bad credentials or model access."""
        self._call(model=self.model, max_tokens=256, output_config={"effort": "low"},
                   messages=[{"role": "user", "content": "Reply with the single word OK."}])



class _Deadline(Exception):
    """A request that kept its connection open without completing."""

class OpenRouterBackend:
    """Any model on OpenRouter through its OpenAI-compatible chat-completions API.

    Conversations are stored in the same block format as for the Anthropic backend
    and translated on each call. Reasoning details returned by the model are kept
    in the assistant turn and sent back, as OpenRouter recommends for tool use.
    """

    URL = "https://openrouter.ai/api/v1/chat/completions"
    FATAL = {401, 402, 403, 404}
    OFFLINE_WAIT_S = 45 * 60   # how long a call waits for the network to come back

    REQUEST_DEADLINE_S = 900.0     # wall-clock limit for one request, then retry

    def __init__(self, model: str, max_retries: int = 6, timeout: float = 300.0,
                 provider: dict | None = None):
        import os

        # OpenRouter provider routing, e.g. {"sort": "price"} or
        # {"order": ["Wafer"], "allow_fallbacks": False} to pin one host.
        self.provider = {"require_parameters": True, **(provider or {})}

        self.key = os.environ.get("OPENROUTER_API_KEY", "").strip().strip('"').strip("'")
        if not self.key:
            raise FatalLLMError("OPENROUTER_API_KEY is not set (put it in .env or the environment)")
        self.model, self.name = model, model
        self.max_retries, self.timeout = max_retries, timeout

    # ----------------------------------------------------------- translation
    @staticmethod
    def _messages(system: list[dict], messages: list[dict]) -> list[dict]:
        out = [{"role": "system", "content": "\n\n".join(b["text"] for b in system)}]
        for m in messages:
            blocks = [to_jsonable(b) for b in m["content"]]
            if m["role"] == "user":
                texts = []
                for b in blocks:
                    if b["type"] == "tool_result":
                        out.append({"role": "tool", "tool_call_id": b["tool_use_id"], "content": b["content"]})
                    elif b["type"] == "text":
                        texts.append(b["text"])
                if texts:
                    out.append({"role": "user", "content": "\n\n".join(texts)})
                continue
            msg: dict[str, Any] = {"role": "assistant",
                                   "content": "".join(b["text"] for b in blocks if b["type"] == "text")}
            calls = [{"id": b["id"], "type": "function", "function": {
                "name": b["name"],
                "arguments": b["input"].get("__invalid_json__") if "__invalid_json__" in b["input"]
                else json.dumps(b["input"])}} for b in blocks if b["type"] == "tool_use"]
            if calls:
                msg["tool_calls"] = calls
            details = [d for b in blocks if b["type"] == "reasoning_details" for d in b["details"]]
            if details:
                msg["reasoning_details"] = details
            out.append(msg)
        return out

    @staticmethod
    def _tools(tools: list[dict]) -> list[dict]:
        return [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                  "parameters": t["input_schema"]}} for t in tools]

    # ------------------------------------------------------------------ HTTP
    def _post(self, body: dict) -> dict:
        import random
        import urllib.error
        import urllib.request

        data = json.dumps(body).encode()
        last = ""
        attempt = 0
        offline_since = None
        while True:
            req = urllib.request.Request(self.URL, data=data, method="POST", headers={
                "Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                "X-Title": "openscientist-controls"})
            try:
                t0 = time.monotonic()
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    # read as bytes arrive: keep-alive padding can hold a dead request open for hours,
                    # so give up after REQUEST_DEADLINE_S of wall-clock time and retry
                    chunks = []
                    while True:
                        b = r.read1(65536) if hasattr(r, "read1") else r.read()
                        if not b:
                            break
                        chunks.append(b)
                        if time.monotonic() - t0 > self.REQUEST_DEADLINE_S:
                            raise _Deadline(f"no complete response after {self.REQUEST_DEADLINE_S:.0f} s")
                    resp = json.loads(b"".join(chunks))
                offline_since = None
                if "error" in resp and not resp.get("choices"):
                    last = f"provider error: {json.dumps(resp['error'])[:300]}"
                elif not resp.get("choices"):
                    last = "empty response"
                else:
                    return resp
            except urllib.error.HTTPError as exc:
                offline_since = None
                detail = exc.read().decode(errors="replace")[:300]
                if exc.code in self.FATAL:
                    raise FatalLLMError(f"HTTP {exc.code}: {detail}") from exc
                last = f"HTTP {exc.code}: {detail}"
                if exc.code == 400:  # malformed for this conversation: do not retry
                    raise TransientLLMError(last) from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                # The network itself is down (outage, captive portal, certificate for the wrong host):
                # wait it out instead of failing the agent, for up to OFFLINE_WAIT_S.
                last = f"{type(exc).__name__}: {exc}"
                offline_since = offline_since or time.monotonic()
                if time.monotonic() - offline_since < self.OFFLINE_WAIT_S:
                    time.sleep(60 + 10 * random.random())
                    continue
            except (json.JSONDecodeError, _Deadline) as exc:
                last = f"{type(exc).__name__}: {exc}"
            attempt += 1
            if attempt > self.max_retries:
                raise TransientLLMError(last)
            time.sleep(min(60, 2 ** attempt + random.random()))

    def _body(self, system, tools, messages, max_tokens, effort) -> dict:
        body = {
            "model": self.model, "messages": self._messages(system, messages),
            "max_tokens": max_tokens, "usage": {"include": True},
            "reasoning": {"effort": {"xhigh": "high", "max": "high"}.get(effort, effort)},
            "provider": self.provider,
        }
        if tools:
            body["tools"] = self._tools(tools)
        return body

    def create(self, *, role, conv_id, system, tools, messages, max_tokens, effort, hints):
        resp = self._post(self._body(system, tools, messages, max_tokens, effort))
        return self._parse(resp)

    def _parse(self, resp: dict) -> LLMResponse:
        choice = resp["choices"][0]
        msg = choice.get("message") or {}
        content: list[dict] = []
        if msg.get("reasoning_details"):
            content.append({"type": "reasoning_details", "details": msg["reasoning_details"]})
        elif msg.get("reasoning_content") or msg.get("reasoning"):   # vLLM / SGLang reasoning parsers
            content.append({"type": "reasoning_details", "details": [
                {"type": "reasoning.text", "text": msg.get("reasoning_content") or msg.get("reasoning")}]})
        if msg.get("content"):
            content.append({"type": "text", "text": msg["content"]})
        for c in msg.get("tool_calls") or []:
            raw = c["function"].get("arguments") or "{}"
            try:
                args = json.loads(raw)
                if not isinstance(args, dict):
                    raise ValueError
            except ValueError:
                args = {"__invalid_json__": raw}
            content.append({"type": "tool_use", "id": c["id"], "name": c["function"]["name"], "input": args})
        u = resp.get("usage") or {}
        usage = {"input_tokens": u.get("prompt_tokens", 0), "output_tokens": u.get("completion_tokens", 0),
                 "cache_read_input_tokens": (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0,
                 "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0,
                 "cost": u.get("cost"), "provider": resp.get("provider")}
        stop = {"tool_calls": "tool_use", "stop": "end_turn", "length": "max_tokens",
                "content_filter": "refusal"}.get(choice.get("finish_reason"), choice.get("finish_reason") or "")
        if any(b["type"] == "tool_use" for b in content):
            stop = "tool_use" if stop != "max_tokens" else stop
        return LLMResponse(content=content, stop_reason=stop, model=resp.get("model", self.model), usage=usage)

    def ping(self) -> None:
        """Check credentials and that the model returns tool calls."""
        echo = {"name": "echo", "description": "Echo a word.", "input_schema": {
            "type": "object", "properties": {"word": {"type": "string"}}, "required": ["word"]}}
        r = self.create(role="ping", conv_id="ping", system=[{"type": "text", "text": "You are a test."}],
                        tools=[echo], messages=[{"role": "user", "content": [
                            {"type": "text", "text": "Call the echo tool with the word ok."}]}],
                        max_tokens=1024, effort="low", hints={})
        if not r.tool_calls:
            raise FatalLLMError(f"{self.model} did not return a tool call in the preflight check")


class OpenAICompatBackend(OpenRouterBackend):
    """A self-hosted model behind an OpenAI-compatible chat-completions server (vLLM, SGLang,
    TGI, llama.cpp server...). Same translation as OpenRouter, without OpenRouter's fields.

    base_url: e.g. http://localhost:8000/v1. extra_body: model-specific request fields merged
    into every request (e.g. {"chat_template_kwargs": {"enable_thinking": True}}). tool_choice:
    None (server default, "auto") or "required" to force a tool call on every turn.
    The model's past reasoning is kept in transcripts but not sent back to the server.
    """

    FATAL = {401, 403, 404}

    def __init__(self, model: str, base_url: str, api_key_env: str = "LOCAL_API_KEY",
                 extra_body: dict | None = None, tool_choice: str | None = None,
                 max_retries: int = 8, timeout: float = 1200.0):
        import os

        if not base_url:
            raise FatalLLMError("models.base_url is not set (e.g. http://localhost:8000/v1)")
        self.URL = base_url.rstrip("/") + "/chat/completions"
        self.key = os.environ.get(api_key_env, "").strip().strip('"').strip("'") or "EMPTY"
        self.model, self.name = model, model
        self.extra_body = dict(extra_body or {})
        self.tool_choice = tool_choice
        self.provider = None
        self.max_retries, self.timeout = max_retries, timeout

    @staticmethod
    def _messages(system: list[dict], messages: list[dict]) -> list[dict]:
        out = OpenRouterBackend._messages(system, messages)
        for m in out:
            m.pop("reasoning_details", None)
        return out

    def _body(self, system, tools, messages, max_tokens, effort) -> dict:
        body = {"model": self.model, "messages": self._messages(system, messages), "max_tokens": max_tokens,
                **self.extra_body}
        if tools:
            body["tools"] = self._tools(tools)
            if self.tool_choice:
                body["tool_choice"] = self.tool_choice
        return body


def to_jsonable(block: Any) -> Any:
    if isinstance(block, dict):
        return {k: to_jsonable(v) for k, v in block.items()}
    if isinstance(block, list):
        return [to_jsonable(b) for b in block]
    if hasattr(block, "to_dict"):
        return block.to_dict()
    return block


@dataclass
class ToolOutcome:
    text: str
    is_error: bool = False
    terminal: bool = False   # ends the agent's turn sequence (e.g. submit_paper)
    payload: Any = None      # structured result for the orchestrator


class Conversation:
    """One append-only conversation between the simulation and one agent."""

    # extra turns after a submission refused on the last turn (research.grace_steps)
    grace_steps: int = 2

    def __init__(self, backend: Backend, tracker: CostTracker, *, role: str, conv_id: str,
                 system: list[dict], tools: list[dict], effort: str, max_tokens: int,
                 hints: dict | None = None, transcript_dir: Path | None = None):
        self.backend, self.tracker = backend, tracker
        self.role, self.conv_id = role, conv_id
        self.system, self.tools = system, tools
        self.effort, self.max_tokens = effort, max_tokens
        self.hints = hints or {}
        self.messages: list[dict] = []
        self.pending: list[dict] = []   # tool results owed to the last assistant turn
        self.transcript_dir = transcript_dir
        self.n_calls = 0
        self.error: str | None = None

    def _send(self, blocks: list[dict]) -> LLMResponse:
        self.tracker.check()
        self.messages.append({"role": "user", "content": self.pending + blocks})
        self.pending = []
        resp = self.backend.create(role=self.role, conv_id=self.conv_id, system=self.system,
                                   tools=self.tools, messages=self.messages,
                                   max_tokens=self.max_tokens, effort=self.effort,
                                   hints=self.hints)
        self.n_calls += 1
        self.tracker.add(resp.model, resp.usage,
                         {"role": self.role, "conv": self.conv_id, "stop": resp.stop_reason})
        if resp.content:  # a refusal before any output has no content to append
            self.messages.append({"role": "assistant", "content": resp.content})
        return resp

    def run(self, user_text: str, handlers: dict[str, Callable[[dict], ToolOutcome]],
            max_steps: int, nudge: str, max_nudges: int = 2) -> ToolOutcome | None:
        """Drive the tool loop until a terminal tool succeeds or limits are hit.

        Returns the terminal ToolOutcome, or None if the agent never got there.
        The terminal tool's result stays pending and is delivered with the next
        user message if the conversation is resumed (e.g. with reviews).
        """
        try:
            return self._run(user_text, handlers, max_steps, nudge, max_nudges)
        except TransientLLMError as exc:
            self.error = str(exc)
            print(f"[agent failed] {self.conv_id}: {exc}", flush=True)
            return None

    def _run(self, user_text, handlers, max_steps, nudge, max_nudges):
        resp = self._send([{"type": "text", "text": user_text}])
        nudges = 0
        step, limit, graced = -1, max_steps, False
        while step + 1 < limit:
            step += 1
            if resp.stop_reason == "refusal":
                return None
            calls = resp.tool_calls
            if not calls:
                if nudges >= max_nudges:
                    return None
                nudges += 1
                resp = self._send([{"type": "text", "text": nudge}])
                continue
            results, terminal, refused = [], None, False
            for call in calls:
                if resp.stop_reason == "max_tokens":
                    out = ToolOutcome("Your reply was cut off before this call was complete. "
                                      "Keep replies and code shorter.", is_error=True)
                elif call.name not in handlers:
                    out = ToolOutcome(f"Unknown tool {call.name}.", is_error=True)
                elif (problem := self._check_input(call)) is not None:
                    out = ToolOutcome(problem, is_error=True)
                elif terminal is not None:
                    out = ToolOutcome("Ignored: you already submitted.", is_error=True)
                else:
                    try:
                        out = handlers[call.name](call.input)
                    except Exception as exc:  # tool bug or malformed input: tell the agent
                        out = ToolOutcome(f"Tool error: {exc}", is_error=True)
                    if out.terminal and not out.is_error:
                        terminal = out
                    elif out.terminal:             # a submission refused by a format check
                        refused = True
                results.append({"type": "tool_result", "tool_use_id": call.id,
                                "content": out.text, **({"is_error": True} if out.is_error else {})})
            if terminal is not None:
                self.pending = results
                return terminal
            left = limit - step - 1
            if left == 0 and refused and not graced and self.grace_steps:
                # a refusal on the very last turn would otherwise end the study on a technicality
                graced, limit, left = True, limit + self.grace_steps, self.grace_steps
                resp = self._send(results + [{"type": "text", "text": (
                    f"[Your submission was not accepted. You have {left} extra turn(s) to correct it "
                    "and submit again.]")}])
                continue
            if left == 0:
                self.pending = results
                break
            extra = []
            if left <= 3:
                extra = [{"type": "text", "text": f"[{left} turn(s) left. {nudge}]"}]
            resp = self._send(results + extra)
        return None

    def _check_input(self, call: ToolCall) -> str | None:
        """Validate and lightly coerce a tool call's arguments against its schema."""
        if "__invalid_json__" in call.input:
            return "Your tool arguments were not valid JSON. Send them again as a JSON object."
        schema = next((t["input_schema"] for t in self.tools if t["name"] == call.name), None)
        if schema is None:
            return None
        missing = [k for k in schema.get("required", []) if k not in call.input]
        if missing:
            return f"Missing required argument(s): {', '.join(missing)}."
        for k, spec in schema.get("properties", {}).items():
            v = call.input.get(k)
            if spec.get("type") == "array" and isinstance(v, str):
                try:
                    parsed = json.loads(v)
                    call.input[k] = parsed if isinstance(parsed, list) else [v]
                except ValueError:
                    call.input[k] = [v]
            elif spec.get("type") == "integer" and isinstance(v, (str, float)):
                try:
                    call.input[k] = int(float(v))
                except ValueError:
                    return f"Argument {k} must be an integer."
        return None

    def save(self) -> None:
        if not self.transcript_dir:
            return
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        path = self.transcript_dir / f"{self.conv_id}.json"
        path.write_text(json.dumps({
            "conv_id": self.conv_id, "role": self.role, "error": self.error,
            "system": self.system, "messages": to_jsonable(self.messages),
        }, indent=1, default=str))


def load_dotenv(path: Path = Path(".env")) -> None:
    """Put KEY=VALUE lines from .env into the environment, without overriding what is set."""
    import os
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    if not os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("CLAUDE_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = os.environ["CLAUDE_API_KEY"]
