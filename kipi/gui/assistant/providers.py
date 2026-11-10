"""Model providers for the assistant.

Most vendors speak OpenAI's ``/chat/completions`` API (DeepSeek, Qwen, GLM, Kimi, Gemini's
compatibility endpoint, Ollama and any local server); Anthropic speaks its own
``/messages`` API. Both are driven from the same neutral conversation below, so the panel
and the tools do not care which one answers.

The request goes through Qt's network stack on the UI thread, asynchronously: no worker
thread, and the window keeps repainting while a model thinks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from qtpy.QtCore import QByteArray, QObject, QSettings, QUrl, Signal
from qtpy.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

#: Provider presets: the base URL, a sensible model and the API shape. Users can edit
#: the URL and model for any of them (an OpenAI-compatible gateway, a proxy, ...).
PRESETS: Dict[str, Dict[str, str]] = {
    "OpenAI": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini",
               "style": "openai"},
    "Anthropic": {"base_url": "https://api.anthropic.com/v1", "model": "claude-sonnet-5-5",
                  "style": "anthropic"},
    "DeepSeek": {"base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat",
                 "style": "openai"},
    "通义千问": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                 "model": "qwen-plus", "style": "openai"},
    "智谱 GLM": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-plus",
                 "style": "openai"},
    "Kimi": {"base_url": "https://api.moonshot.cn/v1", "model": "moonshot-v1-8k",
             "style": "openai"},
    "Gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "model": "gemini-2.0-flash", "style": "openai"},
    "Ollama": {"base_url": "http://localhost:11434/v1", "model": "qwen2.5:7b",
               "style": "openai"},
    "自定义": {"base_url": "", "model": "", "style": "openai"},
}

#: A sensible output limit per provider when the model list does not say. The dialog
#: starts from these and then lets the model's own metadata override them.
PRESET_MAX_OUTPUT: Dict[str, int] = {
    "OpenAI": 16384,
    "Anthropic": 8192,
    "DeepSeek": 8192,
    "通义千问": 8192,
    "智谱 GLM": 4096,
    "Kimi": 8192,
    "Gemini": 8192,
    "Ollama": 8192,
    "自定义": 8192,
}

#: Best-effort output limits for well-known model families, used when the provider's
#: model list carries no token limits (OpenAI and Anthropic do not publish them there).
_OUTPUT_LIMITS = (
    ("gpt-4.1", 32768),
    ("gpt-4o", 16384),
    ("gpt-4-turbo", 4096),
    ("gpt-4", 8192),
    ("gpt-3.5", 4096),
    ("o1", 100000),
    ("o3", 100000),
    ("o4", 100000),
    ("deepseek-chat", 8192),
    ("deepseek-reasoner", 8192),
    ("qwen", 8192),
    ("glm-4", 4096),
    ("moonshot", 8192),
    ("gemini-2.5", 65536),
    ("gemini", 8192),
    ("claude-3-5", 8192),
    ("claude-3-7", 64000),
    ("claude-opus-4", 32000),
    ("claude-sonnet-4", 64000),
    ("claude-sonnet-5", 64000),
    ("claude", 8192),
    ("llama", 4096),
)


def known_output_limit(model: str) -> int:
    """A known output-token limit for a model id, or 0 when nothing is known."""
    name = model.strip().lower()
    for prefix, limit in _OUTPUT_LIMITS:
        if name.startswith(prefix):
            return limit
    return 0


DEFAULT_PROVIDER = "DeepSeek"
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TURNS = 30


@dataclass
class Config:
    provider: str = DEFAULT_PROVIDER
    name: str = ""
    api_style: str = ""
    base_url: str = PRESETS[DEFAULT_PROVIDER]["base_url"]
    model: str = PRESETS[DEFAULT_PROVIDER]["model"]
    api_key: str = ""
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    max_turns: int = DEFAULT_MAX_TURNS

    @property
    def style(self) -> str:
        """``openai`` or ``anthropic``; the preset's format unless one was chosen."""
        if self.api_style in ("openai", "anthropic"):
            return self.api_style
        return PRESETS.get(self.provider, {}).get("style", "openai")

    @property
    def configured(self) -> bool:
        # A local server (Ollama, vLLM) often needs no key.
        local = any(h in self.base_url for h in ("localhost", "127.0.0.1", "0.0.0.0"))
        return bool(self.base_url and self.model and (self.api_key or local))

    @classmethod
    def load(cls, settings: Optional[QSettings] = None) -> "Config":
        s = settings or QSettings("KiPI", "KiPI")
        provider = str(s.value("assistant/provider", DEFAULT_PROVIDER) or DEFAULT_PROVIDER)
        if provider == "自定义 (OpenAI 兼容)":       # renamed in 1.0.0
            provider = "自定义"
        preset = PRESETS.get(provider, {})
        return cls(
            provider=provider,
            name=str(s.value("assistant/name", "") or ""),
            api_style=str(s.value("assistant/api_style", "") or ""),
            base_url=str(s.value("assistant/base_url", preset.get("base_url", "")) or ""),
            model=str(s.value("assistant/model", preset.get("model", "")) or ""),
            api_key=str(s.value("assistant/api_key", "") or ""),
            max_tokens=int(s.value("assistant/max_tokens", DEFAULT_MAX_TOKENS) or
                           DEFAULT_MAX_TOKENS),
            temperature=float(s.value("assistant/temperature", DEFAULT_TEMPERATURE) or
                              DEFAULT_TEMPERATURE),
            max_turns=int(s.value("assistant/max_turns", DEFAULT_MAX_TURNS) or
                          DEFAULT_MAX_TURNS),
        )

    def save(self, settings: Optional[QSettings] = None) -> None:
        s = settings or QSettings("KiPI", "KiPI")
        for key, value in (("provider", self.provider), ("name", self.name),
                           ("api_style", self.api_style), ("base_url", self.base_url),
                           ("model", self.model), ("api_key", self.api_key),
                           ("max_tokens", self.max_tokens),
                           ("temperature", self.temperature),
                           ("max_turns", self.max_turns)):
            s.setValue(f"assistant/{key}", value)
        s.sync()


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class Turn:
    text: str = ""
    tool_calls: List[ToolCall] = None
    raw: Optional[dict] = None
    thinking: str = ""

    def __post_init__(self):
        self.tool_calls = self.tool_calls or []


