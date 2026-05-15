from __future__ import annotations


def normalize_page(page: int | None, page_size: int | None, *, max_page_size: int = 200) -> tuple[int, int, int]:
    p = int(page or 1)
    if p < 1:
        p = 1
    ps = int(page_size or 50)
    if ps < 1:
        ps = 1
    if ps > int(max_page_size):
        ps = int(max_page_size)
    offset = (p - 1) * ps
    return p, ps, offset

