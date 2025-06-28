import os
import json
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, WorkerOptions, RoomInputOptions
from livekit.plugins import openai, silero, deepgram, noise_cancellation

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import query_aws_guide, search_web, send_email
from make_call import make_call

load_dotenv()

class Assistant(agents.Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4o", temperature=0.5),
            tts=openai.TTS(voice="alloy"),
            vad=silero.VAD.load(),
            tools=[query_aws_guide, search_web, send_email],
        )


async def entrypoint(ctx: agents.JobContext):
    # 1) Connect the worker
    await ctx.connect()

    # 2) If TARGET_PHONE_NUMBER is set, place an outbound call
    room_name = ctx.room.name
    phone_number = os.getenv("TARGET_PHONE_NUMBER")
    if phone_number:
        await make_call(room_name, phone_number)

    # 3) Start the voice session
    session = AgentSession()
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            video_enabled=False,
            # optional Krisp/BVC noise cancellation on the call
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # 4) Only greet first on inbound (console) sessions
    if not phone_number:
        await session.generate_reply(instructions=SESSION_INSTRUCTION)


if __name__ == "__main__":
    agents.cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="Friday"    # explicit dispatch name
    ))