def _base_url(config: Config) -> str:
    """The API root, even when the user pasted a full chat/messages endpoint."""
    base = config.base_url.strip().rstrip("/")
    for suffix in ("/chat/completions", "/messages", "/completions", "/responses"):
        if base.endswith(suffix):
            return base[: -len(suffix)].rstrip("/")
    return base


def _endpoint(config: Config) -> str:
    base = _base_url(config)
    return base + ("/messages" if config.style == "anthropic" else "/chat/completions")


def _headers(config: Config) -> Dict[str, str]:
    if config.style == "anthropic":
        return {"x-api-key": config.api_key, "anthropic-version": "2023-06-01",
                "content-type": "application/json"}
    return {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}


def models_endpoint(config: Config) -> str:
    """The provider's model-list URL (``GET /models``)."""
    base = _base_url(config)
    return base if base.endswith("/models") else base + "/models"


_VERSION_IN_PATH = re.compile(r"/v\d", re.IGNORECASE)


def _alternate_models_url(url: str) -> str:
    """A retry URL for a 404: add ``/v1`` when the address has no version path."""
    if not url.endswith("/models"):
        return ""
    base = url[: -len("/models")].rstrip("/")
    if _VERSION_IN_PATH.search(base):
        return ""
    return base + "/v1/models"


def build_models_request(config: Config) -> Tuple[str, Dict[str, str]]:
    """(URL, headers) for the model-list request."""
    headers = {key: value for key, value in _headers(config).items() if value}
    if not config.api_key:
        # A local server (Ollama, vLLM) often has no key; do not send an empty one.
        headers.pop("Authorization", None)
        headers.pop("x-api-key", None)
    return models_endpoint(config), headers


