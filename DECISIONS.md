## Session — Day 1 | Date: 23.03.2026

**What I built today:**

Built the full RAG pipeline from scratch. ingest.py reads PDF and 
txt files, splits the text into overlapping chunks, embeds each 
chunk using nomic-embed-text via Ollama, and stores them in 
ChromaDB. retriever.py takes a query string, embeds it with the 
same model, and returns the 3 most similar chunks from the 
collection.

## Testing Session - Day 2 | Date: 24.03.2026:

**Something to improve:**

Switching from character-based chunking to
sentence or paragraph-aware chunking in the EXPANSION PHASE.

## Session — Day 3 | Date: 25.03.2026

**Somethings to handle later:**

- The way you run coach.py
- Proper fix: Track turns in main.py. On even turns (questions), skip evaluation. 
On odd turns (answers), evaluate the previous user message.
- Shouldn't lose context whenever we refresh
- PDF should be provided by the user