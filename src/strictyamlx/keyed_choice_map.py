from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from strictyaml import Validator
from strictyaml.validators import MapValidator
from strictyaml.ruamel.comments import CommentedMap
from strictyaml.scalar import Str
from strictyaml.exceptions import YAMLSerializationError


class KeyedChoiceMap(MapValidator):
    def __init__(
        self,
        choices: list[tuple[str, Validator]],
        minimum_keys: int | None = 1,
        maximum_keys: int | None = 1,
    ):
        assert isinstance(choices, list), "choices must be a list of (str, Validator) tuples"
        if len(choices) == 0:
            raise AssertionError("choices must be non-empty")

        self._choice_keys: list[str] = []
        self._choice_key_set: set[str] = set[str]()
        self._validator: dict[str, Validator] = {}

        for key, validator in choices:
            assert isinstance(key, str), "choice key must be a str"
            assert isinstance(validator, Validator), "choice validator must be a strictyaml Validator"
            if key in self._choice_key_set:
                raise AssertionError(f"duplicate choice key: {key!r}")
            self._choice_keys.append(key)
            self._choice_key_set.add(key)
            self._validator[key] = validator

        assert minimum_keys is None or isinstance(minimum_keys, int), "minimum_keys must be int or None"
        assert maximum_keys is None or isinstance(maximum_keys, int), "maximum_keys must be int or None"
        if minimum_keys is not None and minimum_keys < 0:
            raise AssertionError("minimum_keys must be >= 0")
        if maximum_keys is not None and maximum_keys < 0:
            raise AssertionError("maximum_keys must be >= 0")
        if (
            minimum_keys is not None
            and maximum_keys is not None
            and minimum_keys > maximum_keys
        ):
            raise AssertionError("minimum_keys must be <= maximum_keys")

        self._minimum_keys = minimum_keys
        self._maximum_keys = maximum_keys
        self._key_validator = Str()

    @property
    def key_validator(self):
        return self._key_validator

    @property
    def minimum_keys(self) -> int | None:
        return self._minimum_keys

    @property
    def maximum_keys(self) -> int | None:
        return self._maximum_keys

    @property
    def choice_keys(self) -> tuple[str, ...]:
        return tuple[str, ...](self._choice_keys)

    def _choice_key_count(self, keys: Iterable[str]) -> int:
        return sum(1 for k in keys if k in self._choice_key_set)

    def validate(self, chunk):
        items = chunk.expect_mapping()

        present_keys: list[str] = []

        for key_chunk, value_chunk in items:
            yaml_key = self._key_validator(key_chunk)
            key_chunk.process(yaml_key)
            strict_key = yaml_key.scalar

            if strict_key not in self._validator:
                key_chunk.expecting_but_found(
                    "while parsing a mapping",
                    "unexpected key not in schema '{0}'".format(str(strict_key)),
                )

            value_chunk.process(self._validator[strict_key](value_chunk))
            chunk.add_key_association(key_chunk.contents, yaml_key.data)
            present_keys.append(strict_key)

        choice_key_count = self._choice_key_count(present_keys)
        if self._minimum_keys is not None and choice_key_count < self._minimum_keys:
            chunk.expecting_but_found(
                "while parsing a mapping",
                "expected a minimum of {0} choice key{1}, found {2}.".format(
                    self._minimum_keys,
                    "s" if self._minimum_keys != 1 else "",
                    choice_key_count,
                ),
            )
        if self._maximum_keys is not None and choice_key_count > self._maximum_keys:
            chunk.expecting_but_found(
                "while parsing a mapping",
                "expected a maximum of {0} choice key{1}, found {2}.".format(
                    self._maximum_keys,
                    "s" if self._maximum_keys != 1 else "",
                    choice_key_count,
                ),
            )

    def to_yaml(self, data):
        self._should_be_mapping(data)

        present_keys = list[Any](data.keys())
        for key in present_keys:
            if key not in self._validator:
                raise YAMLSerializationError(
                    "Unexpected key not in schema '{0}'".format(str(key))
                )

        choice_key_count = self._choice_key_count(present_keys)
        if self._minimum_keys is not None and choice_key_count < self._minimum_keys:
            raise YAMLSerializationError(
                "Expected a minimum of {0} choice key{1}, found {2}.".format(
                    self._minimum_keys,
                    "s" if self._minimum_keys != 1 else "",
                    choice_key_count,
                )
            )
        if self._maximum_keys is not None and choice_key_count > self._maximum_keys:
            raise YAMLSerializationError(
                "Expected a maximum of {0} choice key{1}, found {2}.".format(
                    self._maximum_keys,
                    "s" if self._maximum_keys != 1 else "",
                    choice_key_count,
                )
            )

        return CommentedMap(
            [
                (key, self._validator[key].to_yaml(value))
                for key, value in data.items()
            ]
        )

    def __repr__(self):
        return "KeyedChoiceMap({0}, minimum_keys={1}, maximum_keys={2})".format(
            repr([(k, v) for k, v in self._validator.items()]),
            repr(self._minimum_keys),
            repr(self._maximum_keys),
        )

