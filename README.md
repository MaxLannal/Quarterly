# Quarterly

A course-planning app for the University of Chicago College Catalog, with three parts:

- **Home:** a personal dashboard with this quarter's and next quarter's courses, a plan overview, checks to review, and your programs.
- **Planner:** four years of Autumn, Winter, and Spring columns. Search any course and drag it into a quarter.
- **Ask the catalog:** a chatbot whose answers are grounded in the catalog and cite the page they came from. Everything uses the Python standard library, so there's nothing to install.

## Quick start

```
python3 build_catalog.py                          # crawl the catalog into data/ (about 4 minutes; rerun to resume)
export ANTHROPIC_API_KEY=your-key                 # Windows PowerShell: $env:ANTHROPIC_API_KEY="your-key"
python3 catalog_server.py                         # then open http://localhost:8000
```

Other commands:

```
python3 catalog_server.py --count-tokens          # exact token counts for your snapshot
python3 catalog_server.py --ask "Which statistics courses are offered in Spring?"
```

Settings are environment variables: `ANTHROPIC_MODEL` (default `claude-sonnet-5-5`), `PORT` (default 8000), and `CACHE_TTL` (`1h` by default, or `5m` if questions arrive in quick bursts).

## Why the whole catalog isn't pasted into the prompt

A full crawl in November 2026 found 141 College catalog pages and about 6,500 unique courses, roughly 8.4 million characters. That's about three times the 1M-token context window of current Claude models. Even where a corpus does fit, accuracy drops as the context fills, so a targeted context answers better than a full one.

So each request carries a map of the whole catalog, and Claude fetches details on demand:

1. **Always in context, and cached.** The College-wide policy pages in full, every program page with its section headings, and an index of every course with its code, title, units, and usual terms. That's about 600,000 characters, an estimated 200,000 to 240,000 tokens. It's marked for prompt caching, so after the first question each hour it's read from cache at a small fraction of the normal input price.
2. **Fetched with tools.** Claude calls `search_catalog` for full-text search, `get_courses` for full descriptions and prerequisites, and `get_program` for a program's requirements. The server runs these locally against `data/catalog.json`.
3. **Cited.** Tool results go back to Claude as search result blocks with citations turned on, so the answer comes back with the exact catalog passages and page URLs behind each claim. The chat page shows them as numbered sources.

## Using an Anthropic-compatible gateway

The server works with the Claude API directly or with a gateway that offers the Anthropic Messages format. Point it at the gateway with environment variables, then run the checker before starting the server:

```
export ANTHROPIC_BASE_URL=https://your-gateway.example   # no /v1 at the end
export ANTHROPIC_API_KEY=your-gateway-key
export ANTHROPIC_MODEL=claude-sonnet-5-5                  # use a model ID from the gateway's model list
python3 check_provider.py
```

The checker sends six tiny requests and reports whether the gateway supports tool use, citable search results, prompt caching, and token counting. The chatbot needs tool use. If a gateway rejects citable search results or the 1-hour cache, the server switches automatically to tagged-text sources or the 5-minute cache, and answers still show numbered sources.

Requests through a gateway, including students' questions, pass through that company as well as the model provider, so read its privacy policy and terms before you use it with anything sensitive.

## Files

- `build_catalog.py` crawls every College page in the catalog's sitemap, plus the pages linked from Programs of Study. It follows robots.txt, waits between requests, and backs off when the site is busy or drops connections. Each page is saved in `data/raw/` as it arrives, so if the site stops responding, running it again later fetches only the missing pages. Use `--refresh` to download everything again. It writes `data/catalog.json` (structured pages and courses, including prerequisite links), `data/catalog.md`, and `data/stats.json`.
- `catalog_server.py` runs the search index, the agent loop, the Claude API calls, and the local web server.
- `quarterly.html` is the app: dashboard, planner, and chat.
- `check_provider.py` tests which features your API provider supports.

## The planner

- **Adding courses:** search by code, title, or topic, then drag a result into a quarter. You can also select a course and choose a quarter in the details panel, which works with a keyboard and on touch screens.
- **Sequences:** dropping a multi-quarter sequence, such as a Core sequence, places each part in consecutive quarters.
- **Credit and placement:** a lane above Year 1 for AP, IB, placement, or transfer credit, so those count as earlier than Year 1 in the checks.
- **Checks:** using only catalog data, the planner flags a course placed in a quarter it isn't usually offered, a course with no listed prerequisite earlier in the plan, and a course placed twice. Prerequisite wording often includes "or" and instructor consent, so these are prompts to look closer, not verdicts.
- **Check my plan with Claude:** sends the whole plan and your programs to the chatbot for a full review.
- **Saving:** the plan and profile save automatically to `data/plan.json`. Export plan downloads a copy.

## Checking that every course was captured

After each run, `build_catalog.py` prints, and saves in `data/stats.json`:

- how many pages were fetched and whether any are missing
- how many course entries were on those pages and how many were parsed
- how many unique courses that comes to, since some courses are listed on several pages
- undergraduate course codes that appear only as prerequisites and have no entry anywhere, usually retired or renumbered courses

Cross-listed codes don't get separate entries in the catalog. The server resolves them to the course's main entry, so a student can ask about any of a course's codes.

## Keeping it current

Run `build_catalog.py` again when a new catalog year is published. Requirements depend on the year a student entered, so if you need several years, crawl each one into its own data folder and add the year to the prompt.

## Ready for Phase 2 (visual harness)

Every `/api/chat` response already returns structured data a visual layer can draw:

- `courses`: every course the answer looked up or cited
- `prereq_graph`: prerequisite edges for those courses, parsed from the catalog (`data/catalog.json` has edges for every course)
- `sources` and `segments`: answer text with citation numbers
- `trace`: which tools ran, with their inputs

A natural next step is a `show_visual` tool that Claude calls with a chart type and data, such as a prerequisite graph, requirement progress, or a four-year plan. The server would pass it through to the page, and the page would render it in a canvas next to the chat.

## Notes

This is a prototype built on public catalog pages. Check that your use fits the University's terms, and talk to the College or the Registrar about an official data feed before sharing it widely. Answers aren't official advising.
