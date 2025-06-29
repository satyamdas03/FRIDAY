# import os
# import datetime
# import asyncio
# from dotenv import load_dotenv
# from typing import Any  # For untyped event objects

# from livekit import agents
# from livekit.agents import AgentSession, WorkerOptions, JobContext, ChatRole
# from livekit.plugins import openai, silero, noise_cancellation, sarvam

# from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
# from tools import query_aws_guide, search_web, send_email
# from make_call import make_call

# load_dotenv()

# class ConversationLogger:
#     """Simplified transcript logger"""
#     def __init__(self, path: str):
#         self._path = path
#         self._conversation = []
#         self._active = True
#         print(f"Logger initialized for {path}")

#     def log_message(self, role: ChatRole, text: str):
#         """Log a message to the conversation history"""
#         if not self._active or not text.strip():
#             return
            
#         # Add to conversation history
#         self._conversation.append((role, text))
#         print(f"LOG: {role.name} - {text}")

#     async def save(self):
#         """Write the entire conversation to file"""
#         if not self._conversation:
#             print("No conversation content to save")
#             return
            
#         try:
#             with open(self._path, "w", encoding="utf8") as f:
#                 for role, text in self._conversation:
#                     f.write(f"{role.name.upper()}: {text}\n\n")
#                 print(f"Saved transcript with {len(self._conversation)} messages to {self._path}")
#         except Exception as e:
#             print(f"Error saving transcript: {e}")

#     def close(self):
#         self._active = False

# class Assistant(agents.Agent):
#     def __init__(self, logger: ConversationLogger) -> None:
#         super().__init__(
#             instructions=(
#                 AGENT_INSTRUCTION +
#                 "\nAlways respond in the same language the user spoke."
#             ),
#             stt=sarvam.STT(
#                 language=os.getenv("SARVAM_STT_LANG", "en-IN"),
#                 model=os.getenv("SARVAM_STT_MODEL", "saarika:v2.5"),
#             ),
#             llm=openai.LLM(model="gpt-4o", temperature=0.5),
#             tts=sarvam.TTS(
#                 target_language_code=os.getenv("SARVAM_TTS_LANG", "en-IN"),
#                 model=os.getenv("SARVAM_TTS_MODEL", "bulbul:v2"),
#                 speaker=os.getenv("SARVAM_SPEAKER", "anushka"),
#             ),
#             vad=silero.VAD.load(),
#             tools=[query_aws_guide, search_web, send_email],
#         )
#         self._logger = logger
        
#         # Setup event handlers BEFORE the agent is used
#         self.stt.on("transcription_final", self._on_user_speech)
#         self.llm.on("text_final", self._on_agent_response)
#         print("Agent event handlers registered")

#     async def on_enter(self):
#         await self.session.generate_reply(instructions=SESSION_INSTRUCTION)

#     def _on_user_speech(self, ev: Any):  # Use Any type for events
#         """Handle user speech transcription"""
#         # Access text using correct property from search results :cite[9]
#         if hasattr(ev, 'alternatives') and ev.alternatives:
#             text = ev.alternatives[0].text
#             self._logger.log_message(ChatRole.USER, text)
#             print(f"USER TRANSCRIPT: {text}")

#     def _on_agent_response(self, ev: Any):  # Use Any type for events
#         """Handle agent text response"""
#         # Access text using correct property from search results :cite[1]
#         if hasattr(ev, 'text'):
#             self._logger.log_message(ChatRole.ASSISTANT, ev.text)
#             print(f"AGENT RESPONSE: {ev.text}")

# async def entrypoint(ctx: JobContext):
#     await ctx.connect()
    
#     phone = os.getenv("TARGET_PHONE_NUMBER")
#     if phone:
#         await make_call(ctx.room.name, phone)

#     # Setup transcript path
#     ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
#     os.makedirs("transcripts", exist_ok=True)
#     transcript_path = f"transcripts/{ctx.room.name}_{ts}.txt"
#     logger = ConversationLogger(transcript_path)

#     # Create agent FIRST with the logger
#     agent = Assistant(logger)
#     print("Agent created")

#     # Create session with conversation tracking
#     session = AgentSession()
#     session.track_conversation = True
#     print(f"Session created with tracking: {session.track_conversation}")

#     try:
#         await session.start(
#             agent=agent,
#             room=ctx.room,
#             room_input_options=agents.RoomInputOptions(
#                 video_enabled=False,
#                 text_enabled=True,
#                 noise_cancellation=noise_cancellation.BVCTelephony(),
#             ),
#         )
#         print("Session completed successfully")
#     except Exception as e:
#         print(f"Session error: {e}")
#     finally:
#         # Save and close logger
#         await logger.save()
#         logger.close()
#         print(f"Transcript process completed for {transcript_path}")

# if __name__ == "__main__":
#     agents.cli.run_app(WorkerOptions(
#         entrypoint_fnc=entrypoint,
#         agent_name="inbound-agent",
#     ))












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
        # fires once the session is live — safe to greet here
        await self.session.generate_reply(instructions=SESSION_INSTRUCTION)


async def entrypoint(ctx: JobContext):
    # connect to LiveKit
    await ctx.connect()

    # if outbound dialing is desired
    phone = os.getenv("TARGET_PHONE_NUMBER")
    if phone:
        await make_call(ctx.room.name, phone)

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

    # now start (this blocks until hangup)
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVCTelephony(),
        ),
    )
    # no finally needed — we’ll clean up in _on_closed()

if __name__ == "__main__":
    agents.cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="inbound-agent",
    ))


