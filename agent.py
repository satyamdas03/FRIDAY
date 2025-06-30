import os
import datetime
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, WorkerOptions, JobContext, RoomInputOptions
from livekit.plugins import openai, silero, noise_cancellation, sarvam

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import query_aws_guide, search_web, send_email
from make_call import make_call

load_dotenv()

class Assistant(agents.Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION + "\nAlways respond in the same language the user spoke.",
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
            tools=[query_aws_guide, search_web, send_email],
        )

    async def on_enter(self):
        await self.session.generate_reply(instructions=SESSION_INSTRUCTION)



async def entrypoint(ctx: JobContext):
    # 1) Connect to LiveKit
    await ctx.connect()

    # 2) If TARGET_PHONE_NUMBER is set, make outbound call + dispatch AI
    phone = os.getenv("TARGET_PHONE_NUMBER")
    if phone:
        try:
            await make_call(ctx.room.name, phone)
        except Exception:
            # if outbound dialing fails, we still want the worker up,
            # so just log and continue, or re-raise if you prefer.
            print("⚠️ outbound dialing failed, check trunk / credentials")

    # prepare transcript file
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    os.makedirs("transcripts", exist_ok=True)
    transcript_path = f"transcripts/{ctx.room.name}_{ts}.txt"
    f = open(transcript_path, "a", encoding="utf8")

    # logging helper
    def _log(ev):
        # never write once closed
        if f.closed:
            return

        msg = ev.item  # ChatMessage
        raw = msg.role
        role_str = raw.name.upper() if hasattr(raw, "name") else str(raw).upper()
        for chunk in msg.content:
            f.write(f"{role_str}: {chunk}\n")
        f.flush()

    session = AgentSession()
    session.on("conversation_item_added", _log)

    # when LiveKit tells us the session is done, close the file
    def _on_closed(ev):
        if not f.closed:
            f.close()
            print(f"Transcript saved to {transcript_path}")

    session.on("session_closed", _on_closed)

    await AgentSession().start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )

if __name__ == "__main__":
    agents.cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name=os.getenv("AGENT_NAME", "inbound-agent"),
    ))


