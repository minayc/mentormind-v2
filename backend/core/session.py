from backend.core.schemas import Message, EvaluationResult, ConceptStatus


class Session:
    def __init__(self, coach, evaluator, vector_store, sources: list[str] = None):
        self.coach = coach
        self.evaluator = evaluator
        self.vector_store = vector_store
        self.sources = sources or []
        self.history: list[Message] = []
        self.scores: list[int] = []
        self.concepts: list[ConceptStatus] = []



    def _is_question(self, text: str) -> bool:
        text = text.strip()
        if text.endswith("?"):
            return True
        starters = (
            "what", "how", "why", "when", "where", "who",
            "can", "could", "would", "is", "are", "do",
            "does", "did", "should", "will", "you",
        )
        first_word = text.lower().split()[0] if text else ""
        return first_word in starters

    def _get_difficulty(self) -> str:
        if len(self.scores) < 2:
            return "medium"
        recent = self.scores[-3:]
        average = sum(recent) / len(recent)
        if average >= 7:
            return "hard"
        elif average >= 4:
            return "medium"
        else:
            return "easy"

    def _get_chunks(self, query: str):
        """Search only within session sources. Returns empty if no sources set."""
        if self.sources:
            return self.vector_store.search(query, sources=self.sources)
        return []

    def _find_concept_idx(self, concept: str) -> int | None:
        """Return index of a matching existing concept (case-insensitive), or None."""
        needle = concept.lower().strip()
        for i, c in enumerate(self.concepts):
            if c.concept.lower().strip() == needle:
                return i
        return None

    def _get_struggling_concepts(self) -> list[str]:
        """Concepts seen 2+ times with average score below 5 need a different approach."""
        return [
            c.concept for c in self.concepts
            if c.attempts >= 2 and c.score < 5
        ]

    def _update_concepts(self, evaluation: EvaluationResult, user_message: str) -> ConceptStatus:
        """Apply a new evaluation to the concept registry. Returns the updated concept."""
        concept_name = (
            evaluation.concept.strip()
            if evaluation.concept and len(evaluation.concept.strip()) > 2
            else user_message.strip()[:50]
        )

        existing_idx = self._find_concept_idx(concept_name)
        if existing_idx is not None:
            existing = self.concepts[existing_idx]
            new_attempts = existing.attempts + 1
            new_score = round(
                (existing.score * existing.attempts + evaluation.score) / new_attempts
            )
            self.concepts[existing_idx] = ConceptStatus(
                concept=existing.concept,
                understood=new_score >= 6,
                score=new_score,
                attempts=new_attempts,
            )
            return self.concepts[existing_idx]
        else:
            new_concept = ConceptStatus(
                concept=concept_name,
                understood=evaluation.score >= 6,
                score=evaluation.score,
                attempts=1,
            )
            self.concepts.append(new_concept)
            return new_concept

    #public API

    def chat(self, user_message: str) -> tuple[str, EvaluationResult | None]:
        chunks = self._get_chunks(user_message)
        context = "\n\n".join(
            f"[Source: {chunk.source}]\n{chunk.text}" for chunk in chunks
        )

        struggling = self._get_struggling_concepts()
        struggling_note = ""
        if struggling:
            topics = ", ".join(struggling)
            struggling_note = (
                f"\n\n[Tutor note: The student has repeatedly struggled with: {topics}. "
                f"Try a different angle, analogy, or concrete example for these topics "
                f"instead of the same approach.]"
            )

        prompt = f"Context:\n{context}{struggling_note}\n\nStudent: {user_message}"
        difficulty = self._get_difficulty()
        coach_response = self.coach.generate(prompt, difficulty)

        evaluation = None
        if not self._is_question(user_message):
            evaluation = self.evaluator.generate(user_message, chunks)
            self.scores.append(evaluation.score)
            self._update_concepts(evaluation, user_message)

        self.history.append(Message(role="user", content=user_message))
        self.history.append(Message(role="assistant", content=coach_response))
        return coach_response, evaluation

    def update_after_stream(
            self, user_message: str, full_reply: str, evaluation: EvaluationResult | None
    ) -> ConceptStatus | None:
        """
        Update in-memory state after a streaming response completes.
        Called by the /session/stream endpoint instead of chat().
        Returns the updated ConceptStatus if an evaluation was provided, else None.
        """
        self.history.append(Message(role="user", content=user_message))
        self.history.append(Message(role="assistant", content=full_reply))

        if evaluation is None:
            return None

        self.scores.append(evaluation.score)
        return self._update_concepts(evaluation, user_message)

    def get_scores(self) -> list[int]:
        return self.scores

    def get_history(self) -> list[Message]:
        return self.history

    def get_concepts(self) -> list[ConceptStatus]:
        return self.concepts