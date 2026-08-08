"""Compile repeated verified cognition into deterministic powerless HOT recipes."""
from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from gymact.evidence import digest
from gymact.models import FrozenModel, Standing


class RecipeIdentity(FrozenModel):
    problem_identity: str = Field(min_length=1)
    environment_identity: str = Field(min_length=1)
    authority_class: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    verifier_ref: str = Field(min_length=1)
    action_ref: str = Field(min_length=1)
    input_contract_digest: str = Field(min_length=1)


class CompiledRecipe(FrozenModel):
    identity: RecipeIdentity
    candidate_ref: str = Field(min_length=1)
    source_receipt_refs: tuple[str, ...]
    recipe_digest: str = Field(min_length=1)
    standing: Standing = Standing.STRUCTURAL

    @model_validator(mode="after")
    def verify_content_identity(self) -> Self:
        if not self.source_receipt_refs:
            raise ValueError("COMPILE_OUT_REQUIRES_SOURCE_RECEIPTS")
        payload = {
            "identity": self.identity.model_dump(mode="json"),
            "candidate_ref": self.candidate_ref,
            "source_receipt_refs": self.source_receipt_refs,
        }
        if self.recipe_digest != digest(payload):
            raise ValueError("COMPILED_RECIPE_DIGEST_MISMATCH")
        return self


class RecipeAdmission(FrozenModel):
    admitted: bool
    model_required: bool
    candidate_ref: str | None = None
    standing: Standing
    reason: str


def compile_recipe(
    identity: RecipeIdentity,
    *,
    candidate_ref: str,
    source_receipt_refs: tuple[str, ...],
) -> CompiledRecipe:
    """Manufacture a deterministic recipe only from witnessed source receipts."""
    if not source_receipt_refs:
        raise ValueError("COMPILE_OUT_REQUIRES_SOURCE_RECEIPTS")
    payload = {
        "identity": identity.model_dump(mode="json"),
        "candidate_ref": candidate_ref,
        "source_receipt_refs": source_receipt_refs,
    }
    return CompiledRecipe(
        identity=identity,
        candidate_ref=candidate_ref,
        source_receipt_refs=source_receipt_refs,
        recipe_digest=digest(payload),
    )


def admit_compiled_recipe(
    recipe: CompiledRecipe,
    current: RecipeIdentity,
) -> RecipeAdmission:
    """Admit HOT selection only under exact semantic/authority/verifier identity.

    The result is still a candidate. It cannot carry or manufacture an ExecutionGrant.
    """
    if recipe.identity != current:
        return RecipeAdmission(
            admitted=False,
            model_required=True,
            standing=Standing.STALE,
            reason="COMPILED_RECIPE_IDENTITY_DRIFT",
        )
    if recipe.standing not in {Standing.STRUCTURAL, Standing.ALIVE}:
        return RecipeAdmission(
            admitted=False,
            model_required=True,
            standing=Standing.PARTIAL_ALIVE,
            reason="COMPILED_RECIPE_NOT_ADMISSIBLE",
        )
    return RecipeAdmission(
        admitted=True,
        model_required=False,
        candidate_ref=recipe.candidate_ref,
        standing=Standing.CANDIDATE,
        reason="HOT_RECIPE_CANDIDATE_ADMITTED_AUTHORITY_STILL_REQUIRED",
    )


class RecipeCache:
    """Content-addressed deterministic recipe cache; no authority objects are stored."""

    def __init__(self) -> None:
        self._recipes: dict[str, CompiledRecipe] = {}

    def put(self, recipe: CompiledRecipe) -> None:
        self._recipes[recipe.recipe_digest] = recipe

    def get(self, recipe_digest: str) -> CompiledRecipe | None:
        return self._recipes.get(recipe_digest)
