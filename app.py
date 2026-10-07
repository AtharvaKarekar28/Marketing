"""
Consumer Reaction Simulator: a Streamlit app for testing scenarios on LLM personas.
"""
import os
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv
from openai import OpenAI

from src.runner import run_scenario
from src.database import get_connection
from src.personas import ATTRIBUTES
from src import queries as q

st.set_page_config(page_title="Consumer Reaction Simulator", layout="wide")
load_dotenv()

MODEL = "gpt-4.1-mini"
DECISION_ORDER = ["accept", "reduce", "delay", "switch", "reject"]
DECISION_COLORS = {"accept": "#1D9E75", "reduce": "#97C459", "delay": "#EF9F27",
                   "switch": "#D85A30", "reject": "#A32D2D"}
LABELS = {"age_group": "Age", "income": "Income", "location": "Location",
          "household": "Household", "price_sensitivity": "Price sensitivity",
          "brand_loyalty": "Brand loyalty"}


def escape_dollars(text):
    """Streamlit treats $...$ as math formatting, so escape dollar signs."""
    return text.replace("$", "\\$")


@st.cache_resource
def get_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


st.title("Consumer Reaction Simulator")
st.caption("Simulated customers powered by an LLM. Results are predictions, not real survey data.")

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
            st.session_state["selected"] = new_id
            st.success("Done!")

# ---- Pick a scenario to view ----
conn = get_connection()
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

# ---- Headline numbers ----
s = q.summary(conn, sid)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Customers simulated", int(s["n"]))
c2.metric("Avg purchase intent", f"{s['avg_intent']}/10")
c3.metric("Would keep as normal", f"{s['pct_accept']}%")
c4.metric("Would cancel or switch", f"{s['pct_lost']}%")

# ---- Overall decisions ----
st.subheader("How customers reacted")
d = q.decision_breakdown(conn, sid)
fig = px.bar(d, x="decision", y="pct", color="decision", text="pct",
             category_orders={"decision": DECISION_ORDER},
             color_discrete_map=DECISION_COLORS,
             labels={"pct": "% of customers", "decision": ""})
fig.update_traces(texttemplate="%{text}%", textposition="outside")
fig.update_layout(showlegend=False)
st.plotly_chart(fig)

# ---- Breakdown by group ----
st.subheader("Reactions by customer group")
attr = st.selectbox("Group customers by", list(LABELS), format_func=LABELS.get)
b = q.breakdown_by(conn, sid, attr)
fig2 = px.bar(b, x="pct", y="grp", color="decision", orientation="h",
              category_orders={"decision": DECISION_ORDER, "grp": list(ATTRIBUTES[attr])},
              color_discrete_map=DECISION_COLORS,
              labels={"pct": "% of group", "grp": "", "decision": "Decision"})
fig2.update_layout(barmode="stack")
st.plotly_chart(fig2)

# ---- Quotes ----
st.subheader("In their own words")
for _, row in q.sample_quotes(conn, sid).iterrows():
    st.markdown(
        f"**{row['decision']}** · {row['age_group']}, {escape_dollars(row['income'])}  \n"
        f"> {escape_dollars(row['reason'])}"
    )