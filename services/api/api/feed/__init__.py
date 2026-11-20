"""The feed (`/feed`, docs/BEST-OF-UCHICAGO-PLAN.md): course spotlights, student voices, books
from a hand-written shelf, word clouds, programs and open questions, ranked for the student.

- `categories`: the subject families a student can focus on (every catalog subject maps to one).
- `shelf`: the real books of `data/feed/books.yaml` ("reading for the curious, not a syllabus").
- `text`: excerpts, keywords and plain text from markdown (no model involved).
- `pool`: the catalog's feed-worthy courses, cached per database and catalog year.
- `service`: the ranking (For you / Explore / Following) and the cursor.
- `notes`: the AI curator's one-line notes and headline (`/agents/feed-notes`), with a
  deterministic fallback.
"""
