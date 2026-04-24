# backend/automation_config.py - Autonomy mode rules and decision logic
from typing import List, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from database import ProposedFix

# ─── Fix types that are considered SAFE for auto-approval in Smart mode ───
# These are low-risk, reversible changes that don't alter page meaning
SAFE_FIX_TYPES: Set[str] = {
    "alt_text",           # Adding missing alt text to images
    "meta_description",   # Improving/adding meta descriptions
    "meta_title",         # Fixing title length issues
    "h1_heading",         # Adding missing H1 tags
    "structured_data",    # Adding FAQ schema, author byline, date markup
    "excerpt",            # Improving WordPress excerpts
    "canonical",          # Fixing canonical URL issues
    "duplicate_title",    # Fixing duplicate page titles
}

# ─── Fix types that are HIGH-RISK and always need manual approval in Smart mode ───
RISKY_FIX_TYPES: Set[str] = {
    "thin_content",       # Expanding page content — could change meaning
    "multiple_h1",        # Demoting H1s to H2s — structural change
    "product_description", # Rewriting product descriptions — commercial impact
    "broken_link",        # Changing links — could break navigation
}

# ─── Severities that always require manual approval regardless of fix type ───
HIGH_RISK_SEVERITIES: Set[str] = {"critical", "high"}

# ─── Content change threshold: if proposed differs from current by more than this %,
# require manual approval even for "safe" fix types ───
MAX_SAFE_CONTENT_CHANGE_PCT = 50


def _content_change_pct(current: str, proposed: str) -> float:
    """Calculate how much the content changed as a percentage."""
    if not current:
        return 0.0  # Adding to empty field is always safe
    current_len = len(current.strip())
    if current_len == 0:
        return 0.0
    # Simple diff: how many characters changed relative to original
    from difflib import SequenceMatcher
    similarity = SequenceMatcher(None, current, proposed).ratio()
    change_pct = (1 - similarity) * 100
    return change_pct


def should_auto_approve(fix, mode: str) -> bool:
    """
    Determine if a fix should be auto-approved based on autonomy mode.

    Returns True if the fix should be auto-approved (no user review needed).
    """
    if mode == "manual":
        return False

    if mode == "ultra":
        return True

    if mode == "smart":
        # Always require approval for high-severity fixes
        if fix.severity in HIGH_RISK_SEVERITIES:
            return False

        # Only auto-approve known safe fix types
        if fix.fix_type not in SAFE_FIX_TYPES:
            return False

        # If there's an existing value and the change is dramatic, require approval
        if fix.current_value and len(fix.current_value.strip()) > 0:
            change_pct = _content_change_pct(fix.current_value, fix.proposed_value)
            if change_pct > MAX_SAFE_CONTENT_CHANGE_PCT:
                return False

        return True

    return False


def should_auto_apply(fix, mode: str) -> bool:
    """
    Determine if an already-approved fix should be auto-applied.

    In Smart mode, auto-approved fixes are also auto-applied.
    In Ultra mode, ALL approved fixes are auto-applied.
    In Manual mode, nothing is auto-applied.
    """
    if mode == "manual":
        return False

    if mode == "ultra":
        return True

    if mode == "smart":
        # Only auto-apply fixes that were auto-approved (safe ones)
        return fix.auto_approved_at is not None

    return False


def get_mode_description(mode: str) -> str:
    """Human-readable description of each autonomy mode."""
    descriptions = {
        "manual": "All fixes require manual approval before being applied.",
        "smart": "Safe fixes (alt text, meta tags, structured data) are auto-approved. Content changes need approval.",
        "ultra": "All fixes are auto-approved and applied immediately. Review the daily summary.",
    }
    return descriptions.get(mode, "Unknown mode")


def list_safe_fix_types() -> List[str]:
    """Return the list of fix types considered safe for auto-approval."""
    return sorted(SAFE_FIX_TYPES)


def list_risky_fix_types() -> List[str]:
    """Return the list of fix types considered risky (require manual approval)."""
    return sorted(RISKY_FIX_TYPES)
