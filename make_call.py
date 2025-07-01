# make_call.py
import os, logging, asyncio
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
        # 1) dispatch the AI into the room
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(
                agent_name=os.getenv("AGENT_NAME", "inbound-agent"),
                room=room_name,
                metadata=phone_number,
            )
        )
        logger.info(f"Dispatched AI agent into room {room_name}")

        # 2) dial out over SIP trunk
        sip = await lkapi.sip.create_sip_participant(
            CreateSIPParticipantRequest(
                room_name=room_name,
                sip_trunk_id=os.getenv("SIP_OUTBOUND_TRUNK_ID"),
                sip_number=os.getenv("SIP_CALLER_ID"),
                sip_call_to=phone_number,
                participant_identity=phone_number,
                participant_name="Friday Caller",
                krisp_enabled=True,
                wait_until_answered=True,
                play_dialtone=True,
            )
        )
        logger.info(f"SIP participant created: {sip}")
    except Exception:
        logger.exception("make_call failed")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    # quick smoke‐test
    import time
    room = os.getenv("LIVEKIT_ROOM_NAME") or f"outbound-test-{int(time.time())}"
    num  = os.getenv("TARGET_PHONE_NUMBER")
    asyncio.run(make_call(room, num))
