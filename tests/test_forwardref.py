from strictyaml.exceptions import YAMLSerializationError, YAMLValidationError
import pytest

from strictyamlx import (
    ForwardRef,
    Int,
    Map,
    Optional,
    Seq,
    Str,
    as_document,
    load,
    unpack,
)

def test_forward_ref_init():
    fref = ForwardRef()
    assert fref._validator is None

def test_forward_ref_repr_unexpanded():
    fref = ForwardRef()
    assert repr(fref) == "ForwardRef()"

def test_forward_ref_set_valid():
    fref = ForwardRef()
    fref.set(Str())
    assert repr(fref) == "Str()"

def test_forward_ref_set_invalid():
    fref = ForwardRef()
    with pytest.raises(YAMLSerializationError, match="Expected a Validator"):
        fref.set("not a validator")

def test_forward_ref_use_before_set():
    fref = ForwardRef()
    with pytest.raises(YAMLSerializationError, match="ForwardRef was used before it was set"):
        load("a: 1", fref)

def test_forward_ref_validation_pass():
    fref = ForwardRef()
    fref.set(Int())
    doc = load("10", fref)
    assert doc.data == 10

def test_forward_ref_validation_fail():
    fref = ForwardRef()
    fref.set(Int())
    with pytest.raises(YAMLValidationError):
        load("hello", fref)

def test_forward_ref_nested_in_map():
    tree = ForwardRef()
    tree.set(Map({"name": Str(), Optional("children"): Seq(tree)}))
    
    yaml_str = "name: root\nchildren:\n  - name: child1\n  - name: child2\n    children:\n      - name: grandchild"
    doc = load(yaml_str, tree)
    assert doc.data["name"] == "root"
    assert len(doc.data["children"]) == 2
    assert doc.data["children"][1]["children"][0]["name"] == "grandchild"

def test_forward_ref_to_yaml():
    fref = ForwardRef()
    fref.set(Map({"a": Int()}))
    doc = as_document({"a": 10}, fref)
    assert "a: 10" in doc.as_yaml()

def test_forward_ref_multiple_unpack():
    fref1 = ForwardRef()
    fref2 = ForwardRef()
    fref1.set(fref2)
    fref2.set(Int())
    
    unpacked = unpack(fref1)
    assert isinstance(unpacked, type(Int()))
    
def test_forward_ref_unpack_unresolved():
    fref = ForwardRef()
    with pytest.raises(YAMLSerializationError):
        unpack(fref)
