import pathlib


def test_handlers_do_not_import_firestore():
    """ADR-0008 Decision 3 (pre-CI manual gate)."""
    src = pathlib.Path(__file__).parent.parent / "src" / "sport_slot"
    allowed = {"repositories", "health.py", "dependencies.py"}
    offenders = []
    for path in src.rglob("*.py"):
        rel = path.relative_to(src)
        if rel.parts[0] in allowed or rel.name in allowed:
            continue
        if "google.cloud" in path.read_text():
            offenders.append(str(rel))
    assert offenders == [], f"google.cloud imported outside repository layer: {offenders}"
