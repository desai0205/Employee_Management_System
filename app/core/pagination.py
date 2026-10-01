"""Page parameters shared by list endpoints. Sort fields are allowlisted later."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageParams:
    page: int = 1
    page_size: int = 20
    sort: str | None = None
    order: str = "asc"

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def page_count(total: int, page_size: int) -> int:
    if total <= 0:
        return 0
    return (total + page_size - 1) // page_size
