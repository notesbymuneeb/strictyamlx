import pytest
from strictyaml.exceptions import InvalidValidatorError, YAMLSerializationError, YAMLValidationError
from strictyaml.yamllocation import YAMLChunk
from strictyaml.parser import generic_load

from strictyamlx import (
    Control,
    Enum,
    Int,
    Map,
    Seq,
    Str,
    ensure_validator_dict,
    load,
)

def test_control_init_valid():
    ctrl = Control(Map({"type": Str()}))
    assert ctrl._validator is not None

def test_control_init_invalid():
    with pytest.raises(AssertionError, match="validator must be of type Validator"):
        Control("schema")

def test_control_projection_invalid_validator():
    ctrl = Control(Str())
    with pytest.raises(InvalidValidatorError, match="Control validator must be a Map"):
        ctrl.projection({"a": "b"}, Str())

def test_control_validation_root():
    ctrl = Control(Map({"kind": Str()}))
    chunk = YAMLChunk(generic_load("kind: test\nother: 123", Map({"kind": Str(), "other": Int()}))._chunk.whole_document)
    ctrl.validate(chunk)
    assert ctrl.validated.data == {"kind": "test"}


def test_control_validation_missing_key():
    ctrl = Control(Map({"kind": Str()}))
    chunk = YAMLChunk(generic_load("other: 123", Map({"other": Int()}))._chunk.whole_document)
    
    with pytest.raises(YAMLValidationError, match="required key\\(s\\) 'kind' not found"):
        ctrl.validate(chunk)

def test_control_source_string():
    ctrl = Control(Map({"kind": Str()}), source="meta")
    # This specifically parses a subset. Testing via projection internally.
    pass # To fully test source="meta", it is best done in DMap or with exact mocked chunks

def test_control_repr():
    ctrl = Control(Map({"kind": Str()}))
    assert "Control(Map({'kind': Str()}))" == repr(ctrl)

def test_control_repr_with_source():
    ctrl = Control(Map({"kind": Str()}), source="meta")
    assert "Control(Map({'kind': Str()}), source='meta')" == repr(ctrl)

def test_control_source_tuple():
    ctrl = Control(Map({"kind": Str()}), source=("meta", "inner"))
    assert "source=('meta', 'inner')" in repr(ctrl)

def test_control_ensure_validator_dict_scalar():
    val = ensure_validator_dict(Str())
    assert isinstance(val, type(Str()))


def test_control_scalar_with_tuple_source_validates():
    ctrl = Control(Str(), source=("meta", "mode"))
    chunk = YAMLChunk({"meta": {"mode": "advanced"}})
    ctrl.validate(chunk)
    assert ctrl.validated.data == "advanced"


def test_control_scalar_with_tuple_source_rejects_invalid_value():
    ctrl = Control(Enum(["simple", "advanced"]), source=("meta", "mode"))
    chunk = YAMLChunk({"meta": {"mode": "unsupported"}})
    with pytest.raises(YAMLValidationError):
        ctrl.validate(chunk)


def test_control_scalar_with_string_source_validates():
    ctrl = Control(Str(), source="mode")
    chunk = YAMLChunk({"mode": "simple"})
    ctrl.validate(chunk)
    assert ctrl.validated.data == "simple"
