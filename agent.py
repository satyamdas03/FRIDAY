# agent.py
import os, datetime
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, WorkerOptions, JobContext, RoomInputOptions
from livekit.plugins import openai, silero, noise_cancellation, sarvam

from prompts import AGENT_INSTRUCTION, OUTBOUND_AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import (
    rebuild_aws_index,
    parse_prospect_info,
    query_aws_guide,
    search_web,
    send_email,
)
from make_call import make_call

load_dotenv()

class Assistant(agents.Agent):
    def __init__(self, instructions: str) -> None:
        super().__init__(
            instructions=instructions,
            stt=sarvam.STT(
                language=os.getenv("SARVAM_STT_LANG","en-IN"),
                model=os.getenv("SARVAM_STT_MODEL","saarika:v2.5"),
            ),
            llm=openai.LLM(model="gpt-4o", temperature=0.5),
            tts=sarvam.TTS(
                target_language_code=os.getenv("SARVAM_TTS_LANG","en-IN"),
                model=os.getenv("SARVAM_TTS_MODEL","bulbul:v2"),
                speaker=os.getenv("SARVAM_SPEAKER","anushka"),
            ),
            vad=silero.VAD.load(),
            tools=[query_aws_guide, search_web, send_email],
        )

    async def on_enter(self):
        # kick off the initial message
        await self.session.generate_reply(instructions=SESSION_INSTRUCTION)

async def entrypoint(ctx: JobContext):
    # connect
    await ctx.connect()

    phone = os.getenv("TARGET_PHONE_NUMBER")

    # 1) Outbound: dial + AI dispatch first
    if phone:
        await make_call(ctx.room.name, phone)

    # 2) Rebuild FAISS index with any “deep-research-report…pdf”
    data_dir = os.path.join(os.path.dirname(__file__),"data")
    reports = sorted(
        os.path.join(data_dir,fn)
        for fn in os.listdir(data_dir)
        if fn.startswith("deep-research-report") and fn.endswith(".pdf")
    )
    await rebuild_aws_index(reports if reports else None)

    # 3) If outbound, parse the first report for name/pain
    if phone and reports:
        name, email, pain = await parse_prospect_info(reports[0])
        greeting = (
            f"Hello {name}, I’m Friday from Workmates Core2Cloud. "
            f"I see you’re looking to {pain}. Let’s discuss how we can help."
        )
        inst = OUTBOUND_AGENT_INSTRUCTION + "\n\n" + greeting
    else:
        inst = AGENT_INSTRUCTION

    # 4) Prepare transcript logging
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs("transcripts", exist_ok=True)
    transcript_path = f"transcripts/{ctx.room.name}_{ts}.txt"
    f = open(transcript_path, "a", encoding="utf8")

    def _log(ev):
        if f.closed: return
        msg = ev.item
        raw = msg.role
        role = raw.name.upper() if hasattr(raw,"name") else str(raw).upper()
        for chunk in msg.content:
            f.write(f"{role}: {chunk}\n")
        f.flush()

    def _on_closed(ev):
        if not f.closed:
            f.close()
            print(f"Transcript saved to {transcript_path}")

    # 5) Wire up session
    session = AgentSession()
    session.on("conversation_item_added", _log)
    session.on("session_closed", _on_closed)

    # 6) Start *this* session (single AgentSession)
    await session.start(
        agent=Assistant(instructions=inst),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )

if __name__ == "__main__":
    agents.cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name=os.getenv("AGENT_NAME","inbound-agent"),
    ))
