"""Compute method resolution order. Implements `Class.mro` attribute."""

# MIT License
# Copyright (c) 2019 Vitaly R. Samigullin
# Adapted from https://github.com/pilosus/c3linear
# Adapted from https://github.com/tristanlatr/pydocspec

from __future__ import annotations

from itertools import islice
from typing import Deque, TypeVar

T = TypeVar("T")


class Dependency(Deque[T]):
    @property
    def head(self) -> T | None:
        try:
            return self[0]
        except IndexError:
            return None

    @property
    def tail(self) -> islice:  # type: ignore
        """Return islice object, which is suffice for iteration or calling `in`."""
        try:
            return islice(self, 1, self.__len__())
        except (ValueError, IndexError):
            return islice([], 0, 0)


class DependencyList:
    """A class represents list of linearizations (dependencies).

    The last element of DependencyList is a list of parents.
    It's needed  to the merge process preserves the local
    precedence order of direct parent classes.
    """

    def __init__(self, *lists: list[T | None]) -> None:
        self._lists = [Dependency(i) for i in lists]

    def __contains__(self, item: T) -> bool:
        """Return True if any linearization's tail contains an item."""
        return any(item in l.tail for l in self._lists)  # type: ignore

    def __len__(self) -> int:
        size = len(self._lists)
        return (size - 1) if size else 0

    def __repr__(self) -> str:
        return self._lists.__repr__()

    @property
    def heads(self) -> list[T | None]:
        return [h.head for h in self._lists]

    @property
    def tails(self) -> DependencyList:  # type: ignore
        """Return self so that `__contains__` could be called."""
        return self

    @property
    def exhausted(self) -> bool:
        """Return True if all elements of the lists are exhausted."""
        return all(len(x) == 0 for x in self._lists)

    def remove(self, item: T | None) -> None:
        """Remove an item from the lists.

        Once an item removed from heads, the leftmost elements of the tails
        get promoted to become the new heads.
        """
        for i in self._lists:
            if i and i.head == item:
                i.popleft()


def merge(*lists: list[T | None]) -> list[T | None]:
    result: list[T | None] = []
    linearizations = DependencyList(*lists)

    while True:
        if linearizations.exhausted:
            return result

        for head in linearizations.heads:
            if head and (head not in linearizations.tails):
                result.append(head)  # type: ignore
                linearizations.remove(head)

                # Once candidate is found, continue iteration
                # from the first element of the list.
                break
        else:
            # Loop never broke, no linearization could possibly be found.
            raise ValueError("Cannot compute c3 linearization")
