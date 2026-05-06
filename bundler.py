"""
Context Bundler v6.2

Pipeline:
1. Generate master prompt from user input via meta-prompt template
2. Scan output for banned words and suspicious reference patterns
3. If issues found, retry with progressively stronger directives (max 2 retries)
4. After retries, apply HARD STRING SURGERY for stubborn banned words (skippable)
5. If references section still looks fabricated, strip it entirely (skippable)
6. Append any selected modes (caveman, senior, teacher, etc.)
7. Return output + full validation history + meta-prompt for debugging
"""

import re
from pathlib import Path
from llm import generate

PROMPTS_DIR = Path(__file__).parent / "prompts"
MODES_DIR = PROMPTS_DIR / "modes"
ACTIVE_TEMPLATE = "bundler_v5.md"
MAX_RETRIES = 2

BANNED_WORD_PATTERNS = [
    (r"\bconceptual\w*\b", "conceptual*"),
    (r"\bconsider(?:ed|ing|ation|ations|s)?\b", "consider*"),
    (r"\bpotentially\b", "potentially"),
    (r"\bideally\b", "ideally"),
    (r"\bessentially\b", "essentially"),
    (r"\bhigh-level\b", "high-level"),
    (r"\bapproximate(?:ly|d)?\b", "approximate*"),
    (r"\bpseudocode\b", "pseudocode"),
    (r"\byou might\b", "you might"),
    (r"\bcould potentially\b", "could potentially"),
    (r"\bfeel free to\b", "feel free to"),
    (r"\bas needed\b", "as needed"),
]

# Order matters — longer/compound patterns first
BANNED_SURGERY = [
    (r"\bcould potentially\b", "may"),
    (r"\bfeel free to\b", "you may"),
    (r"\byou might\b", "you must"),
    (r"\bas needed\b", "when relevant"),
    (r"\bhigh-level\b", "broad"),
    (r"\bpotentially\b", ""),
    (r"\bideally\b", ""),
    (r"\bessentially\b", ""),
    (r"\bconceptually\b", "structurally"),
    (r"\bconceptualize\b", "design"),
    (r"\bconceptual\b", "structural"),
    (r"\bconsiderations?\b", "factors"),
    (r"\bconsidering\b", "given"),
    (r"\bconsidered\b", "reviewed"),
    (r"\bconsiders?\b", "reviews"),
    (r"\bapproximately\b", "around"),
    (r"\bapproximated\b", "estimated"),
    (r"\bapproximate\b", "rough"),
    (r"\bpseudocode\b", "code"),
]

SUSPICIOUS_REF_PATTERNS = [
    (r"\([^)]*(?:Blog Post|Article|Tutorial|Guide|Comparison|Documentation|Resource)[^)]*\)",
     "parenthetical category label"),
    (r"vs\.?\s+\w[\w.\s]*:\s*A\s+(?:Deep\s+Dive|Practical\s+Guide|Developer's?\s+Perspective|Comparison)",
     "'X vs Y: A Deep Dive' template"),
    (r":\s*A\s+Developer'?s\s+Perspective\b", "'A Developer's Perspective' template"),
    (r"\*\*[A-Z][\w.]*\s+for\s+[A-Z][\w\s-]+:?\*\*", "'X for [Use Case]' template title"),
]

REFERENCES_SECTION_RE = re.compile(
    r"(?:^|\n)(?:Reference [Ww]orks?:?\s*\n)((?:\s*[*\-]\s+.+\n?)+)",
    re.MULTILINE,
)


def list_available_modes() -> list:
    """Return sorted list of mode names available in prompts/modes/."""
    if not MODES_DIR.exists():
        return []
    return sorted(p.stem for p in MODES_DIR.glob("*.md"))


def find_violations(text: str) -> list:
    found = []
    for pattern, label in BANNED_WORD_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            found.append((m.group(0), label))
    return found


def find_suspicious_refs(text: str) -> list:
    found = []
    for pattern, label in SUSPICIOUS_REF_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            found.append((m.group(0), label))
    return found


