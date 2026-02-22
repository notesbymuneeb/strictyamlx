from strictyaml import Validator
from collections.abc import Callable


class Block:
    def __init__(
        self,
        when: Callable[..., bool],
        schema: Validator,
        constraints: list[Callable[..., bool]] | None = None,
    ):
        assert isinstance(schema, Validator), "schema must be of type Validator"
        self.when = when
        self._validator = schema
        self.constraints = constraints

    def __repr__(self):
        return "{0}(when={1}, schema={2}{3})".format(
            self.__class__.__name__,
            repr(self.when),
            repr(self._validator),
            ", constraints={0}".format(repr(self.constraints)) if self.constraints else "",
        )


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
