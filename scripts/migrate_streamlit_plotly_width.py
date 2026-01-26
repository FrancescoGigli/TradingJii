"""scripts/migrate_streamlit_plotly_width

Purpose
-------
Migrates deprecated Streamlit usage:

    st.plotly_chart(..., use_container_width=True/False)

to the new API:

    st.plotly_chart(..., width='stretch'/'content')

Scope
-----
This script ONLY updates st.plotly_chart calls (it does not touch st.button
or other widgets) to keep the change safe and avoid breaking behavior.

How it works
------------
- Recursively scans a target directory (default: agents/frontend)
- Performs a regex replacement on Python source files

Limitations
-----------
- Regex-based: assumes the plotly_chart call closes with ")" in the same
  syntactic call (works fine for typical formatting).
- Does not rewrite positional arguments.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PLOTLY_CHART_CALL_RE = re.compile(
    r"(st\.plotly_chart\([^\)]*?)\buse_container_width\s*=\s*(True|False)([^\)]*\))",
    re.DOTALL,
)


def migrate_text(text: str) -> tuple[str, int]:
    def repl(match: re.Match) -> str:
        prefix, val, suffix = match.group(1), match.group(2), match.group(3)
        width = "'stretch'" if val == "True" else "'content'"
        return f"{prefix}width={width}{suffix}"

    return PLOTLY_CHART_CALL_RE.subn(repl, text)


def run(root: Path) -> tuple[int, int]:
    changed_files = 0
    changed_occurrences = 0

    for path in root.rglob("*.py"):
        original = path.read_text(encoding="utf-8")
        updated, n = migrate_text(original)
        if n:
            path.write_text(updated, encoding="utf-8")
            changed_files += 1
            changed_occurrences += n

    return changed_files, changed_occurrences


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate Streamlit st.plotly_chart use_container_width -> width",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("agents/frontend"),
        help="Root directory to scan (default: agents/frontend)",
    )
    args = parser.parse_args()

    if not args.root.exists():
        raise SystemExit(f"Root directory not found: {args.root}")

    changed_files, changed_occurrences = run(args.root)
    print(
        "Updated Streamlit Plotly width API: "
        f"{changed_occurrences} occurrences across {changed_files} files"
    )


if __name__ == "__main__":
    main()