@dataclass
class ModelInfo:
    """One entry from a provider's model list."""

    id: str
    max_output_tokens: int = 0
    context_tokens: int = 0


def _positive_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _max_output_tokens(row: dict) -> int:
    top = row.get("top_provider")
    top = top if isinstance(top, dict) else {}
    limits = row.get("limits")
    limits = limits if isinstance(limits, dict) else {}
    for value in (row.get("max_output_tokens"), row.get("max_completion_tokens"),
                  row.get("max_tokens"), top.get("max_completion_tokens"),
                  limits.get("output"), limits.get("max_output_tokens")):
        number = _positive_int(value)
        if number:
            return number
    return 0


def _context_tokens(row: dict) -> int:
    top = row.get("top_provider")
    top = top if isinstance(top, dict) else {}
    for value in (row.get("context_length"), row.get("context_window"),
                  row.get("max_context_length"), row.get("max_input_tokens"),
                  row.get("max_model_len"), top.get("context_length")):
        number = _positive_int(value)
        if number:
            return number
    return 0


def parse_model_infos(payload: Any, config: Optional[Config] = None) -> List[ModelInfo]:
    """Model ids and any limits from an OpenAI-compatible or Anthropic model list."""
    rows: Any = []
    if isinstance(payload, dict):
        rows = payload.get("data") or payload.get("models") or []
    if not isinstance(rows, list):
        return []
    infos: List[ModelInfo] = []
    seen = set()
    for row in rows:
        if isinstance(row, str):
            info = ModelInfo(row.strip())
        elif isinstance(row, dict):
            name = str(row.get("id") or row.get("name") or row.get("model") or "").strip()
            if not name:
                continue
            info = ModelInfo(name, _max_output_tokens(row), _context_tokens(row))
        else:
            continue
        if not info.id or info.id in seen:
            continue
        if not info.max_output_tokens:
            info.max_output_tokens = known_output_limit(info.id)
        if not info.max_output_tokens and config is not None:
            info.max_output_tokens = PRESET_MAX_OUTPUT.get(config.provider, 0)
        seen.add(info.id)
        infos.append(info)
    return infos


def parse_models(payload: Any) -> List[str]:
    """Model ids from an OpenAI-compatible or Anthropic model list."""
    return [info.id for info in parse_model_infos(payload)]


def _openai_messages(system: str, history: List[dict]) -> List[dict]:
    out = [{"role": "system", "content": system}] if system else []
    for m in history:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            out.append({
                "role": "assistant",
                "content": m.get("content") or None,
                "tool_calls": [{"id": tc["id"], "type": "function",
                                "function": {"name": tc["name"],
                                             "arguments": json.dumps(
                                                 tc.get("arguments") or {},
                                                 ensure_ascii=False)}}
                               for tc in m["tool_calls"]],
            })
        elif role == "tool":
            out.append({"role": "tool", "tool_call_id": m.get("tool_call_id", ""),
                        "content": m.get("content", "")})
        else:
            out.append({"role": role, "content": m.get("content", "")})
    return out


