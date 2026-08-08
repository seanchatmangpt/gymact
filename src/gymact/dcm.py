"""Canonical Design for Combinatorial Maximum public API.

Import DCM behavior from here. Lower-level modules remain available for implementation
and compatibility, but this facade defines the intended graph -> court -> cut -> BRCE
surface.
"""
from gymact.action_graph import action_possibility_fragment
from gymact.algebra import compose_paths, identity_path, zero_objectives
from gymact.combinatorial import (
    AdmissionContext,
    Combination,
    CombinationSpace,
    DecisionPhase,
    ExplorationBounds,
    ExplorationResult,
    Factor,
    IrreversibleFrontierEdge,
    MorphismEvaluation,
    MorphismKind,
    MorphismRequirements,
    ObjectiveVector,
    PossibilityGraph,
    PossibilityMorphism,
    PossibilityObject,
    PossibilityObjectKind,
    PossibilityPath,
    manufacture_combination_space,
    pareto_paths,
)
from gymact.combinatorial_rdf import (
    PossibilityRDFValidation,
    graph_to_rdf,
    possibility_shapes,
    query_do_frontier,
    rdf_to_graph,
    validate_possibility_rdf,
)
from gymact.compileout_graph import (
    CompiledGraphRecipe,
    GraphRecipeAdmission,
    GraphRecipeIdentity,
    admit_graph_recipe,
    compile_graph_recipe,
)
from gymact.cut import (
    CombinatorialBRCEBroker,
    CombinatorialBrokerRequest,
    IrreversibleSelection,
    manufacture_broker_request,
    select_irreversible_cut,
)
from gymact.dcm_runtime import DCMDecisionCourt, DecisionCourtRecord, DecisionCourtRequest
from gymact.ecology import (
    EcologyAlternative,
    EcologyDimension,
    IrreversibleOption,
    ManufacturedEcology,
    manufacture_ecology,
)
from gymact.maximal import explore_combinatorial_maximum
from gymact.possibility_index import (
    EmpiricalCombinationRecord,
    EmpiricalPossibilityIndex,
    empirical_pareto,
)
from gymact.structural_scan import StructuralSignature, structural_scan

__all__ = [
    "AdmissionContext",
    "Combination",
    "CombinationSpace",
    "CombinatorialBRCEBroker",
    "CombinatorialBrokerRequest",
    "CompiledGraphRecipe",
    "DCMDecisionCourt",
    "DecisionCourtRecord",
    "DecisionCourtRequest",
    "DecisionPhase",
    "EcologyAlternative",
    "EcologyDimension",
    "EmpiricalCombinationRecord",
    "EmpiricalPossibilityIndex",
    "ExplorationBounds",
    "ExplorationResult",
    "Factor",
    "GraphRecipeAdmission",
    "GraphRecipeIdentity",
    "IrreversibleFrontierEdge",
    "IrreversibleOption",
    "IrreversibleSelection",
    "ManufacturedEcology",
    "MorphismEvaluation",
    "MorphismKind",
    "MorphismRequirements",
    "ObjectiveVector",
    "PossibilityGraph",
    "PossibilityMorphism",
    "PossibilityObject",
    "PossibilityObjectKind",
    "PossibilityPath",
    "PossibilityRDFValidation",
    "StructuralSignature",
    "action_possibility_fragment",
    "admit_graph_recipe",
    "compile_graph_recipe",
    "compose_paths",
    "empirical_pareto",
    "explore_combinatorial_maximum",
    "graph_to_rdf",
    "identity_path",
    "manufacture_broker_request",
    "manufacture_combination_space",
    "manufacture_ecology",
    "pareto_paths",
    "possibility_shapes",
    "query_do_frontier",
    "rdf_to_graph",
    "select_irreversible_cut",
    "structural_scan",
    "validate_possibility_rdf",
    "zero_objectives",
]
