# Context Bundler

Vague request in. Master prompt out. Paste it into Claude, ChatGPT, Gemini — anywhere.

A prompt-engineering tool that takes a short, vague request and expands it into a structured, executor-ready master prompt with code-level validation.

## Try it

Live demo: *(set after deploy)* `https://<your-app>.streamlit.app`

You'll need a free Gemini API key — paste it into the ☰ menu (top right). Stored in your browser session only.

## What it does

| | |
|---|---|
| **Bundle** | Takes a 5-word request → outputs a 500-word master prompt with role, context, task, constraints, edge cases, output format, success criteria |
| **Validate** | Scans output for 12 banned words + 4 fake-reference patterns. Auto-retries up to 3 times if found. |
| **Salvage** | Hard string surgery as last-resort cleanup. Strips fabricated reference sections. |
| **Modes** | 9 stackable modes (caveman, senior, teacher, devil's advocate, production, speedrun, test-first, stdlib-only, TL;DR-first) |
| **Presets** | One-click bundles (Production code = production+senior+testfirst, etc.) |
| **Templates** | 6 starter prompts (CLI tool, web app, explainer, compare, debug, game) |
| **Fallback** | Auto-tries 6 free Gemini models if one is rate-limited |

## Run locally

```bash
git clone https://github.com/<you>/context-bundler.git
cd context-bundler
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Get a free Gemini key from <https://aistudio.google.com/app/apikey> and paste it into the ☰ menu in the running app.

For local-dev convenience, you can also drop it in a `.env`:
```
GEMINI_API_KEY=AIza...
```

## Deploy your own copy (Streamlit Cloud, free)

1. Fork this repo on GitHub
2. Go to <https://share.streamlit.io> → sign in with GitHub → **New app**
3. Pick your fork, branch `main`, file `app.py` → **Deploy**
4. Live in ~2 minutes at `https://<you>-context-bundler.streamlit.app`

No need to set any secrets — the app uses bring-your-own-key, so each visitor uses their own free Gemini quota.

## Architecture

```
context-bundler/
├── app.py              # Streamlit UI (Apple-themed, light/dark/system)
├── bundler.py          # Core: meta-prompt + validation + retry + surgery
├── llm.py              # Gemini API with 6-model fallback chain
├── styles.css          # Dark theme (base)
├── styles-light.css    # Light theme overrides
├── requirements.txt
├── prompts/
│   ├── bundler_v5.md   # The active meta-prompt
│   └── modes/
│       ├── caveman.md       # Token-economy directive
│       ├── senior.md        # No hand-holding
│       ├── teacher.md       # Explain everything
│       ├── devil.md         # Find weaknesses
│       ├── production.md    # Error handling, logging
│       ├── speedrun.md      # Quickest working demo
│       ├── testfirst.md     # TDD discipline
│       ├── stdlib.md        # No third-party deps
│       └── tldr.md          # Answer first, details after
└── .streamlit/
    └── config.toml
```

## How to extend

- **New mode**: drop a markdown file in `prompts/modes/`, add a tuple to the `MODES` list in `app.py`
- **New preset bundle**: append to `PRESETS` list in `app.py`
- **New template**: append to `TEMPLATES` list in `app.py`
- **New banned word**: add a regex to `BANNED_WORD_PATTERNS` in `bundler.py`. Optionally add a replacement to `BANNED_SURGERY` so it gets auto-fixed instead of just flagged.
- **Tune the bundler's reasoning**: edit `prompts/bundler_v5.md` (or make a `bundler_v6.md` and switch `ACTIVE_TEMPLATE` in `bundler.py`)

## Privacy

- Your API key is stored in your browser's Streamlit session state. It's never persisted on the server.
- Prompts you generate are sent to Google's Gemini API per Google's terms.
- No analytics, no tracking, no accounts.

## Built by

[Karanvir Panwar](mailto:karanvirsp8077@gmail.com)
