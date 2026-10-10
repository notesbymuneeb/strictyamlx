from strictyaml import Validator
from strictyaml.validators import MapValidator
from strictyaml import Map, MapCombined
from .utils import unpack, ensure_validator_dict


class ValidatorBuilder:
    def __init__(
        self,
        control_validator: Validator,
        case_validator: Validator,
        overlay_validators: list[Validator] | None = None,
        control_source: tuple[str] | str | None = None,
    ):
        self.control_source = control_source
        self.control_validator = control_validator
        self.case_validator = case_validator
        self.overlay_validators = overlay_validators or []
        self.validator = self._build()

    @staticmethod
    def _normalize_key(key):
        return key.key if hasattr(key, "key") else key

    def _rebuild_like(self, validator, new_dict):
        from .keyed_choice_map import KeyedChoiceMap

        if isinstance(validator, KeyedChoiceMap):
            choice_keys = list(validator.choice_keys)
            choices = [(k, new_dict[k]) for k in choice_keys if k in new_dict]
            rebuilt = KeyedChoiceMap(
                choices=choices,
                minimum_keys=validator.minimum_keys,
                maximum_keys=validator.maximum_keys,
            )
            for k, v in new_dict.items():
                if k not in rebuilt._validator:
                    rebuilt._validator[k] = v
            return rebuilt

        if isinstance(validator, MapCombined):
            return MapCombined(
                new_dict,
                validator.key_validator,
                getattr(validator, "_value_validator", None),
            )
        return Map(new_dict)

    def merge_recursive(self, control_validator, case_validator):
        """Return a new validator with ``control_validator`` keys merged into
        ``case_validator`` without mutating either input. Existing case keys win;
        only keys missing from the case are added. Nested plain ``Map`` values are
        merged recursively; all other validators (including nested ``DMap``) are
        shared by reference.
        """
        control_validator = unpack(control_validator)
        case_validator = ensure_validator_dict(case_validator)
        if not (
            hasattr(control_validator, "_validator")
            and isinstance(control_validator._validator, dict)
        ):
            return case_validator
        if not (
            hasattr(case_validator, "_validator")
            and isinstance(case_validator._validator, dict)
        ):
            return case_validator

        case_dict = case_validator._validator
        new_dict = dict(case_dict)
        case_lookup = {self._normalize_key(k): k for k in case_dict}

        for key, val in control_validator._validator.items():
            normalized_key = self._normalize_key(key)
            case_key = case_lookup.get(normalized_key)

            val_unpacked = unpack(val)
            is_nested_mapping_with_key_schema = (
                isinstance(val_unpacked, MapValidator)
                and hasattr(val_unpacked, "_validator_dict")
            )
            if is_nested_mapping_with_key_schema:
                if case_key is None:
                    case_key = key
                    case_lookup[normalized_key] = key
                    new_dict[case_key] = Map({})

                target = ensure_validator_dict(new_dict[case_key])
                if hasattr(target, "_validator") and isinstance(target._validator, dict):
                    new_dict[case_key] = self.merge_recursive(val, target)
                else:
                    new_dict[case_key] = target
            else:
                if case_key is None:
                    case_lookup[normalized_key] = key
                    new_dict[key] = val

        return self._rebuild_like(case_validator, new_dict)

    def rebuild_validator_recursive(self, validator):
        validator = ensure_validator_dict(validator)
        if not hasattr(validator, "_validator") or not isinstance(validator._validator, dict):
            return validator

        new_dict = {}
        for key, val in validator._validator.items():
            val_unpacked = ensure_validator_dict(val)
            if hasattr(val_unpacked, "_validator") and isinstance(val_unpacked._validator, dict):
                new_dict[key] = self.rebuild_validator_recursive(val_unpacked)
            else:
                new_dict[key] = val_unpacked

        return self._rebuild_like(validator, new_dict)

    def _build(self):
        control_validator = unpack(self.control_validator)
        if self.control_source:
            if isinstance(self.control_source, str):
                self.control_source = [self.control_source]
            for key in reversed(self.control_source):
                map_layer = Map({})
                map_layer._validator[key] = control_validator
                control_validator = map_layer

        case_validator = ensure_validator_dict(self.case_validator)
        overlay_validators = [
            ensure_validator_dict(overlay_validator)
            for overlay_validator in self.overlay_validators
        ]

        from .control import Control
        from .dmap import DMap

        if (
            isinstance(case_validator, DMap)
            and hasattr(case_validator.control, "_validator")
        ):
            nested_validator = ensure_validator_dict(case_validator.control._validator)
            for overlay_validator in overlay_validators:
                nested_validator = self.merge_recursive(overlay_validator, nested_validator)
            nested_validator = self.merge_recursive(control_validator, nested_validator)
            new_control = Control(
                self.rebuild_validator_recursive(nested_validator),
                source=case_validator.control.source,
            )
            return DMap(new_control, list(case_validator.blocks), case_validator.constraints)

        result_validator = case_validator
        for overlay_validator in overlay_validators:
            result_validator = self.merge_recursive(overlay_validator, result_validator)
        result_validator = self.merge_recursive(control_validator, result_validator)

        return self.rebuild_validator_recursive(result_validator)
