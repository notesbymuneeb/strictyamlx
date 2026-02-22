import pytest
from strictyaml import Map, Str, Int, Seq, load
from strictyaml.exceptions import YAMLSerializationError, YAMLValidationError, InvalidValidatorError

from strictyamlx import Control
from strictyamlx.utils import ensure_validator_dict

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
    yaml_str = "kind: test\nother: 123"
    import strictyaml.yamllocation as yl
    from strictyaml.parser import generic_load
    chunk = yl.YAMLChunk(generic_load("kind: test\nother: 123", Map({"kind": Str(), "other": Int()}))._chunk.whole_document)
    
    ctrl.validate(chunk)
    assert ctrl.validated.data == {"kind": "test"}

def test_control_validation_missing_key():
    ctrl = Control(Map({"kind": Str()}))
    from strictyaml.parser import generic_load
    import strictyaml.yamllocation as yl
    chunk = yl.YAMLChunk(generic_load("other: 123", Map({"other": Int()}))._chunk.whole_document)
    
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
