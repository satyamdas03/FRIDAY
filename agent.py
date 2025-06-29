from __future__ import annotations

import logging
from pathlib import Path
from dotenv import load_dotenv

from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli
from livekit.agents.voice import Agent, AgentSession
from livekit.agents import RoomInputOptions
from livekit.plugins import openai, deepgram, silero, noise_cancellation

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import query_aws_guide, search_web, send_email

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

logger = logging.getLogger("friday-agent")
logger.setLevel(logging.INFO)

class FridayAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4o", temperature=0.5),
            tts=openai.TTS(voice="alloy"),
            vad=silero.VAD.load(),
            tools=[query_aws_guide, search_web, send_email],
        )

    async def on_enter(self):
        # greet the caller immediately
        await self.session.generate_reply(instructions=SESSION_INSTRUCTION)

async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")

    # join only audio so we can “answer” the SIP call
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # wait for the caller (SIP participant)
    participant = await ctx.wait_for_participant()
    logger.info(f"caller joined: {participant.identity}")

    # kick off an AgentSession to handle the voice convo
    session = AgentSession()
    await session.start(
        agent=FridayAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )
    logger.info("agent session started")

if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="inbound-agent",
        )
    )
