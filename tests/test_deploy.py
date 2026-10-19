from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_vercelignore_only_skips_top_level_folders():
    # An unanchored "ml/" also matches billbreaker/ml and the deploy fails to import.
    lines = [l for l in (ROOT / ".vercelignore").read_text().splitlines() if l.strip()]
    assert all(l.startswith("/") for l in lines)
