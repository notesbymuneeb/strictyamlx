from strictyaml import Validator
from collections.abc import Callable


class Block:
    def __init__(
        self,
        when: Callable[..., bool],
        schema: Validator,
        constraints: list[Callable[..., bool]] | None = None,
    ):
        self.when = when
        self._validator = schema
        self.constraints = constraints


class Case(Block):
    def __init__(
        self,
        when: Callable[..., bool],
        schema: Validator,
        constraints: list[Callable[..., bool]] | None = None,
    ):
        super().__init__(when, schema, constraints)


# TODO: implement in DMap
class Overlay(Block):
    def __init__(
        self,
        when: Callable[..., bool],
        schema: Validator,
        constraints: list[Callable[..., bool]] | None = None,
    ):
        super().__init__(when, schema, constraints)
