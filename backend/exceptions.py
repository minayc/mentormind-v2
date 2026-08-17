class MentorMindError(Exception):
    """Base exception for all MentorMind Errors."""
    pass

class DocumentNotFoundError(MentorMindError):
    """File path does NOT exist."""
    pass

class EmbeddingError(MentorMindError):
    """Failed in embedding return."""
    pass

class CollectionNotFoundError(MentorMindError):
    """Could NOT find in the database."""
    pass

class EvaluationError(MentorMindError):
    """Unusable data has been returned by Gemini."""
    pass
