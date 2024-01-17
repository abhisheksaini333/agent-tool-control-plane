"""A deliberately bounded subset of JSON Schema Draft 2020-12."""
from jsonschema import Draft202012Validator
from .canonical import canonical

ALLOWED = {"type", "properties", "required", "additionalProperties", "minimum", "maximum", "minLength", "maxLength", "minItems", "maxItems", "items", "enum", "description", "title", "$schema"}
TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}


def _bounded(schema, depth=0):
    if not isinstance(schema, dict) or depth > 8 or set(schema) - ALLOWED:
        raise ValueError("Schema uses unsupported or unsafe keywords")
    kind = schema.get("type")
    if kind not in TYPES:
        raise ValueError("Each schema node requires one explicit type")
    if kind == "object":
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is not False or len(properties) > 32:
            raise ValueError("Objects require closed, bounded properties")
        if set(schema.get("required", [])) - set(properties):
            raise ValueError("Required fields must have declared schemas")
        for child in properties.values():
            _bounded(child, depth + 1)
    if kind == "array":
        if not 0 <= schema.get("maxItems", -1) <= 100:
            raise ValueError("Arrays require maxItems at most 100")
        _bounded(schema.get("items"), depth + 1)
    if kind == "string" and not 0 <= schema.get("maxLength", -1) <= 16000:
        raise ValueError("Strings require maxLength at most 16000")


def validate_schema(schema):
    canonical(schema)
    try:
        Draft202012Validator.check_schema(schema)
        _bounded(schema)
    except Exception as error:
        raise ValueError("Invalid bounded tool schema") from error
    if schema["type"] != "object":
        raise ValueError("Tool arguments must be an object")


def validate_arguments(schema, arguments):
    canonical(arguments)
    errors = sorted(Draft202012Validator(schema).iter_errors(arguments), key=lambda e: str(e.path))
    if errors:
        # Argument values are intentionally excluded from error messages.
        path = ".".join(str(p) for p in errors[0].path) or "arguments"
        raise ValueError(f"Invalid {path}: {errors[0].validator} constraint")
