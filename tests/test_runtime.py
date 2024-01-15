from importlib.metadata import version
from pathlib import Path


def test_installed_dependencies_match_exact_lock():
    for line in (Path(__file__).resolve().parents[1] / "requirements.lock").read_text().splitlines():
        if line and not line.startswith("#"):
            name, expected = line.split("==")
            assert version(name) == expected
