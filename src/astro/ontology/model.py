"""Ontology entities (design §8, phase1-foundations §3.1).

Every entity has an ID `<kind>:<slug>`, `names` (aliases the matcher may use) and
`ambiguous_names` (never matched alone; reported as ambiguous). Each kind's attributes are a
Pydantic model with unknown fields forbidden, so a misspelt key in a YAML file fails loading.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Attrs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    names: tuple[str, ...] = ()
    ambiguous_names: tuple[str, ...] = ()


class SignDegree(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sign: str
    degree: float | None = None
    source: str | None = None


class Range(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sign: str
    from_: float = Field(alias="from")
    to: float
    source: str | None = None


class NaturalFriendship(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    friends: tuple[str, ...]
    neutral: tuple[str, ...]
    enemies: tuple[str, ...]


# A disputed value is a list of views, each with its source (design §8, KNW-2).
class Graha(Attrs):
    own_signs: tuple[str, ...] = ()
    exaltation: SignDegree | tuple[SignDegree, ...] | None = None
    debilitation: SignDegree | tuple[SignDegree, ...] | None = None
    moolatrikona: Range | tuple[Range, ...] | None = None
    natural_friendship: NaturalFriendship | None = None


class Lorded(Attrs):
    id: str
    lord: str


class Listed(Attrs):
    id: str


class Varga(Attrs):
    divisions: int
    parts: Literal["equal", "table"]
    start: dict[str, Any] | None = None
    step: int | None = None
    table: dict[str, Any] | None = None


class DashaSystem(Attrs):
    total_years: float
    sequence: tuple[dict[str, Any], ...]


class KarakaScheme(Attrs):
    roles: dict[str, tuple[str, ...]]
    native: dict[str, str] = {}


class Bhava(Attrs):
    ordinals: tuple[str, ...]
    significations: tuple[str, ...] = ()
    karakas: tuple[str, ...] = ()


class BhavaGroup(Attrs):
    members: tuple[int, ...]


class Yoga(Attrs):
    category: Literal["lunar", "solar", "mahapurusha", "raja", "dhana", "cancellation",
                      "arishta", "nabhasa", "dosha", "other"]


class Topic(Attrs):
    tier: Literal["core", "should"]


@dataclass(frozen=True)
class Entity:
    id: str           # <kind>:<slug>
    kind: str
    file: str         # the YAML file it came from (for messages and the review pack)
    attrs: Attrs

    @property
    def slug(self) -> str:
        return self.id.split(":", 1)[1]


@dataclass(frozen=True)
class Ontology:
    entities: dict[str, Entity]
    version: str                         # every file + the fold rules (passages, releases)
    status: Literal["provisional", "reviewed"]
    file_status: dict[str, str]
    house_words: tuple[str, ...] = ()

    def get(self, entity_id: str) -> Entity:
        return self.entities[entity_id]

    def of_kind(self, kind: str) -> list[Entity]:
        return [e for e in self.entities.values() if e.kind == kind]

    def kinds(self) -> list[str]:
        return sorted({e.kind for e in self.entities.values()})
