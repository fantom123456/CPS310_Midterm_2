import argparse
import json
import math
import os
import random
import time
import urllib.request
from datetime import datetime, timezone

from ontology_validator import build_base_ontology, validate_proposal


class HeadlessZombieBenchmark:
    """
    Self-contained headless benchmark mirroring CPS310-Zombie-Game
    (1200x1200 arena, SpatialGrid cell bucketing, LinearThompsonSwarmLearner directional weights).
    """

    def __init__(self, width=1200.0, height=1200.0, cell_size=40.0, seed=2026):
        self.width = width
        self.height = height
        self.cell_size = cell_size
        self.rng = random.Random(seed)

    def run(self, zombie_props: dict, n_civilians=350, n_armed=50, n_zombies=100, ticks=150) -> dict:
        t0 = time.perf_counter()
        agents = []
        for _ in range(n_civilians):
            agents.append({
                "type": "Civilian",
                "x": self.rng.uniform(0, self.width),
                "y": self.rng.uniform(0, self.height),
                "hp": 100.0,
                "speed": 2.6,
            })
        for _ in range(n_armed):
            agents.append({
                "type": "Armed",
                "x": self.rng.uniform(0, self.width),
                "y": self.rng.uniform(0, self.height),
                "hp": 120.0,
                "speed": 2.8,
            })
        for _ in range(n_zombies):
            agents.append({
                "type": "Zombie",
                "x": self.rng.uniform(0, self.width),
                "y": self.rng.uniform(0, self.height),
                "hp": zombie_props["hasHealth"],
                "speed": zombie_props["hasSpeed"],
                "range": zombie_props["hasAttackRange"],
            })

        infections = 0
        for _ in range(ticks):
            grid = {}
            for idx, a in enumerate(agents):
                if a["hp"] <= 0:
                    continue
                cell = (int(a["x"] // self.cell_size), int(a["y"] // self.cell_size))
                grid.setdefault(cell, []).append(idx)

            for idx, a in enumerate(agents):
                if a["hp"] <= 0:
                    continue
                angle = self.rng.uniform(0, 2 * math.pi)
                a["x"] = min(max(0.0, a["x"] + math.cos(angle) * a["speed"]), self.width)
                a["y"] = min(max(0.0, a["y"] + math.sin(angle) * a["speed"]), self.height)

                if a["type"] == "Zombie":
                    cx, cy = int(a["x"] // self.cell_size), int(a["y"] // self.cell_size)
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            for target_idx in grid.get((cx + dx, cy + dy), []):
                                target = agents[target_idx]
                                if target["type"] in ("Civilian", "Armed") and target["hp"] > 0:
                                    dist = math.hypot(a["x"] - target["x"], a["y"] - target["y"])
                                    if dist <= a["range"] + 12.0:
                                        target["type"] = "Zombie"
                                        target["speed"] = zombie_props["hasSpeed"]
                                        target["range"] = zombie_props["hasAttackRange"]
                                        infections += 1
                                        break

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        survivors = sum(1 for a in agents if a["type"] in ("Civilian", "Armed") and a["hp"] > 0)
        zombies_end = sum(1 for a in agents if a["type"] == "Zombie" and a["hp"] > 0)
        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "ticks": ticks,
            "initial_humans": n_civilians + n_armed,
            "surviving_humans": survivors,
            "survival_rate_pct": round((survivors / (n_civilians + n_armed)) * 100.0, 2),
            "final_zombies": zombies_end,
            "total_infections": infections,
            "runtime_ms": round(elapsed_ms, 2),
        }


def call_llm_agent(task: str, feedback_error: str | None = None) -> dict:
    """
    Calls free-tier Gemini 2.5 Flash if GEMINI_API_KEY is configured;
    otherwise uses a deterministic fallback reproducing the exact
    Prompt B -> HermiT Rejection -> Prompt C Self-Correction trace.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            prompt = (
                "You are an AI developer for CPS310-Zombie-Game. Return ONLY valid JSON with keys: "
                "'class_name', 'parent_class', 'properties' (hasSpeed, hasAttackRange, hasHealth), 'python_code'. "
                f"Task: {task}. "
            )
            if feedback_error:
                prompt += f"PREVIOUS ATTEMPT REJECTED: {feedback_error}. Fix the constraint violation."

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
            body = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                cleaned = raw_text.strip().removeprefix("```json").removesuffix("```").strip()
                return json.loads(cleaned)
        except Exception as exc:
            print(f"[LLM Notice] Live free-tier API unavailable ({exc}); using deterministic demo trace.")

    if feedback_error is None:
        # Attempt 1: Naive LLM proposes ranged zombie (violates Zombie hasAttackRange <= 2.0)
        return {
            "class_name": "AcidSpitterZombie",
            "parent_class": "Zombie",
            "properties": {
                "hasSpeed": 3.2,
                "hasAttackRange": 18.0,
                "hasHealth": 90.0,
            },
            "python_code": (
                "class AcidSpitterZombie(Zombie):\n"
                "    def step(self, grid, context_vec):\n"
                "        self.attack_range = 18.0\n"
            ),
        }
    else:
        # Attempt 2: Repaired proposal after receiving HermiT violation trace via Prompt C
        return {
            "class_name": "StalkerZombie",
            "parent_class": "Zombie",
            "properties": {
                "hasSpeed": 4.1,
                "hasAttackRange": 1.8,
                "hasHealth": 110.0,
            },
            "python_code": (
                "class StalkerZombie(Zombie):\n"
                "    def step(self, grid, context_vec):\n"
                "        return self.select_scent_direction(context_vec)\n"
            ),
        }


def run_demo_pipeline():
    os.makedirs("ontology", exist_ok=True)
    os.makedirs("demos", exist_ok=True)

    base_owl = "ontology/zombie_sim_base.owl"
    build_base_ontology(base_owl)

    log_lines = []

    def log(msg: str):
        print(msg)
        log_lines.append(msg)

    log("=== STAGE 1: Baseline State & Ontology Grounding ===")
    log(f"Loaded canonical OWL 2 DL ontology: {base_owl}")
    log("Active Invariants: Zombie hasAttackRange <= 2.0 | Agent hasSpeed in (0.0, 6.0] | No Disk I/O in Agent logic\n")

    task = "Design a specialized Zombie archetype to increase hunting pressure without breaking melee physics."
    feedback_error = None

    for attempt in range(1, 4):
        log(f"=== ATTEMPT {attempt}: Stage 2 (AI Proposal Generation) ===")
        proposal = call_llm_agent(task, feedback_error=feedback_error)
        log(f"Proposed Class: {proposal['class_name']} | Properties: {json.dumps(proposal['properties'])}")

        snapshot_path = (
            "ontology/zombie_sim_inferred_demo1_rejected.owl"
            if attempt == 1
            else "ontology/zombie_sim_verified_demo2_accepted.owl"
        )
        is_valid, stage, reason = validate_proposal(base_owl, proposal, export_snapshot_path=snapshot_path)

        if not is_valid:
            log(f"[REJECTED] {stage} -> {reason}")
            log(f"Saved inconsistent OWL state snapshot to: {snapshot_path}")
            log("=== Stage 5: Feeding Violation Trace into Prompt C for Automated Repair ===\n")
            feedback_error = f"{stage}: {reason}"
            with open("demos/demo1_rejection_trace.log", "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines) + "\n")
        else:
            log(f"[ACCEPTED] {stage} -> {reason}")
            log(f"Saved verified OWL 2 DL ontology snapshot to: {snapshot_path}\n")

            log("=== STAGE 6: Headless Simulation Execution & Telemetry Logging ===")
            bench = HeadlessZombieBenchmark(seed=2026)
            metrics = bench.run(proposal["properties"])
            log(f"Simulation Telemetry Output: {json.dumps(metrics, indent=2)}")

            with open("demos/demo2_accepted_run.log", "w", encoding="utf-8") as f:
                f.write("\n".join(log_lines) + "\n")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run CPS310 Ontology Process Control Pipeline")
    parser.add_argument("--demo", action="store_true", help="Execute end-to-end rejection and self-correction demos")
    args = parser.parse_args()
    run_demo_pipeline()