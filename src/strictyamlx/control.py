from strictyaml.validators import Validator, MapValidator
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

    def projection(self, chunk, validator):
        projected_chunk = {}
        for key, val in validator._validator_dict.items():
            if key in chunk:
                if isinstance(val, MapValidator):
                    projected_chunk[key] = self.projection(
                        chunk[key], validator._validator[key]
                    )
                else:
                    projected_chunk[key] = chunk[key]
            else:
                raise YAMLSerializationError(f"Control key: {key} not present in chunk")
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