def apply_surgery(text: str) -> tuple:
    replacements = []
    cleaned = text
    for pattern, replacement in BANNED_SURGERY:
        def _sub(match):
            replacements.append((match.group(0), replacement))
            return replacement
        cleaned = re.sub(pattern, _sub, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r" +([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"\(\s+", "(", cleaned)
    cleaned = re.sub(r"\s+\)", ")", cleaned)
    return cleaned, replacements


def strip_references_section(text: str) -> tuple:
    if REFERENCES_SECTION_RE.search(text):
        return REFERENCES_SECTION_RE.sub("\n", text), True
    return text, False


def bundle(
    user_input: str,
    extra_context: str = "",
    modes: list = None,
    cleanup: bool = True,
    api_key: str = None,
) -> dict:
    """
    Returns:
      output, raw_output, meta_prompt, attempts, history, violations,
      suspicious_refs, surgery_replacements, refs_stripped, clean

    api_key: optional user-provided key. If None, falls back to env var.
    """
    template = (PROMPTS_DIR / ACTIVE_TEMPLATE).read_text()
    base_extra = extra_context.strip()

    last_meta_prompt = ""
    output = ""
    history = []

    for attempt in range(MAX_RETRIES + 1):
        retry_notes = []
        if attempt > 0 and history:
            prev = history[-1]
            if prev["violations"]:
                words = sorted({v[0].lower() for v in prev["violations"]})
                retry_notes.append(
                    f"CRITICAL RETRY {attempt + 1} of {MAX_RETRIES + 1}. "
                    f"Your previous draft used these BANNED words: {', '.join(words)}. "
                    f"Rewrite WITHOUT any of them. No paraphrasing — completely remove. "
                    f"This is enforced by automated checks."
                )
            if prev["suspicious_refs"]:
                retry_notes.append(
                    f"CRITICAL RETRY {attempt + 1} of {MAX_RETRIES + 1}. "
                    f"Your Reference Works section looks fabricated. "
                    f"OMIT the entire Reference Works section. "
                    f"Do not invent titles. Better to have no references than fake ones."
                )

        merged_extra = (
            (base_extra + "\n\n" + "\n\n".join(retry_notes)).strip()
            or "(none provided)"
        )
        last_meta_prompt = template.format(
            user_input=user_input.strip(),
            extra_context=merged_extra,
        )

        output = generate(last_meta_prompt, api_key=api_key)
        violations = find_violations(output)
        suspicious_refs = find_suspicious_refs(output)
        history.append({
            "attempt": attempt + 1,
            "violations": violations,
            "suspicious_refs": suspicious_refs,
            "word_count": len(output.split()),
        })

        if not violations and not suspicious_refs:
            break

    raw_output = output

    surgery_replacements = []
    refs_stripped = False

    if cleanup:
        if find_violations(output):
            output, surgery_replacements = apply_surgery(output)
        if find_suspicious_refs(output):
            output, refs_stripped = strip_references_section(output)

    final_violations = find_violations(output)
    final_suspicious = find_suspicious_refs(output)
    is_clean = not final_violations and not final_suspicious

    for mode in (modes or []):
        mode_path = MODES_DIR / f"{mode}.md"
        if mode_path.exists():
            output = output.rstrip() + "\n\n" + mode_path.read_text().rstrip() + "\n"

    return {
        "output": output,
        "raw_output": raw_output,
        "meta_prompt": last_meta_prompt,
        "attempts": len(history),
        "history": history,
        "violations": final_violations,
        "suspicious_refs": final_suspicious,
        "surgery_replacements": surgery_replacements,
        "refs_stripped": refs_stripped,
        "clean": is_clean,
        "cleanup_applied": cleanup,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python bundler.py \"your vague request here\" [mode1,mode2]")
        sys.exit(1)
    modes_arg = sys.argv[2].split(",") if len(sys.argv) > 2 else []
    result = bundle(sys.argv[1], modes=modes_arg)
    print(result["output"])
    print("\n---", file=sys.stderr)
    print(f"Attempts: {result['attempts']}", file=sys.stderr)
    for entry in result["history"]:
        v = len(entry["violations"])
        r = len(entry["suspicious_refs"])
        print(
            f"  Attempt {entry['attempt']}: {v} banned, {r} suspicious refs, "
            f"{entry['word_count']} words",
            file=sys.stderr,
        )
    if result["surgery_replacements"]:
        print(f"Surgery: {len(result['surgery_replacements'])} replacements", file=sys.stderr)
    if result["refs_stripped"]:
        print("References section: STRIPPED", file=sys.stderr)
    print(f"Final: {'CLEAN' if result['clean'] else 'DIRTY'}", file=sys.stderr)
