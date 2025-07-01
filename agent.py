import os, datetime, logging, asyncio
from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentSession, WorkerOptions, JobContext, RoomInputOptions
from livekit.plugins import openai, silero, noise_cancellation, sarvam

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION_INBOUND, SESSION_INSTRUCTION_OUTBOUND
from tools import (
    rebuild_aws_index,
    parse_prospect_info,
    query_aws_guide,
    search_web,
    send_email
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
            tools=[rebuild_aws_index, query_aws_guide, search_web, send_email, parse_prospect_info],
        )

    async def on_enter(self):
        # this sends the session-begin text automatically
        await self.session.generate_reply(instructions=self.instructions)

async def entrypoint(ctx: JobContext):
    await ctx.connect()

    # rebuild index (static + any deep-research reports)
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    extra_pdfs = [
        os.path.join(data_dir, f)
        for f in os.listdir(data_dir)
        if f.startswith("deep-research-report") and f.endswith(".pdf")
    ]
    await rebuild_aws_index(extra_pdfs)

    # outbound vs inbound?
    phone = os.getenv("TARGET_PHONE_NUMBER")
    if phone:
        # parse the first report for greeting context
        prospect = await parse_prospect_info(extra_pdfs[0]) if extra_pdfs else {}
        greet_instr = SESSION_INSTRUCTION_OUTBOUND.format(
            name=prospect.get("name", "there")
        )
        inst = AGENT_INSTRUCTION + "\n\n" + greet_instr

        # dial out—catch SIP errors but continue
        try:
            await make_call(ctx.room.name, phone)
            logging.info("Outbound dial succeeded")
        except Exception as err:
            logging.error(f"make_call failed: {err}")

    else:
        inst = AGENT_INSTRUCTION + "\n\n" + SESSION_INSTRUCTION_INBOUND

    # start transcript logging
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs("transcripts", exist_ok=True)
    transcript = open(f"transcripts/{ctx.room.name}_{ts}.txt", "a", encoding="utf8")

    def _log(ev):
        role = ev.item.role.name.upper()
        for chunk in ev.item.content:
            transcript.write(f"{role}: {chunk}\n")
        transcript.flush()

    session = AgentSession()
    session.on("conversation_item_added", _log)
    session.on("session_closed", lambda ev: transcript.close())

    # launch the conversational agent
    await session.start(
        agent=Assistant(instructions=inst),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )

if __name__ == "__main__":
    agents.cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="inbound-agent"))
