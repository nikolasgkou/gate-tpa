import argparse
import asyncio
import audioop
import logging
import os
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

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
GEMINI_INPUT_RATE = 16000
GEMINI_OUTPUT_RATE = 24000

DEFAULT_MODEL = "gemini-3.1-flash-live-preview"
DEFAULT_VOICE = "Kore"

SYSTEM_INSTRUCTION = (
    "You are Gate, a concise and professional AI call screening agent. "
    "You are speaking on a phone call. Keep responses short and calm. "
    "When an instruction starts with 'Say exactly:', speak only the words after "
    "that prefix. Do not add, remove, explain, or rephrase anything."
)

GREETING = (
    "Start the call now. Say: Thank you for calling. I am Gate, the call "
    "screening assistant. Who is calling, and what is this regarding?"
)

OUTCOME_DIR = Path(os.environ.get("GATE_OUTCOME_DIR", "/run/gate-tpa"))
EXECUTIVE_URGENT_WINDOW_SECONDS = float(
    os.environ.get("GATE_EXECUTIVE_URGENT_WINDOW_SECONDS", "5")
)


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    call_uuid: str
    prompt: str
    close_after_first_turn: bool
    system_instruction: str | None = None
    post_transfer: str | None = None


SCENARIOS = {
    "00000000-0000-0000-0000-000000001001": Scenario(
        scenario_id="trusted_parent_to_child",
        call_uuid="00000000-0000-0000-0000-000000001001",
        prompt="Say exactly: Hi Sarah. Connecting you to Emma.",
        close_after_first_turn=True,
    ),
    "00000000-0000-0000-0000-000000001002": Scenario(
        scenario_id="unknown_to_child_parent_reroute",
        call_uuid="00000000-0000-0000-0000-000000001002",
        prompt="Say exactly: This call will be routed to Sarah Newman.",
        close_after_first_turn=True,
    ),
    "00000000-0000-0000-0000-000000001003": Scenario(
        scenario_id="unknown_to_elderly_caregiver",
        call_uuid="00000000-0000-0000-0000-000000001003",
        prompt=(
            "Say exactly: Olivia cannot take this call directly. "
            "Would you like to leave a message or speak with her caregiver?"
        ),
        close_after_first_turn=True,
    ),
    "00000000-0000-0000-0000-000000001005": Scenario(
        scenario_id="executive_meeting",
        call_uuid="00000000-0000-0000-0000-000000001005",
        prompt="Say exactly: Bruce is in a meeting. What is this regarding?",
        close_after_first_turn=False,
        system_instruction=(
            "You are Gate, Bruce Jameson's concise call screening assistant. "
            "Speak only short phone-call lines. First follow the exact prompt. "
            "After the caller responds, if the caller uses the word urgent, say exactly: "
            "Understood. I'll try Bruce now. Please hold. "
            "If the caller does not use the word urgent, say exactly: "
            "Thanks. Bruce is in a meeting and will be notified about this call after the meeting. "
            "Do not ask follow-up questions."
        ),
        post_transfer="1005",
    ),
}


def read_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def outcome_path(scenario: Scenario) -> Path:
    return OUTCOME_DIR / f"{scenario.call_uuid}.outcome"


def write_outcome(scenario: Scenario, outcome: str) -> None:
    OUTCOME_DIR.mkdir(parents=True, exist_ok=True)
    path = outcome_path(scenario)
    path.write_text(f"{outcome}\n", encoding="utf-8")
    path.chmod(0o644)
    LOGGER.info("Scenario %s outcome=%s", scenario.scenario_id, outcome)


def call_uuid_from_payload(payload: bytes) -> str:
    return str(UUID(bytes=payload))


