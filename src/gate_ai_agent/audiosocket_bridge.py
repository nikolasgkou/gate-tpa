import argparse
import asyncio
import audioop
import logging
import os
import socket
from contextlib import suppress

from google import genai
from google.genai import types


LOGGER = logging.getLogger("gate-ai-audiosocket")

AUDIO_TYPES_TO_RATE = {
    0x10: 8000,
    0x11: 12000,
    0x12: 16000,
    0x13: 24000,
    0x14: 32000,
    0x15: 44100,
    0x16: 48000,
    0x17: 96000,
    0x18: 192000,
}

ASTERISK_OUTPUT_TYPE = 0x10
ASTERISK_OUTPUT_RATE = 8000
ASTERISK_OUTPUT_FRAME_BYTES = 320
GEMINI_OUTPUT_RATE = 24000

DEFAULT_MODEL = "gemini-3.1-flash-live-preview"
DEFAULT_VOICE = "Kore"

SYSTEM_INSTRUCTION = (
    "You are Gate, a concise and professional AI call screening agent. "
    "You are speaking on a phone call. Ask who is calling, who they are trying "
    "to reach, the reason for the call, and whether it is urgent. Do not reveal "
    "private details about the target. Keep responses short and calm."
)

GREETING = (
    "Start the call now. Say: Thank you for calling. I am Gate, the call "
    "screening assistant. Who is calling, and what is this regarding?"
)


def read_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


async def read_frame(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    header = await reader.readexactly(3)
    frame_type = header[0]
    payload_length = int.from_bytes(header[1:3], "big")
    payload = await reader.readexactly(payload_length) if payload_length else b""
    return frame_type, payload


async def write_frame(writer: asyncio.StreamWriter, frame_type: int, payload: bytes) -> None:
    writer.write(bytes([frame_type]) + len(payload).to_bytes(2, "big") + payload)
    await writer.drain()


async def stream_gemini_audio_to_asterisk(session, writer: asyncio.StreamWriter) -> None:
    output_frames = 0
    output_bytes = 0
    ratecv_state = None
    output_buffer = bytearray()

    while True:
        async for response in session.receive():
            content = getattr(response, "server_content", None)
            if not content:
                continue

            if getattr(content, "input_transcription", None):
                LOGGER.info("Caller transcript: %s", content.input_transcription.text)
            if getattr(content, "output_transcription", None):
                LOGGER.info("Gemini transcript: %s", content.output_transcription.text)
            if not getattr(content, "model_turn", None):
                continue

            for part in content.model_turn.parts or []:
                inline_data = getattr(part, "inline_data", None)
                if not inline_data or not inline_data.data:
                    continue

                audio, ratecv_state = audioop.ratecv(
                    inline_data.data,
                    2,
                    1,
                    GEMINI_OUTPUT_RATE,
                    ASTERISK_OUTPUT_RATE,
                    ratecv_state,
                )
                output_buffer.extend(audio)
                output_bytes += len(audio)

                while len(output_buffer) >= ASTERISK_OUTPUT_FRAME_BYTES:
                    chunk = bytes(output_buffer[:ASTERISK_OUTPUT_FRAME_BYTES])
                    del output_buffer[:ASTERISK_OUTPUT_FRAME_BYTES]
                    await write_frame(writer, ASTERISK_OUTPUT_TYPE, chunk)
                    output_frames += 1
                    await asyncio.sleep(0.02)

                LOGGER.info(
                    "Sent Gemini audio to Asterisk: frames=%s bytes=%s",
                    output_frames,
                    output_bytes,
                )


async def stream_asterisk_audio_to_gemini(reader: asyncio.StreamReader, session) -> None:
    input_frames = 0
    input_bytes = 0

    while True:
        frame_type, payload = await read_frame(reader)
        if frame_type == 0x00:
            LOGGER.info("Asterisk sent hangup")
            return
        if frame_type == 0x01:
            LOGGER.info("AudioSocket call UUID: %s", payload.hex())
            continue
        if frame_type == 0x03:
            LOGGER.info("DTMF digit: %s", payload.decode(errors="replace"))
            continue

        sample_rate = AUDIO_TYPES_TO_RATE.get(frame_type)
        if sample_rate and payload:
            input_frames += 1
            input_bytes += len(payload)
            if input_frames == 1 or input_frames % 50 == 0:
                LOGGER.info(
                    "Received Asterisk audio: frames=%s bytes=%s rate=%s",
                    input_frames,
                    input_bytes,
                    sample_rate,
                )
            await session.send_realtime_input(
                audio=types.Blob(
                    data=payload,
                    mime_type=f"audio/pcm;rate={sample_rate}",
                )
            )
            continue

        LOGGER.warning("Ignoring unsupported AudioSocket frame type 0x%02x", frame_type)


async def handle_call(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer = writer.get_extra_info("peername")
    LOGGER.info("AudioSocket connection from %s", peer)

    client = genai.Client(api_key=read_env("GEMINI_API_KEY"))
    model = os.environ.get("GEMINI_LIVE_MODEL", DEFAULT_MODEL)
    voice_name = os.environ.get("GEMINI_VOICE", DEFAULT_VOICE)
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": os.environ.get("GATE_AI_SYSTEM_INSTRUCTION", SYSTEM_INSTRUCTION),
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "speech_config": {
            "voice_config": {"prebuilt_voice_config": {"voice_name": voice_name}}
        },
    }

    try:
        async with client.aio.live.connect(model=model, config=config) as session:
            await session.send_realtime_input(text=os.environ.get("GATE_AI_GREETING", GREETING))
            gemini_to_asterisk = asyncio.create_task(
                stream_gemini_audio_to_asterisk(session, writer)
            )
            asterisk_to_gemini = asyncio.create_task(
                stream_asterisk_audio_to_gemini(reader, session)
            )

            done, pending = await asyncio.wait(
                {gemini_to_asterisk, asterisk_to_gemini},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in pending:
                with suppress(asyncio.CancelledError):
                    await task
            for task in done:
                task.result()
    except asyncio.IncompleteReadError:
        LOGGER.info("AudioSocket connection closed by Asterisk")
    except Exception:
        LOGGER.exception("Call bridge failed")
        with suppress(Exception):
            await write_frame(writer, 0xFF, b"bridge-failed")
    finally:
        writer.close()
        await writer.wait_closed()
        LOGGER.info("AudioSocket connection closed")


async def serve(host: str, port: int) -> None:
    server = await asyncio.start_server(handle_call, host, port)
    sockets = ", ".join(str(sock.getsockname()) for sock in server.sockets or [])
    LOGGER.info("Gate Gemini AudioSocket bridge listening on %s", sockets)
    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate TPA Gemini AudioSocket bridge")
    parser.add_argument("--host", default=os.environ.get("GATE_AI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("GATE_AI_PORT", "9092")))
    args = parser.parse_args()

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(serve(args.host, args.port))


if __name__ == "__main__":
    main()
