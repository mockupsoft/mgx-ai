# -*- coding: utf-8 -*-
"""Apply SEARCH/REPLACE blocks to HTML (same logic as deepsite-locally ask-ai PUT)."""

from __future__ import annotations

from .prompts import DIVIDER, REPLACE_END, SEARCH_START


def apply_search_replace_blocks(chunk: str, html: str) -> tuple[str, list[list[int]]]:
    """
    Parse model output and apply SEARCH/REPLACE blocks.
    Returns (new_html, updated_lines) where updated_lines is [[start_line, end_line], ...].
    """
    new_html = html
    updated_lines: list[list[int]] = []
    position = 0
    while True:
        search_start_index = chunk.find(SEARCH_START, position)
        if search_start_index == -1:
            break
        divider_index = chunk.find(DIVIDER, search_start_index)
        if divider_index == -1:
            break
        replace_end_index = chunk.find(REPLACE_END, divider_index)
        if replace_end_index == -1:
            break

        search_block = chunk[
            search_start_index + len(SEARCH_START) : divider_index
        ]
        replace_block = chunk[
            divider_index + len(DIVIDER) : replace_end_index
        ]

        if search_block.strip() == "":
            new_html = f"{replace_block}\n{new_html}"
            updated_lines.append([1, len(replace_block.split("\n"))])
        else:
            block_position = new_html.find(search_block)
            if block_position != -1:
                before_text = new_html[:block_position]
                start_line_number = len(before_text.split("\n"))
                replace_lines = len(replace_block.split("\n"))
                end_line_number = start_line_number + replace_lines - 1
                updated_lines.append([start_line_number, end_line_number])
                new_html = new_html.replace(search_block, replace_block, 1)

        position = replace_end_index + len(REPLACE_END)

    return new_html, updated_lines
