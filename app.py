import os
from pathlib import Path
import streamlit as st
from bundler import bundle

# ==========================================
# Page setup
# ==========================================
st.set_page_config(
    page_title="Context Bundler",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ==========================================
# Sync Streamlit secrets → env vars
# (so the deployer's shared key is picked up without code changes in llm.py)
# ==========================================
try:
    if "GEMINI_API_KEY" in st.secrets:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass  # st.secrets may not exist locally; fall back to .env

HAS_SHARED_KEY = bool(os.getenv("GEMINI_API_KEY"))

# Read theme choice early (so we can inject correct CSS at the top)
theme_choice = st.session_state.get("theme_choice", "System")

# Load CSS
_root = Path(__file__).parent
_dark_css = (_root / "styles.css").read_text() if (_root / "styles.css").exists() else ""
_light_css = (_root / "styles-light.css").read_text() if (_root / "styles-light.css").exists() else ""

st.markdown(f"<style>{_dark_css}</style>", unsafe_allow_html=True)

if theme_choice == "Light" and _light_css:
    st.markdown(f"<style>{_light_css}</style>", unsafe_allow_html=True)
elif theme_choice == "System" and _light_css:
    st.markdown(
        f"<style>@media (prefers-color-scheme: light) {{ {_light_css} }}</style>",
        unsafe_allow_html=True,
    )


# ==========================================
# Catalogs
# ==========================================
MODES = [
    ("caveman",   "Caveman",            "Token economy",
     "3-6 word sentences, no preamble, tool-first responses. 50-75% per-response token savings."),
    ("senior",    "Senior engineer",    "No hand-holding",
     "Assume 5+ years experience. Skip basics. Trade-offs over single answers. Decision-first."),
    ("teacher",   "Teacher",            "Explain everything",
     "Define every term, walk through code line-by-line, explain WHY before WHAT."),
    ("devil",     "Devil's advocate",   "Find weaknesses",
     "Stress-test recommendations. 'Where this breaks' section. Name alternatives. Reverse conditions."),
    ("production", "Production-grade",  "Error handling, logging",
     "Real users, not demo. Error handling on every external call. Structured logging. Hostile inputs."),
    ("speedrun",  "Speedrun",           "Quickest working demo",
     "Single file. Hardcoded defaults. No tests, no types, no comments. Working > clean."),
    ("testfirst", "Test-first",         "TDD discipline",
     "Failing test before any implementation. Red → green → refactor. Behavior-named tests."),
    ("stdlib",    "Stdlib-only",        "No third-party deps",
     "No pip/npm/cargo. urllib not requests, json not orjson. Stops if external pkg truly required."),
    ("tldr",      "TL;DR-first",        "Answer first, details after",
     "First line: one-sentence answer. Second line: most important caveat. Then details."),
]

PRESETS = [
    ("production_set", "Production code",   ["production", "senior", "testfirst"],
     "Senior tone + production-grade code + TDD. For shippable work."),
    ("demo_set",       "Quick demo",        ["speedrun", "caveman"],
     "Speedrun output + minimal tokens. For prototypes you'll throw away."),
    ("learning_set",   "Learning material", ["teacher", "tldr"],
     "Teacher mode + TL;DR-first. For tutorials and explainers."),
    ("review_set",     "Critical review",   ["devil", "senior"],
     "Devil's advocate + senior tone. For stress-testing existing decisions."),
]

TEMPLATES = [
    {"label": "CLI",     "title": "Build a CLI tool",
     "input":  "build a python cli tool that converts markdown files into nicely formatted PDFs",
     "extra":  ""},
    {"label": "Web",     "title": "Make a web app",
     "input":  "build me a habit tracker web app where i can log daily habits and see streaks",
     "extra":  "should be a single-page app, deployable on a free tier (vercel/netlify), data persists locally"},
    {"label": "Doc",     "title": "Write an explainer",
     "input":  "explain how transformers work in a 2000-word blog post for a CS undergraduate",
     "extra":  ""},
    {"label": "Compare", "title": "Compare options",
     "input":  "compare postgres vs sqlite for a personal finance app i'm building solo",
     "extra":  ""},
    {"label": "Debug",   "title": "Debug a problem",
     "input":  "my flask app returns 502 when uploading files larger than 10MB, walk me through how to diagnose and fix",
     "extra":  ""},
    {"label": "Game",    "title": "Game from scratch",
     "input":  "build me a 2D side-scrolling platformer in pygame with double-jump and collectibles",
     "extra":  ""},
]


# ==========================================
# Session state
# ==========================================
def _init_state():
    if "user_input" not in st.session_state:
        st.session_state.user_input = ""
    if "extra" not in st.session_state:
        st.session_state.extra = ""
    if "_pending_preset" not in st.session_state:
        st.session_state._pending_preset = None
    if "_pending_template" not in st.session_state:
        st.session_state._pending_template = None

_init_state()

if st.session_state._pending_preset is not None:
    target_modes = st.session_state._pending_preset
    for mode_id, *_ in MODES:
        st.session_state[f"mode_{mode_id}"] = mode_id in target_modes
    st.session_state._pending_preset = None

if st.session_state._pending_template is not None:
    tpl = st.session_state._pending_template
    st.session_state.user_input = tpl["input"]
    st.session_state.extra = tpl["extra"]
    st.session_state._pending_template = None


# ==========================================
# Sidebar — modes + options
# ==========================================
with st.sidebar:
    st.markdown("## MODES")
    st.caption("Stack any combo. They append to the master prompt.")
    selected_modes = []
    for mode_id, label, _short, help_text in MODES:
        if st.checkbox(label, key=f"mode_{mode_id}", help=help_text):
            selected_modes.append(mode_id)

    st.markdown("## OPTIONS")
    show_meta = st.checkbox(
        "Show meta-prompt sent",
        help="Debug: see the exact prompt the bundler sent to the LLM.",
    )
    disable_cleanup = st.checkbox(
        "Disable auto-cleanup (raw)",
        help="Skip post-generation surgery and reference stripping. See exactly what the LLM produced.",
    )


# ==========================================
# Top bar — title (left) + accessibility menu (right)
# ==========================================
title_col, menu_col = st.columns([14, 1])

with menu_col:
    user_api_key = st.session_state.get("user_api_key", "")
    has_user_key = bool(user_api_key)
    has_any_key = has_user_key or HAS_SHARED_KEY
    menu_label = "☰" if has_any_key else "☰ ●"
    menu_help = "Settings: API key + theme" + ("" if has_any_key else "  ·  API key required")

    with st.popover(menu_label, use_container_width=True, help=menu_help):
        # ===== API KEY SECTION =====
        st.markdown(
            '<div class="popover-section-title">GEMINI API KEY</div>',
            unsafe_allow_html=True,
        )

        # Status badge at the very top — biggest visual signal
        if has_user_key:
            st.markdown(
                '<div class="key-status set">'
                '<span class="dot"></span> Personal key active &middot; unlimited use'
                '</div>',
                unsafe_allow_html=True,
            )
        elif HAS_SHARED_KEY:
            st.markdown(
                '<div class="key-status env">'
                '<span class="dot"></span> Using shared key &middot; community quota'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="key-status missing">'
                '<span class="dot"></span> No key set &middot; required to generate'
                '</div>',
                unsafe_allow_html=True,
            )

        st.text_input(
            "Your own key (optional, for unlimited use)" if HAS_SHARED_KEY else "Paste your key here",
            type="password",
            key="user_api_key",
            placeholder="AIzaSy...",
            label_visibility="visible",
        )

        if HAS_SHARED_KEY:
            help_text = (
                'You can use the app immediately with the shared community key. '
                'Paste your own free key from '
                '<a href="https://aistudio.google.com/app/apikey" target="_blank">'
                'aistudio.google.com/app/apikey</a> '
                'to get unlimited generations and bypass the shared quota.'
            )
        else:
            help_text = (
                'Get a free key from '
                '<a href="https://aistudio.google.com/app/apikey" target="_blank">'
                'aistudio.google.com/app/apikey</a>. '
                'Stored in your browser session only — never sent to a server.'
            )
        st.markdown(f'<div class="popover-help">{help_text}</div>', unsafe_allow_html=True)

        # localStorage sync — paste once, persist across visits on this device
        st.components.v1.html(
            """
<script>
(function() {
    const STORAGE_KEY = 'context_bundler_gemini_key';

    function findKeyInput() {
        // Find the password input across all Streamlit frames
        const inputs = window.parent.document.querySelectorAll('input[type="password"]');
        for (const input of inputs) {
            if (input.placeholder && input.placeholder.includes('AIza')) return input;
        }
        return null;
    }

    function syncToStreamlit(value) {
        const input = findKeyInput();
        if (!input) return false;
        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        setter.call(input, value);
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
    }

    // On load: restore from localStorage if present
    try {
        const saved = window.parent.localStorage.getItem(STORAGE_KEY);
        if (saved) {
            let attempts = 0;
            const restore = setInterval(function() {
                attempts++;
                if (syncToStreamlit(saved) || attempts > 20) clearInterval(restore);
            }, 200);
        }
    } catch (e) {}

    // On change: save to localStorage
    setInterval(function() {
        const input = findKeyInput();
        if (!input) return;
        try {
            const current = input.value || '';
            const stored = window.parent.localStorage.getItem(STORAGE_KEY) || '';
            if (current && current !== stored) {
                window.parent.localStorage.setItem(STORAGE_KEY, current);
            } else if (!current && stored) {
                // user cleared the field — remove from storage
                window.parent.localStorage.removeItem(STORAGE_KEY);
            }
        } catch (e) {}
    }, 1000);
})();
</script>
            """,
            height=0,
        )

        st.divider()

        # ===== APPEARANCE SECTION =====
        st.markdown(
            '<div class="popover-section-title">APPEARANCE</div>',
            unsafe_allow_html=True,
        )
        st.radio(
            "Theme",
            ["System", "Light", "Dark"],
            index=["System", "Light", "Dark"].index(theme_choice),
            horizontal=True,
            key="theme_choice",
            label_visibility="collapsed",
            help="System matches your OS setting and switches automatically.",
        )

with title_col:
    mode_count = len(selected_modes)
    mode_pill_html = (
        f'<span class="mode-pill">{mode_count} mode{"s" if mode_count != 1 else ""} active</span>'
        if mode_count else ""
    )
    st.markdown(
        f"""
<div class="hero">
    <h1>Context Bundler{mode_pill_html}</h1>
    <p class="tagline">Vague request in. Master prompt out. Paste it into Claude, ChatGPT, Gemini — anywhere.</p>
</div>
""",
        unsafe_allow_html=True,
    )


# ==========================================
# Main columns — input + output
# ==========================================
left, right = st.columns(2, gap="large")

with left:
    st.subheader("Input")

    user_input = st.text_area(
        "What do you want?",
        height=160,
        placeholder="e.g. build me a snake game in python",
        key="user_input",
    )
    wc = len(user_input.split())
    cc = len(user_input)
    counter_class = "good" if wc >= 8 else ("thin" if wc >= 3 else "")
    counter_msg = ""
    if wc < 3 and wc > 0:
        counter_msg = "  ·  add more detail"
    elif wc >= 8:
        counter_msg = "  ·  enough context"
    st.markdown(
        f'<div class="char-counter {counter_class}">{cc} chars · {wc} words{counter_msg}</div>',
        unsafe_allow_html=True,
    )

    extra = st.text_area(
        "Extra context (optional)",
        height=140,
        placeholder="anything the bundler should know — tech stack, audience, constraints, examples",
        key="extra",
    )
    extra_wc = len(extra.split())
    extra_cc = len(extra)
    if extra_cc > 0:
        st.markdown(
            f'<div class="char-counter">{extra_cc} chars · {extra_wc} words</div>',
            unsafe_allow_html=True,
        )

    go = st.button("Generate master prompt", type="primary", use_container_width=True)


def render_validation_card(result: dict) -> None:
    attempts = result["attempts"]
    clean = result["clean"]
    surgery = result["surgery_replacements"]
    refs_stripped = result["refs_stripped"]
    history = result["history"]

    if clean and not surgery and not refs_stripped:
        card_class = badge_class = "clean"
        badge_text = "CLEAN" if attempts == 1 else f"CLEAN AFTER {attempts} TRIES"
    elif clean:
        card_class = badge_class = "warn"
        badge_text = "SALVAGED"
    else:
        card_class = badge_class = "dirty"
        badge_text = "RESIDUAL ISSUES"

    rows_html = ""
    for entry in history:
        v_count = len(entry["violations"])
        r_count = len(entry["suspicious_refs"])
        status = "OK" if v_count + r_count == 0 else f"{v_count + r_count} issue(s)"
        rows_html += (
            f'<div class="row"><span>Attempt {entry["attempt"]}</span>'
            f'<span>{entry["word_count"]} words · {status}</span></div>'
        )
        if entry["violations"]:
            words = sorted({v[0].lower() for v in entry["violations"]})
            rows_html += (
                f'<div class="row" style="padding-left:1rem">'
                f'<span>banned</span><span>{", ".join(words)}</span></div>'
            )
        if entry["suspicious_refs"]:
            refs = sorted({r[0] for r in entry["suspicious_refs"]})
            short = [r[:40] + ("..." if len(r) > 40 else "") for r in refs[:3]]
            rows_html += (
                f'<div class="row" style="padding-left:1rem">'
                f'<span>fake refs</span><span>{", ".join(short)}</span></div>'
            )

    notes = []
    if surgery:
        notes.append(f"Hard surgery: replaced {len(surgery)} stubborn banned word(s)")
    if refs_stripped:
        notes.append("Stripped fabricated Reference Works section")
    if not result.get("cleanup_applied", True):
        notes.append("Auto-cleanup disabled — raw output shown")
    notes_html = f'<div class="note">{" · ".join(notes)}</div>' if notes else ""

    st.markdown(
        f"""
<div class="validation-card {card_class}">
    <div class="header-line">
        <span>Validation</span>
        <span class="badge {badge_class}">{badge_text}</span>
    </div>
    {rows_html}
    {notes_html}
</div>
""",
        unsafe_allow_html=True,
    )


def render_empty_state():
    active_summary = (
        ", ".join(label for mid, label, *_ in MODES if mid in selected_modes)
        if selected_modes else "none"
    )
    st.markdown(
        f"""
<div class="empty-state">
    <div class="title">Ready when you are</div>
    <div class="subtitle">Type your request, pick a template below, or stack modes — then hit Generate.</div>
    <div class="features">
        <div class="feature">Active modes: <strong style="color:#0A84FF">{active_summary}</strong></div>
        <div class="feature">Output validated against banned words and fake references</div>
        <div class="feature">Auto-retries up to 3 times if violations are detected</div>
        <div class="feature">Hard string surgery as last-resort cleanup</div>
        <div class="feature">Auto-fallback across 6 Gemini models if rate-limited</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


with right:
    st.subheader("Master prompt")
    if go and user_input.strip():
        # Pre-flight key check
        api_key = st.session_state.get("user_api_key") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            st.error(
                "No API key set. Open the ☰ menu (top right) and paste your free Gemini key. "
                "Get one at https://aistudio.google.com/app/apikey"
            )
        else:
            with st.spinner("Bundling context..."):
                try:
                    result = bundle(
                        user_input,
                        extra,
                        modes=selected_modes,
                        cleanup=not disable_cleanup,
                        api_key=api_key,
                    )
                    render_validation_card(result)
                    st.code(result["output"], language="markdown")
                    st.download_button(
                        "Download as .md",
                        data=result["output"],
                        file_name="master_prompt.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )

                    if show_meta:
                        with st.expander("Meta-prompt sent to LLM (final attempt)"):
                            st.code(result["meta_prompt"], language="markdown")

                    if disable_cleanup or result["surgery_replacements"] or result["refs_stripped"]:
                        with st.expander("Raw LLM output (before cleanup)"):
                            st.code(result["raw_output"], language="markdown")

                except Exception as e:
                    err_str = str(e).lower()
                    if any(t in err_str for t in ["rate limit", "quota", "all free-tier"]):
                        st.error(
                            "**Daily quota exhausted.** The shared key for this app has hit its "
                            "free-tier limit for today. Two options:\n\n"
                            "1. **Wait** — Google's free quota resets at midnight Pacific time.\n"
                            "2. **Use your own free key** — paste it into the ☰ menu (top right) "
                            "for unlimited generations. Get one at "
                            "[aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)."
                        )
                    else:
                        st.error(f"Error: {e}")
    elif go:
        st.warning("Type a request on the left first.")
    else:
        render_empty_state()


# ==========================================
# Below-the-fold: helpers
# ==========================================
st.divider()


# Quick start templates
st.markdown('<div class="section-title">Quick start templates</div>', unsafe_allow_html=True)
tpl_cols = st.columns(6, gap="small")
for i, tpl in enumerate(TEMPLATES):
    with tpl_cols[i]:
        if st.button(
            f"**{tpl['label']}**\n\n{tpl['title']}",
            key=f"tpl_{i}",
            use_container_width=True,
            help=tpl["input"],
        ):
            st.session_state._pending_template = tpl
            st.rerun()


# Preset bundles
st.markdown(
    '<div class="section-title">Preset bundles · one click stacks multiple modes</div>',
    unsafe_allow_html=True,
)
preset_cols = st.columns(len(PRESETS) + 1, gap="small")
for i, (preset_id, label, target_modes, help_text) in enumerate(PRESETS):
    with preset_cols[i]:
        if st.button(label, key=f"pre_{preset_id}", help=help_text, use_container_width=True):
            st.session_state._pending_preset = target_modes
            st.rerun()
with preset_cols[-1]:
    if st.button("Reset all", key="pre_reset", help="Clear all selected modes.", use_container_width=True):
        st.session_state._pending_preset = []
        st.rerun()


# Mode library — clickable cards
st.markdown(
    '<div class="section-title">Mode library — click any card to toggle</div>',
    unsafe_allow_html=True,
)

for row_start in range(0, len(MODES), 4):
    row_modes = MODES[row_start:row_start + 4]
    cols = st.columns(4, gap="small")
    for col_idx, (mode_id, label, short, help_text) in enumerate(row_modes):
        with cols[col_idx]:
            active = mode_id in selected_modes
            indicator = "● " if active else "○ "
            btn_label = f"{indicator}**{label}**\n\n{short}"
            btn_type = "primary" if active else "secondary"
            if st.button(
                btn_label,
                key=f"card_{mode_id}",
                use_container_width=True,
                type=btn_type,
                help=help_text,
            ):
                if active:
                    new_modes = [m for m in selected_modes if m != mode_id]
                else:
                    new_modes = selected_modes + [mode_id]
                st.session_state._pending_preset = new_modes
                st.rerun()
            st.caption(help_text)
    st.write("")


with st.expander("How to iterate on the bundler itself"):
    st.markdown(
        "- **Prompt-level rules**: edit `prompts/bundler_v5.md` to change how the bundler thinks.\n"
        "- **Code-level enforcement**: edit `BANNED_WORD_PATTERNS`, `SUSPICIOUS_REF_PATTERNS`, "
        "and `BANNED_SURGERY` in `bundler.py`.\n"
        "- **Add a mode**: drop a new `prompts/modes/<name>.md` file. Add a tuple to the `MODES` list in `app.py` "
        "with `(id, label, short, help)`.\n"
        "- **Add a preset**: append to the `PRESETS` list in `app.py` with `(id, label, [mode_ids], help)`.\n"
        "- **Add a template**: append to the `TEMPLATES` list with `{label, title, input, extra}`.\n"
        "- **Tweak styles**: edit `styles.css` (dark) or `styles-light.css` (light overrides). Hot-reloads on save."
    )


# ==========================================
# Footer
# ==========================================
st.markdown(
    """
<div class="footer-card">
    <div class="left">
        <span class="name">Karanvir Panwar</span>
        <span class="role">Built this. Open to feedback.</span>
        <span class="stats-inline">v6.2 · 9 modes · 12 banned-word filters · 6 Gemini fallback models</span>
    </div>
    <a class="email-link" href="mailto:karanvirsp8077@gmail.com">karanvirsp8077@gmail.com</a>
</div>
""",
    unsafe_allow_html=True,
)
