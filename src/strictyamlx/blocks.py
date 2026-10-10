import copy
import inspect
from functools import partial
from typing import (
    TYPE_CHECKING,
    cast,
)

from strictyaml import Validator
from strictyaml.compound import (
    Optional,
    Map,
)
from strictyaml.exceptions import YAMLSerializationError
from strictyaml.parser import as_document

from .keyed_choice_map import KeyedChoiceMap

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any
    from collections.abc import Callable

    from strictyamlx.control import Control

    # drop py310 then remove this import block
    try:
        # py311+
        from typing import Self
    except ImportError:
        # py310 (already EOL)
        from typing_extensions import Self

__all__ = ("Case", "Overlay")


class Block:
    def __init__(
        self,
        when: "Callable[..., bool]",
        schema: Validator,
        constraints: "list[Callable[..., bool]] | None" = None,
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
        when: "Callable[..., bool]",
        schema: Validator,
        constraints: "list[Callable[..., bool]] | None" = None,
    ):
        super().__init__(when, schema, constraints)


def _cb_choice(
    validator_choices: Validator,
    raw: "dict[str, Any]",
    ctrl: "dict[str, Any]",
    validated: "dict[str, Any]",
) -> bool:
    """raw --> :py:class:`~strictyamlx.KeyedChoiceMap` --> chosen dict. From
    validated, remove non-chosen items.

    :type validator_choices: strictyamlx.keyed_choice_map.KeyedChoiceMap
    :param raw:

       As process each DMap block, param raw is updated with respective
       Case/Overlay items. Only interact/modify with current Overlay items
       (this Overlay fragment).

    :type raw: dict[str, typing.Any]
    :param ctrl: :py:class:`~strictyamlx.control.Control` dict ignored
    :type ctrl: dict[str, typing.Any]
    :param validated:

       Unmodified this would contain all KeyedChoiceMap choices.
       Only want the one choice contained within param, raw.
       The other choices' will be removed.

    :type validated: dict[str, typing.Any]
    :returns:

       False -- constraint rejects the Overlay
       True  -- excess non-chosen item(s) removed

    :rtype: bool
    """
    ret = True
    if isinstance(validator_choices, KeyedChoiceMap):  # pragma: no branch
        # raw items that are sx.KeyedChoiceMap choices
        t_validator_keys = tuple(validator_choices._validator.keys())
        d_choices = {k: v for k, v in raw.items() if k in t_validator_keys}

        try:
            # validate d_choices with schema sx.KeyedChoiceMap
            yaml_obj = as_document(d_choices, schema=validator_choices)
        except YAMLSerializationError:
            # raw items contain no matches or more than one match
            ret = False
        else:
            d_chosen = cast("dict[str, Any]", yaml_obj.data)
            # From `validated`, remove items that bleed thru, but shouldn't be there
            remove_these = []
            for k in validated.keys():
                if k not in d_chosen:  # pragma: no branch
                    remove_these.append(k)
            for k in remove_these:  # pragma: no branch
                validated.pop(k)

    return ret


class Overlay(Block):
    def __init__(
        self,
        when: "Callable[..., bool]",
        schema: Validator,
        constraints: "list[Callable[..., bool]] | None" = None,
    ):
        super().__init__(when, schema, constraints)

    @classmethod
    def choice(
        cls,
        keyed_choice_map: KeyedChoiceMap,
        when: "bool | Callable[[dict[str, Any], Control], bool]" = True,
        constraints: "list[Callable[[dict[str, Any], Control, dict[str, Any]], None]]" = [],
    ) -> "Self":
        """:py:class:`KeyedChoiceMap <strictyamlx.keyed_choice_map.KeyedChoiceMap>`
        support for :py:class:`~strictyamlx.blocks.Overlay`.

        Overlay treats
        :py:class:`~strictyamlx.keyed_choice_map.KeyedChoiceMap` as a mere
        :py:class:`s.Map <strictyaml.compound.Map>`. To get the intended
        behavior, the schema is feed a promiscuous dummy
        :py:class:`s.Map <strictyaml.compound.Map>`. Within the constraint,
        undesirable choices are filtered out.

        :type keyed_choice_map: strictyamlx.keyed_choice_map.KeyedChoiceMap
        :param when:

           To control whether or not the :py:class:`~strictyamlx.blocks.Overlay`
           is applied, provide a :py:class:`collections.abc.Callable` with
           params are: raw, ctrl.
           Default True; always apply the :py:class:`~strictyamlx.blocks.Overlay`.

        :type when: typing.Literal[True] | collections.abc.Callable[[dict[str, typing.Any], strictyamlx.control.Control], bool]
        :param constraints:

           Feed in additional constraints. The Callable params are: raw, ctrl,
           and validated.

        :type constraints: list[collections.abc.Callable[[dict[str, typing.Any], strictyamlx.control.Control, dict[str, typing.Any]], None]]
        :rtype: strictyamlx.blocks.Overlay
        """

        if not isinstance(keyed_choice_map, KeyedChoiceMap):  # pragma: no branch
            msg_warn_0 = (
                "param keyed_choice_map, expected KeyedChoiceMap got "
                f"{keyed_choice_map!r}"
            )
            raise TypeError(msg_warn_0)

        when_ng = False
        if when is not None and (isinstance(when, bool) or inspect.isclass(when)):
            if isinstance(when, bool) and not when:  # pragma: no branch
                # False
                when_ng = True
        else:
            # unsupported type
            when_ng = True
        if when_ng:  # pragma: no branch
            msg_warn_1 = f"param when, expected True or a Callable got {when!r}"
            raise TypeError(msg_warn_1)
        when_apply = when

        if not isinstance(constraints, list):  # pragma: no branch
            msg_warn_2 = (
                f"param constaints, expected list got {constraints!r}"
            )
            raise TypeError(msg_warn_2)

        # Without the copy, the list would be modified in-place.
        # list will be consumed, so work with a copy.
        my_constaints = copy.deepcopy(constraints)
        cb_constraint = partial(_cb_choice, keyed_choice_map)
        my_constaints.append(cb_constraint)

        # keyed_choice_map --> opportunistic s.Map
        pending_choice = Map(
            {
                Optional(str_k): validator_v
                for str_k, validator_v in keyed_choice_map._validator.items()
            },
        )

        # get_locals_dynamic inspects runtime locals, without frame stack
        # inspection, but only if single return statement.
        # logging_strict.tech_niques.context_locals.get_locals_dynamic friendly
        # Person A: this is the way
        # Person B: this is the way
        ret = cls(
            when=when_apply,
            schema=pending_choice,
            constraints=my_constaints,
        )
        return ret
