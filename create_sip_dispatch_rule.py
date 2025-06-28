import asyncio
from livekit import api

async def main():
    lkapi = api.LiveKitAPI()

    # match all inbound trunks by omitting trunk_ids
    rule = api.SIPDispatchRule(
        dispatch_rule_individual=api.SIPDispatchRuleIndividual(
            room_prefix="call-",
        )
    )

    room_cfg = api.RoomConfiguration(
        agents=[api.RoomAgentDispatch(agent_name="Friday", metadata="{}")]
    )

    req = api.CreateSIPDispatchRuleRequest(rule=rule, room_config=room_cfg)
    dispatch = await lkapi.sip.create_sip_dispatch_rule(req)
    print("Created dispatch:", dispatch)
    await lkapi.aclose()

asyncio.run(main())
