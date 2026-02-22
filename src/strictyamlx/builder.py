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
        control_source: tuple[str] | str | None = None,
    ):
        self.control_source = control_source
        self.control_validator = control_validator
        self.case_validator = case_validator
        self.validator = self._build()

    def merge_recursive(self, control_validator, case_validator):
        control_validator = unpack(control_validator)
        if not hasattr(control_validator, '_validator') or not isinstance(control_validator._validator, dict):
            return
        if not hasattr(case_validator, '_validator') or not isinstance(case_validator._validator, dict):
            return

        for key, val in control_validator._validator.items():
            val_unpacked = unpack(val)
            if isinstance(val_unpacked, MapValidator):
                if key not in case_validator._validator:
                    case_validator._validator[key] = Map({})
                    
                target = ensure_validator_dict(case_validator._validator[key])
                case_validator._validator[key] = target
                self.merge_recursive(val, target)
            else:
                if key not in case_validator._validator:
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

        if hasattr(case_validator, 'control') and hasattr(case_validator.control, '_validator'):
            case_validator.control._validator = ValidatorBuilder(
                control_validator, case_validator.control._validator
            ).validator
            return case_validator

        self.merge_recursive(control_validator, case_validator)
        final_validator = self.rebuild_validator_recursive(case_validator)

        return final_validator
