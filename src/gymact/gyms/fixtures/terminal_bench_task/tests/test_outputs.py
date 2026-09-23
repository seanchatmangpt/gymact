from pathlib import Path


def test_output_file_has_expected_content() -> None:
    output_path = Path("/app/output.txt")
    assert output_path.is_file(), "expected /app/output.txt to exist"
    assert output_path.read_text() == "gymact-terminal-bench-ok"
