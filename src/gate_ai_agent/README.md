# Gate AI Agent

Gemini-backed call screening service for Gate TPA.

## Runtime Settings

- `GEMINI_API_KEY`: Gemini API key.
- `GEMINI_LIVE_MODEL`: optional Live API model, defaults to `gemini-3.1-flash-live-preview`.
- `GEMINI_TEXT_MODEL`: optional text model for non-voice screening decisions, defaults to `gemini-2.5-flash`.
- `GATE_AI_AGENT_NAME`: optional display name used in smoke-test prompts.

## Routes

- `GET /healthz`: health check.
- `POST /screen-text`: text-only call-screening decision helper.
- `POST /live-smoke`: opens a Gemini Live session and verifies that audio output is returned.

## AudioSocket Bridge

Run the bridge on the PBX host:

```sh
python -m src.gate_ai_agent.audiosocket_bridge --host 127.0.0.1 --port 9092
```

Gemini Live is WebSocket-based and does not expose a SIP trunk. In the PBX, route `9001` answers the call and uses Asterisk `AudioSocket()` to stream call audio to this process.
