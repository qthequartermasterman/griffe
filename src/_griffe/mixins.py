"""This module contains some mixins classes about accessing and setting members."""

from __future__ import annotations

import json
import warnings
from contextlib import suppress
from typing import TYPE_CHECKING, Any, Sequence, TypeVar

from _griffe.enumerations import Kind
from _griffe.exceptions import AliasResolutionError, CyclicAliasError
from _griffe.logger import get_logger
from _griffe.merger import merge_stubs

if TYPE_CHECKING:
    from _griffe.dataclasses import Alias, Attribute, Class, Function, Module, Object

_logger = get_logger("griffe")
_ObjType = TypeVar("_ObjType")


def _get_parts(key: str | Sequence[str]) -> Sequence[str]:
    if isinstance(key, str):
        if not key:
            raise ValueError("Empty strings are not supported")
        parts = key.split(".")
    else:
        parts = list(key)
    if not parts:
        raise ValueError("Empty tuples are not supported")
    return parts


class GetMembersMixin:
    """Mixin class to share methods for accessing members.

    Methods:
        get_member: Get a member with its name or path.
        __getitem__: Same as `get_member`, with the item syntax `[]`.
    """

    def __getitem__(self, key: str | Sequence[str]) -> Any:
        """Get a member with its name or path.

        This method is part of the consumer API:
        do not use when producing Griffe trees!

        Members will be looked up in both declared members and inherited ones,
        triggering computation of the latter.

        Parameters:
            key: The name or path of the member.

        Examples:
            >>> foo = griffe_object["foo"]
            >>> bar = griffe_object["path.to.bar"]
            >>> qux = griffe_object[("path", "to", "qux")]
        """
        parts = _get_parts(key)
        if len(parts) == 1:
            return self.all_members[parts[0]]  # type: ignore[attr-defined]
        return self.all_members[parts[0]][parts[1:]]  # type: ignore[attr-defined]

    def get_member(self, key: str | Sequence[str]) -> Any:
        """Get a member with its name or path.

        This method is part of the producer API:
        you can use it safely while building Griffe trees
        (for example in Griffe extensions).

        Members will be looked up in declared members only, not inherited ones.

        Parameters:
            key: The name or path of the member.

        Examples:
            >>> foo = griffe_object["foo"]
            >>> bar = griffe_object["path.to.bar"]
            >>> bar = griffe_object[("path", "to", "bar")]
        """
        parts = _get_parts(key)
        if len(parts) == 1:
            return self.members[parts[0]]  # type: ignore[attr-defined]
        return self.members[parts[0]].get_member(parts[1:])  # type: ignore[attr-defined]


class DelMembersMixin:
    """Mixin class to share methods for deleting members.

    Methods:
        del_member: Delete a member with its name or path.
        __delitem__: Same as `del_member`, with the item syntax `[]`.
    """

    def __delitem__(self, key: str | Sequence[str]) -> None:
        """Delete a member with its name or path.

        This method is part of the consumer API:
        do not use when producing Griffe trees!

        Members will be looked up in both declared members and inherited ones,
        triggering computation of the latter.

        Parameters:
            key: The name or path of the member.

        Examples:
            >>> del griffe_object["foo"]
            >>> del griffe_object["path.to.bar"]
            >>> del griffe_object[("path", "to", "qux")]
        """
        parts = _get_parts(key)
        if len(parts) == 1:
            name = parts[0]
            try:
                del self.members[name]  # type: ignore[attr-defined]
            except KeyError:
                del self.inherited_members[name]  # type: ignore[attr-defined]
        else:
            del self.all_members[parts[0]][parts[1:]]  # type: ignore[attr-defined]

    def del_member(self, key: str | Sequence[str]) -> None:
        """Delete a member with its name or path.

        This method is part of the producer API:
        you can use it safely while building Griffe trees
        (for example in Griffe extensions).

        Members will be looked up in declared members only, not inherited ones.

        Parameters:
            key: The name or path of the member.

        Examples:
            >>> griffe_object.del_member("foo")
            >>> griffe_object.del_member("path.to.bar")
            >>> griffe_object.del_member(("path", "to", "qux"))
        """
        parts = _get_parts(key)
        if len(parts) == 1:
            name = parts[0]
            del self.members[name]  # type: ignore[attr-defined]
        else:
            self.members[parts[0]].del_member(parts[1:])  # type: ignore[attr-defined]


