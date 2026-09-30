from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class CoreRelation(str, Enum):
    PROPOSES = "PROPOSES"
    USES = "USES"
    BUILDS_ON = "BUILDS_ON"
    IMPROVES = "IMPROVES"
    CONTRADICTS = "CONTRADICTS"
    EVALUATES = "EVALUATES"
    AUTHORED_BY = "AUTHORED_BY"
    CITES = "CITES"
    EXTENDS = "EXTENDS"
    COMPARED_WITH = "COMPARED_WITH"
    OTHER = "OTHER"


class ExtractedTriplet(BaseModel):
    subject: str = Field(
        ...,
        description="Canonical name of the subject entity (e.g. BERT, CoAL-RAG, Hallucination)",
    )
    subject_type: str = Field(
        ...,
        description="Category of subject entity (e.g. Method, Model, Metric, Dataset, Problem, Task, Concept, Author)",
    )
    relation: CoreRelation = Field(
        ...,
        description="Relation type from fixed vocabulary, or OTHER if candidate_relation is populated",
    )
    candidate_relation: Optional[str] = Field(
        None,
        description="Proposed new relation name if none of the fixed core relations fit",
    )
    object: str = Field(
        ...,
        description="Canonical name of the object entity (e.g. Transformer, Accuracy, LegalQA)",
    )
    object_type: str = Field(
        ...,
        description="Category of object entity (e.g. Architecture, Dataset, Metric, Problem, Task)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Self-reported extraction confidence score between 0.0 and 1.0",
    )
    evidence_span: str = Field(
        ...,
        description="Verbatim sentence or text span from the chunk supporting this extracted triplet",
    )
    paper_id: str = Field(..., description="ArXiv Paper ID")
    section: str = Field(..., description="Section title where chunk originated")
    chunk_id: Optional[str] = Field(None, description="Chunk identifier")


class ExtractionResponse(BaseModel):
    triplets: List[ExtractedTriplet] = Field(default_factory=list)
