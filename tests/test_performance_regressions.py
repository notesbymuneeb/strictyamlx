"""Regression tests for the performance refactor.

These guard the behaviours that were easy to break while removing the
per-parse deepcopy, the double validation traversal and the repeated rebuilds:

* nested ``DMap``s reachable from both ``Control`` and the ``Case`` schema are
  validated a linear number of times (not ``2 ** depth``),
* the per-``DMap`` build cache is safe across repeated loads and alternating
  case selection,
* validating against the filtered control view keeps the same ``.data`` and the
  original document's error locations.
"""

import pytest
from strictyaml.exceptions import YAMLValidationError

from strictyamlx import (
    Case,
    Control,
    DMap,
    Int,
    Map,
    Optional,
    Overlay,
    Seq,
    Str,
    load,
)


def _build_chain(depth):
    inner = DMap(
        control=Control(Map({"kind": Str()})),
        blocks=[Case(when=True, schema=Map({"kind": Str(), "value": Int()}))],
    )
    schema = inner
    for level in range(depth):
        fields = {"selector": Str(), "child": schema}
        schema = DMap(
            control=Control(Map(fields)),
            blocks=[Case(when=True, schema=Map(fields))],
        )
    return schema


def _chain_yaml(depth):
    lines = []
    for level in range(depth):
        indent = "  " * level
        lines.append(indent + "selector: s{0}".format(level))
        lines.append(indent + "child:")
    indent = "  " * depth
    lines.append(indent + "kind: leaf")
    lines.append(indent + "value: 1")
    return "\n".join(lines) + "\n"


def test_nested_control_dmap_validation_is_linear(monkeypatch):
    from strictyamlx.dmap import DMap as DMapClass

    calls = {"count": 0}
    original = DMapClass.validate

    def counting_validate(self, chunk):
        calls["count"] += 1
        return original(self, chunk)

    monkeypatch.setattr(DMapClass, "validate", counting_validate)

    depth = 12
    load(_chain_yaml(depth), _build_chain(depth))

    # One root plus one per level; anything close to 2 ** depth fails.
    assert calls["count"] <= 2 * depth + 4


def test_repeated_loads_are_stable():
    schema = _build_chain(8)
    data = _chain_yaml(8)
    first = load(data, schema).data
    for _ in range(5):
        assert load(data, schema).data == first


def test_build_cache_handles_alternating_case_selection():
    schema = DMap(
        control=Control(Map({"t": Str()})),
        blocks=[
            Case(when=lambda raw, ctrl: ctrl["t"] == "a", schema=Map({"t": Str(), "x": Int()})),
            Case(when=lambda raw, ctrl: ctrl["t"] == "b", schema=Map({"t": Str(), "y": Str()})),
        ],
    )
    for _ in range(5):
        assert load("t: a\nx: 1\n", schema).data == {"t": "a", "x": 1}
        assert load("t: b\ny: hi\n", schema).data == {"t": "b", "y": "hi"}


def test_reused_dmap_instance_at_two_keys_keeps_distinct_data():
    child = DMap(
        control=Control(Map({"k": Str()})),
        blocks=[Case(when=True, schema=Map({"k": Str(), "n": Int()}))],
    )
    schema = DMap(
        control=Control(Map({"left": child, "right": child})),
        blocks=[Case(when=True, schema=Map({"left": child, "right": child, "v": Int()}))],
    )
    parsed = load(
        "left:\n  k: a\n  n: 1\nright:\n  k: b\n  n: 2\nv: 3\n", schema
    ).data
    assert parsed == {
        "left": {"k": "a", "n": 1},
        "right": {"k": "b", "n": 2},
        "v": 3,
    }


def test_control_with_nested_plain_map_filters_extra_keys():
    schema = DMap(
        control=Control(Map({"meta": Map({"a": Str()})})),
        blocks=[
            Case(
                when=True,
                schema=Map({"meta": Map({"a": Str(), "b": Int()}), "v": Int()}),
            )
        ],
    )
    parsed = load("meta:\n  a: x\n  b: 2\nv: 1\n", schema).data
    assert parsed == {"meta": {"a": "x", "b": 2}, "v": 1}


def test_control_with_optional_default():
    schema = DMap(
        control=Control(Map({"mode": Str(), Optional("debug", default="off"): Str()})),
        blocks=[
            Case(
                when=lambda raw, ctrl: ctrl["mode"] == "run",
                schema=Map({"mode": Str(), Optional("debug"): Str(), "v": Int()}),
            )
        ],
    )
    assert load("mode: run\ndebug: on\nv: 1\n", schema).data == {
        "mode": "run",
        "debug": "on",
        "v": 1,
    }
    assert load("mode: run\nv: 1\n", schema).data == {"mode": "run", "v": 1}


def test_control_with_sequence_value():
    schema = DMap(
        control=Control(Map({"tags": Seq(Str())})),
        blocks=[
            Case(
                when=lambda raw, ctrl: "x" in ctrl["tags"],
                schema=Map({"tags": Seq(Str()), "v": Int()}),
            )
        ],
    )
    assert load("tags:\n  - x\n  - y\nv: 1\n", schema).data == {
        "tags": ["x", "y"],
        "v": 1,
    }


def test_nested_control_error_reports_original_line():
    inner = DMap(
        control=Control(Map({"kind": Str()})),
        blocks=[Case(when=True, schema=Map({"kind": Str(), "value": Int()}))],
    )
    schema = DMap(
        control=Control(Map({"type": Str(), "child": inner})),
        blocks=[
            Case(
                when=True,
                schema=Map({"type": Str(), "child": inner, "extra": Int()}),
            )
        ],
    )
    with pytest.raises(YAMLValidationError) as excinfo:
        load("type: t\nchild:\n  kind: leaf\n  value: nope\nextra: 2\n", schema)
    assert "line 4" in str(excinfo.value)


def test_control_missing_required_key_raises():
    schema = DMap(
        control=Control(Map({"needed": Str()})),
        blocks=[Case(when=True, schema=Map({"needed": Str(), "v": Int()}))],
    )
    with pytest.raises(YAMLValidationError, match="required key\\(s\\) 'needed' not found"):
        load("v: 1\n", schema)
