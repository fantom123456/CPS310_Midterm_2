import ast
import os
import types
from owlready2 import (
    AllDisjoint,
    ConstrainedDatatype,
    DataProperty,
    FunctionalProperty,
    OwlReadyInconsistentOntologyError,
    Thing,
    World,
    get_ontology,
    sync_reasoner,
)


def build_base_ontology(save_path: str = "ontology/zombie_sim_base.owl"):
    """Creates and saves the canonical OWL 2 DL ontology for CPS310-Zombie-Game."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    onto = get_ontology("http://misericordia.edu/cps310/zombie_sim.owl")

    with onto:
        # Core Simulation Hierarchy
        class SimulationEntity(Thing):
            pass

        class Agent(SimulationEntity):
            pass

        class Civilian(Agent):
            pass

        class Armed(Agent):
            pass

        class Zombie(Agent):
            pass

        AllDisjoint([Civilian, Armed, Zombie])

        # Architectural Subsystems (Decoupled Design)
        class ArchitectureComponent(Thing):
            pass

        class SpatialGrid(ArchitectureComponent):
            pass

        class StorageBackend(ArchitectureComponent):
            pass

        class RAMStorage(StorageBackend):
            pass

        class JSONStorage(StorageBackend):
            pass

        class SwarmLearner(ArchitectureComponent):
            pass

        class PostgresTelemetry(ArchitectureComponent):
            pass

        AllDisjoint([Agent, SpatialGrid, StorageBackend, SwarmLearner, PostgresTelemetry])

        # Datatype Properties
        class hasSpeed(DataProperty, FunctionalProperty):
            domain = [Agent]
            range = [float]

        class hasAttackRange(DataProperty, FunctionalProperty):
            domain = [Agent]
            range = [float]

        class hasHealth(DataProperty, FunctionalProperty):
            domain = [Agent]
            range = [float]

        class hasContextDim(DataProperty, FunctionalProperty):
            domain = [SwarmLearner]
            range = [int]

        # Formal OWL 2 DL Restrictions (Invariants)
        # 1. All agents must have speed in (0.0, 6.0]
        Agent.is_a.append(
            hasSpeed.some(ConstrainedDatatype(float, min_exclusive=0.0, max_inclusive=6.0))
        )
        # 2. All agents must have health in (0.0, 200.0]
        Agent.is_a.append(
            hasHealth.some(ConstrainedDatatype(float, min_exclusive=0.0, max_inclusive=200.0))
        )
        # 3. Zombies are strictly melee-only: attack range <= 2.0
        Zombie.is_a.append(
            hasAttackRange.some(ConstrainedDatatype(float, min_exclusive=0.0, max_inclusive=2.0))
        )
        # 4. LinearThompsonSwarmLearner must match 6D scent-trail feature vector
        SwarmLearner.is_a.append(hasContextDim.value(6))

    onto.save(file=save_path, format="rdfxml")
    return onto


def check_ast_architecture(code_str: str) -> tuple[bool, str]:
    """Enforces decoupled architecture: forbids direct disk/DB I/O inside Agent logic."""
    try:
        tree = ast.parse(code_str)
    except SyntaxError as exc:
        return False, f"AST SyntaxError: {exc}"

    forbidden_imports = {"psycopg2", "psycopg", "sqlite3", "pickle"}
    forbidden_calls = {"open", "dump", "dumps", "write", "writelines"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden_imports:
                    return False, f"AST Violation: Forbidden persistence import '{alias.name}' in Agent logic."
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in forbidden_imports:
                return False, f"AST Violation: Forbidden persistence import from '{node.module}'."
        elif isinstance(node, ast.Call):
            func_name = getattr(node.func, "id", getattr(node.func, "attr", ""))
            if func_name in forbidden_calls:
                return False, (
                    f"AST Violation: Direct I/O call '{func_name}()' violates decoupled StorageBackend invariant."
                )

    return True, "AST Check Passed: Decoupled architecture preserved."


def validate_proposal(
    onto_path: str,
    proposal: dict,
    export_snapshot_path: str | None = None,
) -> tuple[bool, str, str]:
    """
    Validates an AI proposal against both AST rules and HermiT OWL 2 DL reasoning.
    Returns: (is_valid, stage_name, message)
    """
    # Stage 4: AST Architectural Gatekeeper
    ast_ok, ast_msg = check_ast_architecture(proposal["python_code"])
    if not ast_ok:
        return False, "Stage 4 (AST Gatekeeper)", ast_msg

    # Stage 3: Symbolic Ontology Reasoning (HermiT)
    world = World()
    onto = world.get_ontology(onto_path).load()
    parent_name = proposal.get("parent_class", "Zombie")
    parent_cls = getattr(onto, parent_name, None)
    if parent_cls is None:
        return False, "Stage 3 (Ontology Lookup)", f"Unknown parent class '{parent_name}' in ontology."

    props = proposal["properties"]
    with onto:
        candidate_cls = types.new_class(proposal["class_name"], (parent_cls,))
        candidate_ind = candidate_cls(f"{proposal['class_name'].lower()}_instance")
        candidate_ind.hasSpeed = float(props["hasSpeed"])
        candidate_ind.hasAttackRange = float(props["hasAttackRange"])
        candidate_ind.hasHealth = float(props["hasHealth"])

        try:
            sync_reasoner(world, infer_property_values=True)
            inconsistent = list(world.inconsistent_classes())
            if inconsistent:
                if export_snapshot_path:
                    onto.save(file=export_snapshot_path, format="rdfxml")
                return (
                    False,
                    "Stage 3 (HermiT Reasoner)",
                    f"Logical contradiction detected; inconsistent classes: {inconsistent}",
                )
        except OwlReadyInconsistentOntologyError as exc:
            if export_snapshot_path:
                onto.save(file=export_snapshot_path, format="rdfxml")
            return (
                False,
                "Stage 3 (HermiT Reasoner)",
                f"OwlReadyInconsistentOntologyError: Proposal violates OWL axioms ({exc})",
            )

    if export_snapshot_path:
        onto.save(file=export_snapshot_path, format="rdfxml")

    return True, "All Gatekeepers Passed", "PASS: HermiT consistency verified and AST decoupling enforced."