def _anthropic_messages(history: List[dict]) -> List[dict]:
    out: List[dict] = []
    for m in history:
        role = m.get("role")
        if role == "assistant":
            blocks: List[dict] = []
            if m.get("content"):
                blocks.append({"type": "text", "text": m["content"]})
            for tc in m.get("tool_calls") or []:
                blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["name"],
                               "input": tc.get("arguments") or {}})
            out.append({"role": "assistant", "content": blocks or [{"type": "text",
                                                                   "text": "..."}]})
        elif role == "tool":
            block = {"type": "tool_result", "tool_use_id": m.get("tool_call_id", ""),
                     "content": m.get("content", "")}
            last = out[-1] if out else None
            if (last and last.get("role") == "user" and isinstance(last.get("content"), list)
                    and all(b.get("type") == "tool_result" for b in last["content"])):
                last["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        else:
            out.append({"role": "user", "content": m.get("content", "")})
    return out


def build_request(config: Config, system: str, history: List[dict],
                  tools: List[dict]) -> Tuple[str, Dict[str, str], dict]:
    """(URL, headers, JSON body) for one completion request."""
    if config.style == "anthropic":
        body: Dict[str, Any] = {
            "model": config.model,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "system": system,
            "messages": _anthropic_messages(history),
        }
        if tools:
            body["tools"] = [{"name": t["function"]["name"],
                              "description": t["function"].get("description", ""),
                              "input_schema": t["function"].get("parameters",
                                                                {"type": "object",
                                                                 "properties": {}})}
                             for t in tools]
    else:
        body = {
            "model": config.model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "messages": _openai_messages(system, history),
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
    return _endpoint(config), _headers(config), body


def _text_of(value: Any) -> str:
    """Text from a reasoning field that may be a string, dict or list of parts."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "summary", "content", "reasoning"):
            text = _text_of(value.get(key))
            if text:
                return text
        return ""
    if isinstance(value, list):
        parts = [_text_of(item) for item in value]
        return "\n\n".join(part for part in parts if part)
    return ""


def _join_unique(parts: List[str]) -> str:
    out: List[str] = []
    for part in parts:
        part = (part or "").strip()
        if part and part not in out:
            out.append(part)
    return "\n\n".join(out)


def _openai_content(message: dict) -> Tuple[str, str]:
    """The answer and any reasoning, from a chat-completions message."""
    text: List[str] = []
    thinking: List[str] = []
    content = message.get("content")
    if isinstance(content, str):
        text.append(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, str):
                text.append(part)
            elif isinstance(part, dict):
                kind = str(part.get("type") or "")
                if kind in ("thinking", "reasoning", "reasoning_content"):
                    thinking.append(_text_of(part))
                elif kind in ("text", "output_text", ""):
                    text.append(_text_of(part))
    for key in ("reasoning_content", "reasoning", "thinking"):
        if message.get(key):
            thinking.append(_text_of(message[key]))
    if message.get("reasoning_details"):
        thinking.append(_text_of(message["reasoning_details"]))
    return _join_unique(text), _join_unique(thinking)


def parse_response(config: Config, payload: dict) -> Turn:
    """The assistant's text, reasoning and tool calls from a successful response body."""
    if config.style == "anthropic":
        text, thinking, calls = [], [], []
        for block in payload.get("content") or []:
            kind = block.get("type")
            if kind == "text":
                text.append(block.get("text", ""))
            elif kind == "tool_use":
                calls.append(ToolCall(str(block.get("id", "")), str(block.get("name", "")),
                                      block.get("input") or {}))
            elif kind == "thinking":
                thinking.append(str(block.get("thinking") or ""))
            elif kind == "redacted_thinking":
                thinking.append("[加密的思考内容]")
        return Turn(_join_unique(text), calls, payload, _join_unique(thinking))
    try:
        message = (payload.get("choices") or [{}])[0].get("message") or {}
    except (AttributeError, IndexError):
        message = {}
    calls = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function") or {}
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except ValueError:
            args = {}
        calls.append(ToolCall(str(tc.get("id", "")), str(fn.get("name", "")), args))
    text, thinking = _openai_content(message)
    return Turn(text, calls, payload, thinking)


def error_message(payload: Optional[dict], status: int, body: bytes = b"") -> str:
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])
        if isinstance(error, str):
            return error
        if payload.get("message"):
            return str(payload["message"])
    text = body.decode("utf-8", "replace").strip()
    return f"HTTP {status}: {text[:400]}" if text else f"HTTP {status}"


