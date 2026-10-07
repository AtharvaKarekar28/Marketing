"""
Simulator: sends a scenario to a persona and returns a structured reaction.
"""
import json
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

INSTRUCTIONS = (
    "React to the scenario above as yourself. Choose your decision:\n"
    "- accept: buy or keep the product as normal\n"
    "- reduce: keep it but downgrade or use it less\n"
    "- delay: wait before deciding\n"
    "- switch: move to a competitor\n"
    "- reject: cancel or don't buy\n"
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
            {"role": "user", "content": f"{scenario}\n\n{INSTRUCTIONS}"},
        ],
        response_format=RESPONSE_FORMAT,
    )
    reaction = json.loads(response.choices[0].message.content)
    return {"persona_id": persona["id"], **reaction}