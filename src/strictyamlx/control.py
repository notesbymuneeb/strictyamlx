from strictyaml import Validator
from strictyaml.validators import MapValidator
from strictyaml.yamllocation import YAMLChunk
from functools import reduce
from strictyaml.ruamel.comments import CommentedMap
from strictyaml.exceptions import YAMLSerializationError


class Control:
    def __init__(self, validator: Validator, source: tuple[str] | str | None = None):
        self._validator = validator
        self.source = source
        self.validated = None

        assert isinstance(
            self._validator, Validator
        ), "validator must be of type Validator"

    def __repr__(self):
        return "Control({0}{1})".format(
            repr(self._validator),
            ", source={0}".format(repr(self.source)) if self.source else "",
        )

    def projection(self, chunk, validator):
        from .utils import unpack
        validator = unpack(validator)
        projected_chunk = {}
        
        if hasattr(validator, '_validator_dict'):
            keys = validator._validator_dict.items()
        elif hasattr(validator, '_validator') and isinstance(validator._validator, dict):
            # for when _validator_dict isn't explicitly built but _validator is a dict
            keys = [
                (k.key if hasattr(k, 'key') else k, v)
                for k, v in validator._validator.items()
            ]
        else:
            from strictyaml.exceptions import InvalidValidatorError
            raise InvalidValidatorError("Control validator must be a Map with specific keys")

        for key, val in keys:
            val = unpack(val)
            if key in chunk:
                if isinstance(val, MapValidator):
                    projected_chunk[key] = self.projection(
                        chunk[key], val
                    )
                else:
                    projected_chunk[key] = chunk[key]
                    
        return CommentedMap(projected_chunk)

    def validate(self, chunk):
        if self.source and self.source != "":
            if isinstance(self.source, str):
                chunk_pointer = chunk.contents[self.source]
            elif isinstance(self.source, tuple):
                chunk_pointer = reduce(
                    lambda d, key: d[key], self.source, chunk.contents
                )
        else:
            chunk_pointer = chunk.contents
        source_chunk = YAMLChunk(self.projection(chunk_pointer, self._validator))
        self.validated = self._validator(source_chunk)
