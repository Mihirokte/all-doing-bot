# all-doing-bot

A personal, always-on LLM-powered bot that turns natural language queries into structured data pipelines. Ask it to do something, and it creates a **cohort** (a named collection), defines an **action** (a repeatable task), executes it via a locally-hosted LLM, and stores results in Google Sheets.

## Architecture

```
┌─────────────────┐       GET        ┌────────────────────────────┐
│  GitHub Pages   │ ───────────────► │  FastAPI Backend           │
│  (Frontend)     │ ◄─────────────── │  (AWS EC2, always-on)      │
└─────────────────┘    JSON response │                            │
                                     │  Query → Parse → Plan      │
                                     │    → Execute → Store        │
                                     │                            │
                                     │  LLM: Qwen3.5-2B (CPU)    │
                                     │  via llama.cpp             │
                                     └─────────┬──────────────────┘
                                               │
                                               ▼
                                     ┌────────────────────────┐
                                     │  Google Sheets / Drive  │
                                     │  (Cohort-based storage) │
                                     └────────────────────────┘
```

## How It Works

1. **You send a query**: *"Fetch me latest Twitter posts about AI agents"*
2. **Parse**: The LLM extracts intent → cohort name, action type, parameters.
3. **Plan**: The LLM generates execution steps (search, extract, summarize).
4. **Execute**: The action engine fetches web content, cleans it to markdown, and processes it through focused LLM calls.
5. **Store**: Results are written to a Google Sheet under the cohort's tab.

Each LLM call is small and focused (< 1000 input tokens). Web pages are converted to clean markdown before the LLM sees them, following the [markdowner](https://github.com/supermemoryai/markdowner) approach.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Qwen3.5-2B (Q4 quantized) via llama-cpp-python |
| Backend | FastAPI + uvicorn (Python 3.11+) |
| Database | Google Sheets via gspread |
| Web extraction | readability-lxml + markdownify |
| Frontend | Static HTML/JS on GitHub Pages |
| Hosting | AWS EC2 free tier + systemd |

## Design Principles

- **Structured pipeline**: Every query flows through Parse → Plan → Execute → Store. No shortcuts.
- **Minimal token usage**: Each LLM call gets only the data it needs. No conversation history accumulation.
- **General & extensible**: New action types are added by creating one file. No pipeline changes needed.
- **Cohort-based storage**: Google Sheets as a human-readable, browsable database. One sheet per category.

Architectural inspiration from [agent-orchestrator](https://github.com/ComposioHQ/agent-orchestrator) — plugin architecture, work delegation, and structured pipelines.

## Repository Structure

```
all-doing-bot/
├── README.md              # This file
├── CLAUDE.md              # Agent instructions for AI coding assistants
├── plan.md                # Detailed implementation plan (7 phases)
├── backend/               # FastAPI server, LLM pipeline, actions, DB layer
├── frontend/              # GitHub Pages static site
└── tests/                 # pytest test suite
```

## Documentation

| Document | Purpose |
|----------|---------|
| [plan.md](./plan.md) | Phased implementation plan with tasks, file structures, and acceptance criteria |
| [CLAUDE.md](./CLAUDE.md) | Coding conventions, architecture rules, and instructions for AI agents building this project |

## Status

**Pre-implementation** — Documentation and architecture planning phase. See [plan.md](./plan.md) for the full roadmap.

## License

See [LICENSE](./LICENSE).