async def read_frame(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    header = await reader.readexactly(3)
    frame_type = header[0]
    payload_length = int.from_bytes(header[1:3], "big")
    payload = await reader.readexactly(payload_length) if payload_length else b""
    return frame_type, payload


async def write_frame(writer: asyncio.StreamWriter, frame_type: int, payload: bytes) -> None:
    writer.write(bytes([frame_type]) + len(payload).to_bytes(2, "big") + payload)
    await writer.drain()


class ScenarioController:
    def __init__(self, scenario: Scenario, session) -> None:
        self.scenario = scenario
        self.session = session
        self.done = asyncio.Event()
        self.decided = False
        self.close_after_next_turn = False
        self.turns_completed = 0
        self.transcript_parts: list[str] = []
        self.output_transcript_parts: list[str] = []
        self.deadline_task: asyncio.Task | None = None

    def start(self) -> None:
        if self.scenario.scenario_id == "executive_meeting":
            write_outcome(self.scenario, "notify")

    async def stop(self) -> None:
        if self.deadline_task:
            self.deadline_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.deadline_task

    async def _executive_deadline(self) -> None:
        await asyncio.sleep(EXECUTIVE_URGENT_WINDOW_SECONDS)
        if self.decided:
            return

        self.decided = True
        write_outcome(self.scenario, "notify")
        self.close_after_next_turn = True
        await self.session.send_realtime_input(
            text=(
                "Say exactly: Thanks. Bruce is in a meeting and will be "
                "notified about this call after the meeting."
            )
        )

    async def on_input_transcript(self, text: str) -> None:
        if self.scenario.scenario_id != "executive_meeting" or self.decided:
            return

        self.transcript_parts.append(text)
        transcript = " ".join(self.transcript_parts).lower()
        if "urgent" not in transcript:
            return

        self.decided = True
        write_outcome(self.scenario, "transfer")
        self.close_after_next_turn = True
        if self.deadline_task:
            self.deadline_task.cancel()
        await self.session.send_realtime_input(
            text="Say exactly: Understood. I'll try Bruce now. Please hold."
        )

    async def on_output_transcript(self, text: str) -> None:
        if self.scenario.scenario_id != "executive_meeting":
            return

        self.output_transcript_parts.append(text)
        transcript = " ".join(self.output_transcript_parts).lower()
        if "try bruce" in transcript or "please hold" in transcript:
            if not self.decided:
                write_outcome(self.scenario, "transfer")
            self.decided = True
            self.close_after_next_turn = True
            if self.deadline_task:
                self.deadline_task.cancel()
        elif "will be notified" in transcript:
            if not self.decided:
                write_outcome(self.scenario, "notify")
            self.decided = True
            self.close_after_next_turn = True
            if self.deadline_task:
                self.deadline_task.cancel()

    async def on_turn_complete(self) -> None:
        self.turns_completed += 1
        if (
            self.scenario.scenario_id == "executive_meeting"
            and self.turns_completed == 1
            and not self.decided
        ):
            self.deadline_task = asyncio.create_task(self._executive_deadline())
        if self.scenario.close_after_first_turn and self.turns_completed >= 1:
            self.done.set()
        if self.close_after_next_turn:
            self.done.set()


async def read_call_uuid(reader: asyncio.StreamReader) -> str:
    frame_type, payload = await read_frame(reader)
    if frame_type != 0x01:
        LOGGER.warning("Expected AudioSocket UUID frame, got 0x%02x", frame_type)
        return "00000000-0000-0000-0000-000000000001"

    call_uuid = call_uuid_from_payload(payload)
    LOGGER.info("AudioSocket call UUID: %s", call_uuid)
    return call_uuid


async def stream_gemini_audio_to_asterisk(
    session,
    writer: asyncio.StreamWriter,
    controller: ScenarioController,
) -> None:
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
                transcript = content.input_transcription.text
                LOGGER.info("Caller transcript: %s", transcript)
                await controller.on_input_transcript(transcript)
            if getattr(content, "output_transcription", None):
                transcript = content.output_transcription.text
                LOGGER.info("Gemini transcript: %s", transcript)
                await controller.on_output_transcript(transcript)
            if getattr(content, "model_turn", None):
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
            if getattr(content, "turn_complete", False):
                await controller.on_turn_complete()


async def stream_asterisk_audio_to_gemini(reader: asyncio.StreamReader, session) -> None:
    input_frames = 0
    input_bytes = 0
    input_ratecv_state = None

    while True:
        frame_type, payload = await read_frame(reader)
        if frame_type == 0x00:
            LOGGER.info("Asterisk sent hangup")
            return
        if frame_type == 0x03:
            digit = payload.decode(errors="replace")
            LOGGER.info("DTMF digit: %s", digit)
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
            if sample_rate == GEMINI_INPUT_RATE:
                gemini_audio = payload
            else:
                gemini_audio, input_ratecv_state = audioop.ratecv(
                    payload,
                    2,
                    1,
                    sample_rate,
                    GEMINI_INPUT_RATE,
                    input_ratecv_state,
                )

            await session.send_realtime_input(
                audio=types.Blob(
                    data=gemini_audio,
                    mime_type=f"audio/pcm;rate={GEMINI_INPUT_RATE}",
                )
            )
            continue

        LOGGER.warning("Ignoring unsupported AudioSocket frame type 0x%02x", frame_type)


async def handle_call(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    peer = writer.get_extra_info("peername")
    LOGGER.info("AudioSocket connection from %s", peer)

    call_uuid = await read_call_uuid(reader)
    scenario = SCENARIOS.get(
        call_uuid,
        Scenario(
            scenario_id="default_screening",
            call_uuid=call_uuid,
            prompt=os.environ.get("GATE_AI_GREETING", GREETING),
            close_after_first_turn=False,
        ),
    )
    LOGGER.info("Selected scenario: %s", scenario.scenario_id)

    client = genai.Client(api_key=read_env("GEMINI_API_KEY"))
    model = os.environ.get("GEMINI_LIVE_MODEL", DEFAULT_MODEL)
    voice_name = os.environ.get("GEMINI_VOICE", DEFAULT_VOICE)
    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": scenario.system_instruction
        or os.environ.get("GATE_AI_SYSTEM_INSTRUCTION", SYSTEM_INSTRUCTION),
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "speech_config": {
            "voice_config": {"prebuilt_voice_config": {"voice_name": voice_name}}
        },
    }

    try:
        async with client.aio.live.connect(model=model, config=config) as session:
            controller = ScenarioController(scenario, session)
            controller.start()
            await session.send_realtime_input(text=scenario.prompt)
            gemini_to_asterisk = asyncio.create_task(
                stream_gemini_audio_to_asterisk(session, writer, controller)
            )
            asterisk_to_gemini = asyncio.create_task(
                stream_asterisk_audio_to_gemini(reader, session)
            )

            done, pending = await asyncio.wait(
                {
                    gemini_to_asterisk,
                    asterisk_to_gemini,
                    asyncio.create_task(controller.done.wait()),
                },
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in pending:
                with suppress(asyncio.CancelledError):
                    await task
            for task in done:
                task.result()
            await controller.stop()
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
