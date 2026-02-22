from .forwardref import ForwardRef
from strictyaml import Map, MapCombined, MapPattern
from strictyaml.validators import Validator
from strictyaml.exceptions import YAMLSerializationError

def unpack(validator):
    while isinstance(validator, ForwardRef):
        if validator._validator is None:
            raise YAMLSerializationError("ForwardRef was used before it was set")
        validator = validator._validator
    return validator

def ensure_validator_dict(validator):
    validator = unpack(validator)
    if isinstance(validator, MapPattern):
        return MapCombined({}, validator._key_validator, validator._value_validator)
    return validator