class SetMembersMixin:
    """Mixin class to share methods for setting members.

    Methods:
        set_member: Set a member with its name or path.
        __setitem__: Same as `set_member`, with the item syntax `[]`.
    """

    def __setitem__(self, key: str | Sequence[str], value: Object | Alias) -> None:
        """Set a member with its name or path.

        This method is part of the consumer API:
        do not use when producing Griffe trees!

        Parameters:
            key: The name or path of the member.
            value: The member.

        Examples:
            >>> griffe_object["foo"] = foo
            >>> griffe_object["path.to.bar"] = bar
            >>> griffe_object[("path", "to", "qux")] = qux
        """
        parts = _get_parts(key)
        if len(parts) == 1:
            name = parts[0]
            self.members[name] = value  # type: ignore[attr-defined]
            if self.is_collection:  # type: ignore[attr-defined]
                value._modules_collection = self  # type: ignore[union-attr]
            else:
                value.parent = self  # type: ignore[assignment]
        else:
            self.members[parts[0]][parts[1:]] = value  # type: ignore[attr-defined]

    def set_member(self, key: str | Sequence[str], value: Object | Alias) -> None:
        """Set a member with its name or path.

        This method is part of the producer API:
        you can use it safely while building Griffe trees
        (for example in Griffe extensions).

        Parameters:
            key: The name or path of the member.
            value: The member.

        Examples:
            >>> griffe_object.set_member("foo", foo)
            >>> griffe_object.set_member("path.to.bar", bar)
            >>> griffe_object.set_member(("path", "to", "qux"), qux)
        """
        parts = _get_parts(key)
        if len(parts) == 1:
            name = parts[0]
            if name in self.members:  # type: ignore[attr-defined]
                member = self.members[name]  # type: ignore[attr-defined]
                if not member.is_alias:
                    # When reassigning a module to an existing one,
                    # try to merge them as one regular and one stubs module
                    # (implicit support for .pyi modules).
                    if member.is_module and not (member.is_namespace_package or member.is_namespace_subpackage):
                        with suppress(AliasResolutionError, CyclicAliasError):
                            if value.is_module and value.filepath != member.filepath:
                                with suppress(ValueError):
                                    value = merge_stubs(member, value)  # type: ignore[arg-type]
                    for alias in member.aliases.values():
                        with suppress(CyclicAliasError):
                            alias.target = value
            self.members[name] = value  # type: ignore[attr-defined]
            if self.is_collection:  # type: ignore[attr-defined]
                value._modules_collection = self  # type: ignore[union-attr]
            else:
                value.parent = self  # type: ignore[assignment]
        else:
            self.members[parts[0]].set_member(parts[1:], value)  # type: ignore[attr-defined]


class SerializationMixin:
    """Mixin class to share methods for de/serializing objects.

    Methods:
        as_json: Return this object's data as a JSON string.
        from_json: Create an instance of this class from a JSON string.
    """

    def as_json(self, *, full: bool = False, **kwargs: Any) -> str:
        """Return this object's data as a JSON string.

        Parameters:
            full: Whether to return full info, or just base info.
            **kwargs: Additional serialization options passed to encoder.

        Returns:
            A JSON string.
        """
        from _griffe.encoders import JSONEncoder  # avoid circular import

        return json.dumps(self, cls=JSONEncoder, full=full, **kwargs)

    @classmethod
    def from_json(cls: type[_ObjType], json_string: str, **kwargs: Any) -> _ObjType:  # noqa: PYI019
        """Create an instance of this class from a JSON string.

        Parameters:
            json_string: JSON to decode into Object.
            **kwargs: Additional options passed to decoder.

        Returns:
            An Object instance.

        Raises:
            TypeError: When the json_string does not represent and object
                of the class from which this classmethod has been called.
        """
        from _griffe.encoders import json_decoder  # avoid circular import

        kwargs.setdefault("object_hook", json_decoder)
        obj = json.loads(json_string, **kwargs)
        if not isinstance(obj, cls):
            raise TypeError(f"provided JSON object is not of type {cls}")
        return obj


