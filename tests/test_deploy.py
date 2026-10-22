from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_vercelignore_only_skips_top_level_folders():
    # An unanchored "ml/" also matches billbreaker/ml and the deploy fails to import.
    lines = [l for l in (ROOT / ".vercelignore").read_text().splitlines() if l.strip()]
    assert all(l.startswith("/") for l in lines)


def test_vercel_installs_every_requirement():
    """Vercel installs from pyproject.toml, so a package only in requirements.txt crashes the site."""
    import re
    import tomllib
    from pathlib import Path

    def names(lines):
        return {re.split(r"[<>=\[ ]", line.strip())[0].lower() for line in lines if line.strip() and not line.startswith("#")}

    root = Path(__file__).resolve().parent.parent
    project = names(tomllib.loads((root / "pyproject.toml").read_text())["project"]["dependencies"])
    assert names((root / "requirements.txt").read_text().splitlines()) <= project
