#!/usr/bin/env python3
"""Published error and exit-code contract for the adoption engine.

Exit codes are a durable interface: an agent branches on them and a human wires
them into automation, so a code never changes meaning. Bands:

    0        ok
    1        a violation or unmet requirement was found (the work ran, the answer is no)
    2        usage error (bad flags, unknown verb)
    3        a comparison found a difference (`diff` reports 3, `plan --check` reports 3)
    10-19    input and catalog errors (nothing was read that could have been changed)
    20-29    verification errors (a tool ran and said no, or could not run)
    30-31    retryable (transport, registry, rate limit)
    40+      run and closure errors (an immutable record was violated)

Every failure carries an `E-*` name at the user-visible boundary, because exit
code 1 from three different causes is how an agent starts guessing.
"""

from __future__ import annotations

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2
EXIT_DIFF = 3

# code -> (name, meaning). Keep sorted; the self-test asserts the bands hold.
_CODES: dict[int, tuple[str, str]] = {
    0: ("OK", "success"),
    1: ("E-UNMET", "a requirement is not satisfied"),
    2: ("E-USAGE", "invocation error"),
    3: ("E-DIFF", "comparison found a difference"),
    10: ("E-INPUT-MISSING", "an authored input file does not exist"),
    11: ("E-INPUT-PARSE", "an authored input file is not readable YAML or JSON"),
    12: ("E-SCHEMA", "an authored input does not match its schema"),
    13: ("E-UNIT-UNKNOWN", "a Definition names a unit that does not exist"),
    14: ("E-SLOT-UNKNOWN", "a Definition names a slot the library does not define"),
    15: ("E-PIN-MISSING", "the lock has no entry the plan requires"),
    16: ("E-REGISTRY-DIGEST", "a registry file carries a digest; digests belong in the lock"),
    17: ("E-LOCK-STALE", "the lock does not match the registry it claims to pin"),
    18: ("E-GRAPH-CYCLE", "the dependency graph cannot be ordered"),
    19: ("E-LANE-VIOLATION", "the Definition asks for work the Environment's lane forbids"),
    20: ("E-TOOL-MISSING", "a required tool or script is not available"),
    21: ("E-VERIFY-FAIL", "a verification step reported failure"),
    22: ("E-VERIFY-INCONCLUSIVE", "a verification step could not reach a verdict"),
    30: ("E-TRANSPORT", "a network or registry call failed"),
    31: ("E-RATE-LIMIT", "throttled; safe to retry"),
    40: ("E-IMMUTABLE", "an attempt record was already written; a new attempt is required"),
    41: ("E-RUN-INCOMPLETE", "expected slots were not all observed"),
    42: ("E-CLOSURE-REJECT", "the closure record does not satisfy the consumer policy"),
    50: ("E-INTERNAL", "an engine fault; no claim about the estate is made either way"),
}

NAMES = {code: name for code, (name, _) in _CODES.items()}
MEANINGS = {code: text for code, (_, text) in _CODES.items()}

# Symbolic names for the numeric codes, so call sites read as intents.
OK = 0
E_UNMET = 1
E_USAGE = 2
E_DIFF = 3
E_INPUT_MISSING = 10
E_INPUT_PARSE = 11
E_SCHEMA = 12
E_UNIT_UNKNOWN = 13
E_SLOT_UNKNOWN = 14
E_PIN_MISSING = 15
E_REGISTRY_DIGEST = 16
E_LOCK_STALE = 17
E_GRAPH_CYCLE = 18
E_LANE_VIOLATION = 19
E_TOOL_MISSING = 20
E_VERIFY_FAIL = 21
E_VERIFY_INCONCLUSIVE = 22
E_TRANSPORT = 30
E_RATE_LIMIT = 31
E_IMMUTABLE = 40
E_RUN_INCOMPLETE = 41
E_CLOSURE_REJECT = 42
E_INTERNAL = 50


class AdoptionError(Exception):
    """A failure with a published code. The CLI turns this into JSON + an exit."""

    def __init__(self, code: int, detail: str, *, hint: str | None = None):
        if code not in NAMES:
            raise ValueError(f"undocumented exit code {code}")
        super().__init__(detail)
        self.code = code
        self.name = NAMES[code]
        self.detail = detail
        self.hint = hint

    def to_payload(self) -> dict:
        out = {"error": self.name, "code": self.code, "detail": str(self)}
        if self.hint:
            out["hint"] = self.hint
        return out


def fail(code: int, detail: str, *, hint: str | None = None) -> None:
    raise AdoptionError(code, detail, hint=hint)
