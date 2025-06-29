# import os
# import json
# from dotenv import load_dotenv

# from livekit import agents
# from livekit.agents import AgentSession, WorkerOptions, RoomInputOptions
# from livekit.plugins import (
#     openai,
#     silero,
#     noise_cancellation,
#     sarvam,          
# )

# from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
# from tools import query_aws_guide, search_web, send_email
# from make_call import make_call

# load_dotenv()

# class Assistant(agents.Agent):
#     def __init__(self) -> None:
#         super().__init__(
#             instructions=AGENT_INSTRUCTION,
#             # Use Sarvam for STT (auto-detect if you leave language empty, 
#             # or pin it to one code like "hi-IN", "bn-IN", etc.)
#             stt=sarvam.STT(
#                 language=os.getenv("SARVAM_STT_LANG", "hi-IN"),
#                 model=os.getenv("SARVAM_STT_MODEL", "saarika:v2.5"),
#             ),
#             # LLM stays on OpenAI
#             llm=openai.LLM(model="gpt-4o", temperature=0.5),
#             # Use Sarvam TTS in the same language
#             tts=sarvam.TTS(
#                 target_language_code=os.getenv("SARVAM_TTS_LANG", "hi-IN"),
#                 model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v2"),
#                 speaker=os.getenv("SARVAM_SPEAKER", "anushka"),
#             ),
#             vad=silero.VAD.load(),
#             tools=[query_aws_guide, search_web, send_email],
#         )


# async def entrypoint(ctx: agents.JobContext):
#     # 1) Connect the worker
#     await ctx.connect()

#     # 2) If TARGET_PHONE_NUMBER is set, place an outbound call
#     room_name = ctx.room.name
#     phone_number = os.getenv("TARGET_PHONE_NUMBER")
#     if phone_number:
#         await make_call(room_name, phone_number)

#     # 3) Start the voice session—
#     #    Sarvam will now transcribe and speak in your chosen language(s).
#     session = AgentSession()
#     await session.start(
#         agent=Assistant(),
#         room=ctx.room,
#         room_input_options=RoomInputOptions(
#             video_enabled=False,
#             # Krisp noise-cancellation for telephony
#             noise_cancellation=noise_cancellation.BVCTelephony(),
#         ),
#     )

#     # 4) Only greet first on inbound (console) sessions
#     if not phone_number:
#         await session.generate_reply(instructions=SESSION_INSTRUCTION)


# if __name__ == "__main__":
#     agents.cli.run_app(WorkerOptions(
#         entrypoint_fnc=entrypoint,
#         agent_name="inbound-agent"
#     ))










## female voice (bengali accent to improve)
import os
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, WorkerOptions, RoomInputOptions, JobContext
from livekit.plugins import openai, silero, noise_cancellation, sarvam

from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import query_aws_guide, search_web, send_email
from make_call import make_call

load_dotenv()

class Assistant(agents.Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION + "\nAlways respond in the same language the user spoke.",
            # Sarvam STT for Indian languages
            stt=sarvam.STT(
                language=os.getenv("SARVAM_STT_LANG", "en-IN"),
                model=os.getenv("SARVAM_STT_MODEL", "saarika:v2.5"),
            ),
            # use the OpenAI plugin correctly
            llm=openai.LLM(model="gpt-4o", temperature=0.5),
            # Sarvam TTS with a female default speaker
            tts=sarvam.TTS(
                target_language_code=os.getenv("SARVAM_TTS_LANG", "en-IN"),
                model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v2"),
                speaker=os.getenv("SARVAM_SPEAKER", "anushka"),
            ),
            vad=silero.VAD.load(),
            tools=[query_aws_guide, search_web, send_email],
        )

async def entrypoint(ctx: JobContext):
    # 1) Connect the worker
    await ctx.connect()

    # 2) If configured, place an outbound call first
    phone_number = os.getenv("TARGET_PHONE_NUMBER")
    if phone_number:
        await make_call(ctx.room.name, phone_number)

    # 3) Start the agent session (inbound or outbound)
    session = AgentSession()
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )

    # 4) On console/inbound flows, kick off the greeting
    if not phone_number:
        await session.generate_reply(instructions=SESSION_INSTRUCTION)

if __name__ == "__main__":
    agents.cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="inbound-agent",
    ))


