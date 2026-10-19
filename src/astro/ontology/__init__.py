"""The ontology: canonical entities, their names, and the alias matcher (design §8)."""

from astro.ontology.load import OntologyError, cached_ontology, load_ontology
from astro.ontology.model import Entity, Ontology

__all__ = ["Entity", "Ontology", "OntologyError", "cached_ontology", "load_ontology"]
