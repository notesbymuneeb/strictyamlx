from strictyaml import Validator
from strictyaml.exceptions import YAMLSerializationError
from .control import Control
from .blocks import Block
from collections.abc import Callable
from .builder import ValidatorBuilder


class DMapValidator(Validator):
    pass


class DMap(DMapValidator):
    def __init__(
        self,
        control: Control,
        blocks: list[Block],
        constraints: list[Callable[..., bool]] | None = None,
    ):
        self.control = control
        self.blocks = blocks
        self.constraints = None
        if constraints:
            self.constraints = constraints
        self.validated = None

    @staticmethod
    def compile_when(when):
        if callable(when):
            return when
        return lambda raw, ctrl: bool(when)

    @staticmethod
    def compile_constraint(when):
        if callable(when):
            return when
        return lambda raw, ctrl, val: bool(when)

    def validate(self, chunk):
        self.control.validate(chunk)
        ctrl = self.control.validated.data
        raw = chunk.whole_document
        control_validator = self.control._validator
        true_case_block = None
        # TODO: what if the user doesn't really want a control validator and only selects based on raw
        for block in self.blocks:
            if DMap.compile_when(block.when)(raw, ctrl):
                if true_case_block is None:
                    true_case_block = block
                else:
                    raise YAMLSerializationError("Only one case can be true")

        if true_case_block is None:
            raise YAMLSerializationError("None of the cases were true")

        final_validator = ValidatorBuilder(
            control_validator, true_case_block._validator, self.control.source
        ).validator

        self.validated = final_validator(chunk)
        val = self.validated.data

        if self.constraints:
            for constraint in self.constraints:
                if not DMap.compile_constraint(constraint)(raw, ctrl, val):
                    raise YAMLSerializationError("Constraints not fulfilled")

        if true_case_block.constraints:
            for constraint in true_case_block.constraints:
                if not DMap.compile_constraint(constraint)(raw, ctrl, val):
                    raise YAMLSerializationError("Constraints not fulfilled")
