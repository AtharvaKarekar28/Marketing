"""
Analysis queries: the SQL that powers the app's charts.
"""
import pandas as pd

# Persona columns users can group by. Column names can't be passed with "?",
# so we only allow names from this list to prevent SQL injection.
GROUPABLE = {"age_group", "income", "location", "household", "price_sensitivity",
             "brand_loyalty", "usage_level", "customer_status"}


def list_scenarios(conn):
    """All scenarios run so far, newest first, with their response counts."""
    return pd.read_sql_query("""
        SELECT s.scenario_id, s.description, s.created_at,
               COUNT(r.response_id) AS n_responses
        FROM scenarios s
        LEFT JOIN responses r ON s.scenario_id = r.scenario_id
        GROUP BY s.scenario_id
        ORDER BY s.scenario_id DESC
    """, conn)


def summary(conn, scenario_id):
    """Headline numbers for one scenario."""
    return pd.read_sql_query("""
        SELECT COUNT(*) AS n,
               ROUND(AVG(intent_score), 1) AS avg_intent,
               ROUND(100.0 * AVG(decision = 'accept'), 1) AS pct_accept,
               ROUND(100.0 * AVG(decision IN ('switch', 'reject')), 1) AS pct_lost
        FROM responses
        WHERE scenario_id = ?
    """, conn, params=(scenario_id,)).iloc[0]


def customer_effect(conn, scenario_id):
    """Simulated customers gained and lost.
    Gained: non-customers and non-paying users who would start paying (accept).
    Lost: current paying customers who would cancel or switch."""
    return pd.read_sql_query("""
        SELECT
            COUNT(*) AS n,
            SUM(p.customer_status = 'current customer') AS n_current,
            SUM(p.customer_status != 'current customer') AS n_prospects,
            SUM(p.customer_status != 'current customer' AND r.decision = 'accept') AS gained,
            SUM(p.customer_status = 'current customer'
                AND r.decision IN ('switch', 'reject')) AS lost
        FROM responses r
        JOIN personas p ON r.persona_id = p.persona_id
        WHERE r.scenario_id = ?
    """, conn, params=(scenario_id,)).iloc[0]


def decision_breakdown(conn, scenario_id):
    """Share of customers choosing each decision."""
    return pd.read_sql_query("""
        SELECT decision, COUNT(*) AS n,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM responses
        WHERE scenario_id = ?
        GROUP BY decision
    """, conn, params=(scenario_id,))


def sentiment_breakdown(conn, scenario_id):
    """Share of customers with each sentiment."""
    return pd.read_sql_query("""
        SELECT sentiment, COUNT(*) AS n,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
        FROM responses
        WHERE scenario_id = ?
        GROUP BY sentiment
    """, conn, params=(scenario_id,))


def breakdown_by(conn, scenario_id, attribute):
    """Decision shares within each value of a persona attribute."""
    if attribute not in GROUPABLE:
        raise ValueError(f"Can't group by {attribute}")
    return pd.read_sql_query(f"""
        SELECT p.{attribute} AS grp, r.decision, COUNT(*) AS n,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY p.{attribute}), 1) AS pct
        FROM responses r
        JOIN personas p ON r.persona_id = p.persona_id
        WHERE r.scenario_id = ?
        GROUP BY p.{attribute}, r.decision
    """, conn, params=(scenario_id,))


def sample_quotes(conn, scenario_id, per_decision=2):
    """A few random quotes for each decision type."""
    return pd.read_sql_query("""
        WITH ranked AS (
            SELECT r.decision, r.reason, p.age_group, p.income, p.customer_status,
                   ROW_NUMBER() OVER (PARTITION BY r.decision ORDER BY RANDOM()) AS rn
            FROM responses r
            JOIN personas p ON r.persona_id = p.persona_id
            WHERE r.scenario_id = ?
        )
        SELECT decision, reason, age_group, income, customer_status
        FROM ranked
        WHERE rn <= ?
    """, conn, params=(scenario_id, per_decision))