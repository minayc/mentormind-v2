# 🧠 MentorMind

**An AI-powered Socratic tutoring system that learns your study material and adapts to how well you understand it.**

MentorMind combines Retrieval-Augmented Generation (RAG) with the SM-2 spaced repetition algorithm into a single adaptive pipeline. Upload your lecture notes or textbook chapters, and the system tutors you exclusively on that material — asking guiding questions rather than giving away answers, tracking every concept you discuss, and scheduling weak topics for future review at the optimal moment.

> *It doesn't tell you. It makes you think.*

---

## Features

- **Socratic tutoring** — the Coach never gives direct answers; it guides you to reason through concepts yourself
- **RAG-grounded responses** — every reply is grounded in your uploaded documents; the tutor cannot drift into general knowledge
- **Dual-LLM architecture** — LLaMA 3.1 8B (Groq) for fast streaming responses, Gemini 2.5 Flash for structured evaluation
- **Adaptive difficulty** — rolling average of the last 3 scores automatically shifts the Coach between easy, medium, and hard modes
- **Concept tracking** — Gemini extracts the concept discussed in each turn and maintains a registry with scores and attempt counts
- **SM-2 spaced repetition** — weak concepts are scheduled for review at scientifically optimal intervals
- **Session persistence** — full conversation history, scores, and concepts are saved to SQLite and restored across restarts
- **PDF export** — export any session as a styled PDF report
- **Local embeddings** — document chunks are embedded locally via Ollama (nomic-embed-text), keeping your data on your machine
- **Offline fallback** — OllamaCoach provides a fully local tutoring pipeline when internet is unavailable

---

## Architecture

```
React Frontend (Vite)
        │  HTTP + SSE
        ▼
FastAPI Backend
        │
   ┌────┴────┐
   │ Session │  ← orchestrates the full pipeline
   └────┬────┘
        │
   ┌────┴──────────────────┐
   │                       │
Coach (Groq/Ollama)   Evaluator (Gemini)
LLaMA 3.1 8B          Gemini 2.5 Flash
Socratic responses    Scores + concept extraction
        │                       │
   ┌────┴────┐           ┌──────┴──────┐
   │ChromaDB │           │   SQLite    │
   │Vectors  │           │Sessions/SM-2│
   └─────────┘           └─────────────┘
```

**Design principles:**
- `BaseLLM` ABC enforces the Strategy pattern — Coach and OllamaCoach are interchangeable
- `@dataclass` typed contracts (`Chunk`, `Message`, `EvaluationResult`, `ConceptStatus`) at every module boundary
- `Session` owns all business logic; `main.py` is purely the HTTP boundary
- Source filtering in ChromaDB prevents context contamination between sessions

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, Vite, Server-Sent Events |
| Backend | FastAPI, Python 3.11+ |
| LLM (Coach) | LLaMA 3.1 8B via Groq API |
| LLM (Evaluator) | Gemini 2.5 Flash via Google AI |
| Embeddings | nomic-embed-text via Ollama (local) |
| Vector store | ChromaDB |
| Database | SQLite |
| PDF generation | ReportLab |

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) installed and running
- A [Groq API key](https://console.groq.com)
- A [Google AI API key](https://aistudio.google.com)

### 1. Clone the repository

```bash
git clone https://github.com/minayc/mentormind-v2.git
cd mentormind-v2
```

### 2. Pull the required Ollama models

```bash
ollama pull nomic-embed-text
ollama pull llama3
```

### 3. Set up the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### 4. Set up the frontend

```bash
cd frontend
npm install
```

### 5. Run the app

**Backend** (from project root, with venv active):
```bash
uvicorn backend.main:app --reload
```

**Frontend** (in a separate terminal):
```bash
cd frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## How It Works

1. **Upload** your PDF or text document — it gets chunked into 500-character overlapping segments, embedded locally by Ollama, and stored in ChromaDB
2. **Start a session** — select your uploaded documents as the knowledge source
3. **Chat** — type what you think you know; the Coach retrieves the most relevant chunks from your document and responds with a Socratic question
4. **Get evaluated** — Gemini scores your answer (1–10), extracts the concept, and feeds the score into the difficulty calculator and SM-2 scheduler simultaneously
5. **Track progress** — view score history, concept mastery, document coverage, and your spaced repetition review queue in the right panel
6. **Resume anytime** — close the app and reopen it; your full session history is restored from SQLite instantly

---

## Project Structure

```
mentormind-v2/
├── backend/
│   ├── core/
│   │   ├── base_llm.py          # Abstract base class (Strategy pattern)
│   │   ├── coach.py             # Groq LLaMA coach
│   │   ├── ollama_coach.py      # Local Ollama fallback
│   │   ├── evaluator.py         # Gemini evaluator
│   │   ├── session.py           # Orchestrator — full pipeline
│   │   ├── vector_store.py      # ChromaDB interface
│   │   ├── document_processor.py# PDF/text chunking
│   │   ├── session_store.py     # SQLite persistence
│   │   ├── spaced_repetition.py # SM-2 algorithm
│   │   └── schemas.py           # Typed dataclasses
│   └── main.py                  # FastAPI routes
├── frontend/
│   └── src/
│       └── App.jsx              # React single-page app
├── requirements.txt
└── start.sh
```

---

## Limitations

- Requires internet for Groq and Gemini APIs (switch to OllamaCoach for fully offline use)
- No automated test suite
- Single-user local deployment — not designed for concurrent users
- Concept deduplication uses substring matching, which can occasionally create near-duplicates

---

## Authors

Built by **Cansu** and **Mina**.
