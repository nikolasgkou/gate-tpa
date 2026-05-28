import asyncio
import json
import logging
import os
import threading

import requests
import websockets
from flask import Flask, Response, request
from openai import InvalidWebhookSignatureError, OpenAI


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gate-ai-agent")

app = Flask(__name__)
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY", "webhook-only-placeholder"),
    webhook_secret=os.environ["OPENAI_WEBHOOK_SECRET"],
)

AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
AZURE_OPENAI_API_KEY = os.environ["AZURE_OPENAI_API_KEY"]
AZURE_OPENAI_REALTIME_DEPLOYMENT = os.environ.get(
    "AZURE_OPENAI_REALTIME_DEPLOYMENT", "gpt-realtime"
)
GATE_AI_AGENT_NAME = os.environ.get("GATE_AI_AGENT_NAME", "Gate")

AUTH_HEADER = {"api-key": AZURE_OPENAI_API_KEY}

CALL_ACCEPT = {
    "type": "realtime",
    "model": AZURE_OPENAI_REALTIME_DEPLOYMENT,
    "voice": os.environ.get("GATE_AI_AGENT_VOICE", "verse"),
    "instructions": (
        "You are Gate, a concise and professional call screening agent. "
        "Ask who is calling, who they are trying to reach, the reason for the call, "
        "and whether it is urgent. Do not reveal private details about the target. "
        "Keep the interaction short and calm."
    ),
}

RESPONSE_CREATE = {
    "type": "response.create",
    "response": {
        "instructions": (
            f"Answer as {GATE_AI_AGENT_NAME}. Say: "
            "'Thank you for calling. I am Gate, the call screening assistant. "
            "Who is calling, and what is this regarding?'"
        )
    },
}


def call_api_url(call_id: str, action: str) -> str:
    return f"{AZURE_OPENAI_ENDPOINT}/openai/v1/realtime/calls/{call_id}/{action}"


def websocket_url(call_id: str) -> str:
    return f"{AZURE_OPENAI_ENDPOINT.replace('https://', 'wss://')}/openai/v1/realtime?call_id={call_id}"


def header_value(headers, name):
    for header in headers or []:
        if header.get("name", "").lower() == name.lower():
            return header.get("value")
    return None


async def monitor_call(call_id: str) -> None:
    try:
        async with websockets.connect(
            websocket_url(call_id),
            additional_headers=AUTH_HEADER,
            ping_interval=20,
            ping_timeout=20,
        ) as websocket:
            await websocket.send(json.dumps(RESPONSE_CREATE))
            async for message in websocket:
                logger.info("Realtime event for %s: %s", call_id, message)
    except Exception:
        logger.exception("Realtime websocket failed for %s", call_id)


def accept_call(call_id: str) -> None:
    response = requests.post(
        call_api_url(call_id, "accept"),
        headers={**AUTH_HEADER, "Content-Type": "application/json"},
        json=CALL_ACCEPT,
        timeout=10,
    )
    response.raise_for_status()
    threading.Thread(
        target=lambda: asyncio.run(monitor_call(call_id)),
        daemon=True,
    ).start()


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/webhook")
def webhook():
    try:
        event = client.webhooks.unwrap(request.data, request.headers)
    except InvalidWebhookSignatureError:
        logger.warning("Invalid webhook signature")
        return Response("Invalid signature", status=400)
    except Exception:
        logger.exception("Webhook parsing failed")
        return Response("Invalid webhook", status=400)

    if event.type != "realtime.call.incoming":
        logger.info("Ignoring event type %s", event.type)
        return Response(status=200)

    call_id = event.data.call_id
    from_header = header_value(event.data.sip_headers, "From")
    to_header = header_value(event.data.sip_headers, "To")
    logger.info("Incoming realtime SIP call %s from=%s to=%s", call_id, from_header, to_header)

    try:
        accept_call(call_id)
    except Exception:
        logger.exception("Failed to accept realtime SIP call %s", call_id)
        return Response("Failed to accept call", status=502)

    return Response(status=200)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