class ObjectAliasMixin(GetMembersMixin, SetMembersMixin, DelMembersMixin, SerializationMixin):
    """Mixin class to share methods that appear both in objects and aliases, unchanged.

    Attributes:
        all_members: All members (declared and inherited).
        modules: The module members.
        classes: The class members.
        functions: The function members.
        attributes: The attribute members.
        has_private_name: Whether this object/alias has a private name.
        is_exported: Whether this object/alias is exported (listed in `__all__`).
        is_wildcard_exposed: Whether this object/alias is exposed to wildcard imports.
        is_public: Whether this object is considered public.
    """

    @property
    def all_members(self) -> dict[str, Object | Alias]:
        """All members (declared and inherited).

        This method is part of the consumer API:
        do not use when producing Griffe trees!
        """
        return {**self.inherited_members, **self.members}  # type: ignore[attr-defined]

    @property
    def modules(self) -> dict[str, Module]:
        """The module members.

        This method is part of the consumer API:
        do not use when producing Griffe trees!
        """
        return {name: member for name, member in self.all_members.items() if member.kind is Kind.MODULE}  # type: ignore[misc]

    @property
    def classes(self) -> dict[str, Class]:
        """The class members.

        This method is part of the consumer API:
        do not use when producing Griffe trees!
        """
        return {name: member for name, member in self.all_members.items() if member.kind is Kind.CLASS}  # type: ignore[misc]

    @property
    def functions(self) -> dict[str, Function]:
        """The function members.

        This method is part of the consumer API:
        do not use when producing Griffe trees!
        """
        return {name: member for name, member in self.all_members.items() if member.kind is Kind.FUNCTION}  # type: ignore[misc]

    @property
    def attributes(self) -> dict[str, Attribute]:
        """The attribute members.

        This method is part of the consumer API:
        do not use when producing Griffe trees!
        """
        return {name: member for name, member in self.all_members.items() if member.kind is Kind.ATTRIBUTE}  # type: ignore[misc]

    @property
    def has_private_name(self) -> bool:
        """Whether this object/alias has a private name."""
        return self.name.startswith("_")  # type: ignore[attr-defined]

    @property
    def is_exported(self) -> bool:
        """Whether this object/alias is exported (listed in `__all__`)."""
        result = self.parent.is_module and bool(self.parent.exports and self.name in self.parent.exports)  # type: ignore[attr-defined]
        return _True if result else _False  # type: ignore[return-value]

    @property
    def is_explicitely_exported(self) -> bool:
        """Deprecated. Use the [`is_exported`][griffe.ObjectAliasMixin.is_exported] property instead."""
        warnings.warn(
            "The `is_explicitely_exported` property is deprecated. Use `is_exported` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.is_exported

    @property
    def is_implicitely_exported(self) -> bool:
        """Deprecated. Use the [`is_exported`][griffe.ObjectAliasMixin.is_exported] property instead."""
        warnings.warn(
            "The `is_implicitely_exported` property is deprecated. Use `is_exported` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.is_exported

    @property
    def is_wildcard_exposed(self) -> bool:
        """Whether this object/alias is exposed to wildcard imports.

        To be exposed to wildcard imports, an object/alias must:

        - be available at runtime
        - have a module as parent
        - be listed in `__all__` if `__all__` is defined
        - or not be private (having a name starting with an underscore)

        Special case for Griffe trees: a submodule is only exposed if its parent imports it.

        Returns:
            True or False.
        """
        if not self.runtime or not self.parent.is_module:  # type: ignore[attr-defined]
            return False
        if self.parent.exports is not None:  # type: ignore[attr-defined]
            return self.name in self.parent.exports  # type: ignore[attr-defined]
        if self.has_private_name:
            return False
        return self.is_alias or not self.is_module or self.name in self.parent.imports  # type: ignore[attr-defined]

    @property
    def is_public(self) -> bool:
        """Whether this object is considered public.

        In modules, developers can mark objects as public thanks to the `__all__` variable.
        In classes however, there is no convention or standard to do so.

        Therefore, to decide whether an object is public, we follow this algorithm:

        - If the object's `public` attribute is set (boolean), return its value.
        - If the object is exposed to wildcard imports, it is public.
        - If the object has a private name, it is private.
        - If the object was imported from another module, it is private.
        - Otherwise, the object is public.
        """
        # TODO: Return regular True/False values in next version.
        if self.public is not None:  # type: ignore[attr-defined]
            return _True if self.public else _False  # type: ignore[return-value,attr-defined]
        if self.is_wildcard_exposed:
            return _True  # type: ignore[return-value]
        if self.has_private_name:
            return _False  # type: ignore[return-value]
        # The following condition effectively filters out imported objects.
        # TODO: In a future version, we will support two conventions regarding imports:
        # - `from a import x as x` marks `x` as public.
        # - `from a import *` marks all wildcard imported objects as public.
        if self.is_alias and not (self.inherited or (self.parent and self.parent.is_alias)):  # type: ignore[attr-defined]
            return _False  # type: ignore[return-value]
        return _True  # type: ignore[return-value]


# This is used to allow the `is_public` property to be "callable",
# for backward compatibility with the previous implementation.
class _Bool:
    def __init__(self, value: bool) -> None:  # noqa: FBT001
        self.value = value

    def __bool__(self) -> bool:
        return self.value

    def __call__(self, *args: Any, **kwargs: Any) -> bool:  # noqa: ARG002
        warnings.warn(
            "This method is now a property and should be accessed as such (without parentheses).",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.value


_True = _Bool(True)  # noqa: FBT003
_False = _Bool(False)  # noqa: FBT003
