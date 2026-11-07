"""Lenient field types for LLM structured output.

Models sometimes return `true` instead of "true", a number instead of a string, or null
instead of an empty list. Strict Pydantic types reject those and the whole response is lost,
so agent schemas use these coercing types instead.
"""

from typing import Annotated, Any

from pydantic import BeforeValidator


def _to_str(v: Any) -> Any:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int | float):
        return str(v)
    return v


def _to_list(v: Any) -> Any:
    if v is None:
        return []
    if isinstance(v, str | int | float | bool):
        return [v]
    return v


def _to_int_list(v: Any) -> Any:
    v = _to_list(v)
    out = []
    for x in v:
        if isinstance(x, str):
            x = x.strip().strip("[]")
            if not x.isdigit():
                continue
        out.append(x)
    return out


LStr = Annotated[str, BeforeValidator(_to_str)]
LStrList = Annotated[list[LStr], BeforeValidator(_to_list)]
LIntList = Annotated[list[int], BeforeValidator(_to_int_list)]
