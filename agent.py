import os
import json
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, WorkerOptions, RoomInputOptions
from livekit.plugins import telephony, openai, silero, deepgram

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import query_aws_guide, search_web, send_email
from make_call import make_call

load_dotenv()

class Assistant(agents.Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            # use Deepgram for speech‐to‐text
            stt=deepgram.STT(),

            # use OpenAI for your model; GPT-4o is what you had in mind
            llm=openai.LLM(model="gpt-4o", temperature=0.5),

            # pick the voice you want; e.g. "Aoede"
            tts=openai.TTS(voice="Aoede"),

            # voice-activity detection
            vad=silero.VAD.load(),

            # your existing tools
            tools=[query_aws_guide, search_web, send_email],
        )


async def entrypoint(ctx: agents.JobContext):
    # 1) Connect the worker
    await ctx.connect()

    # 2) If you provided TARGET_PHONE_NUMBER in .env, make an outbound call
    room_name = ctx.room.name
    phone_number = os.getenv("TARGET_PHONE_NUMBER")
    if phone_number:
        await make_call(room_name, phone_number)

    # 3) Start the agent session over telephony
    session = AgentSession()
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            video_enabled=False,
            telephony=telephony.BVCTelephony(),
        ),
    )

    # 4) Only greet first on inbound (console) sessions
    if not phone_number:
        await session.generate_reply(instructions=SESSION_INSTRUCTION)

if __name__ == "__main__":
    agents.cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="Friday"   # explicit dispatch name
    ))
