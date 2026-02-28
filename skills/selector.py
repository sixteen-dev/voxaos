from llm.client import LLMClient
from skills.loader import Skill

SELECTION_PROMPT = """Given this user request, which skill (if any) should be activated?

Available skills:
{skill_list}

User request: "{user_input}"

Respond with ONLY the skill name, or "none" if no skill applies. No explanation."""


async def select_skill(
    user_input: str,
    skills: list[Skill],
    llm_client: LLMClient,
) -> Skill | None:
    """Use LLM to select the best matching skill for user input.

    Stage 1 of the two-stage skill system. Only descriptions are sent,
    not the full bodies — keeps this call cheap (~100 tokens).
    """
    if not skills:
        return None

    skill_list = "\n".join(f"- {s.name}: {s.description}" for s in skills)
    prompt = SELECTION_PROMPT.format(skill_list=skill_list, user_input=user_input)

    result = await llm_client.chat_simple([{"role": "user", "content": prompt}])
    result = result.strip().lower().strip('"').strip("'")

    if result == "none":
        return None

    # Match to skill by name
    for skill in skills:
        if skill.name.lower() == result:
            return skill

    return None
