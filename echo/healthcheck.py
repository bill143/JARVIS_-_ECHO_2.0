"""ECHO provider-key health check — reports per-key status.

Two modes:
  * default       : checks that each provider key is present in the environment.
  * ``--live``    : additionally makes one tiny completion per provider to prove
                    the key actually works (costs a few tokens; needs network).

Exit code 0 = all required providers OK, non-zero otherwise. Prints a JSON
report. Used by `docker compose` healthchecks and as a manual preflight before
the Block-8 live test.

    python echo/healthcheck.py
    python echo/healthcheck.py --live
"""

from __future__ import annotations

import json
import os
import sys

# provider -> (env var, a cheap model to ping in --live mode)
PROVIDERS = {
    "anthropic": ("ANTHROPIC_API_KEY", "anthropic/claude-haiku-4-5-20251001"),
    "openai": ("OPENAI_API_KEY", "openai/gpt-4o-mini"),
    "google": ("GEMINI_API_KEY", "gemini/gemini-1.5-flash"),
    "deepseek": ("DEEPSEEK_API_KEY", "deepseek/deepseek-chat"),
    "xai": ("XAI_API_KEY", "xai/grok-2-mini"),
}


def check_presence() -> dict:
    report = {}
    for provider, (env_var, _model) in PROVIDERS.items():
        present = bool(os.getenv(env_var))
        report[provider] = {
            "env_var": env_var,
            "key_present": present,
            "status": "ok" if present else "missing",
        }
    return report


def check_live(report: dict) -> dict:
    """Ping each present provider with a 1-token completion via LiteLLM."""
    try:
        import litellm
    except ImportError:
        for p in report.values():
            p["live"] = "litellm-not-installed"
        return report

    for provider, (_env_var, model) in PROVIDERS.items():
        entry = report[provider]
        if not entry["key_present"]:
            entry["live"] = "skipped-no-key"
            continue
        try:
            litellm.completion(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            entry["live"] = "ok"
        except Exception as exc:  # report, don't crash
            entry["live"] = f"error: {type(exc).__name__}: {exc}"
            entry["status"] = "unhealthy"
    return report


def main() -> None:
    live = "--live" in sys.argv[1:]
    report = check_presence()
    if live:
        report = check_live(report)

    print(json.dumps({"providers": report, "mode": "live" if live else "presence"}, indent=2))

    # Healthy if every provider that has a key is "ok". Missing keys are warned
    # but don't fail presence mode (you may not use all 5 providers).
    unhealthy = [p for p, v in report.items() if v.get("status") == "unhealthy"]
    any_key = any(v["key_present"] for v in report.values())
    if unhealthy or not any_key:
        sys.exit(1)


if __name__ == "__main__":
    main()
