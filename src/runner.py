"""
Scenario runner: sends one scenario to many personas and saves every reaction.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.personas import generate_personas
from src.simulator import ask_persona
from src import database as db


def ask_with_retry(client, model, persona, scenario, attempts=3):
    """Try a request up to 3 times, waiting longer after each failure."""
    for attempt in range(attempts):
        try:
            return ask_persona(client, model, persona, scenario)
        except Exception as e:
            if attempt == attempts - 1:
                print(f"Persona {persona['id']} failed: {e}")
                return None
            time.sleep(2 ** attempt)  # wait 1s, then 2s


def run_scenario(client, model, scenario, n_personas=50, max_workers=5):
    """Run a scenario across n personas and save all responses to the database."""
    personas = generate_personas(n_personas)
    conn = db.get_connection()
    db.save_personas(conn, personas)
    scenario_id = db.create_scenario(conn, scenario, model)

    saved = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(ask_with_retry, client, model, p, scenario)
                   for p in personas]
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                db.save_response(conn, scenario_id, result)
                saved += 1

    conn.close()
    print(f"Scenario {scenario_id}: saved {saved}/{n_personas} responses")
    return scenario_id