import pytest
from keel.schemas import validate_schema, validate_arguments

SCHEMA = {"type": "object", "properties": {"quantity": {"type": "integer", "minimum": 1, "maximum": 10}}, "required": ["quantity"], "additionalProperties": False}


def test_typed_arguments_reject_extra_fields_and_boolean_integers():
    validate_schema(SCHEMA)
    validate_arguments(SCHEMA, {"quantity": 2})
    for args in [{"quantity": True}, {"quantity": "2"}, {"quantity": 11}, {"quantity": 1, "admin": True}, {}]:
        with pytest.raises(ValueError):
            validate_arguments(SCHEMA, args)


@pytest.mark.parametrize("schema", [{"$ref": "https://attacker/schema"}, {"type": "object"}, {"type": "object", "additionalProperties": False, "properties": {"x": {"type": "string", "pattern": "(a+)+$"}}}])
def test_registry_rejects_remote_references_unbounded_objects_and_patterns(schema):
    with pytest.raises(ValueError):
        validate_schema(schema)
