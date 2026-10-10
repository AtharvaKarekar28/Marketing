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
                                 "description": "1-10, likelihood to pay for the product"},
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

# Definitions work for current customers and non-customers alike
DECISION_TEXT = {
    "accept": "accept: pay for the product as normal (keep paying, or start paying if you don't now)",
    "reduce": "reduce: keep or get it, but downgrade, use it less, or choose a cheaper option",
    "delay": "delay: wait before deciding",
    "switch": "switch: move to a competing product or brand",
    "reject": "reject: don't pay for it (cancel, stop using it, or don't buy), without replacing it",
}


def build_instructions(seed):
    """Build the instructions with the options in a shuffled order,
    so no option gets an advantage from always being listed first."""
    options = list(DECISION_TEXT.values())
    random.Random(seed).shuffle(options)
    return (
        "React to the scenario above as yourself. Before deciding, think about "
        "the realistic alternatives available to you, including staying with "
        "what you have.\nChoose your decision:\n- " + "\n- ".join(options) + "\n"
        "Give an intent_score from 1 (definitely won't pay for it) to 10 "
        "(definitely will pay for it), your sentiment, and a short reason in your own voice."
    )


def ask_persona(client, model, persona, scenario, temperature=0.9):
    """Send one scenario to one persona and return their structured reaction."""
    instructions = build_instructions(persona["id"])
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": persona_to_prompt(persona)},
            {"role": "user", "content": f"{scenario}\n\n{instructions}"},
        ],
        response_format=RESPONSE_FORMAT,
    )
    reaction = json.loads(response.choices[0].message.content)
    return {"persona_id": persona["id"], **reaction}