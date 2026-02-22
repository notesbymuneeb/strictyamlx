import pytest
from strictyaml import Map, Str

from strictyamlx import Block, Case
from strictyamlx.blocks import Overlay

def test_block_init():
    bl = Block(when=lambda r,c: True, schema=Map({"a": Str()}))
    assert callable(bl.when)
    assert bl._validator is not None

def test_block_invalid_schema():
    with pytest.raises(AssertionError, match="schema must be of type Validator"):
        Block(when=lambda r,c: True, schema="not a validator")

def test_block_repr():
    bl = Block(when=lambda r,c: True, schema=Map({"a": Str()}))
    assert "Block(" in repr(bl)
    assert "schema=Map" in repr(bl)

def test_case_init():
    ca = Case(when=lambda r,c: True, schema=Map({"a": Str()}))
    assert isinstance(ca, Block)

def test_case_repr():
    ca = Case(when=lambda r,c: True, schema=Map({"a": Str()}))
    assert "Case(" in repr(ca)

def test_overlay_init():
    ov = Overlay(when=lambda r,c: True, schema=Map({"a": Str()}))
    assert isinstance(ov, Block)

def test_overlay_repr():
    ov = Overlay(when=lambda r,c: True, schema=Map({"a": Str()}))
    assert "Overlay(" in repr(ov)

def test_block_with_constraints():
    bl = Block(
        when=lambda r,c: True, 
        schema=Map({"a": Str()}),
        constraints=[lambda r,c,v: True]
    )
    assert bl.constraints is not None
    assert len(bl.constraints) == 1

def test_block_repr_with_constraints():
    bl = Block(
        when=lambda r,c: True, 
        schema=Map({"a": Str()}),
        constraints=[lambda r,c,v: True]
    )
    assert "constraints=" in repr(bl)

def test_case_is_block():
    assert issubclass(Case, Block)
