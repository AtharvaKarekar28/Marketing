"""
Persona generator: creates simulated customers with realistic attribute mixes.

NOTE: Age, income, location, and household weights are approximate U.S. adult
figures, rounded for simplicity. Price sensitivity, brand loyalty, usage level,
and customer status weights are our own assumptions, not population data.
"""
import random

# Each attribute maps values to how common they are (weights sum to ~1.0)
ATTRIBUTES = {
    "age_group": {"18-24": 0.12, "25-34": 0.18, "35-44": 0.17,
                  "45-54": 0.16, "55-64": 0.17, "65+": 0.20},
    "income": {"under $35k": 0.25, "$35k-$75k": 0.28,
               "$75k-$150k": 0.28, "over $150k": 0.19},
    "location": {"urban": 0.31, "suburban": 0.55, "rural": 0.14},
    "household": {"lives alone": 0.28, "with partner": 0.30,
                  "with family and kids": 0.30, "with roommates": 0.12},
    "price_sensitivity": {"low": 0.30, "medium": 0.45, "high": 0.25},
    "brand_loyalty": {"low": 0.30, "medium": 0.45, "high": 0.25},
    "usage_level": {"heavy": 0.30, "regular": 0.45, "occasional": 0.25},
    "customer_status": {"current customer": 0.55, "non-paying user": 0.15,
                        "not a customer": 0.30},
}

# Readable phrasing for each attribute value
LOCATION_TEXT = {"urban": "an urban area", "suburban": "a suburban area",
                 "rural": "a rural area"}
HOUSEHOLD_TEXT = {"lives alone": "living alone",
                  "with partner": "living with a partner",
                  "with family and kids": "living with family and kids",
                  "with roommates": "living with roommates"}
USAGE_TEXT = {"heavy": "a heavy user who relies on it daily",
              "regular": "a regular user",
              "occasional": "an occasional user"}
STATUS_TEXT = {
    "current customer": "You currently pay for the product or brand in the scenario.",
    "non-paying user": ("You currently use the product or brand in the scenario without "
                        "paying for it yourself, for example through someone else's "
                        "account or a free version."),
    "not a customer": "You don't currently use the product or brand in the scenario.",
}


def generate_personas(n, seed=42):
    """Create n personas by randomly drawing each attribute by its weight."""
    rng = random.Random(seed)
    personas = []
    for i in range(n):
        persona = {"id": i}
        for attr, options in ATTRIBUTES.items():
            values = list(options.keys())
            weights = list(options.values())
            persona[attr] = rng.choices(values, weights=weights)[0]
        personas.append(persona)
    return personas


def persona_to_prompt(p):
    """Turn a persona's attributes into a system prompt for the LLM."""
    return (
        f"You are a U.S. consumer aged {p['age_group']}, with a household income "
        f"of {p['income']}, living in {LOCATION_TEXT[p['location']]}, "
        f"{HOUSEHOLD_TEXT[p['household']]}. Your price sensitivity is "
        f"{p['price_sensitivity']} and your brand loyalty is {p['brand_loyalty']}. "
        f"For the product category in any scenario, you are "
        f"{USAGE_TEXT[p['usage_level']]}. {STATUS_TEXT[p['customer_status']]} "
        f"Respond as this person realistically would, based on their situation, "
        f"not as an AI assistant."
    )