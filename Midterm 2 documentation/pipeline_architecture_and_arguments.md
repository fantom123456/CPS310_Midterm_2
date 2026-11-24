# Ontology-Driven Process Control Pipeline for AI-Driven Development of CPS310-Zombie-Game

## 1. Explicit 6-Stage Process Control Pipeline

Every AI-proposed modification to `CPS310-Zombie-Game` (whether introducing a new agent class or tuning `LinearThompsonSwarmLearner` parameters) passes through a deterministic 6-stage closed-loop control pipeline:

1. **Stage 1 — Baseline State & Ontology Grounding (`sense_state`):**
   * Loads the canonical simulation ontology (`ontology/zombie_sim_base.owl`) using `owlready2`.
   * Retrieves baseline performance metrics from the PostgreSQL 18 `simulation_runs` telemetry schema (port 5432), including survivor percentages, infection counts, and tick execution latency.
   * Serializes active class hierarchies, disjointness axioms, and datatype bounds into a structured context payload.
2. **Stage 2 — Constrained AI Synthesis (`propose_change`):**
   * Sends a structured prompt (documented in `docs/prompts_catalog.md`) containing the active ontology rules, recent telemetry, and engineering goal to a free-tier LLM (e.g., Gemini 2.5 Flash or Llama-3.3-70B, with an offline deterministic fallback if API rate limits occur).
   * Requires a structured JSON payload containing both an **ontological assertion** (new subclass/individual + property values) and a **Python implementation patch**.
3. **Stage 3 — Symbolic Description Logic Reasoning (`validate_semantics`):**
   * Instantiates the proposed class and individual inside an isolated `owlready2.World` and executes the **HermiT** OWL 2 DL reasoner (`sync_reasoner()`).
   * Halts execution immediately if HermiT raises `OwlReadyInconsistentOntologyError` or infers unsatisfiable classes (`owl:Nothing`)—for example, if a `Zombie` subclass is given ranged attack capabilities (`hasAttackRange > 2.0`) or invalid speed bounds.
4. **Stage 4 — Architectural & AST Gatekeeping (`validate_architecture`):**
   * Parses the AI-generated Python code via Python's built-in `ast` module.
   * Enforces the decoupled architectural invariants modeled in the ontology:
     * Simulation entities (`Agent`, `SpatialGrid`, `LinearThompsonSwarmLearner`) are disjoint from `StorageBackend` (`RAMStorage`, `JSONStorage`) and `PostgresTelemetry`.
     * Direct disk I/O calls (`open`, `json.dump`, `json.dumps`, `write`) and database drivers (`psycopg2`, `psycopg`, `sqlite3`) are blocked inside `Agent` step logic.
5. **Stage 5 — Automated Feedback & Self-Correction (`feedback_retry`):**
   * Upon Stage 3 or Stage 4 rejection, captures the exact HermiT consistency error or AST rule violation.
   * Injects that error trace into **Prompt C (Violation Repair)** and re-queries the LLM (up to $N = 3$ attempts) so the AI repairs its own proposal against the formal rules before execution.
6. **Stage 6 — Headless Simulation Execution & Telemetry Commit (`execute_and_log`):**
   * Once validated, runs a deterministic headless benchmark (`1200.0 x 1200.0` arena, `SpatialGrid` spatial bucketing, and `LinearThompsonSwarmLearner` directional weights).
   * Logs the resulting metrics and saves the verified OWL 2 DL snapshot (`ontology/zombie_sim_verified_demo2_accepted.owl`) alongside the demo transcript for GitHub version control.

---

## 2. Pipeline Design & Control Theory Rationale

The pipeline applies **closed-loop feedback control** to AI-assisted software development:

* **The Plant:** The `CPS310-Zombie-Game` simulation engine (`SpatialGrid`, `LinearThompsonSwarmLearner`, and decoupled persistence backends).
* **The Actuator:** The LLM code and parameter generator.
* **The Sensor & Comparator:** The OWL 2 DL ontology (`zombie_sim_base.owl`) + HermiT reasoner + Python `ast` static analyzer.
* **The Feedback Loop:** Pre-execution logical violation traces (inner symbolic repair loop) and post-execution simulation telemetry (outer empirical evaluation loop).

Separating **probabilistic synthesis** (LLM creativity) from **deterministic invariant verification** (HermiT + AST) guarantees that invalid physics, broken matrix dimensions, or tightly coupled disk I/O never enter the simulation runtime or corrupt `ProcessPoolExecutor` workers.

---

## 3. Rigorous Argument: Controlled Pipeline vs. Naive AI-Driven Development

| Controlled Aspect | Naive AI-Driven Development (Uncontrolled LLM) | Ontology-Controlled Process Pipeline | Why the Control Is Effective |
| :--- | :--- | :--- | :--- |
| **1. Domain Physics & Game Balance** | When asked to "increase zombie lethality," an unconstrained LLM frequently invents ranged acid attacks or supersonic speeds (`speed > Armed`), breaking core melee mechanics and causing instant civilian wipeouts. | Enforced via OWL `ConstrainedDatatype` axioms (`Zombie` restricted to `hasAttackRange <= 2.0` and `0.0 < hasSpeed <= 6.0`). HermiT detects violations statically in `< 0.5s`. | Prevents wasted compute on trivial, unbalanced simulations and guarantees every agent archetype obeys domain semantics. |
| **2. Architectural Decoupling (CPS310 Midterm Invariant)** | When asked to "log agent state," naive LLMs routinely inject `open('debug.json', 'w')` directly inside `Agent.step()` or `SpatialGrid`, violating separation of concerns and creating severe disk I/O bottlenecks at 10,000 agents. | `SimulationEntity` and `StorageBackend` are declared `AllDisjoint` in OWL; the AST gatekeeper rejects file I/O calls inside simulation logic modules. | Preserves the decoupled `RAMStorage` / `JSONStorage` architecture and protects $O(1)$ spatial grid lookup throughput. |
| **3. Contextual Bandit Dimensional Integrity** | Naive edits to `LinearThompsonSwarmLearner` often alter prior covariance matrices ($B$) or weight vectors ($\mu$) without matching the 6-element scent-trail context vector, causing runtime NumPy `ValueError: shapes not aligned` crashes mid-run. | Ontology binds `SwarmLearner` via `hasContextDim == 6`, verified statically before instantiation. | Eliminates mid-simulation matrix dimension crashes during multi-tick reinforcement learning runs. |
| **4. Reproducibility & Auditability** | Ad-hoc chat edits leave no formal record of which domain assumptions changed between runs, making `simulation_runs` comparisons ambiguous. | Every accepted run serializes a versioned `.owl` artifact alongside the Python patch and demo log. | Provides an auditable formal specification tied directly to empirical simulation outcomes. |