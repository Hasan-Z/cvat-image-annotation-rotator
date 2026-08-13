from pathlib import Path


def test_working_checkpoint_documents_reset_dot_export_contract() -> None:
    checkpoint = Path("WORKING_CHECKPOINT.md")

    assert checkpoint.exists()
    text = checkpoint.read_text(encoding="utf-8")
    assert "Reset dot" in text
    assert "exports CVAT XML with rotation value `0`" in text
    assert "exported boxes do not rotate unexpectedly" in text
