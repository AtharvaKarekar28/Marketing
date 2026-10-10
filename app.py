"""
Consumer Reaction Simulator: a Streamlit app for testing scenarios on LLM personas,
with an automatic real-world evidence check for scenarios that really happened.
"""
import os
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv
from openai import OpenAI

from src.runner import run_scenario
from src.evidence import find_evidence
from src.personas import ATTRIBUTES
from src import database as db
from src import queries as q

st.set_page_config(page_title="Consumer Reaction Simulator", layout="wide")
load_dotenv()

MODEL = "gpt-4.1-mini"
DECISION_ORDER = ["accept", "reduce", "delay", "switch", "reject"]
DECISION_COLORS = {"accept": "#1D9E75", "reduce": "#97C459", "delay": "#EF9F27",
                   "switch": "#D85A30", "reject": "#A32D2D"}
SENTIMENT_ORDER = ["negative", "neutral", "positive"]
SENTIMENT_COLORS = {"negative": "#A32D2D", "neutral": "#888780", "positive": "#1D9E75"}
LABELS = {"age_group": "Age", "income": "Income", "location": "Location",
          "household": "Household", "price_sensitivity": "Price sensitivity",
          "brand_loyalty": "Brand loyalty", "usage_level": "Usage level"}


def escape_dollars(text):
    """Streamlit treats $...$ as math formatting, so escape dollar signs."""
    return text.replace("$", "\\$")


@st.cache_resource
def get_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def simulated_sentiment_label(sentiment_df):
    """Summarize simulated sentiments into the same labels the evidence uses.
    The 60% cutoff is a design choice, not a standard."""
    pct = dict(zip(sentiment_df["sentiment"], sentiment_df["pct"]))
    if pct.get("negative", 0) >= 60:
        return "mostly negative"
    if pct.get("positive", 0) >= 60:
        return "mostly positive"
    return "mixed"


def compare_labels(simulated, reported):
    """Rate how well the simulated mood matches the reported real-world mood."""
    if reported == "unknown":
        return None
    if simulated == reported:
        return "match"
    if "mixed" in (simulated, reported):
        return "partial"
    return "mismatch"


def check_evidence(conn, scenario_id, description):
    """Search for real-world evidence and save it, without crashing the app on failure."""
    try:
        ev = find_evidence(get_client(), MODEL, description)
        db.save_evidence(conn, scenario_id, ev)
    except Exception as e:
        st.warning(f"Couldn't check real-world evidence: {e}")


st.title("Consumer Reaction Simulator")
st.caption("Simulated customers powered by an LLM. Results are predictions, not real survey data.")
conn = db.get_connection()

# ---- Sidebar: run a new scenario ----
with st.sidebar:
    st.header("Run a new scenario")
    scenario = st.text_area(
        "Describe the scenario",
        placeholder="e.g. Our phone's price increases from $899 to $999 with a better camera.",
    )
    n = st.slider("Number of simulated customers", 10, 100, 30, step=10)
    if st.button("Run simulation", type="primary"):
        if not scenario.strip():
            st.error("Enter a scenario first.")
        else:
            with st.spinner(f"Asking {n} simulated customers..."):
                new_id = run_scenario(get_client(), MODEL, scenario.strip(), n_personas=n)
            with st.spinner("Searching for real-world reactions..."):
                check_evidence(conn, new_id, scenario.strip())
            st.session_state["selected"] = new_id
            st.success("Done!")

# ---- Pick a scenario to view ----
scenarios = q.list_scenarios(conn)
if scenarios.empty:
    st.info("No scenarios yet. Describe one in the sidebar to get started.")
    st.stop()

options = scenarios["scenario_id"].tolist()
descriptions = scenarios.set_index("scenario_id")["description"]
selected = st.session_state.get("selected")
sid = st.selectbox("Scenario", options,
                   index=options.index(selected) if selected in options else 0,
                   format_func=lambda i: descriptions[i])

s = q.summary(conn, sid)
tab_sim, tab_real = st.tabs(["Simulated reactions", "Real-world reality check"])

