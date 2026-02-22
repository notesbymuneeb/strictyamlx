import pytest
from strictyaml import Map, Str, Int
from strictyamlx.builder import ValidatorBuilder

def test_builder_simple_merge():
    ctrl = Map({"type": Str()})
    case = Map({"value": Int()})
    
    builder = ValidatorBuilder(ctrl, case)
    final = builder.validator
    
    assert "type" in final._validator
    assert "value" in final._validator

def test_builder_nested_merge():
    ctrl = Map({"meta": Map({"type": Str()})})
    case = Map({"meta": Map({"version": Int()}), "data": Str()})
    
    builder = ValidatorBuilder(ctrl, case)
    final = builder.validator
    
    assert "meta" in final._validator
    assert "type" in final._validator["meta"]._validator
    assert "version" in final._validator["meta"]._validator
    assert "data" in final._validator

def test_builder_merge_disparate():
    ctrl = Map({"meta": Map({"type": Str()})})
    case = Map({"data": Str()})
    
    builder = ValidatorBuilder(ctrl, case)
    final = builder.validator
    
    assert "meta" in final._validator
    assert "type" in final._validator["meta"]._validator
    assert "data" in final._validator

def test_builder_control_source_string():
    ctrl = Map({"type": Str()})
    case = Map({"data": Str()})
    
    builder = ValidatorBuilder(ctrl, case, control_source="meta")
    final = builder.validator
    
    assert "meta" in final._validator
    assert "type" in final._validator["meta"]._validator
    assert "data" in final._validator

def test_builder_control_source_tuple():
    ctrl = Map({"type": Str()})
    case = Map({"data": Str()})
    
    builder = ValidatorBuilder(ctrl, case, control_source=("a", "b"))
    final = builder.validator
    
    assert "a" in final._validator
    assert "b" in final._validator["a"]._validator
    assert "type" in final._validator["a"]._validator["b"]._validator

def test_builder_rebuild_recursive():
    ctrl = Map({"type": Str()})
    case = Map({"data": Map({"inner": Int()})})
    builder = ValidatorBuilder(ctrl, case)
    final = builder.validator
    
    assert isinstance(final, Map)
    assert isinstance(final._validator["data"], Map)

def test_builder_ignores_non_map_control():
    ctrl = Str() # If control is not a map, it doesn't merge
    case = Map({"data": Int()})
    builder = ValidatorBuilder(ctrl, case)
    final = builder.validator
    assert "data" in final._validator
    assert "type" not in final._validator

def test_builder_keys_in_case_override_control():
    # Builder only injects control keys into case if case doesn't have them
    # If case already has a mapping/scalar for that key, it respects case.
    ctrl = Map({"type": Str()})
    case = Map({"type": Int()})
    builder = ValidatorBuilder(ctrl, case)
    final = builder.validator
    assert isinstance(final._validator["type"], type(Int()))

def test_builder_empty_case():
    ctrl = Map({"type": Str()})
    case = Map({})
    builder = ValidatorBuilder(ctrl, case)
    final = builder.validator
    assert "type" in final._validator

def test_builder_empty_control():
    ctrl = Map({})
    case = Map({"value": Int()})
    builder = ValidatorBuilder(ctrl, case)
    final = builder.validator
    assert "value" in final._validator
