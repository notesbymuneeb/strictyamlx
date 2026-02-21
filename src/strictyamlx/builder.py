from strictyaml.validators import Validator, MapValidator
from strictyaml import Map
import copy


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

    def merge_recursive(self, control_validator, case_valdiator):
        for key, val in control_validator._validator.items():
            if isinstance(val, MapValidator):
                if not key in case_valdiator._validator:
                    case_valdiator._validator[key] = Map({})
                    self.merge_recursive(val, case_valdiator._validator[key])
                else:
                    if isinstance(case_valdiator._validator[key], MapValidator):
                        self.merge_recursive(val, case_valdiator._validator[key])
            else:
                if key not in case_valdiator._validator:
                    case_valdiator._validator[key] = val

    # TODO: rebuild can be improved
    def find_map_paths(self, validator, map_paths, path=[]):
        for key, val in validator._validator.items():
            if isinstance(val, MapValidator):
                path.append(key)
                self.find_map_paths(val, map_paths, path)
                map_paths.append(list(path))
                path.pop()

    def rebuild_validator(self, validator):
        map_paths = []
        self.find_map_paths(validator, map_paths)
        for map_path in map_paths:
            parent = validator
            if len(map_path) > 1:
                for key in map_path[:-1]:
                    parent = parent._validator[key]
            parent._validator[map_path[-1]] = Map(
                parent._validator[map_path[-1]]._validator
            )
        validator = Map(validator._validator)
        return validator

    def _build(self):
        control_validator = copy.deepcopy(self.control_validator)
        if self.control_source:
            if isinstance(self.control_source, str):
                self.control_source = [self.control_source]
            for key in reversed(self.control_source):
                map = Map({})
                map._validator[key] = control_validator
                control_validator = map

        self.merge_recursive(control_validator, self.case_validator)
        final_validator = self.rebuild_validator(validator=self.case_validator)

        return final_validator