# ================= Tab 1: Simulated reactions =================
with tab_sim:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Customers simulated", int(s["n"]))
    c2.metric("Avg purchase intent", f"{s['avg_intent']}/10")
    c3.metric("Would keep as normal", f"{s['pct_accept']}%")
    c4.metric("Would cancel or switch", f"{s['pct_lost']}%")

    st.subheader("How customers reacted")
    d = q.decision_breakdown(conn, sid)
    fig = px.bar(d, x="decision", y="pct", color="decision", text="pct",
                 category_orders={"decision": DECISION_ORDER},
                 color_discrete_map=DECISION_COLORS,
                 labels={"pct": "% of customers", "decision": ""})
    fig.update_traces(texttemplate="%{text}%", textposition="outside")
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, key="decisions_chart")

    st.subheader("Reactions by customer group")
    attr = st.selectbox("Group customers by", list(LABELS), format_func=LABELS.get)
    b = q.breakdown_by(conn, sid, attr)
    fig2 = px.bar(b, x="pct", y="grp", color="decision", orientation="h",
                  category_orders={"decision": DECISION_ORDER, "grp": list(ATTRIBUTES[attr])},
                  color_discrete_map=DECISION_COLORS,
                  labels={"pct": "% of group", "grp": "", "decision": "Decision"})
    fig2.update_layout(barmode="stack")
    st.plotly_chart(fig2, key="groups_chart")

    st.subheader("In their own words")
    for _, row in q.sample_quotes(conn, sid).iterrows():
        st.markdown(
            f"**{row['decision']}** · {row['age_group']}, {escape_dollars(row['income'])}  \n"
            f"> {escape_dollars(row['reason'])}"
        )

# ================= Tab 2: Real-world reality check =================
with tab_real:
    ev = db.get_evidence(conn, sid)

    if ev is None:
        st.info("This scenario hasn't been checked against real-world evidence yet.")
        if st.button("Check real-world evidence"):
            with st.spinner("Searching for real-world reactions..."):
                check_evidence(conn, sid, descriptions[sid])
            st.rerun()

    elif not ev["is_real_event"]:
        st.info("This looks like a hypothetical scenario, so there are no real-world "
                "reactions to compare against. Treat the simulated results as a prediction.")
        st.caption(escape_dollars(ev["event_summary"]))

    else:
        st.markdown(f"**What happened:** {escape_dollars(ev['event_summary'])}")

        # Mood comparison
        sent = q.sentiment_breakdown(conn, sid)
        sim_label = simulated_sentiment_label(sent)
        result = compare_labels(sim_label, ev["reported_sentiment"])

        c1, c2 = st.columns(2)
        c1.metric("Simulated customer mood", sim_label.capitalize())
        c2.metric("Reported real-world mood", ev["reported_sentiment"].capitalize())

        if result == "match":
            st.success("**Match:** the simulated mood matches how real customers reacted.")
        elif result == "partial":
            st.warning("**Partial match:** one side was mixed, so the moods only partly agree.")
        elif result == "mismatch":
            st.error("**Mismatch:** the simulated mood is the opposite of the real reaction.")
        else:
            st.info("There isn't enough reported evidence on customer mood to compare.")

        fig3 = px.bar(sent, x="sentiment", y="pct", color="sentiment", text="pct",
                      category_orders={"sentiment": SENTIMENT_ORDER},
                      color_discrete_map=SENTIMENT_COLORS,
                      labels={"pct": "% of simulated customers", "sentiment": ""},
                      title="Simulated customer mood")
        fig3.update_traces(texttemplate="%{text}%", textposition="outside")
        fig3.update_layout(showlegend=False)
        st.plotly_chart(fig3, key="sentiment_chart")

        # Behavior comparison
        st.subheader("What customers said vs. what they did")
        st.markdown(f"**Real world:** {escape_dollars(ev['stated_vs_actual'])}")
        st.markdown(f"**Simulation:** {s['pct_lost']}% of simulated customers "
                    f"said they would cancel or switch.")

        if ev["key_findings"]:
            st.subheader("Key findings")
            for finding in ev["key_findings"]:
                st.markdown(f"- {escape_dollars(finding)}")

        strength = ev["evidence_strength"]
        if strength in ("weak", "none"):
            st.warning(f"Evidence strength: **{strength}**. Treat this comparison with caution.")
        else:
            st.caption(f"Evidence strength: {strength}")

        with st.expander(f"Sources ({len(ev['sources'])})"):
            for src in ev["sources"]:
                st.markdown(f"- [{escape_dollars(src['title'])}]({src['url']})")