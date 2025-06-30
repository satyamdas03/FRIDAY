import os
import logging
import asyncio
from dotenv import load_dotenv
from livekit import api

load_dotenv()

logger = logging.getLogger("make-call")
logger.setLevel(logging.INFO)

async def make_call(room_name: str, phone_number: str):
    """Dispatch our agent into the room, then dial out and bridge the phone user in."""
    lkapi = api.LiveKitAPI()

    # 1) Grab your SIP trunk ID
    trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")
    if not trunk_id or not trunk_id.startswith("ST_"):
        raise RuntimeError("SIP_OUTBOUND_TRUNK_ID is not set or invalid")

    # 2) Dispatch the agent (must match the name in agent.py: cli.run_app(..., agent_name="inbound-agent"))
    dispatch = await lkapi.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name="inbound-agent",
            room=room_name,
            metadata=phone_number,           # could also be a JSON blob
        )
    )
    logger.info(f"Agent dispatched: {dispatch.dispatch_id}")

    # 3) Create the SIP participant (dial out)
    sip_part = await lkapi.sip.create_sip_participant(
        api.CreateSIPParticipantRequest(
            room_name=room_name,
            sip_trunk_id=trunk_id,
            sip_call_to=phone_number,
            participant_identity=f"sip-{phone_number}",
            participant_name="Outbound Caller",
            krisp_enabled=True,
            wait_until_answered=True,
        )
    )
    logger.info(f"SIP participant created: {sip_part.participant_identity}")

    # 4) Clean up
    await lkapi.aclose()


if __name__ == "__main__":
    # Local smoke test
    tgt = os.getenv("TARGET_PHONE_NUMBER")
    if not tgt:
        raise RuntimeError("Set TARGET_PHONE_NUMBER in .env for a quick test")
    room = os.getenv("LIVEKIT_ROOM_NAME", "outbound-test-room")
    asyncio.run(make_call(room, tgt))
