import os
import uuid
import pathlib
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from backend.core.coach import Coach
from backend.core.ollama_coach import OllamaCoach
from backend.core.evaluator import Evaluator          # fixed: was evaluater
from backend.core.vector_store import VectorStore
from backend.core.document_processor import DocumentProcessor
from backend.core.session import Session
from backend.core.schemas import Message, ConceptStatus
from backend.core import spaced_repetition as sr
from backend.core import session_store

from fastapi.responses import FileResponse, StreamingResponse
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from datetime import datetime
import json

load_dotenv()

app = FastAPI()

sr.init_db()
session_store.init_session_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

vector_store = VectorStore()
document_processor = DocumentProcessor()
sessions: dict[str, Session] = {}


class MessageRequest(BaseModel):
    session_id: str
    message: str


class MessageResponse(BaseModel):
    reply: str
    score: Optional[int] = None
    feedback: Optional[str] = None
    concept: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str


class SessionRequest(BaseModel):
    backend: str = "groq"
    sources: list[str] = []


#Documents

@app.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    total_chunks = 0
    stored_sources = []
    for file in files:
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        chunks = document_processor.process(temp_path)
        vector_store.store(chunks)
        total_chunks += len(chunks)
        stored_sources.append(pathlib.Path(file.filename).stem)
    return {"message": f"Stored {total_chunks} chunks from {len(files)} document(s)", "sources": stored_sources}


@app.get("/documents")
def list_documents():
    sources = vector_store.list_sources()
    return {"documents": sources}


@app.delete("/documents")
def clear_documents():
    """Delete all documents from ChromaDB so old uploads don't contaminate new sessions."""
    vector_store.clear()
    return {"message": "Knowledge base cleared."}


#Sessions

@app.post("/session/start", response_model=SessionResponse)
def start_session(request: SessionRequest = None):
    session_id = str(uuid.uuid4())
    if request and request.backend == "ollama":
        coach = OllamaCoach(model="llama3")
    else:
        coach = Coach(api_key=os.getenv("GROQ_API_KEY"), model="llama-3.1-8b-instant")
    evaluator = Evaluator(api_key=os.getenv("GEMINI_API_KEY"), model="gemini-2.5-flash")

    sources = request.sources if request else []
    sessions[session_id] = Session(
        coach=coach, evaluator=evaluator, vector_store=vector_store, sources=sources
    )
    session_store.create_session(session_id, request.backend if request else "groq", sources)
    return SessionResponse(session_id=session_id)


@app.post("/session/message", response_model=MessageResponse)
def send_message(request: MessageRequest):
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    coach_response, evaluation = session.chat(request.message)

    score        = evaluation.score    if evaluation else None
    feedback     = evaluation.feedback if evaluation else None
    concept_name = ""

    if evaluation:
        concept_name = evaluation.concept.strip() if evaluation.concept else ""
        if concept_name:
            sr.upsert_concept(concept_name, evaluation.score)

    session_store.save_turn(
        request.session_id, request.message, coach_response,
        score=score, feedback=feedback
    )
    if concept_name:
        idx = session._find_concept_idx(concept_name)
        if idx is not None:
            c = session.concepts[idx]
            session_store.save_concept(
                request.session_id, c.concept, c.understood, c.score, c.attempts
            )

    return MessageResponse(
        reply=coach_response,
        score=score,
        feedback=feedback,
        concept=concept_name or None,
    )


@app.get("/sessions")
def list_sessions():
    """Return all saved sessions (newest first) for the Past Sessions sidebar."""
    return {"sessions": session_store.list_sessions()}


@app.delete("/session/{session_id}")
def delete_session(session_id: str):
    """Permanently delete a session and all its data from the database."""
    session_store.delete_session(session_id)
    sessions.pop(session_id, None)  # also remove from in-memory dict if present
    return {"message": f"Session {session_id} deleted."}


