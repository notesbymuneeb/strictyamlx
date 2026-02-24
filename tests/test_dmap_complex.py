import pytest
from strictyaml.exceptions import YAMLSerializationError, YAMLValidationError

from strictyamlx import (
    Case,
    Control,
    DMap,
    ForwardRef,
    Int,
    Map,
    MapPattern,
    Seq,
    Str,
    as_document,
    load,
)

def test_dmap_to_yaml_success_first_case():
    ctrl = Control(Map({"type": Str()}))
    blocks = [
        Case(when=lambda r, c: c["type"] == "A", schema=Map({"a_val": Int()})),
        Case(when=lambda r, c: c["type"] == "B", schema=Map({"b_val": Str()})),
    ]
    schema = DMap(ctrl, blocks)
    doc = as_document({"type": "A", "a_val": 42}, schema)
    yaml_str = doc.as_yaml()
    assert "type: A" in yaml_str
    assert "a_val: 42" in yaml_str

def test_dmap_to_yaml_success_second_case():
    ctrl = Control(Map({"type": Str()}))
    blocks = [
        Case(when=lambda r, c: c["type"] == "A", schema=Map({"a_val": Int()})),
        Case(when=lambda r, c: c["type"] == "B", schema=Map({"b_val": Str()})),
    ]
    schema = DMap(ctrl, blocks)
    doc = as_document({"type": "B", "b_val": "hello"}, schema)
    yaml_str = doc.as_yaml()
    assert "type: B" in yaml_str
    assert "b_val: hello" in yaml_str

def test_dmap_to_yaml_fail_all_cases():
    ctrl = Control(Map({"type": Str()}))
    blocks = [
        Case(when=lambda r, c: c["type"] == "A", schema=Map({"a_val": Int()})),
    ]
    schema = DMap(ctrl, blocks)
    doc = as_document({"type": "B"}, schema)
    yaml_str = doc.as_yaml()
    assert "type: B" in yaml_str

def test_dmap_nested_dmap():
    ctrl_outer = Control(Map({"kind": Str()}))
    
    ctrl_inner = Control(Map({"subkind": Str()}))
    blocks_inner = [
        Case(when=lambda r, c: c["subkind"] == "V1", schema=Map({"v1": Int()})),
        Case(when=lambda r, c: c["subkind"] == "V2", schema=Map({"v2": Str()})),
    ]
    inner_schema = DMap(ctrl_inner, blocks_inner)
    
    blocks_outer = [
        Case(when=lambda r, c: c["kind"] == "complex", schema=inner_schema),
        Case(when=lambda r, c: c["kind"] == "simple", schema=Map({"value": Str()})),
    ]
    
    schema = DMap(ctrl_outer, blocks_outer)
    
    doc = load("kind: complex\nsubkind: V1\nv1: 100", schema)
    assert doc.data == {"kind": "complex", "subkind": "V1", "v1": 100}

    doc2 = load("kind: simple\nvalue: test", schema)
    assert doc2.data == {"kind": "simple", "value": "test"}

def test_dmap_with_forward_ref():
    ref = ForwardRef()
    ctrl = Control(Map({"type": Str()}))
    blocks = [
        Case(when=lambda r, c: c["type"] == "recursive", schema=Map({"value": Int(), "child": ref})),
        Case(when=lambda r, c: c["type"] == "leaf", schema=Map({"value": Int()})),
    ]
    schema = DMap(ctrl, blocks)
    ref.set(schema)
    
    yaml_str = "type: recursive\nvalue: 1\nchild:\n  type: leaf\n  value: 2"
    doc = load(yaml_str, schema)
    assert doc.data["type"] == "recursive"
    assert doc.data["child"]["type"] == "leaf"

def test_dmap_with_map_pattern():
    ctrl = Control(Map({"type": Str()}))
    
    blocks = [
        Case(
            when=lambda r, c: c["type"] == "dynamic", 
            schema=MapPattern(Str(), Int())
        )
    ]
    
    schema = DMap(ctrl, blocks)
    doc = load("type: dynamic\na: 10\nb: 20", schema)
    assert doc.data == {"type": "dynamic", "a": 10, "b": 20}

def test_dmap_complex_constraints():
    ctrl = Control(Map({"action": Str()}))
    
    blocks = [
        Case(
            when=lambda r, c: c["action"] == "transfer",
            schema=Map({"amount": Int(), "from": Str(), "to": Str()}),
            constraints=[
                lambda r, c, v: v["amount"] > 0,
                lambda r, c, v: v["from"] != v["to"]
            ]
        )
    ]
    
    schema = DMap(ctrl, blocks)
    
    # Pass
    load("action: transfer\namount: 100\nfrom: A\nto: B", schema)
    
    # Fail amount
    with pytest.raises(YAMLValidationError, match="constraints not fulfilled"):
        load("action: transfer\namount: -10\nfrom: A\nto: B", schema)
        
    # Fail accounts identical
    with pytest.raises(YAMLValidationError, match="constraints not fulfilled"):
        load("action: transfer\namount: 100\nfrom: A\nto: A", schema)

def test_dmap_global_constraints():
    ctrl = Control(Map({"action": Str()}))
    blocks = [
        Case(when=lambda r, c: True, schema=Map({"val": Int()}))
    ]
    schema = DMap(
        ctrl, 
        blocks,
        constraints=[lambda r, c, v: v["val"] < 100]
    )
    
    load("action: init\nval: 50", schema)
    with pytest.raises(YAMLValidationError, match="constraints not fulfilled"):
        load("action: init\nval: 150", schema)
