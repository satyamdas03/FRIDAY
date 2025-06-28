import os
import logging
import asyncio
from dotenv import load_dotenv
from livekit import api

load_dotenv()

logger = logging.getLogger("make-call")
logger.setLevel(logging.INFO)

async def make_call(room_name: str, phone_number: str):
    """Dispatch the agent and dial the phone user into the same LiveKit room."""
    lkapi = api.LiveKitAPI()

    trunk = os.getenv("SIP_OUTBOUND_TRUNK_ID")
    if not trunk or not trunk.startswith("ST_"):
        raise RuntimeError("SIP_OUTBOUND_TRUNK_ID is not set or invalid")

    # 1) Dispatch the agent explicitly
    dispatch = await lkapi.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name="Friday",
            room=room_name,
            metadata=phone_number
        )
    )
    logger.info(f"Dispatch created: {dispatch}")

    # 2) Dial out and bridge the phone user
    sip = await lkapi.sip.create_sip_participant(
        api.CreateSIPParticipantRequest(
            room_name=room_name,
            sip_trunk_id=trunk,
            sip_call_to=phone_number,
            participant_identity=phone_number,
            wait_until_answered=True,
        )
    )
    logger.info(f"Created SIP participant: {sip}")

    await lkapi.aclose()


if __name__ == "__main__":
    # quick local test
    num = os.getenv("TARGET_PHONE_NUMBER")
    room = os.getenv("LIVEKIT_ROOM_NAME", "aws-call-room")
    asyncio.run(make_call(room, num))
