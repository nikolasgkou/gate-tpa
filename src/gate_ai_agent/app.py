import asyncio
import logging
import os

from flask import Flask, Response, request
from google import genai


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gate-ai-agent")

app = Flask(__name__)

GEMINI_LIVE_MODEL = os.environ.get(
    "GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview"
)
GEMINI_TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
GATE_AI_AGENT_NAME = os.environ.get("GATE_AI_AGENT_NAME", "Gate")

SYSTEM_INSTRUCTION = (
    "You are Gate, a concise and professional call screening agent. "
    "Ask who is calling, who they are trying to reach, the reason for the call, "
    "and whether it is urgent. Do not reveal private details about the target. "
    "Keep the interaction short and calm."
)


def gemini_client():
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


async def run_live_audio_smoke(prompt: str) -> int:
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": SYSTEM_INSTRUCTION,
    }

    async with gemini_client().aio.live.connect(
        model=GEMINI_LIVE_MODEL,
        config=config,
    ) as session:
        await session.send_client_content(turns=prompt, turn_complete=True)

        async for message in session.receive():
            server_content = getattr(message, "server_content", None)
            model_turn = getattr(server_content, "model_turn", None)
            for part in getattr(model_turn, "parts", None) or []:
                inline_data = getattr(part, "inline_data", None)
                if inline_data and inline_data.data:
                    return len(inline_data.data)

    return 0


@app.get("/healthz")
def healthz():
    return {
        "ok": True,
        "provider": "gemini",
        "live_model": GEMINI_LIVE_MODEL,
        "text_model": GEMINI_TEXT_MODEL,
    }


@app.post("/screen-text")
def screen_text():
    payload = request.get_json(silent=True) or {}
    caller = payload.get("caller", "unknown caller")
    target = payload.get("target", "the user")
    reason = payload.get("reason", "not provided")
    urgency = payload.get("urgency", "unknown")

    prompt = (
        f"Caller: {caller}\n"
        f"Target: {target}\n"
        f"Reason: {reason}\n"
        f"Urgency: {urgency}\n\n"
        "Return a concise call-screening decision with action, summary, and one sentence to say to the caller."
    )

    response = gemini_client().models.generate_content(
        model=GEMINI_TEXT_MODEL,
        contents=prompt,
        config={"system_instruction": SYSTEM_INSTRUCTION},
    )
    return {
        "provider": "gemini",
        "model": GEMINI_TEXT_MODEL,
        "result": response.text,
    }


@app.post("/live-smoke")
def live_smoke():
    payload = request.get_json(silent=True) or {}
    prompt = payload.get(
        "prompt",
        f"Answer as {GATE_AI_AGENT_NAME}. Say a short greeting for a phone screening call.",
    )

    try:
        audio_bytes = asyncio.run(run_live_audio_smoke(prompt))
    except KeyError:
        return Response("Missing GEMINI_API_KEY", status=500)
    except Exception:
        logger.exception("Gemini Live smoke check failed")
        return Response("Gemini Live smoke check failed", status=502)

    return {
        "provider": "gemini",
        "model": GEMINI_LIVE_MODEL,
        "audio_bytes": audio_bytes,
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
