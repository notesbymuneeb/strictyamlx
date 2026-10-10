from strictyaml import Validator
from strictyaml.validators import MapValidator
from strictyaml.yamllocation import YAMLChunk
from functools import reduce
from copy import copy
from strictyaml.ruamel.comments import CommentedMap, CommentedSeq
from strictyaml.exceptions import YAMLSerializationError


def _wrap_strict(pointer, node):
    """Wrap ``node`` so that ``pointer.get(wrapped, strictdoc=True) == node``.

    A ``YAMLChunk`` uses a single pointer to index both its ruamel and strict
    documents. To validate a projected (filtered) subdocument while keeping the
    original document for locations, we need a strict document whose structure
    mirrors the pointer path down to ``node``.
    """
    result = node
    for index_type, index in reversed(pointer._indices):
        if index_type == "val":
            result = CommentedMap({index[0]: result})
        elif index_type == "index":
            seq = CommentedSeq()
            for _ in range(index):
                seq.append(None)
            seq.append(result)
            result = seq
        elif index_type == "key":
            result = CommentedMap({index[0]: result})
        else:  # pragma: no cover - textslice is not used for control nodes
            result = CommentedMap({})
    return result


class _FilteredChunk(YAMLChunk):
    """A mapping view that only exposes the keys present in a filtered
    (projected) strict document, while resolving contents and source locations
    against the *original* document.

    This lets ``Control`` validate a subset of keys without copying the document,
    so nested validators (including ``DMap``) receive the original sub-chunks and
    keep correct line/column information.
    """

    def _select(self, pointer):
        return _FilteredChunk(
            self._ruamelparsed,
            pointer=pointer,
            label=self._label,
            strictparsed=self._strictparsed,
            key_association=copy(self._key_association),
        )

    def expect_mapping(self):
        if not self.is_mapping():
            self.expecting_but_found(
                "when expecting a mapping", "found {0}".format(self.found())
            )
        result = []
        for strict_key in self.strictparsed().keys():
            regular_key = self._key_association.get(strict_key, strict_key)
            result.append(
                (self.key(regular_key, strict_key), self.val(strict_key))
            )
        return result


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

        def to_marked_up(value):
            if isinstance(value, CommentedMap):
                return CommentedMap({k: to_marked_up(v) for k, v in value.items()})
            if isinstance(value, dict):
                return CommentedMap({k: to_marked_up(v) for k, v in value.items()})
            if isinstance(value, CommentedSeq):
                return CommentedSeq([to_marked_up(v) for v in value])
            if isinstance(value, list):
                return CommentedSeq([to_marked_up(v) for v in value])
            return value

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
                is_mapping_with_key_schema = (
                    hasattr(val, "_validator_dict")
                    or (hasattr(val, "_validator") and isinstance(val._validator, dict))
                )
                if isinstance(val, MapValidator) and is_mapping_with_key_schema:
                    projected_chunk[key] = self.projection(
                        chunk[key], val
                    )
                else:
                    projected_chunk[key] = to_marked_up(chunk[key])
                    
        return CommentedMap(projected_chunk)

    def _control_pointer(self, chunk):
        if not self.source or self.source == "":
            return chunk.pointer
        if isinstance(self.source, str):
            regular = chunk.ruamelindex(self.source) if chunk.is_mapping() else self.source
            return chunk.pointer.val(regular, self.source)
        pointer = chunk.pointer
        for key in self.source:
            regular = chunk.ruamelindex(key) if chunk.is_mapping() else key
            pointer = pointer.val(regular, key)
        return pointer

    def validate(self, chunk):
        from .utils import unpack

        if self.source and self.source != "":
            if isinstance(self.source, str):
                chunk_pointer = chunk.contents[self.source]
            elif isinstance(self.source, tuple):
                chunk_pointer = reduce(
                    lambda d, key: d[key], self.source, chunk.contents
                )
        else:
            chunk_pointer = chunk.contents
        unpacked_validator = unpack(self._validator)
        is_mapping_validator = (
            hasattr(unpacked_validator, "_validator_dict")
            or (
                hasattr(unpacked_validator, "_validator")
                and isinstance(unpacked_validator._validator, dict)
            )
        )
        if is_mapping_validator:
            projected = self.projection(chunk_pointer, self._validator)
            if isinstance(chunk_pointer, CommentedMap):
                pointer = self._control_pointer(chunk)
                source_chunk = _FilteredChunk(
                    chunk._ruamelparsed,
                    pointer=pointer,
                    label=chunk.label,
                    strictparsed=_wrap_strict(pointer, projected),
                    key_association=copy(chunk.key_association),
                )
            else:
                source_chunk = YAMLChunk(unpacked_validator.to_yaml(projected))
        else:
            source_chunk = YAMLChunk(chunk_pointer)
        self.validated = self._validator(source_chunk)
