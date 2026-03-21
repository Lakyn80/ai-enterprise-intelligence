"""Schemas for deterministic facts queries and results."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

FactEntity = Literal["product"]
FactOperation = Literal["rank"]
FactMetric = Literal["quantity", "revenue", "promo_lift", "avg_price"]
FactDirection = Literal["desc", "asc"]


class FactQuerySpec(BaseModel):
    """Canonical machine-readable spec for deterministic fact queries."""

    spec_version: Literal[1] = 1
    query_type: Literal["fact"] = "fact"
    entity: FactEntity = "product"
    operation: FactOperation = "rank"
    metric: FactMetric
    direction: FactDirection
    filters: dict[str, Any] = Field(default_factory=dict)
    date_range: None = None
    limit: int = 1

    @field_validator("limit")
    @classmethod
    def _validate_limit(cls, value: int) -> int:
        if value != 1:
            raise ValueError("Deterministic facts v1 supports only limit=1")
        return value

    @model_validator(mode="after")
    def _validate_v1_scope(self) -> "FactQuerySpec":
        if self.filters:
            raise ValueError("Deterministic facts v1 does not support filters")
        if self.date_range is not None:
            raise ValueError("Deterministic facts v1 does not support date_range")
        return self

    def canonical_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def spec_hash(self) -> str:
        canonical = json.dumps(
            self.canonical_payload(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FactWinner(BaseModel):
    product_id: str
    value: float


class FactResolveResult(BaseModel):
    resolved: bool = True
    entity: FactEntity
    metric: FactMetric
    direction: FactDirection
    winners: list[FactWinner]
    tie: bool
