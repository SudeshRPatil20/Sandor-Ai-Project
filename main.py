import os
import asyncio
import logging
import json
import sqlite3
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv
import smtplib
from email.message import EmailMessage


load_dotenv()


GOOGLE_GEMINI_API_KEYS = os.getenv("GOOGLE_GEMINI_API_KEYS", "")
GEMINI_KEYS: List[str] = [k.strip() for k in GOOGLE_GEMINI_API_KEYS.split(",") if k.strip()]

GEMINI_API_ENDPOINT = os.getenv("GEMINI_API_ENDPOINT", "https://api.google.com/gemini/generate")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.0") 


SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
DEFAULT_WARNING_TO = os.getenv("WARNING_TO_EMAIL")  

WATCH_KEYS_INDICES = {5, 8, 10}  #


REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS") or 20)
MAX_TOTAL_RETRIES_PER_PROMPT = int(os.getenv("MAX_TOTAL_RETRIES_PER_PROMPT") or 30)
BASE_BACKOFF_SECONDS = float(os.getenv("BASE_BACKOFF_SECONDS") or 1.0)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gemini-rotator")


SQLITE_DB = os.getenv("SQLITE_DB_PATH", "warnings_state.db")


def init_db():
    conn = sqlite3.connect(SQLITE_DB)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS key_notifications (
            key_index INTEGER PRIMARY KEY,
            notified_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def get_notified_keys() -> set:
    conn = sqlite3.connect(SQLITE_DB)
    c = conn.cursor()
    c.execute("SELECT key_index FROM key_notifications")
    rows = c.fetchall()
    conn.close()
    return {r[0] for r in rows}

def mark_key_notified(key_index: int):
    conn = sqlite3.connect(SQLITE_DB)
    c = conn.cursor()
    now = datetime.utcnow().isoformat() + "Z"
    c.execute(
        "INSERT OR REPLACE INTO key_notifications (key_index, notified_at) VALUES (?, ?)",
        (key_index, now),
    )
    conn.commit()
    conn.close()


init_db()


app = FastAPI(title="Gemini Key-Rotating Prompt Server (FastAPI)")

class GenerateRequest(BaseModel):
    prompt: str
    email_to: Optional[str] = None
    
    metadata: Optional[dict] = None

class GeminiResponse(BaseModel):
    success: bool
    key_used_index: Optional[int]
    raw_response: Optional[dict] = None
    error: Optional[str] = None


def send_warning_email(subject: str, body: str, to_email: str):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and to_email):
        logger.warning("SMTP not fully configured or no recipient; skipping email")
        return False

    msg = EmailMessage()
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        logger.info(f"Warning email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.exception(f"Failed to send warning email: {e}")
        return False


async def call_gemini_with_key(key: str, prompt: str, metadata: Optional[dict] = None) -> httpx.Response:
    """
    Sends a request to Gemini. Adjust payload to Gemini's real REST API.
    Returns httpx.Response
    """
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


    payload = {
        "model": GEMINI_MODEL,
        "prompt": prompt,
        "max_tokens": 800,
        "temperature": 0.2,
    }
    if metadata:
        payload["metadata"] = metadata

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        resp = await client.post(GEMINI_API_ENDPOINT, headers=headers, json=payload)
        return resp
@app.post("/generate", response_model=GeminiResponse)
async def generate(req: GenerateRequest):
    """
    Try each key in order. If a key returns a rate-limit error, rotate to the next key.
    If keys #5, #8, #10 are used for the first time (i.e., we attempted them and received rate-limit),
    send an email notification (exact text per assignment).
    """

    if not GEMINI_KEYS:
        raise HTTPException(status_code=500, detail="No Gemini API keys configured.")

    email_to = req.email_to or DEFAULT_WARNING_TO
    prompt = req.prompt
    metadata = req.metadata

    total_attempts = 0
    last_error = None
    notified_keys = get_notified_keys()

    for idx, key in enumerate(GEMINI_KEYS, start=1):

        if total_attempts >= MAX_TOTAL_RETRIES_PER_PROMPT:
            break

        try:
            total_attempts += 1
            logger.info(f"Attempting Gemini request with key index {idx}/{len(GEMINI_KEYS)} (attempt #{total_attempts})")
            resp = await call_gemini_with_key(key, prompt, metadata)
        except httpx.RequestError as e:
            logger.exception(f"Network error using key index {idx}: {e}")
            last_error = str(e)

            await asyncio.sleep(BASE_BACKOFF_SECONDS * (1.5 ** (total_attempts - 1)))
            continue


        status = resp.status_code
        text = resp.text
        try:
            payload = resp.json()
        except Exception:
            payload = {"raw_text": text}

        if 200 <= status < 300:
            logger.info(f"Successful response with key index {idx}")
            return GeminiResponse(success=True, key_used_index=idx, raw_response=payload)


        is_rate_limit = False

        if status == 429:
            is_rate_limit = True
        else:

            body_str = json.dumps(payload) if isinstance(payload, dict) else str(payload)
            lower = body_str.lower()
            if "ratelimit" in lower or "rate limit" in lower or "ratelimitexceeded" in lower or "quota" in lower:
                is_rate_limit = True

        if is_rate_limit:
            logger.warning(f"Rate limit detected for key index {idx}.")
            last_error = f"Rate limit for key index {idx}"

            if idx in WATCH_KEYS_INDICES and idx not in notified_keys:
                subject = f"API Key #{idx} has reached its limit. Please prepare the next batch of 10 keys."
                body = (
                    f"Automated alert: API Key #{idx} (1-based index) triggered a rate limit response at {datetime.utcnow().isoformat()}Z.\n\n"
                    "Please prepare the next batch of 10 keys and rotate them into your environment variables.\n\n"
                    "This is an automated notification from the Gemini key-rotating server."
                )
                sent = send_warning_email(subject, body, email_to)
                if sent:
                    mark_key_notified(idx)
                else:
                    logger.warning(f"Failed to send notification for key {idx}. Continuing rotation.")

            await asyncio.sleep(BASE_BACKOFF_SECONDS * (1.5 ** (total_attempts - 1)))
            continue


        logger.error(f"Non-success status {status} for key index {idx}. Body: {payload}")
        last_error = f"Status {status}: {payload}"

        if status in (401, 403):
            logger.info(f"Auth error for key index {idx}. Trying next key.")
            await asyncio.sleep(0.2)
            continue

        if 500 <= status < 600:
            await asyncio.sleep(BASE_BACKOFF_SECONDS * (1.5 ** (total_attempts - 1)))
            continue


        break


    logger.error("All keys exhausted or retries exceeded.")
    raise HTTPException(status_code=502, detail=f"Failed to generate with any key. Last error: {last_error}")
