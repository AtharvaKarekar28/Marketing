"""
Simulator: sends a scenario to a persona and returns a structured reaction.
"""
import json
import random
from src.personas import persona_to_prompt

DECISIONS = ["accept", "reduce", "delay", "switch", "reject"]

# The strict template the model must follow
RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "persona_reaction",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "decision": {"type": "string", "enum": DECISIONS},
                "intent_score": {"type": "integer",
                                 "description": "1-10, likelihood to buy or keep the product"},
                "sentiment": {"type": "string",
                              "enum": ["negative", "neutral", "positive"]},
                "reason": {"type": "string",
                           "description": "1-2 sentences, first person, in character"},
            },
            "required": ["decision", "intent_score", "sentiment", "reason"],
            "additionalProperties": False,
        },
    },
}

DECISION_TEXT = {
    "accept": "accept: buy or keep the product as normal",
    "reduce": "reduce: keep it, but downgrade or use it less",
    "delay": "delay: wait before deciding or buying",
    "switch": "switch: move to a competing product or brand",
    "reject": "reject: cancel or don't buy, without replacing it",
}


def build_instructions(seed):
    """Build the instructions with the options in a shuffled order."""
    options = list(DECISION_TEXT.values())
    random.Random(seed).shuffle(options)
    return (
        "React to the scenario above as yourself. Before deciding, think about "
        "the realistic alternatives available to you, including staying with "
        "what you have.\nChoose your decision:\n- " + "\n- ".join(options) + "\n"
        "Give an intent_score from 1 (definitely not buying/keeping) to 10 "
        "(definitely buying/keeping), your sentiment, and a short reason in your own voice."
    )

def ask_persona(client, model, persona, scenario, temperature=0.9):
    """Send one scenario to one persona and return their structured reaction."""
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": persona_to_prompt(persona)},
            {"role": "user", "content": f"{scenario}\n\n{build_instructions(persona['id'])}"},"},
        ],
        response_format=RESPONSE_FORMAT,
    )
    reaction = json.loads(response.choices[0].message.content)
    return {"persona_id": persona["id"], **reaction}