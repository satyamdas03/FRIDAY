# create_sip_dispatch_rule.py

import asyncio
from livekit import api

async def create_sip_dispatch_rule(
    trunk_ids: list[str],
    room_prefix: str,
    agent_name: str
):
    """
    Create a SIP dispatch rule that sends inbound calls on the given trunks
    to LiveKit rooms prefixed by room_prefix, and dispatches to the named agent.
    """
    lkapi = api.LiveKitAPI()

    # build the rule
    rule = api.SIPDispatchRule(
        trunk_ids=trunk_ids,
        dispatch_rule_individual=api.SIPDispatchRuleIndividual(
            room_prefix=room_prefix,
        )
    )

    # configure which agent to send into the room
    room_cfg = api.RoomConfiguration(
        agents=[api.RoomAgentDispatch(agent_name=agent_name, metadata="{}")]
    )

    req = api.CreateSIPDispatchRuleRequest(rule=rule, room_config=room_cfg)
    dispatch = await lkapi.sip.create_sip_dispatch_rule(req)
    await lkapi.aclose()
    return dispatch


# If you still want to be able to run this file directly:
if __name__ == "__main__":
    # example usage
    example_trunks = ["ST_7SBaKYvoFYc4"]
    example_prefix = "call-"
    example_agent  = "Friday"
    result = asyncio.run(create_sip_dispatch_rule(example_trunks, example_prefix, example_agent))
    print("Created dispatch:", result)
