from __future__ import annotations

import re
from dataclasses import dataclass


DIFF_RE = re.compile(
    r"<<<<<<< ORIGINAL\n(?P<original>.*?)\n=======\n(?P<fixed>.*?)\n>>>>>>> FIXED",
    re.DOTALL,
)


@dataclass(frozen=True)
class DiffBlock:
    original: str
    fixed: str


def parse_diff_blocks(text: str) -> list[DiffBlock]:
    return [DiffBlock(match.group("original"), match.group("fixed")) for match in DIFF_RE.finditer(text)]


def apply_diff_blocks(content: str, blocks: list[DiffBlock]) -> str:
    updated = content
    for block in blocks:
        if block.original not in updated:
            raise ValueError("Original block was not found in target content")
        updated = updated.replace(block.original, block.fixed, 1)
    return updated
