"""Static validation of ECHO's model registry (no network, no keys).

Asserts the Definition-of-Done structure holds:
  * exactly 6 tier aliases (tier-*),
  * at least 16 concrete model aliases,
  * every tier has a non-empty fallback chain,
  * no hardcoded secrets — every api_key references os.environ/...,
  * every model carries a provider prefix (anthropic/, openai/, gemini/, ...).

Usage:  ``python echo/validate_config.py``  (exit 0 = clean)
"""

from __future__ import annotations

import os
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    print("PyYAML is required: pip install pyyaml")
    sys.exit(2)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

EXPECTED_TIERS = {
    "tier-compliance",
    "tier-long-doc",
    "tier-strategy",
    "tier-bulk",
    "tier-reasoning",
    "tier-realtime",
}
KNOWN_PROVIDER_PREFIXES = (
    "anthropic/",
    "openai/",
    "gemini/",
    "deepseek/",
    "xai/",
)


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate(config: dict) -> list[str]:
    errors: list[str] = []

    model_list = config.get("model_list") or []
    names = [m.get("model_name") for m in model_list]
    tiers = sorted(n for n in names if n and n.startswith("tier-"))
    aliases = sorted(n for n in names if n and not n.startswith("tier-"))

    # 6 tiers, exactly.
    if set(tiers) != EXPECTED_TIERS:
        errors.append(
            f"tiers mismatch: found {tiers}, expected {sorted(EXPECTED_TIERS)}"
        )

    # >= 16 concrete aliases.
    if len(aliases) < 16:
        errors.append(f"need >=16 model aliases, found {len(aliases)}: {aliases}")

    # No duplicate model_names.
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        errors.append(f"duplicate model_name entries: {dupes}")

    # Every entry: env-based key + provider-prefixed model.
    for entry in model_list:
        name = entry.get("model_name", "<unnamed>")
        params = entry.get("litellm_params", {}) or {}
        model = params.get("model", "")
        api_key = params.get("api_key", "")
        if not str(model).startswith(KNOWN_PROVIDER_PREFIXES):
            errors.append(f"{name}: model '{model}' lacks a known provider prefix")
        if not str(api_key).startswith("os.environ/"):
            errors.append(f"{name}: api_key must reference os.environ/ (got '{api_key}')")

    # Every tier has a non-empty fallback chain.
    fallbacks = {}
    for item in (config.get("router_settings", {}) or {}).get("fallbacks", []) or []:
        fallbacks.update(item)
    for tier in EXPECTED_TIERS:
        chain = fallbacks.get(tier)
        if not chain:
            errors.append(f"{tier}: missing fallback chain")
            continue
        unknown = [m for m in chain if m not in names]
        if unknown:
            errors.append(f"{tier}: fallback targets not defined as aliases: {unknown}")

    # Observability + master key wired.
    ls = config.get("litellm_settings", {}) or {}
    if "langfuse" not in (ls.get("success_callback") or []):
        errors.append("litellm_settings.success_callback must include 'langfuse'")
    gs = config.get("general_settings", {}) or {}
    if not str(gs.get("master_key", "")).startswith("os.environ/"):
        errors.append("general_settings.master_key must reference os.environ/")

    return errors


def main() -> None:
    config = load_config()
    errors = validate(config)

    model_list = config.get("model_list") or []
    names = [m.get("model_name") for m in model_list]
    tiers = sorted(n for n in names if n and n.startswith("tier-"))
    aliases = sorted(n for n in names if n and not n.startswith("tier-"))

    print(f"ECHO config: {len(aliases)} model aliases, {len(tiers)} tiers")
    print(f"  tiers:   {tiers}")
    print(f"  aliases: {aliases}")

    if errors:
        print("\nFAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("\nECHO config valid: 6 tiers, >=16 aliases, fallbacks + env keys OK.")


if __name__ == "__main__":
    main()
