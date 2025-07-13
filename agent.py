# agent.py (original)
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
from tools import query_aws_guide, search_web, send_email

load_dotenv()

logger = logging.getLogger("friday-agent")
logger.setLevel(logging.INFO)
logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s")


class Assistant(agents.Agent):
    def __init__(self, session_instructions: str) -> None:
        super().__init__(
            # only pass instructions + your function‐tools here:
            instructions=AGENT_INSTRUCTION + "\nAlways respond in the same language the user spoke.",
            tools=[query_aws_guide, search_web, send_email],
        )
        self._session_instructions = session_instructions

    async def on_enter(self):
        # This is called once, right when the call starts:
        await self.session.generate_reply(instructions=self._session_instructions)


async def entrypoint(ctx: JobContext):
    # ─── 1) Decide inbound vs outbound script
    ctx_file = Path("data") / "temp_context.txt"
    session_inst = SESSION_INSTRUCTION

    if ctx_file.exists():
        lines = [l.strip() for l in ctx_file.read_text("utf8").splitlines() if l.strip()]
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

    # ─── 2) Build the STT ⇢ LLM ⇢ TTS pipeline in AgentSession
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
        # no turn‐detector here
    )

    # ─── 3) Connect & set up transcript logging
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

    # ─── 4) Start the call with our Assistant
    assistant = Assistant(session_instructions=session_inst)
    await session.start(
        agent=assistant,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )


if __name__ == "__main__":
    agents.cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=os.getenv("AGENT_NAME", "inbound-agent"),
        )
    )
















## FIRANGI
# # agent.py
# import os
# import datetime
# import logging
# from pathlib import Path
# from dotenv import load_dotenv

# from livekit import agents
# from livekit.agents import AgentSession, WorkerOptions, JobContext, RoomInputOptions
# from livekit.plugins import openai, silero, noise_cancellation, deepgram, cartesia

# from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
# from prompts_outbound import get_outbound_session_instruction
# from tools import query_aws_guide, search_web, send_email

# load_dotenv()

# # set up a logger
# logger = logging.getLogger("friday-agent")
# logger.setLevel(logging.INFO)
# logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s")


# class Assistant(agents.Agent):
#     def __init__(self) -> None:
#         # now including your full AGENT_INSTRUCTION as the base system prompt
#         super().__init__(
#             instructions=AGENT_INSTRUCTION + "\nAlways respond in the same language the user spoke.",
#             tools=[query_aws_guide, search_web, send_email],
#         )


# async def entrypoint(ctx: JobContext):
#     # ─── 1) Decide inbound vs outbound script ────────────────────────────────
#     ctx_file = Path("data") / "temp_context.txt"
#     session_inst = SESSION_INSTRUCTION

#     if ctx_file.exists():
#         lines = [l.strip() for l in ctx_file.read_text("utf8").splitlines() if l.strip()]
#         name = next((l.split(":", 1)[1].strip()
#                      for l in lines if l.lower().startswith("name:")), None)
#         pain = next((l.split(":", 1)[1].strip()
#                      for l in lines if l.lower().startswith("painpoints:")), None)
#         soln = next((l.split(":", 1)[1].strip()
#                      for l in lines if l.lower().startswith("solutions:")), None)

#         logger.info(f"Loaded context → Name: {name}")
#         logger.info(f"Loaded context → PainPoints: {pain}")
#         logger.info(f"Loaded context → Solutions: {soln}")

#         if name and pain and soln:
#             session_inst = get_outbound_session_instruction(name, pain, soln)
#     else:
#         logger.warning(f"No context file found at {ctx_file!r}; using inbound prompt.")

#     # ─── 2) Build the STT ⇢ LLM ⇢ TTS pipeline in AgentSession ───────────────
#     session = AgentSession(
#         stt=deepgram.STT(model="nova-3", language="multi"),
#         llm=openai.LLM(model="gpt-4o", temperature=0.5),
#         tts=cartesia.TTS(model="sonic-2", voice=os.getenv("CARTESIA_VOICE")),
#         vad=silero.VAD.load(),
#         turn_detection=None,  # disable turn-detector
#     )

#     # ─── 3) Connect & set up transcript logging ───────────────────────────────
#     await ctx.connect()
#     ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
#     os.makedirs("transcripts", exist_ok=True)
#     transcript_path = f"transcripts/{ctx.room.name}_{ts}.txt"
#     f = open(transcript_path, "a", encoding="utf8")

#     def _log(ev):
#         if f.closed:
#             return
#         msg = ev.item
#         role = msg.role.name.upper() if hasattr(msg.role, "name") else str(msg.role).upper()
#         for chunk in msg.content:
#             f.write(f"{role}: {chunk}\n")
#         f.flush()

#     session.on("conversation_item_added", _log)
#     session.on("session_closed", lambda ev: (not f.closed and f.close()))

#     # ─── 4) Start the call with our Assistant ────────────────────────────────
#     assistant = Assistant()
#     await session.start(
#         agent=assistant,
#         room=ctx.room,
#         room_input_options=RoomInputOptions(
#             video_enabled=False,
#             noise_cancellation=noise_cancellation.BVCTelephony(),
#         ),
#     )

#     # ─── 5) Immediately fire off your inbound/outbound script ────────────────
#     await session.generate_reply(instructions=session_inst)


# if __name__ == "__main__":
#     agents.cli.run_app(
#         WorkerOptions(
#             entrypoint_fnc=entrypoint,
#             agent_name=os.getenv("AGENT_NAME", "inbound-agent"),
#         )
#     )
