from strictyaml import Validator
from strictyaml.exceptions import YAMLSerializationError


class ForwardRefValidator(Validator):
    def _should_be_validator(self, validator):
        if not isinstance(validator, Validator):
            raise YAMLSerializationError(
                "Expected a Validator, found '{}'".format(validator)
            )


class ForwardRef(ForwardRefValidator):
    def __init__(self):
        self._validator = None
        self.has_expanded = False

    def set(self, validator: Validator):
        self._should_be_validator(validator)
        self._validator = validator

    def __call__(self, chunk):
        if self._validator is None:
            raise YAMLSerializationError("ForwardRef was used before it was set")
        return self._validator(chunk)

    def __repr__(self):
        if self._validator is None:
            return "{0}()".format(self.__class__.__name__)
        if not self.has_expanded:
            self.has_expanded = True
            return "{0}".format(repr(self._validator))
        else:
            return "{0}()".format(self.__class__.__name__)

    def to_yaml(self, data):
        return self._validator.to_yaml(data)
