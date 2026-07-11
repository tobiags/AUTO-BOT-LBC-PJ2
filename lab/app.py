import asyncio
import hashlib
import ipaddress
import json
import os
import secrets
import socket
import time
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="AutoTransfert Experimental Lab", version="0.1.0")
REPORT_DIR = Path("/runtime/reports")


class DiagnosticRequest(BaseModel):
    engine: str
    url: HttpUrl


def _authorize(token: str | None) -> None:
    expected = os.environ.get("LAB_API_TOKEN", "")
    if not expected or token is None or not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def validate_target(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only HTTP(S) targets are accepted")
    allowed = {
        item.strip().lower()
        for item in os.environ.get("LAB_ALLOWED_DOMAINS", "").split(",")
        if item.strip()
    }
    if parsed.hostname.lower() not in allowed:
        raise ValueError("Target domain is not allowlisted")
    for address in socket.getaddrinfo(parsed.hostname, parsed.port or 443):
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Private or reserved target addresses are forbidden")
    return raw_url


def classify_page(title: str, text: str) -> str:
    sample = f"{title} {text[:3000]}".lower()
    markers = ("captcha", "datadome", "verify you are human", "challenge")
    return "intervention_required" if any(marker in sample for marker in markers) else "completed"


async def run_camoufox(url: str) -> dict:
    from camoufox.async_api import AsyncCamoufox

    started = time.perf_counter()
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        response = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        title = await page.title()
        text = await page.locator("body").inner_text(timeout=10_000)
    return _result("camoufox", url, title, text, response.status if response else None, started)


async def run_obscura(url: str) -> dict:
    started = time.perf_counter()
    process = await asyncio.create_subprocess_exec(
        "obscura", "fetch", url, "--dump", "text", "--quiet",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=60)
    if process.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace")[:500])
    text = stdout.decode(errors="replace")
    return _result("obscura", url, "", text, None, started)


def _result(
    engine: str, url: str, title: str, text: str, http_status: int | None, started: float
) -> dict:
    result = {
        "engine": engine,
        "url": url,
        "status": classify_page(title, text),
        "title": title,
        "http_status": http_status,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "text_length": len(text),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_id = f"{int(time.time())}-{engine}"
    (REPORT_DIR / f"{report_id}.json").write_text(json.dumps(result), encoding="utf-8")
    result["report_id"] = report_id
    return result


@app.get("/health")
async def health(x_lab_token: str | None = Header(default=None)):
    _authorize(x_lab_token)
    return {"status": "ok", "engines": ["camoufox", "obscura"]}


@app.post("/diagnostics")
async def diagnostic(request: DiagnosticRequest, x_lab_token: str | None = Header(default=None)):
    _authorize(x_lab_token)
    try:
        url = validate_target(str(request.url))
        if request.engine == "camoufox":
            return await run_camoufox(url)
        if request.engine == "obscura":
            return await run_obscura(url)
        raise ValueError("Unsupported engine")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/compare")
async def compare(request: DiagnosticRequest, x_lab_token: str | None = Header(default=None)):
    _authorize(x_lab_token)
    url = validate_target(str(request.url))
    results = await asyncio.gather(
        run_camoufox(url), run_obscura(url), return_exceptions=True
    )
    return {
        "url": url,
        "results": [
            result if isinstance(result, dict) else {"status": "failed", "error": str(result)[:500]}
            for result in results
        ],
    }


@app.get("/reports/{report_id}")
async def report(report_id: str, x_lab_token: str | None = Header(default=None)):
    _authorize(x_lab_token)
    if not report_id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid report id")
    path = REPORT_DIR / f"{report_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return json.loads(path.read_text(encoding="utf-8"))
