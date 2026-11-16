"""Counts site visits: every page load, not unique visitors."""

from . import counts


async def count() -> None:
    await counts.bump("visits")


async def total() -> int:
    return await counts.total("visits")
