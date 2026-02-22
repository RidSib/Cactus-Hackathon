"""
cloudNein chat API: local entity extraction (Cactus) + redacted cloud (Gemini).
Encrypt sensitive entities and send to server farm container for processing.
Run from repo root: uvicorn api.main:app --reload
"""
import os
import re
import sys
import urllib.request
import json

# Run from repo root so main is importable
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_REPO_ROOT, ".env"))
except ImportError:
    pass

sys.path.insert(0, os.path.join(_REPO_ROOT, "cactus", "python", "src"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from main import TOOLS, generate_cactus, generate_cactus_chat

# Optional: Fernet for encrypting entity names before sending to server farm
_FERNET = None

def _get_fernet():
    global _FERNET
    if _FERNET is None:
        key = os.environ.get("CLOUDNEIN_SECRET_KEY")
        if not key:
            return None
        try:
            from cryptography.fernet import Fernet
            _FERNET = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception:
            return None
    return _FERNET

def _encrypt_value(plaintext: str) -> str | None:
    f = _get_fernet()
    if not f:
        return None
    try:
        return f.encrypt(plaintext.encode()).decode()
    except Exception:
        return None

def _decrypt_value(ciphertext: str) -> str | None:
    f = _get_fernet()
    if not f:
        return None
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return None

def _encrypt_message_entities(
    message: str, placeholders: list[tuple[str, str]]
) -> tuple[str, list[str], list[dict]]:
    """
    Replace entity values with encrypted ciphertext.
    Returns (message, ciphertexts, encrypted_entities for UI).
    """
    out = message
    ciphertexts = []
    encrypted_entities = []
    for key, value in placeholders:
        if not value:
            continue
        ct = _encrypt_value(value)
        if ct is None:
            continue
        pattern = re.compile(re.escape(value), re.IGNORECASE)
        out = pattern.sub(ct, out)
        ciphertexts.append(ct)
        encrypted_entities.append({"label": key, "value": value, "encrypted": ct})
    return out, ciphertexts, encrypted_entities

SERVER_FARM_URL = os.environ.get(
    "SERVER_FARM_URL", "http://localhost:8001"
)


def _server_farm_request(
    encrypted_message: str,
    ciphertexts: list[str],
    key: str,
) -> str:
    """Send encrypted message + key to server farm container for processing."""
    payload = json.dumps({
        "encrypted_message": encrypted_message,
        "ciphertexts": ciphertexts,
        "key": key,
    }).encode()
    req = urllib.request.Request(
        f"{SERVER_FARM_URL}/process",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
            return data.get("response", "No response from server.")
    except Exception as exc:
        return f"Server farm error: {exc}"

try:
    from google import genai
except ImportError:
    genai = None

app = FastAPI(title="cloudNein API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    source: str
    redacted: bool
    confidence: float | None = None
    tool_calls: list[dict] | None = None
    encrypted_entities: list[dict] | None = None  # [{label, value, encrypted}]
    encrypted_message: str | None = None  # full sentence with ciphertexts in place


def _extract_entities(function_calls: list) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """From Cactus function_calls build placeholder->real mapping and list for order."""
    mapping = {}
    placeholders = []
    company_count = 0
    person_count = 0
    seen = set()
    for call in function_calls:
        name = call.get("name", "")
        args = call.get("arguments") or {}
        if name == "lookup_company_data" and "company" in args:
            val = args["company"]
            if isinstance(val, str) and val.strip() and val not in seen:
                seen.add(val)
                company_count += 1
                key = f"[Company {company_count}]"
                placeholders.append((key, val))
                mapping[key] = val
        elif name == "lookup_person" and "name" in args:
            val = args["name"]
            if isinstance(val, str) and val.strip() and val not in seen:
                seen.add(val)
                person_count += 1
                key = f"[Person {person_count}]"
                placeholders.append((key, val))
                mapping[key] = val
    return mapping, placeholders


def _redact_message(message: str, placeholders: list[tuple[str, str]]) -> str:
    """Replace entity values with placeholders (case-insensitive safe)."""
    out = message
    for key, value in placeholders:
        if not value:
            continue
        # Replace whole-word occurrences
        pattern = re.compile(re.escape(value), re.IGNORECASE)
        out = pattern.sub(key, out)
    return out


def _restore_placeholders(text: str, mapping: dict[str, str]) -> str:
    """Replace placeholders back with real values in the reply."""
    out = text
    for placeholder, value in mapping.items():
        out = out.replace(placeholder, value)
    return out


def _gemini_chat(redacted_message: str, placeholders: list) -> str | None:
    """Get a text reply from Gemini for the redacted message (no tools). Returns None if no key."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or not genai:
        return None
    client = genai.Client(api_key=api_key)
    hint = ""
    if placeholders:
        names = [p[0] for p in placeholders]
        hint = (
            f" The user message used placeholders for privacy: {', '.join(names)}. "
            "Answer naturally; you may refer to them by placeholder."
        )
    contents = [redacted_message + hint]
    model_candidates = ["gemini-3-flash-preview", "gemini-2.5-flash"]
    last_error = None
    for model_name in model_candidates:
        try:
            r = client.models.generate_content(
                model=model_name,
                contents=contents,
            )
            if r and r.candidates:
                for part in r.candidates[0].content.parts:
                    if getattr(part, "text", None):
                        return part.text
            break
        except Exception as exc:
            last_error = exc
    if last_error:
        raise HTTPException(
            status_code=502,
            detail=f"Gemini error: {getattr(last_error, 'message', str(last_error))}",
        )
    return "I couldn't generate a response."


CONFIDENCE_THRESHOLD = 0.7  # Use local reply if confidence >= this


def _normalize_tool_calls(function_calls: list) -> list[dict] | None:
    if not function_calls:
        return None
    return [
        {
            "name": c.get("name", ""),
            "arguments": {
                k: str(v) for k, v in (c.get("arguments") or {}).items()
            },
        }
        for c in function_calls
    ]


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not (req.message and req.message.strip()):
        raise HTTPException(status_code=400, detail="message is required")
    message = req.message.strip()
    messages = [{"role": "user", "content": message}]

    # Always run tool extraction so we can show tool_calls in the UI
    local_tools = generate_cactus(messages, TOOLS)
    function_calls = local_tools.get("function_calls") or []
    tool_calls_out = _normalize_tool_calls(function_calls)
    mapping, placeholders = _extract_entities(function_calls)
    secret_key = os.environ.get("CLOUDNEIN_SECRET_KEY")
    encrypted_message_for_ui = None
    encrypted_entities_for_ui = None
    if secret_key and placeholders:
        encrypted_message_for_ui, _, encrypted_entities_for_ui = (
            _encrypt_message_entities(message, placeholders)
        )

    # Prefer local LLM; fall back to cloud only when needed
    local_chat = generate_cactus_chat(messages)
    local_response = (local_chat.get("response") or "").strip()
    local_conf = local_chat.get("confidence") or 0
    cloud_handoff = local_chat.get("cloud_handoff", True)

    # When we have entities + server key, always route to server farm
    force_server = bool(secret_key and placeholders)
    use_local = (
        local_response
        and not cloud_handoff
        and not force_server
        and local_conf >= CONFIDENCE_THRESHOLD
    )
    if use_local:
        return ChatResponse(
            response=local_response,
            source="on-device",
            redacted=False,
            confidence=float(local_conf),
            tool_calls=tool_calls_out,
            encrypted_entities=encrypted_entities_for_ui,
            encrypted_message=encrypted_message_for_ui,
        )

    # Fallback: encrypt and send to server farm (mocked), or redact and Gemini
    confidence = local_tools.get("confidence")
    redacted = len(placeholders) > 0

    encrypted_entities_out = None
    if secret_key and placeholders:
        ciphertexts = [e["encrypted"] for e in encrypted_entities_for_ui]
        reply = _server_farm_request(
            encrypted_message_for_ui, ciphertexts, secret_key,
        )
        encrypted_entities_out = encrypted_entities_for_ui
        source = "server farm"
    else:
        redacted_message = _redact_message(message, placeholders) if placeholders else message
        reply = _gemini_chat(redacted_message, placeholders)
        if reply is not None:
            if mapping:
                reply = _restore_placeholders(reply, mapping)
            source = "cloud (fallback)"
        else:
            parts = [
                "No cloud API key set. Your message was processed locally."
            ]
            if placeholders:
                parts.append(
                    " Detected: " + ", ".join(
                        f"{k} → {v}" for k, v in placeholders
                    ) + "."
                )
            parts.append(
                " Set GEMINI_API_KEY for Gemini or CLOUDNEIN_SECRET_KEY for "
                "encrypted server farm."
            )
            reply = "".join(parts)
            source = "on-device only"

    return ChatResponse(
        response=reply,
        source=source,
        redacted=redacted,
        confidence=float(confidence) if confidence is not None else None,
        tool_calls=tool_calls_out,
        encrypted_entities=encrypted_entities_out or encrypted_entities_for_ui,
        encrypted_message=encrypted_message_for_ui,
    )
