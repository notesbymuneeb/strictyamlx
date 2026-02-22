from strictyaml import Validator
from strictyaml.validators import MapValidator
from strictyaml.exceptions import YAMLSerializationError, InvalidValidatorError
from .control import Control
from .blocks import Block, Case, Overlay
from collections.abc import Callable
from .builder import ValidatorBuilder
from strictyaml.yamllocation import YAMLChunk


class DMap(MapValidator):
    def __init__(
        self,
        control: Control,
        blocks: list[Block],
        constraints: list[Callable[..., bool]] | None = None,
    ):
        assert isinstance(control, Control), "control must be of type Control"
        assert isinstance(blocks, list), "blocks must be a list of Block"
        for block in blocks:
            assert isinstance(block, Block), "all blocks must be of type Block"
            
        if constraints is not None:
            assert isinstance(constraints, list), "constraints must be a list of Callable"
            for constraint in constraints:
                assert callable(constraint), "every constraint must be callable"

        self.control = control
        self.blocks = blocks
        self.constraints = constraints

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

    @staticmethod
    def normalize_raw(raw):
        if isinstance(raw, dict):
            return {key: DMap.normalize_raw(value) for key, value in raw.items()}
        if isinstance(raw, list):
            return [DMap.normalize_raw(value) for value in raw]
        if isinstance(raw, str):
            lowered = raw.lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
        return raw

    def validate(self, chunk):
        chunk.expect_mapping()
        self.control.validate(chunk)
        ctrl = self.control.validated.data
        raw = DMap.normalize_raw(chunk.whole_document)
        control_validator = self.control._validator
        true_case_block = None
        true_overlay_blocks = []
        # TODO: what if the user doesn't really want a control validator and only selects based on raw
        for block in self.blocks:
            if not DMap.compile_when(block.when)(raw, ctrl):
                continue
            if isinstance(block, Case):
                if true_case_block is None:
                    true_case_block = block
                else:
                    chunk.expecting_but_found("when evaluating DMap blocks", "multiple cases were true")
            elif isinstance(block, Overlay):
                true_overlay_blocks.append(block)
            else:
                chunk.expecting_but_found(
                    "when evaluating DMap blocks",
                    "unknown block type; expected Case or Overlay",
                )

        if true_case_block is None:
            chunk.expecting_but_found("when evaluating DMap blocks", "none of the cases were true")

        final_validator = ValidatorBuilder(
            control_validator,
            true_case_block._validator,
            [overlay._validator for overlay in true_overlay_blocks],
            self.control.source,
        ).validator

        self.validated = final_validator(chunk)
        val = self.validated.data

        if self.constraints:
            for constraint in self.constraints:
                if not DMap.compile_constraint(constraint)(raw, ctrl, val):
                    chunk.expecting_but_found("when evaluating DMap constraints", "constraints not fulfilled")
        if true_case_block.constraints:
            for constraint in true_case_block.constraints:
                if not DMap.compile_constraint(constraint)(raw, ctrl, val):
                    chunk.expecting_but_found("when evaluating DMap case constraints", "constraints not fulfilled")
        for overlay in true_overlay_blocks:
            if overlay.constraints:
                for constraint in overlay.constraints:
                    if not DMap.compile_constraint(constraint)(raw, ctrl, val):
                        chunk.expecting_but_found(
                            "when evaluating DMap overlay constraints",
                            "constraints not fulfilled",
                        )

    def to_yaml(self, data):
        self._should_be_mapping(data)
        self.control.validate(YAMLChunk(data))
        ctrl = self.control.validated.data
        raw = DMap.normalize_raw(data)

        true_case_block = None
        true_overlay_blocks = []
        for block in self.blocks:
            if not DMap.compile_when(block.when)(raw, ctrl):
                continue
            if isinstance(block, Case):
                if true_case_block is None:
                    true_case_block = block
                else:
                    raise YAMLSerializationError("Multiple DMap cases evaluated to true")
            elif isinstance(block, Overlay):
                true_overlay_blocks.append(block)
            else:
                raise YAMLSerializationError("Unknown DMap block type; expected Case or Overlay")

        if true_case_block is None:
            raise YAMLSerializationError("None of the DMap cases successfully serialized the data")

        final_validator = ValidatorBuilder(
            self.control._validator,
            true_case_block._validator,
            [overlay._validator for overlay in true_overlay_blocks],
            self.control.source,
        ).validator
        return final_validator.to_yaml(data)

    def __repr__(self):
        return "DMap({0}, {1}{2})".format(
            repr(self.control),
            repr(self.blocks),
            ", constraints={0}".format(repr(self.constraints)) if self.constraints else "",
        )
