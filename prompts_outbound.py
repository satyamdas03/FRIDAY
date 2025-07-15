# # prompts_outbound.py

# from prompts import AGENT_INSTRUCTION
# from textwrap import dedent

# def get_outbound_session_instruction(
#     name: str,
#     pain: str,
#     solutions: str
# ) -> str:
#     """
#     Build a single‐utterance session prompt for outbound calls:
#      1) Confirm you’re speaking to the right person
#      2) Acknowledge their pain
#      3) Pitch your solution
#      4) Ask a call-to-action question
#     """
#     return dedent(f"""{AGENT_INSTRUCTION}

# # Outbound Call Script

# Hello {name}, i am Supriya from workmates core2cloud. I understand you’re currently facing:
# “{pain}.” Here’s how we can help you right away: {solutions}. 

# Does that sound like something that would address your needs today?
# """)









# prompts_outbound.py

from prompts import AGENT_INSTRUCTION
from textwrap import dedent

def get_outbound_session_instruction(
    name: str,
    pain: str,
    solutions: str
) -> str:
    """
    Build a single‐utterance session prompt for outbound calls:
     1) Confirm you’re speaking to the right person
     2) Acknowledge their pain
     3) Pitch your solution
     4) Ask a call-to-action question
    """
    return dedent(f"""{AGENT_INSTRUCTION}

# Outbound Call Script

Hello I am Supriya from Workmates Core2Cloud, how can i help you today?
""")