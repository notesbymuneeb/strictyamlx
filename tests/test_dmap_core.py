import pytest
from strictyaml.exceptions import YAMLSerializationError, YAMLValidationError

from strictyamlx import Case, Control, DMap, Int, Map, Str, load

def test_dmap_init_valid():
    ctrl = Control(Map({"type": Str()}))
    case = Case(when=lambda r, c: True, schema=Map({"b": Int()}))
    dmap = DMap(ctrl, [case])
    assert dmap.control == ctrl
    assert dmap.blocks == [case]
    assert dmap.constraints is None

def test_dmap_init_invalid_control():
    case = Case(when=lambda r, c: True, schema=Map({"b": Int()}))
    with pytest.raises(AssertionError, match="control must be of type Control"):
        DMap("not control", [case])

def test_dmap_init_invalid_blocks():
    ctrl = Control(Map({"type": Str()}))
    with pytest.raises(AssertionError, match="blocks must be a list of Block"):
        DMap(ctrl, "not list")

def test_dmap_init_invalid_block_type():
    ctrl = Control(Map({"type": Str()}))
    with pytest.raises(AssertionError, match="all blocks must be of type Block"):
        DMap(ctrl, ["not block"])

def test_dmap_init_invalid_constraints():
    ctrl = Control(Map({"type": Str()}))
    case = Case(when=lambda r, c: True, schema=Map({"b": Int()}))
    with pytest.raises(AssertionError, match="constraints must be a list of Callable"):
        DMap(ctrl, [case], constraints="not list")

def test_dmap_init_invalid_constraint_type():
    ctrl = Control(Map({"type": Str()}))
    case = Case(when=lambda r, c: True, schema=Map({"b": Int()}))
    with pytest.raises(AssertionError, match="every constraint must be callable"):
        DMap(ctrl, [case], constraints=["not callable"])

def test_dmap_compile_when():
    func = lambda r, c: True
    compiled = DMap.compile_when(func)
    assert compiled("raw", "ctrl") is True

    compiled_bool = DMap.compile_when(False)
    assert compiled_bool("raw", "ctrl") is False


def test_dmap_compile_when_kwargs_backward_compatible():
    def func_with_kwargs(r, c, **kwargs):
        return kwargs.get("parents") == [{"ctrl": {"a": 1}, "raw": {"a": 1}, "val": {"a": 1}}]

    compiled = DMap.compile_when(func_with_kwargs)
    assert (
        compiled(
            "raw",
            "ctrl",
            parents=[{"ctrl": {"a": 1}, "raw": {"a": 1}, "val": {"a": 1}}],
        )
        is True
    )


def test_dmap_compile_when_signature_fallback(monkeypatch):
    def func(r, c):
        return r == "raw" and c == "ctrl"

    monkeypatch.setattr("strictyamlx.dmap.inspect.signature", lambda _func: (_ for _ in ()).throw(ValueError("no signature")))
    compiled = DMap.compile_when(func)
    assert compiled("raw", "ctrl") is True

def test_dmap_compile_constraint():
    func = lambda r, c, v: True
    compiled = DMap.compile_constraint(func)
    assert compiled("raw", "ctrl", "val") is True
    assert compiled("raw", "ctrl", "val", parents=[{"raw": {}, "ctrl": {}, "val": {}}]) is True

    compiled_bool = DMap.compile_constraint(False)
    assert compiled_bool("raw", "ctrl", "val") is False
    assert (
        compiled_bool("raw", "ctrl", "val", parents=[{"raw": {}, "ctrl": {}, "val": {}}])
        is False
    )


def test_dmap_compile_constraint_kwargs_backward_compatible():
    def func_with_kwargs(r, c, v, **kwargs):
        return kwargs.get("parents") == [{"ctrl": {"a": 1}, "raw": {"a": 1}, "val": {"a": 1}}]

    compiled = DMap.compile_constraint(func_with_kwargs)
    assert (
        compiled(
            "raw",
            "ctrl",
            "val",
            parents=[{"ctrl": {"a": 1}, "raw": {"a": 1}, "val": {"a": 1}}],
        )
        is True
    )

def test_dmap_routing_basic():
    ctrl = Control(Map({"type": Str()}))
    
    blocks = [
        Case(when=lambda r, c: c["type"] == "X", schema=Map({"x": Int()})),
        Case(when=lambda r, c: c["type"] == "Y", schema=Map({"y": Str()})),
    ]
    
    schema = DMap(ctrl, blocks)
    doc = load("type: X\nx: 123", schema)
    assert doc.data == {"type": "X", "x": 123}

def test_dmap_routing_no_case():
    ctrl = Control(Map({"type": Str()}))
    
    blocks = [
        Case(when=lambda r, c: c["type"] == "X", schema=Map({"x": Int()})),
    ]
    
    schema = DMap(ctrl, blocks)
    with pytest.raises(YAMLValidationError, match="none of the cases were true"):
        load("type: Y\ny: hello", schema)
