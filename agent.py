# agent.py
import os
import datetime
import logging
from pathlib import Path
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, WorkerOptions, JobContext, RoomInputOptions
from livekit.plugins import openai, silero, noise_cancellation, sarvam

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from prompts_outbound import get_outbound_session_instruction

# bring in your function-tools + RAG helpers
from tools import (
    query_aws_guide,
    search_web,
    send_email,
    rag_query,
    reload_rag_index,    # <— reloadable FAISS index
)

load_dotenv()

logger = logging.getLogger("friday-agent")
logger.setLevel(logging.INFO)
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s")


class Assistant(agents.Agent):
    def __init__(self, session_instructions: str) -> None:
        super().__init__(
            # core instructions stay the same
            instructions=AGENT_INSTRUCTION + "\nAlways respond in the same language the user spoke.",
            # include your standard tools + the new rag_query
            tools=[query_aws_guide, search_web, send_email, rag_query],
        )
        self._session_instructions = session_instructions

    async def on_enter(self):
        # run the inbound or outbound script as soon as the session starts
        await self.session.generate_reply(instructions=self._session_instructions)


async def entrypoint(ctx: JobContext):
    # ─── 0) Ensure your RAG index reflects the latest uploads ─────────────────
    reload_rag_index()
    logger.info("RAG index reloaded before starting voice session")

    # ─── 1) Decide inbound vs outbound script ────────────────────────────────
    ctx_file = Path("data") / "temp_context.txt"
    session_inst = SESSION_INSTRUCTION

    if ctx_file.exists():
        lines = [
            l.strip()
            for l in ctx_file.read_text("utf8").splitlines()
            if l.strip()
        ]
        name = next((l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("name:")), None)
        pain = next((l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("painpoints:")), None)
        soln = next((l.split(":", 1)[1].strip() for l in lines if l.lower().startswith("solutions:")), None)

        logger.info(f"Loaded context → Name: {name}")
        logger.info(f"Loaded context → PainPoints: {pain}")
        logger.info(f"Loaded context → Solutions: {soln}")

        if name and pain and soln:
            session_inst = get_outbound_session_instruction(name, pain, soln)
    else:
        logger.warning(f"No context file found at {ctx_file!r}; using inbound prompt.")

    # ─── 2) Build the STT ⇢ LLM ⇢ TTS pipeline ────────────────────────────────
    session = AgentSession(
        stt=sarvam.STT(
            language=os.getenv("SARVAM_STT_LANG", "en-IN"),
            model=os.getenv("SARVAM_STT_MODEL", "saarika:v2.5"),
        ),
        llm=openai.LLM(model="gpt-4o", temperature=0.5),
        tts=sarvam.TTS(
            target_language_code=os.getenv("SARVAM_TTS_LANG", "en-IN"),
            model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v2"),
            speaker=os.getenv("SARVAM_SPEAKER", "anushka"),
        ),
        vad=silero.VAD.load(),
        # no turn-detector
    )

    # ─── 3) Connect & set up transcript logging ───────────────────────────────
    await ctx.connect()
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs("transcripts", exist_ok=True)
    transcript_path = f"transcripts/{ctx.room.name}_{ts}.txt"
    f = open(transcript_path, "a", encoding="utf8")

    def _log(ev):
        if f.closed:
            return
        msg = ev.item
        role = msg.role.name.upper() if hasattr(msg.role, "name") else str(msg.role).upper()
        for chunk in msg.content:
            f.write(f"{role}: {chunk}\n")
        f.flush()

    session.on("conversation_item_added", _log)
    session.on("session_closed", lambda ev: (not f.closed and f.close()))

    # ─── 4) Start the voice session with our Assistant ───────────────────────
    assistant = Assistant(session_instructions=session_inst)
    await session.start(
        agent=assistant,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )

    # ─── 5) Kick off with a RAG-aware greeting ───────────────────────────────
    await session.generate_reply(
        instructions="Hello! I’m Friday—ask me anything about your uploaded documents."
    )


if __name__ == "__main__":
    agents.cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=os.getenv("AGENT_NAME", "inbound-agent"),
        )
    )
