import os
import sys
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()

# Free-tier model fallback chain. Order = preference.
# Each model has its own daily/per-minute quota bucket, so when one hits the wall,
# the next one usually still has room.
GEMINI_FALLBACK_CHAIN = [
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
]


def generate(prompt: str, api_key: str = None) -> str:
    if PROVIDER == "gemini":
        return _gemini(prompt, api_key)
    if PROVIDER == "ollama":
        return _ollama(prompt)
    raise ValueError(f"Unknown LLM_PROVIDER: {PROVIDER}")


def _is_rate_limit_error(err: Exception) -> bool:
    s = str(err).lower()
    return any(token in s for token in ["429", "resource_exhausted", "quota", "rate limit"])


def _gemini(prompt: str, user_api_key: str = None) -> str:
    import google.generativeai as genai

    # Priority: user-provided key (from UI) > env var (local .env)
    api_key = user_api_key or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No Gemini API key set. Get a free key at "
            "https://aistudio.google.com/app/apikey and paste it into the "
            "app's settings menu (☰ icon, top right)."
        )
    genai.configure(api_key=api_key)

    primary = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    chain = [primary] + [m for m in GEMINI_FALLBACK_CHAIN if m != primary]

    last_err: Exception = None
    rate_limited = []
    for model_name in chain:
        try:
            model = genai.GenerativeModel(model_name)
            return model.generate_content(prompt).text
        except Exception as err:
            if _is_rate_limit_error(err):
                rate_limited.append(model_name)
                print(f"[llm] {model_name} rate-limited, trying next model...", file=sys.stderr)
                last_err = err
                continue
            raise

    raise RuntimeError(
        "All free-tier Gemini models hit their rate limits.\n"
        f"Models tried: {', '.join(rate_limited)}\n"
        "Daily free quotas reset at midnight Pacific time. Either wait, or "
        "use a different API key."
    ) from last_err


def _ollama(prompt: str) -> str:
    import ollama

    model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    return ollama.generate(model=model, prompt=prompt)["response"]
