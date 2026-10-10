"""
Evidence finder: searches the web for how real people reacted to a scenario,
so simulated reactions can be compared with reported real-world reactions.

Two-step pipeline:
  1. Research: the model searches the web and writes notes with citations.
  2. Structure: a second request turns those notes into a fixed format,
     using only information found in the notes.

Code-level safeguards (these always apply, whatever the model decides):
  - Scenarios about "our/my/we/us" are treated as hypothetical with no search.
  - If the model can't name the specific company, or says the evidence isn't
    about this exact event, the scenario is treated as hypothetical.

The evidence is gathered separately and is never shown to the personas.
"""
import json
import re
from urllib.parse import urlparse

# Words that mean the scenario is about the user's own (unnamed) business
FIRST_PERSON = re.compile(r"\b(our|my|we|us)\b", re.IGNORECASE)

EVIDENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_real_event": {"type": "boolean"},
        "named_company": {"type": "string"},
        "evidence_matches_scenario": {"type": "boolean"},
        "event_summary": {"type": "string"},
        "reported_sentiment": {"type": "string",
                               "enum": ["mostly negative", "mixed", "mostly neutral",
                                        "mostly positive", "unknown"]},
        "net_customer_effect": {"type": "string",
                                "enum": ["gained customers", "lost customers",
                                         "no clear change", "unknown"]},
        "stated_vs_actual": {"type": "string"},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "evidence_strength": {"type": "string",
                              "enum": ["strong", "moderate", "weak", "none"]},
    },
    "required": ["is_real_event", "named_company", "evidence_matches_scenario",
                 "event_summary", "reported_sentiment", "net_customer_effect",
                 "stated_vs_actual", "key_findings", "evidence_strength"],
    "additionalProperties": False,
}

RESEARCH_PROMPT = (
    "You are a market research analyst. Decide whether the scenario describes a real "
    "event that has already happened. If it is real, search the web for how real "
    "CONSUMERS reacted. Look for: (1) surveys and polls of customers, (2) sales, "
    "subscriber, sign-up, or cancellation data from before and after the event, and "
    "(3) news or social media coverage of public sentiment. Report separately what "
    "consumers SAID they would do and what consumers ACTUALLY did, since these often "
    "differ. Focus on customer reactions, not on describing the company's policy or "
    "statements. Include specific numbers and dates when sources give them, and cite "
    "your sources. Never invent figures. Only treat the scenario as real if it names a "
    "specific, identifiable company or brand and you find coverage of that exact event. "
    "General industry trends, or similar events at other companies, do not count as "
    "evidence for this scenario. If the scenario is hypothetical or hasn't happened, "
    "say so clearly."
)

STRUCTURE_PROMPT = (
    "Convert the research notes into the required fields. Use ONLY information found "
    "in the notes; do not add any facts of your own. Rules:\n"
    "- named_company: the specific company or brand the scenario is about, exactly as "
    "named. If the scenario doesn't name one, use an empty string.\n"
    "- evidence_matches_scenario: true ONLY if the notes describe this exact event at "
    "this exact company. False if they describe general trends, a different company, "
    "or a different event.\n"
    "- event_summary: at most 2 sentences.\n"
    "- reported_sentiment: the overall tone of what consumers SAID and felt.\n"
    "- net_customer_effect: based on what consumers ACTUALLY did (sales, subscriber, "
    "sign-up, or cancellation data), not what they said. 'gained customers' if the "
    "business ended up with more customers, 'lost customers' if fewer, 'no clear "
    "change' if the data shows little change, 'unknown' if the notes have no data "
    "on actual behavior.\n"
    "- stated_vs_actual: what CONSUMERS said they would do vs. what CONSUMERS actually "
    "did. Never describe the company's statements here. If unknown, write 'Unknown'.\n"
    "- key_findings: up to 5 short findings about consumer reactions, each with a "
    "number or date when the notes give one. Exclude policy details.\n"
    "- evidence_strength: 'strong' only if the notes contain hard data (surveys, sales "
    "or subscriber numbers); 'moderate' for consistent news coverage; 'weak' for thin "
    "or anecdotal evidence.\n"
    "- If the notes say the scenario is hypothetical or not a real event, set "
    "is_real_event to false, reported_sentiment and net_customer_effect to 'unknown', "
    "stated_vs_actual to 'Unknown', key_findings to an empty list, and "
    "evidence_strength to 'none'."
)


def hypothetical_result(summary):
    """The standard result for a scenario with no real-world evidence."""
    return {
        "is_real_event": False,
        "named_company": "",
        "evidence_matches_scenario": False,
        "event_summary": summary,
        "reported_sentiment": "unknown",
        "net_customer_effect": "unknown",
        "stated_vs_actual": "Unknown",
        "key_findings": [],
        "evidence_strength": "none",
        "sources": [],
        "research_notes": "",
    }


def extract_sources(response):
    """Collect cited pages and pages the search visited, without duplicates."""
    sources, seen = [], set()

    def add(url, title):
        if not url:
            return
        url = url.replace("?utm_source=openai", "").replace("&utm_source=openai", "")
        if url in seen:
            return
        seen.add(url)
        if not title or title.startswith("http"):
            title = urlparse(url).netloc.replace("www.", "")
        sources.append({"title": title, "url": url})

    def field(obj, key):
        return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)

    for item in response.output:
        if item.type == "message":
            for part in item.content:
                for ann in getattr(part, "annotations", None) or []:
                    if ann.type == "url_citation":
                        add(ann.url, ann.title)
        elif item.type == "web_search_call":
            action = getattr(item, "action", None)
            for src in field(action, "sources") or []:
                add(field(src, "url"), field(src, "title"))
    return sources


def research(client, model, scenario):
    """Step 1: search the web and write research notes with citations."""
    return client.responses.create(
        model=model,
        tools=[{"type": "web_search"}],
        tool_choice="required",
        include=["web_search_call.action.sources"],
        input=[
            {"role": "system", "content": RESEARCH_PROMPT},
            {"role": "user", "content": f"Scenario: {scenario}"},
        ],
    )


def structure(client, model, scenario, notes):
    """Step 2: turn the research notes into the fixed evidence format."""
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": STRUCTURE_PROMPT},
            {"role": "user", "content": f"Scenario: {scenario}\n\nResearch notes:\n{notes}"},
        ],
        response_format={"type": "json_schema",
                         "json_schema": {"name": "real_world_evidence",
                                         "strict": True, "schema": EVIDENCE_SCHEMA}},
    )
    return json.loads(response.choices[0].message.content)


def find_evidence(client, model, scenario, debug=False):
    """Run the full pipeline with code-level safeguards against false matches."""
    # Safeguard 1: a scenario about your own business has no public evidence
    if FIRST_PERSON.search(scenario):
        return hypothetical_result(
            "This scenario describes your own business, so there is no public "
            "real-world evidence to search for.")

    research_response = research(client, model, scenario)
    if debug:
        print("Output item types:", [item.type for item in research_response.output])

    notes = research_response.output_text
    evidence = structure(client, model, scenario, notes)

    # Safeguards 2 and 3: no named company, or evidence about a different event
    if not evidence["named_company"].strip() or not evidence["evidence_matches_scenario"]:
        result = hypothetical_result(
            "No evidence was found about this exact event, so it's treated as "
            "hypothetical. Related news (like general industry trends) doesn't count.")
        result["research_notes"] = notes
        return result

    evidence["sources"] = extract_sources(research_response)
    evidence["research_notes"] = notes
    return evidence