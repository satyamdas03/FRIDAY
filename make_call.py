# make_call.py
import os
import logging
import asyncio
from dotenv import load_dotenv
from livekit import api
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest
from livekit.protocol.sip import CreateSIPParticipantRequest

load_dotenv()
logger = logging.getLogger("make-call")
logger.setLevel(logging.INFO)

async def make_call(room_name: str, phone_number: str):
    lkapi = api.LiveKitAPI()
    try:
        # 1) Dispatch the agent into the room
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(
                agent_name=os.getenv("AGENT_NAME", "inbound-agent"),
                room=room_name,
                metadata=phone_number,
            )
        )
        logger.info(f"Dispatch created: {dispatch.id}")

        # 2) Dial the SIP user into the same room
        sip = await lkapi.sip.create_sip_participant(
            CreateSIPParticipantRequest(
                room_name=room_name,
                sip_trunk_id=os.getenv("SIP_OUTBOUND_TRUNK_ID"),
                sip_call_to=phone_number,
                # optional: override the caller ID to match a number on your trunk:
                # sip_number=os.getenv("SIP_CALLER_ID"),
                participant_identity=phone_number,
                participant_name="Friday Caller",
                krisp_enabled=True,
                wait_until_answered=True,
                play_dialtone=True,
            )
        )
        logger.info(f"SIP participant created: {sip}")
    except Exception as e:
        logger.error(f"make_call error: {e}", exc_info=True)
        raise
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    # quick local smoke-test:
    num = os.getenv("TARGET_PHONE_NUMBER")
    room = os.getenv("LIVEKIT_ROOM_NAME", "outbound-test-room")
    asyncio.run(make_call(room, num))
