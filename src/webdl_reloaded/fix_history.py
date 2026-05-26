#!/usr/bin/env python3
# cspell:ignore webdl, autograbber
"""Quick and dirty script to update old history files to match webdl_reloaded format.

As it should be once and done, emphasise readability over efficiency.

Currently is a 75% fix for old SBS format only.
"""

import re
import sys
from pathlib import Path

from webdl_reloaded.common import standardize_title

NEW_HISTORY = ".history.new.txt"


def fix_sbs(this_line: str) -> str:
    """Fix SBS."""
    found = re.match(r"(.+ S\d+) +Ep(\d+) *-? *( .*)", this_line)

    if found:
        return (
            found.group(1)
            + "E"
            + f"{int(found.group(2)):02}"
            + found.group(3)
            + " (SBS)"
        )

    return ""


if __name__ == "__main__":
    old_history = Path(sys.argv[1]).resolve()

    new_history = old_history.parent / NEW_HISTORY
    if new_history.exists():
        raise FileExistsError(
            f"File (or directory) '{NEW_HISTORY}' already exists!"
            f"\n Fix utility will not override existing files. Exiting."
        )

    with (
        open(old_history, "r", encoding="utf-8") as hfp,
        open(new_history, "w", encoding="utf-8") as nfp,
    ):
        for line in hfp:
            if fixed := fix_sbs(line):
                nfp.write(fixed + "\n")
                continue

            abc_line = standardize_title(line.strip(), "ABC")
            nfp.write(abc_line + "\n")