@app.get("/session/resume/{session_id}")
def resume_session(session_id: str):
    """Reload a persisted session from SQLite into the in-memory sessions dict."""
    data = session_store.load_session(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found in database")

    if data["backend"] == "ollama":
        coach = OllamaCoach(model="llama3")
    else:
        coach = Coach(api_key=os.getenv("GROQ_API_KEY"), model="llama-3.1-8b-instant")
    evaluator = Evaluator(api_key=os.getenv("GEMINI_API_KEY"), model="gemini-2.5-flash")

    session = Session(
        coach=coach, evaluator=evaluator,
        vector_store=vector_store, sources=data["sources"]
    )

    for msg in data["messages"]:
        session.history.append(Message(role=msg["role"], content=msg["content"]))

    # Re-inject last 20 messages into coach context window
    recent = data["messages"][-20:]
    for msg in recent:
        session.coach.history.append({"role": msg["role"], "content": msg["content"]})

    session.scores = data["scores"]
    for c in data["concepts"]:
        session.concepts.append(ConceptStatus(
            concept=c["concept"],
            understood=c["understood"],
            score=c["score"],
            attempts=c["attempts"],
        ))

    sessions[session_id] = session

    return {
        "session_id": session_id,
        "sources":    data["sources"],
        "messages":   data["messages"],
        "scores":     data["scores"],
        "concepts":   data["concepts"],
    }


@app.post("/session/stream")
async def stream_message(request: MessageRequest):
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Use session methods — no logic duplication
    chunks = session._get_chunks(request.message)
    context = "\n\n".join(f"[Source: {chunk.source}]\n{chunk.text}" for chunk in chunks)
    difficulty = session._get_difficulty()

    # Struggling concept injection (was missing from stream endpoint before)
    struggling = session._get_struggling_concepts()
    struggling_note = ""
    if struggling:
        topics = ", ".join(struggling)
        struggling_note = (
            f"\n\n[Tutor note: The student has repeatedly struggled with: {topics}. "
            f"Try a different angle, analogy, or concrete example for these topics "
            f"instead of the same approach.]"
        )

    difficulty_instruction = session.coach.DIFFICULTY_PROMPTS.get(difficulty, "")
    prompt = f"{difficulty_instruction}\n\nContext:\n{context}{struggling_note}\n\nStudent: {request.message}".strip()

    def generate():
        stream = session.coach.client.chat.completions.create(
            model=session.coach.model,
            messages=session.coach.history + [{"role": "user", "content": prompt}],
            stream=True
        )
        full_reply = ""
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            full_reply += token
            if token:
                yield f"data: {json.dumps({'token': token})}\n\n"

        # Update coach's own history
        session.coach.history.append({"role": "user", "content": prompt})
        session.coach.history.append({"role": "assistant", "content": full_reply})

        if not session._is_question(request.message):
            evaluation = session.evaluator.generate(request.message, chunks)

            # Delegate state update to session — single source of truth
            updated_concept = session.update_after_stream(request.message, full_reply, evaluation)
            concept_name = updated_concept.concept if updated_concept else None

            if concept_name:
                sr.upsert_concept(concept_name, evaluation.score)

            session_store.save_turn(
                request.session_id, request.message, full_reply,
                score=evaluation.score, feedback=evaluation.feedback
            )
            if updated_concept:
                session_store.save_concept(
                    request.session_id, updated_concept.concept,
                    updated_concept.understood, updated_concept.score,
                    updated_concept.attempts
                )

            yield f"data: {json.dumps({'done': True, 'score': evaluation.score, 'feedback': evaluation.feedback, 'concept': concept_name})}\n\n"
        else:
            session.update_after_stream(request.message, full_reply, None)
            session_store.save_turn(request.session_id, request.message, full_reply)
            yield f"data: {json.dumps({'done': True, 'score': None, 'feedback': None, 'concept': None})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


#Progress

@app.get("/session/{session_id}/progress")
def get_progress(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    scores = session.get_scores()
    average = round(sum(scores) / len(scores), 1) if scores else 0
    return {"scores": scores, "average": average, "total_turns": len(scores)}


@app.get("/session/{session_id}/concepts")
def get_concepts(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "concepts": [
            {
                "concept":    c.concept,
                "understood": c.understood,
                "score":      c.score,
                "attempts":   c.attempts,
            }
            for c in session.get_concepts()
        ]
    }


#Spaced Repetition

@app.get("/concepts/due")
def due_concepts():
    """Return all concepts due for spaced-repetition review today."""
    return {"concepts": sr.get_due_concepts()}


@app.get("/concepts/all")
def all_concepts():
    """Return every concept ever tracked with full SM-2 metadata."""
    return {"concepts": sr.get_all_concepts()}


@app.delete("/concepts/{concept}")
def delete_concept(concept: str):
    """Permanently remove a concept from the spaced-repetition database."""
    sr.delete_concept(concept)
    return {"message": f"Deleted '{concept}'"}


#Export

@app.get("/session/{session_id}/export")
def export_session(session_id: str):
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    path = f"/tmp/{session_id}_export.pdf"
    doc = SimpleDocTemplate(
        path, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch
    )

    base = getSampleStyleSheet()
    W = 7.0 * inch

    RED     = colors.HexColor("#e94560")
    DARK    = colors.HexColor("#0d0d1a")
    NAVY    = colors.HexColor("#16213e")
    MUTED   = colors.HexColor("#8892a4")
    GREEN   = colors.HexColor("#22c55e")
    YELLOW  = colors.HexColor("#f59e0b")
    CRIMSON = colors.HexColor("#ef4444")
    LBLUE   = colors.HexColor("#dbeafe")
    LGRAY   = colors.HexColor("#f1f5f9")

    def score_color(s):
        return GREEN if s >= 7 else YELLOW if s >= 4 else CRIMSON

    def score_label(s):
        return "Excellent" if s >= 8 else "Good" if s >= 6 else "Developing" if s >= 4 else "Keep going"

    sNormal = base["Normal"]
    sUser   = ParagraphStyle("user",  parent=sNormal, fontSize=9, textColor=DARK, leading=13)
    sTutor  = ParagraphStyle("tutor", parent=sNormal, fontSize=9, textColor=DARK, leading=13)

    story = []

    # Header
    header_data = [[
        Paragraph('<font color="#e94560"><b>Mentor</b></font><b>Mind</b>',
                  ParagraphStyle("h", parent=sNormal, fontSize=22, fontName="Helvetica-Bold")),
        Paragraph(
            f'Session Export<br/>'
            f'<font color="#8892a4">{datetime.now().strftime("%B %d, %Y")}</font>',
            ParagraphStyle("hr", parent=sNormal, fontSize=10, alignment=2)
        )
    ]]
    header_table = Table(header_data, colWidths=[W * 0.6, W * 0.4])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=2, color=RED, spaceAfter=14))

    scores   = session.get_scores()
    history  = session.get_history()
    concepts = session.get_concepts()

    # Summary stats
    if scores:
        avg = round(sum(scores) / len(scores), 1)
        best = max(scores)
        trend = scores[-1] - scores[0] if len(scores) > 1 else 0
        trend_str = (f"+{trend}" if trend > 0 else str(trend)) + " pts"

        stats = [
            ["Exchanges", "Scored", "Average", "Best", "Trend"],
            [str(len(history) // 2), str(len(scores)), f"{avg}/10", f"{best}/10", trend_str],
        ]
        cw = W / 5
        st = Table(stats, colWidths=[cw] * 5)
        st.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0),  8),
            ("BACKGROUND",    (0, 1), (-1, 1),  LGRAY),
            ("FONTNAME",      (0, 1), (-1, 1),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 1), (-1, 1),  13),
            ("TEXTCOLOR",     (2, 1), (2, 1),   score_color(avg)),
            ("TEXTCOLOR",     (3, 1), (3, 1),   score_color(best)),
            ("TEXTCOLOR",     (4, 1), (4, 1),   GREEN if trend >= 0 else CRIMSON),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BOX",           (0, 0), (-1, -1), 0.5, MUTED),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, MUTED),
        ]))
        story.append(Paragraph("<b>Session Summary</b>",
                               ParagraphStyle("sh", parent=sNormal, fontSize=11,
                                              fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=6)))
        story.append(st)
        story.append(Spacer(1, 14))

    # Score progression
    if scores:
        story.append(Paragraph("<b>Score Progression</b>",
                               ParagraphStyle("sh", parent=sNormal, fontSize=11,
                                              fontName="Helvetica-Bold", spaceAfter=6)))
        n   = len(scores)
        cw  = min(0.55 * inch, (W - 0.9 * inch) / n)
        hdr = ["Response"] + [f"#{i+1}" for i in range(n)]
        vals = ["Score"] + [f"{s}/10" for s in scores]
        pt  = Table([hdr, vals], colWidths=[0.9 * inch] + [cw] * n)
        cmds = [
            ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("BOX",           (0, 0), (-1, -1), 0.5, MUTED),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, MUTED),
        ]
        for i, s in enumerate(scores):
            cmds += [
                ("BACKGROUND", (i+1, 1), (i+1, 1), score_color(s)),
                ("TEXTCOLOR",  (i+1, 1), (i+1, 1), colors.white),
                ("FONTNAME",   (i+1, 1), (i+1, 1), "Helvetica-Bold"),
            ]
        pt.setStyle(TableStyle(cmds))
        story.append(pt)
        story.append(Spacer(1, 14))

    # Concepts
    if concepts:
        story.append(Paragraph("<b>Concepts Explored</b>",
                               ParagraphStyle("sh", parent=sNormal, fontSize=11,
                                              fontName="Helvetica-Bold", spaceAfter=6)))
        rows = [["Concept", "Score", "Status", "Feedback"]]
        for c in concepts:
            rows.append([
                Paragraph(c.concept, ParagraphStyle("cc", parent=sNormal, fontSize=8)),
                f"{c.score}/10",
                "Understood" if c.understood else "Developing",
                Paragraph("Keep elaborating with evidence." if not c.understood else "Good depth shown.",
                          ParagraphStyle("cf", parent=sNormal, fontSize=8)),
            ])
        ct = Table(rows, colWidths=[2.8*inch, 0.7*inch, 0.9*inch, 2.6*inch])
        c_cmds = [
            ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0),  8),
            ("ALIGN",         (1, 0), (2, -1),  "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("BOX",           (0, 0), (-1, -1), 0.5, MUTED),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, MUTED),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LGRAY]),
        ]
        for i, c in enumerate(concepts):
            r = i + 1
            c_cmds.append(("TEXTCOLOR", (2, r), (2, r), GREEN if c.understood else CRIMSON))
            c_cmds.append(("FONTNAME",  (2, r), (2, r), "Helvetica-Bold"))
        ct.setStyle(TableStyle(c_cmds))
        story.append(ct)
        story.append(Spacer(1, 14))

    # Conversation
    story.append(HRFlowable(width="100%", thickness=1, color=MUTED, spaceAfter=10))
    story.append(Paragraph("<b>Full Conversation</b>",
                           ParagraphStyle("sh", parent=sNormal, fontSize=11,
                                          fontName="Helvetica-Bold", spaceAfter=8)))

    turn = 1
    score_idx = 0
    for msg in history:
        if msg.role == "user":
            cell = Table([[Paragraph(
                f'<font color="#1e40af"><b>You — Turn {turn}</b></font><br/>{msg.content}',
                sUser
            )]], colWidths=[W])
            cell.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), LBLUE),
                ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#93c5fd")),
                ("TOPPADDING",    (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ]))
            story.append(cell)
            story.append(Spacer(1, 4))

        elif msg.role == "assistant":
            cell = Table([[Paragraph(
                f'<font color="#166534"><b>Tutor</b></font><br/>{msg.content}',
                sTutor
            )]], colWidths=[W])
            cell.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), LGRAY),
                ("BOX",           (0, 0), (-1, -1), 0.5, MUTED),
                ("TOPPADDING",    (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING",   (0, 0), (-1, -1), 10),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
            ]))
            story.append(cell)

            if score_idx < len(scores):
                s = scores[score_idx]
                sc = score_color(s)
                sl = score_label(s)
                score_row = Table([[
                    Paragraph(f'<font color="{sc.hexval()}"><b>{s}/10 · {sl}</b></font>',
                              ParagraphStyle("sr", parent=sNormal, fontSize=8))
                ]], colWidths=[W])
                score_row.setStyle(TableStyle([
                    ("ALIGN",         (0, 0), (-1, -1), "RIGHT"),
                    ("TOPPADDING",    (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                ]))
                story.append(score_row)
                score_idx += 1

            story.append(Spacer(1, 10))
            turn += 1

    # Footer
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=RED, spaceAfter=6))
    story.append(Paragraph(
        "MentorMind · Socratic AI Tutoring · Powered by RAG + Groq + Gemini",
        ParagraphStyle("foot", parent=sNormal, fontSize=8, textColor=MUTED, alignment=1)
    ))

    doc.build(story)
    return FileResponse(path, media_type="application/pdf", filename="mentormind_session.pdf")