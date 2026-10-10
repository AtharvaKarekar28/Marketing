"""
Evidence finder: searches the web for how real people reacted to a scenario,
so simulated reactions can be compared with reported real-world reactions.

Two-step pipeline:
  1. Research: the model searches the web and writes notes with citations.
  2. Structure: a second request turns those notes into a fixed format,
     using only information found in the notes.

The evidence is gathered separately and is never shown to the personas.
"""

from urllib.parse import urlparse
import json

EVIDENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_real_event": {"type": "boolean"},
        "event_summary": {"type": "string"},
        "reported_sentiment": {"type": "string",
                               "enum": ["mostly negative", "mixed", "mostly positive", "unknown"]},
        "stated_vs_actual": {"type": "string"},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "evidence_strength": {"type": "string",
                              "enum": ["strong", "moderate", "weak", "none"]},
    },
    "required": ["is_real_event", "event_summary", "reported_sentiment",
                 "stated_vs_actual", "key_findings", "evidence_strength"],
    "additionalProperties": False,
}

RESEARCH_PROMPT = (
    "You are a market research analyst. Decide whether the scenario describes a real "
    "event that has already happened. If it is real, search the web for how real "
    "CONSUMERS reacted. Look for: (1) surveys and polls of customers, (2) sales, "
    "subscriber, or cancellation data from before and after the event, and (3) news or "
    "social media coverage of public sentiment. Report separately what consumers SAID "
    "they would do and what consumers ACTUALLY did, since these often differ. Focus on "
    "customer reactions, not on describing the company's policy or statements. Include "
    "specific numbers and dates when sources give them, and cite your sources. Never "
    "invent figures. If the scenario is hypothetical or hasn't happened, say so clearly."
)

STRUCTURE_PROMPT = (
    "Convert the research notes into the required fields. Use ONLY information found "
    "in the notes; do not add any facts of your own. Rules:\n"
    "- event_summary: at most 2 sentences.\n"
    "- stated_vs_actual: what CONSUMERS said they would do vs. what CONSUMERS actually "
    "did. Never describe the company's statements here. If unknown, write 'Unknown'.\n"
    "- key_findings: up to 5 short findings about consumer reactions, each with a "
    "number or date when the notes give one. Exclude policy details.\n"
    "- evidence_strength: 'strong' only if the notes contain hard data (surveys, sales "
    "or subscriber numbers); 'moderate' for consistent news coverage; 'weak' for thin "
    "or anecdotal evidence.\n"
    "- If the notes say the scenario is hypothetical or not a real event, set "
    "is_real_event to false, reported_sentiment to 'unknown', stated_vs_actual to "
    "'Unknown', key_findings to an empty list, and evidence_strength to 'none'."
)


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
    """Run the full pipeline: research, then structure, then attach sources."""
    research_response = research(client, model, scenario)
    if debug:
        print("Output item types:", [item.type for item in research_response.output])

    notes = research_response.output_text
    evidence = structure(client, model, scenario, notes)
    evidence["sources"] = extract_sources(research_response)
    evidence["research_notes"] = notes
    return evidence