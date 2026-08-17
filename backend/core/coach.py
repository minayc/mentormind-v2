from backend.core.base_llm import BaseLLM
from groq import Groq


class Coach(BaseLLM):

    SYSTEM_PROMPT = """You are a Socratic tutor. Your job is to help students deeply understand the material they are studying through guided questioning — never by giving direct answers.

    The study material (context) may be written in any language, including Turkish. You must read and understand it regardless of the language, then always respond to the student in English.

    Rules:
    - Ask one focused question at a time to probe the student's understanding
    - Never reveal answers directly — guide through questions
    - Ground your questions in the provided context
    - If the student goes off-topic, gently redirect them back to the material
    - Keep responses concise and conversational"""

    DIFFICULTY_PROMPTS = {
        "easy": "The student is struggling. Ask simpler, more foundational questions that guide them step by step.",
        "medium": "The student is developing. Ask moderately challenging questions that push their thinking.",
        "hard": "The student is excelling. Ask abstract, challenging questions that push them beyond the material."
    }


    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        self.history = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        self.client = Groq(api_key=self.api_key)

    def generate(self, prompt: str, difficulty: str = "medium") -> str:
        difficulty_instruction = self.DIFFICULTY_PROMPTS.get(difficulty, "")
        full_prompt = f"{difficulty_instruction}\n\n{prompt}" if difficulty_instruction else prompt

        self.history.append({"role": "user", "content": full_prompt})
        response = self.client.chat.completions.create(model=self.model, messages=self.history)
        reply = response.choices[0].message.content
        self.history.append({"role": "assistant", "content": reply})
        return reply
