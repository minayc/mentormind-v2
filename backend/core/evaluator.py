import google.generativeai as genai
import json
import re
from backend.core.schemas import EvaluationResult

SYSTEM_PROMPT = """You are an educational evaluator assessing a student's understanding.

Scoring rules:
- Factual content: grade on accuracy and completeness relative to the source material.
- Subjective content (reviews, essays, opinions): grade on quality of reasoning,
  connection to text, depth of analysis, and use of textual evidence.

Score scale:
  9-10  Insightful, well-supported, demonstrates deep understanding
  7-8   Good understanding, mostly accurate, some depth
  5-6   Developing — partially correct, some gaps or vague
  3-4   Weak — mostly incorrect or very shallow
  1-2   Off-topic or no meaningful engagement

Additional rules:
- A short but correct observation should score at least 5.
- Do NOT penalise brevity if the core idea is right.
- Do NOT give 0 for subjective opinions that are grounded in the text.

Return ONLY valid JSON — no markdown, no explanation:
{
  "score": <integer 1-10>,
  "feedback": "<one concise sentence of feedback>",
  "concept": "<2-6 word noun phrase naming the main topic or idea the student addressed>"
}

The "concept" field must be a noun phrase like "vector embeddings", "cosine similarity",
"narrative structure", "character motivation" — NOT a sentence fragment or the student's words verbatim."""


class Evaluator:
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=SYSTEM_PROMPT,
        )

    def generate(self, student_message: str, chunks) -> EvaluationResult:
        context = "\n\n".join(
            f"[Source: {chunk.source}]\n{chunk.text}" for chunk in chunks
        )
        prompt = (
            f"Context (source material):\n{context}\n\n"
            f"Student response:\n{student_message}"
        )

        try:
            response = self.model.generate_content(prompt)
            raw = response.text.strip()


            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)

            data = json.loads(raw)
            return EvaluationResult(
                score=int(data.get("score", 5)),
                feedback=str(data.get("feedback", "")),
                concept=str(data.get("concept", "")),
            )
        except Exception as e:
            return EvaluationResult(score=5, feedback=f"Evaluation error: {e}", concept="")