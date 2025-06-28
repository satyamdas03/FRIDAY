import os
from pathlib import Path
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, WorkerOptions
from livekit.plugins import openai, deepgram, silero

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import query_aws_guide, search_web, send_email

# Load environment variables
load_dotenv(dotenv_path=Path(__file__).parent / '.env')

class Assistant(agents.Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4o", temperature=0.5),
            tts=openai.TTS(),
            vad=silero.VAD.load(),
            tools=[query_aws_guide, search_web, send_email],
        )

    async def on_enter(self):
        # Greet the caller as soon as the call starts
        await self.session.generate_reply(instructions=SESSION_INSTRUCTION)

async def entrypoint(ctx: agents.JobContext):
    # Connect the worker to LiveKit
    await ctx.connect()

    # Start a session in the room provided by the JobContext (incoming call)
    session = AgentSession()
    agent = Assistant()
    await session.start(agent=agent, room=ctx.room)

    # The on_enter handler will automatically run and greet the caller

if __name__ == "__main__":
    agents.cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="Friday",  # match your dispatch rule agent_name
    ))
