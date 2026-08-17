from dataclasses import dataclass


@dataclass
class Chunk:
    id: str
    text: str
    source: str


@dataclass
class Message:
    role: str
    content: str


@dataclass
class EvaluationResult:
    score: int
    feedback: str
    concept: str = ""


@dataclass
class ConceptStatus:
    concept: str
    understood: bool
    score: int
    attempts: int = 1