class ChatClient(QObject):
    """One request at a time; emits the parsed JSON body, or an error string."""

    done = Signal(object, str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._reply: Optional[QNetworkReply] = None

    def busy(self) -> bool:
        return self._reply is not None

    def send(self, config: Config, system: str, history: List[dict],
             tools: List[dict]) -> None:
        url, headers, body = build_request(config, system, history, tools)
        request = QNetworkRequest(QUrl(url))
        for key, value in headers.items():
            request.setRawHeader(key.encode("utf-8"), value.encode("utf-8"))
        try:
            request.setTransferTimeout(180_000)
        except AttributeError:          # Qt 5 has no per-request timeout
            pass
        data = QByteArray(json.dumps(body, ensure_ascii=False).encode("utf-8"))
        self._reply = self._nam.post(request, data)
        self._reply.finished.connect(self._finished)

    def abort(self) -> None:
        reply, self._reply = self._reply, None
        if reply is not None:
            reply.abort()
            reply.deleteLater()

    def _finished(self) -> None:
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        body = bytes(reply.readAll())
        status = int(reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) or 0)
        network_error = reply.error() != QNetworkReply.NetworkError.NoError
        error = reply.errorString() if network_error else ""
        reply.deleteLater()
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            payload = None
        if payload is None:
            self.done.emit(None, error or error_message(None, status, body))
        elif status >= 400 or (isinstance(payload, dict) and payload.get("error")):
            self.done.emit(None, error_message(payload, status, body))
        else:
            self.done.emit(payload, "")


def _model_list_error(payload: Optional[dict], status: int, body: bytes,
                      network_error: str, url: str) -> str:
    if status == 404:
        detail = ("HTTP 404：接口不存在，请检查接口地址（可能需要 /v1），"
                  "或该服务不提供 /models 接口")
    elif payload is None:
        detail = (error_message(None, status, body) if status
                  else (network_error or "网络请求失败"))
    else:
        detail = error_message(payload, status, body)
        if status:
            detail = f"HTTP {status}：{detail}"
    return f"{detail}；请求：{url}" if url else detail


class ModelListClient(QObject):
    """Fetches a provider's model list; emits ``(models, error)``."""

    done = Signal(object, str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._reply: Optional[QNetworkReply] = None
        self._config: Optional[Config] = None
        self._headers: Dict[str, str] = {}
        self._url = ""
        self._retried = False
        #: The URL that answered the last successful request (after a /v1 retry).
        self.resolved_url = ""

    def busy(self) -> bool:
        return self._reply is not None

    def fetch(self, config: Config) -> None:
        if self._reply is not None:
            return
        self._config = config
        self._retried = False
        url, headers = build_models_request(config)
        self._headers = headers
        self._start(url)

    def _start(self, url: str) -> None:
        self._url = url
        request = QNetworkRequest(QUrl(url))
        for key, value in self._headers.items():
            request.setRawHeader(key.encode("utf-8"), value.encode("utf-8"))
        try:
            request.setTransferTimeout(30_000)
        except AttributeError:          # Qt 5 has no per-request timeout
            pass
        self._reply = self._nam.get(request)
        self._reply.finished.connect(self._finished)

    def abort(self) -> None:
        reply, self._reply = self._reply, None
        if reply is not None:
            reply.abort()
            reply.deleteLater()

    def _finished(self) -> None:
        reply = self._reply
        self._reply = None
        if reply is None:
            return
        body = bytes(reply.readAll())
        status = int(reply.attribute(QNetworkRequest.HttpStatusCodeAttribute) or 0)
        network_error = reply.error() != QNetworkReply.NetworkError.NoError
        error = reply.errorString() if network_error else ""
        reply.deleteLater()
        url = self._url
        try:
            payload = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            payload = None

        if status == 404 and not self._retried:
            alternate = _alternate_models_url(url)
            if alternate:
                self._retried = True
                self._start(alternate)
                return

        config, self._config = self._config, None
        self._url = ""
        if payload is None:
            self.resolved_url = ""
            self.done.emit([], _model_list_error(None, status, body, error, url))
            return
        if status >= 400 or (isinstance(payload, dict) and payload.get("error")):
            self.resolved_url = ""
            self.done.emit([], _model_list_error(payload, status, body, error, url))
            return
        self.resolved_url = url
        self.done.emit(parse_model_infos(payload, config), "")
