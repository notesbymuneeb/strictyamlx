from strictyaml import Validator
from strictyaml.validators import MapValidator
from strictyaml import Map, MapCombined
import copy
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

    def merge_recursive(self, control_validator, case_validator):
        control_validator = unpack(control_validator)
        if not hasattr(control_validator, '_validator') or not isinstance(control_validator._validator, dict):
            return
        if not hasattr(case_validator, '_validator') or not isinstance(case_validator._validator, dict):
            return

        def normalize_key(key):
            return key.key if hasattr(key, "key") else key

        for key, val in control_validator._validator.items():
            normalized_key = normalize_key(key)
            case_key_lookup = {
                normalize_key(case_key): case_key
                for case_key in case_validator._validator.keys()
            }
            case_key = case_key_lookup.get(normalized_key)

            val_unpacked = unpack(val)
            is_nested_mapping_with_key_schema = (
                isinstance(val_unpacked, MapValidator)
                and hasattr(val_unpacked, "_validator_dict")
            )
            if is_nested_mapping_with_key_schema:
                if case_key is None:
                    case_key = key
                    case_validator._validator[case_key] = Map({})
                    
                target = ensure_validator_dict(case_validator._validator[case_key])
                case_validator._validator[case_key] = target
                self.merge_recursive(val, target)
            else:
                if case_key is None:
                    case_validator._validator[key] = val

    def rebuild_validator_recursive(self, validator):
        validator = ensure_validator_dict(validator)
        if not hasattr(validator, '_validator') or not isinstance(validator._validator, dict):
            return validator

        new_dict = {}
        for key, val in validator._validator.items():
            val_unpacked = ensure_validator_dict(val)
            if hasattr(val_unpacked, '_validator') and isinstance(val_unpacked._validator, dict):
                new_dict[key] = self.rebuild_validator_recursive(val_unpacked)
            else:
                new_dict[key] = val_unpacked

        from .keyed_choice_map import KeyedChoiceMap
        if isinstance(validator, KeyedChoiceMap):
            choice_keys = list(validator.choice_keys)
            choices = [(k, new_dict[k]) for k in choice_keys]
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
            return MapCombined(new_dict, validator.key_validator, getattr(validator, '_value_validator', None))
        return Map(new_dict)

    def _build(self):
        control_validator = copy.deepcopy(unpack(self.control_validator))
        if self.control_source:
            if isinstance(self.control_source, str):
                self.control_source = [self.control_source]
            for key in reversed(self.control_source):
                map_layer = Map({})
                map_layer._validator[key] = control_validator
                control_validator = map_layer

        case_validator = copy.deepcopy(ensure_validator_dict(self.case_validator))
        overlay_validators = [
            copy.deepcopy(ensure_validator_dict(overlay_validator))
            for overlay_validator in self.overlay_validators
        ]

        if hasattr(case_validator, 'control') and hasattr(case_validator.control, '_validator'):
            nested_validator = copy.deepcopy(ensure_validator_dict(case_validator.control._validator))
            for overlay_validator in overlay_validators:
                self.merge_recursive(overlay_validator, nested_validator)
            self.merge_recursive(control_validator, nested_validator)
            case_validator.control._validator = self.rebuild_validator_recursive(nested_validator)
            return case_validator

        result_validator = case_validator
        for overlay_validator in overlay_validators:
            self.merge_recursive(overlay_validator, result_validator)
        self.merge_recursive(control_validator, result_validator)
        final_validator = self.rebuild_validator_recursive(result_validator)

        return final_validator
