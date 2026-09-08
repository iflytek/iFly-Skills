"""Stage a self-contained UV MCPB source directory without deleting outputs."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVER_DIR.parent
sys.path.insert(0, str(SERVER_DIR))

from iflyskills_mcp.registry import load_registry  # noqa: E402


def stage(output: Path) -> None:
    destination = output.resolve()
    if destination.exists():
        raise FileExistsError(f"Refusing to replace existing output: {destination}")

    destination.mkdir(parents=True)
    for filename in ("manifest.json", "pyproject.toml", "uv.lock", "README.md"):
        shutil.copy2(SERVER_DIR / filename, destination / filename)
    shutil.copy2(REPO_ROOT / "LICENSE", destination / "LICENSE")
    shutil.copytree(
        SERVER_DIR / "iflyskills_mcp",
        destination / "iflyskills_mcp",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    skill_ids = sorted({skill.id for skill in load_registry()})
    for skill_id in skill_ids:
        source = REPO_ROOT / "skills" / skill_id / "scripts"
        shutil.copytree(
            source,
            destination / "skills" / skill_id / "scripts",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    print(f"Staged {len(skill_ids)} skill packages in {destination}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    stage(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
