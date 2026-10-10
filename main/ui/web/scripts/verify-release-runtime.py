"""Fail closed when a release runner differs from the validated Windows runtime."""
from importlib.metadata import distributions
from pathlib import Path
import re
import sys


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def verify() -> None:
    if sys.platform != "win32" or sys.version_info[:2] != (3, 13):
        raise SystemExit("The desktop release requires Windows and Python 3.13.")
    expected = {}
    for line in Path(__file__).with_name("requirements-desktop.lock.txt").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            name, version = line.split("==")
            expected[normalize(name)] = version
    actual = {normalize(d.metadata["Name"]): d.version for d in distributions()}
    errors = [f"{name}: expected {version}, got {actual.get(name, 'missing')}"
              for name, version in expected.items() if actual.get(name) != version]
    extras = sorted(set(actual) - set(expected) - {"pip"})
    if extras:
        errors.append("Unvalidated extra packages: " + ", ".join(extras))
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Validated release runtime: {len(expected)} exact package versions")


if __name__ == "__main__":
    verify()
