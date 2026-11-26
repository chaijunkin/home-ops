#!/usr/bin/env python3
"""Strict validation for authored inputs. No dependencies, and no leniency.

A typo in a Definition is the most likely failure in the whole system, and the
two lenient options are both bad: ignore the unknown key (the operator believes
they asked for something they did not) or accept a misspelled required key as
absent. So an unrecognised field is an error naming the fields it did accept.

Shape spec is a small literal DSL:

    "str" | "int" | "bool" | "any"      scalars
    [spec]                              list, every element checked
    {"req": spec, "?opt": spec}         object; "?" prefix means optional
    one_of("a", "b")                    enumeration
    map_of(spec)                        mapping with string keys
    list_of(spec, min=1)                list with a length floor
"""

from __future__ import annotations

from errors import E_SCHEMA, fail


class _OneOf:
    def __init__(self, *choices):
        self.choices = list(choices)


class _MapOf:
    def __init__(self, value_spec):
        self.value_spec = value_spec


class _List:
    def __init__(self, item_spec, minimum=0):
        self.item_spec = item_spec
        self.minimum = minimum


def one_of(*choices):
    return _OneOf(*choices)


def map_of(value_spec):
    return _MapOf(value_spec)


def list_of(item_spec, minimum=0):
    return _List(item_spec, minimum)


def validate(where: str, data, spec, *, defaults: bool = True):
    """Return `data` checked against `spec`, filling optional defaults."""
    if isinstance(spec, _OneOf):
        if not isinstance(data, str) or data not in spec.choices:
            fail(E_SCHEMA, f"{where}: want one of {'|'.join(spec.choices)}, got {data!r}")
        return data

    if isinstance(spec, _MapOf):
        if not isinstance(data, dict):
            fail(E_SCHEMA, f"{where}: want a mapping, got {_kind(data)}")
        return {k: validate(f"{where}.{k}", v, spec.value_spec) for k, v in data.items()}

    if isinstance(spec, _List):
        if not isinstance(data, list):
            fail(E_SCHEMA, f"{where}: want a list, got {_kind(data)}")
        if len(data) < spec.minimum:
            fail(E_SCHEMA, f"{where}: want at least {spec.minimum} item(s), got {len(data)}")
        return [
            validate(f"{where}[{i}]", item, spec.item_spec) for i, item in enumerate(data)
        ]

    if isinstance(spec, dict):
        if not isinstance(data, dict):
            fail(E_SCHEMA, f"{where}: want a mapping, got {_kind(data)}")
        required = [k for k in spec if not k.startswith("?")]
        optional = [k[1:] for k in spec if k.startswith("?")]
        allowed = set(required) | set(optional)
        for key in sorted(data):
            if key not in allowed:
                fail(
                    E_SCHEMA,
                    f"{where}: unknown field {key!r}",
                    hint=f"accepted fields: {', '.join(sorted(allowed)) or '(none)'}",
                )
        for key in required:
            if key not in data or data[key] is None:
                fail(E_SCHEMA, f"{where}.{key}: required field missing")
        out = {}
        for key in sorted(allowed):
            sub = spec.get(key, spec.get("?" + key))
            if key in data:
                out[key] = validate(f"{where}.{key}", data[key], sub)
            elif defaults and _has_default(sub):
                out[key] = _default(sub)
        return out

    if spec == "str":
        if not isinstance(data, str) or not data.strip():
            fail(E_SCHEMA, f"{where}: want a non-empty string, got {data!r}")
        return data
    if spec == "int":
        if isinstance(data, bool) or not isinstance(data, int):
            fail(E_SCHEMA, f"{where}: want an integer, got {data!r}")
        return data
    if spec == "bool":
        if not isinstance(data, bool):
            fail(E_SCHEMA, f"{where}: want a boolean, got {data!r}")
        return data
    if spec == "any":
        return data
    raise AssertionError(f"unsupported spec {spec!r}")


def _kind(value) -> str:
    if isinstance(value, dict):
        return "a mapping"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, str):
        return "a string"
    if value is None:
        return "nothing"
    return repr(value)


def _has_default(spec) -> bool:
    # Only collections default, and only to empty. An optional nested object that
    # silently materialised as {} would look like an intentional empty choice.
    return isinstance(spec, (_List, _MapOf))


def _default(spec):
    return []
