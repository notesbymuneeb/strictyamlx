from strictyaml import Validator
from strictyaml.validators import MapValidator
from strictyaml.exceptions import YAMLSerializationError, InvalidValidatorError
from strictyaml import Map
from .control import Control
from .blocks import Block, Case, Overlay
from collections.abc import Callable
from .builder import ValidatorBuilder
from strictyaml.yamllocation import YAMLChunk
import inspect
import threading


class DMap(MapValidator):
    _local = threading.local()

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

    def __call__(self, chunk):
        self.validate(chunk)
        return self.validated

    @classmethod
    def get_stack(cls):
        if not hasattr(cls._local, 'stack'):
            cls._local.stack = []
        return cls._local.stack

    @classmethod
    def get_constraint_state(cls):
        if not hasattr(cls._local, 'constraint_state'):
            cls._local.constraint_state = {
                "active_validations": 0,
                "pending_constraints": [],
            }
        return cls._local.constraint_state

    @classmethod
    def reset_constraint_state(cls):
        cls._local.constraint_state = {
            "active_validations": 0,
            "pending_constraints": [],
        }

    @staticmethod
    def _callback_shape(func):
        try:
            sig = inspect.signature(func)
        except (TypeError, ValueError):
            # Fall back to legacy behavior when a callable cannot be introspected.
            return 2, False, False, False
        params = list(sig.parameters.values())
        positional_count = sum(
            1
            for p in params
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        )
        has_var_positional = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
        has_var_keyword = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
        has_named_parents = any(p.name == "parents" for p in params)
        return positional_count, has_var_positional, has_var_keyword, has_named_parents

    @staticmethod
    def compile_when(when):
        if callable(when):
            positional_count, has_var_positional, has_var_keyword, has_named_parents = DMap._callback_shape(when)
            if positional_count >= 3 or has_var_positional:
                return lambda raw, ctrl, parents=None: when(raw, ctrl, parents)
            if has_named_parents or has_var_keyword:
                return lambda raw, ctrl, parents=None: when(raw, ctrl, parents=parents)
            return lambda raw, ctrl, parents=None: when(raw, ctrl)
        return lambda raw, ctrl, parents=None: bool(when)

    @staticmethod
    def compile_constraint(when):
        if callable(when):
            positional_count, has_var_positional, has_var_keyword, has_named_parents = DMap._callback_shape(when)
            if positional_count >= 4 or has_var_positional:
                return lambda raw, ctrl, val, parents=None: when(raw, ctrl, val, parents)
            if has_named_parents or has_var_keyword:
                return lambda raw, ctrl, val, parents=None: when(raw, ctrl, val, parents=parents)
            return lambda raw, ctrl, val, parents=None: when(raw, ctrl, val)
        return lambda raw, ctrl, val, parents=None: bool(when)

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
        constraint_state = DMap.get_constraint_state()
        is_root_validation = constraint_state["active_validations"] == 0
        constraint_state["active_validations"] += 1
        validation_succeeded = False
        stack = DMap.get_stack()
        chunk.expect_mapping()
        raw = DMap.normalize_raw(chunk.whole_document)
        parents = list(stack)
        when_parents = [{"raw": parent["raw"], "ctrl": parent["ctrl"]} for parent in parents]

        # Push a provisional frame before control validation so control-nested DMaps
        # can still inspect parent raw/context (ctrl may be None until resolved).
        frame = {"ctrl": None, "raw": raw, "val": None, "parents": parents}
        stack.append(frame)
        try:
            self.control.validate(chunk)
            ctrl = self.control.validated.data
            frame["ctrl"] = ctrl
        except Exception:
            stack.pop()
            constraint_state["active_validations"] -= 1
            if is_root_validation:
                DMap.reset_constraint_state()
            raise

        control_validator = self.control._validator
        true_case_block = None
        true_overlay_blocks = []

        try:
            # TODO: what if the user doesn't really want a control validator and only selects based on raw
            for block in self.blocks:
                if not DMap.compile_when(block.when)(raw, ctrl, parents=when_parents):
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
    
            final_validator = ValidatorBuilder(
                control_validator,
                true_case_block._validator if true_case_block is not None else Map({}),
                [overlay._validator for overlay in true_overlay_blocks],
                self.control.source,
            ).validator
    
            self.validated = final_validator(chunk)
            val = self.validated.data
            frame["val"] = val

            if self.constraints:
                for constraint in self.constraints:
                    constraint_state["pending_constraints"].append(
                        {
                            "constraint": constraint,
                            "frame": frame,
                            "chunk": chunk,
                            "where": "when evaluating DMap constraints",
                            "depth": len(frame["parents"]),
                        }
                    )
            if true_case_block and true_case_block.constraints:
                for constraint in true_case_block.constraints:
                    constraint_state["pending_constraints"].append(
                        {
                            "constraint": constraint,
                            "frame": frame,
                            "chunk": chunk,
                            "where": "when evaluating DMap case constraints",
                            "depth": len(frame["parents"]),
                        }
                    )
            for overlay in true_overlay_blocks:
                if overlay.constraints:
                    for constraint in overlay.constraints:
                        constraint_state["pending_constraints"].append(
                            {
                                "constraint": constraint,
                                "frame": frame,
                                "chunk": chunk,
                                "where": "when evaluating DMap overlay constraints",
                                "depth": len(frame["parents"]),
                            }
                        )
            validation_succeeded = True
        finally:
            stack.pop()
            constraint_state["active_validations"] -= 1

        if is_root_validation and validation_succeeded:
            try:
                for pending in sorted(
                    constraint_state["pending_constraints"],
                    key=lambda item: item["depth"],
                ):
                    parent_frames = pending["frame"]["parents"]
                    parent_context = [
                        {
                            "raw": parent["raw"],
                            "ctrl": parent["ctrl"],
                            "val": parent["val"],
                        }
                        for parent in parent_frames
                    ]
                    if not DMap.compile_constraint(pending["constraint"])(
                        pending["frame"]["raw"],
                        pending["frame"]["ctrl"],
                        pending["frame"]["val"],
                        parents=parent_context,
                    ):
                        pending["chunk"].expecting_but_found(
                            pending["where"],
                            "constraints not fulfilled",
                        )
            finally:
                DMap.reset_constraint_state()
        elif is_root_validation:
            DMap.reset_constraint_state()

    def to_yaml(self, data):
        self._should_be_mapping(data)
        stack = DMap.get_stack()
        raw = DMap.normalize_raw(data)
        parents = list(stack)
        when_parents = [{"raw": parent["raw"], "ctrl": parent["ctrl"]} for parent in parents]
        frame = {"ctrl": None, "raw": raw, "val": None, "parents": parents}
        stack.append(frame)
        try:
            self.control.validate(YAMLChunk(data))
            ctrl = self.control.validated.data
            frame["ctrl"] = ctrl
        except Exception:
            stack.pop()
            raise

        try:
            true_case_block = None
            true_overlay_blocks = []
            for block in self.blocks:
                if not DMap.compile_when(block.when)(raw, ctrl, parents=when_parents):
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
    
            final_validator = ValidatorBuilder(
                self.control._validator,
                true_case_block._validator if true_case_block is not None else Map({}),
                [overlay._validator for overlay in true_overlay_blocks],
                self.control.source,
            ).validator
            return final_validator.to_yaml(data)
        finally:
            stack.pop()

    def __repr__(self):
        return "DMap({0}, {1}{2})".format(
            repr(self.control),
            repr(self.blocks),
            ", constraints={0}".format(repr(self.constraints)) if self.constraints else "",
        )
