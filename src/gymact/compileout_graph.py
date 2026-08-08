"""Compile repeated cognition into reusable graph routes, never cached authority.

A HOT recipe is an index into an admitted possibility topology: reversible path plus
irreversible frontier identity. Reuse re-admits that route against the current graph.
Execution authority is deliberately absent and must still be minted at the cut.
"""
from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from gymact.combinatorial import ExplorationResult
from gymact.evidence import digest
from gymact.models import FrozenModel, Standing


class GraphRecipeIdentity(FrozenModel):
    problem_identity: str = Field(min_length=1)
    environment_identity: str = Field(min_length=1)
    authority_class: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    verifier_ref: str = Field(min_length=1)
    input_contract_digest: str = Field(min_length=1)
    graph_digest: str = Field(min_length=1)


class CompiledGraphRecipe(FrozenModel):
    identity: GraphRecipeIdentity
    path_id: str = Field(min_length=1)
    reversible_morphism_ids: tuple[str, ...]
    irreversible_morphism_id: str = Field(min_length=1)
    source_receipt_refs: tuple[str, ...] = Field(min_length=1)
    recipe_digest: str = Field(min_length=1)
    standing: Standing = Standing.STRUCTURAL

    @model_validator(mode="after")
    def verify_content_identity(self) -> Self:
        if self.irreversible_morphism_id in self.reversible_morphism_ids:
            raise ValueError("IRREVERSIBLE_MORPHISM_CANNOT_BE_IN_REVERSIBLE_ROUTE")
        payload = self.model_dump(
            mode="json",
            exclude={"recipe_digest", "standing"},
        )
        if self.recipe_digest != digest(payload):
            raise ValueError("COMPILED_GRAPH_RECIPE_DIGEST_MISMATCH")
        return self


class GraphRecipeAdmission(FrozenModel):
    admitted: bool
    model_required: bool
    path_id: str | None = None
    irreversible_morphism_id: str | None = None
    standing: Standing
    reason: str


def compile_graph_recipe(
    identity: GraphRecipeIdentity,
    exploration: ExplorationResult,
    *,
    path_id: str,
    irreversible_morphism_id: str,
    source_receipt_refs: tuple[str, ...],
) -> CompiledGraphRecipe:
    """Compile one successful route while preserving its graph and frontier identity."""
    if exploration.graph_digest != identity.graph_digest:
        raise ValueError("COMPILE_OUT_GRAPH_IDENTITY_MISMATCH")
    path = next((item for item in exploration.paths if item.path_id == path_id), None)
    if path is None:
        raise ValueError("COMPILE_OUT_PATH_NOT_IN_EXPLORATION")
    frontier = next(
        (
            item
            for item in exploration.irreversible_frontier
            if item.path_id == path_id and item.morphism_id == irreversible_morphism_id
        ),
        None,
    )
    if frontier is None:
        raise ValueError("COMPILE_OUT_FRONTIER_NOT_IN_EXPLORATION")
    if not source_receipt_refs:
        raise ValueError("COMPILE_OUT_REQUIRES_SOURCE_RECEIPTS")
    values = {
        "identity": identity,
        "path_id": path_id,
        "reversible_morphism_ids": path.morphism_ids,
        "irreversible_morphism_id": irreversible_morphism_id,
        "source_receipt_refs": source_receipt_refs,
    }
    payload = {
        "identity": identity.model_dump(mode="json"),
        "path_id": path_id,
        "reversible_morphism_ids": path.morphism_ids,
        "irreversible_morphism_id": irreversible_morphism_id,
        "source_receipt_refs": source_receipt_refs,
    }
    return CompiledGraphRecipe(**values, recipe_digest=digest(payload))


def admit_graph_recipe(
    recipe: CompiledGraphRecipe,
    current_identity: GraphRecipeIdentity,
    exploration: ExplorationResult,
) -> GraphRecipeAdmission:
    """Reuse only if the exact graph route and current semantic identity still exist."""
    if recipe.identity != current_identity:
        return GraphRecipeAdmission(
            admitted=False,
            model_required=True,
            standing=Standing.STALE,
            reason="COMPILED_GRAPH_RECIPE_IDENTITY_DRIFT",
        )
    if exploration.graph_digest != recipe.identity.graph_digest:
        return GraphRecipeAdmission(
            admitted=False,
            model_required=True,
            standing=Standing.STALE,
            reason="COMPILED_GRAPH_RECIPE_GRAPH_DRIFT",
        )
    path = next((item for item in exploration.paths if item.path_id == recipe.path_id), None)
    if path is None or path.morphism_ids != recipe.reversible_morphism_ids:
        return GraphRecipeAdmission(
            admitted=False,
            model_required=True,
            standing=Standing.STALE,
            reason="COMPILED_GRAPH_RECIPE_ROUTE_DRIFT",
        )
    frontier_exists = any(
        item.path_id == recipe.path_id
        and item.morphism_id == recipe.irreversible_morphism_id
        for item in exploration.irreversible_frontier
    )
    if not frontier_exists:
        return GraphRecipeAdmission(
            admitted=False,
            model_required=True,
            standing=Standing.STALE,
            reason="COMPILED_GRAPH_RECIPE_FRONTIER_DRIFT",
        )
    return GraphRecipeAdmission(
        admitted=True,
        model_required=False,
        path_id=recipe.path_id,
        irreversible_morphism_id=recipe.irreversible_morphism_id,
        standing=Standing.CANDIDATE,
        reason="HOT_GRAPH_ROUTE_ADMITTED_AUTHORITY_STILL_REQUIRED",
    )
