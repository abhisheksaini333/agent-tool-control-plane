"""Installed demo contracts; descriptions never supply policy or code."""
TEXT_SCHEMA = {
    "type": "object",
    "properties": {"text": {"type": "string", "minLength": 1, "maxLength": 4096}},
    "required": ["text"],
    "additionalProperties": False,
}
INVENTORY_SCHEMA = {
    "type": "object",
    "properties": {
        "sku": {"type": "string", "minLength": 1, "maxLength": 40},
        "quantity": {"type": "integer", "minimum": 1, "maximum": 10},
    },
    "required": ["sku", "quantity"],
    "additionalProperties": False,
}
TOOLS = [
    {
        "name": "text.digest",
        "version": "1.0.0",
        "handler": "sha256",
        "description": "Create a SHA-256 digest of a short text. No approval or business effect.",
        "schema": TEXT_SCHEMA,
    },
    {
        "name": "report.sign",
        "version": "1.0.0",
        "handler": "sign_report",
        "description": "Sign a report digest using the dedicated report credential. No business effect.",
        "schema": TEXT_SCHEMA,
    },
    {
        "name": "inventory.reserve",
        "version": "1.0.0",
        "handler": "reserve_inventory",
        "description": "Reserve up to ten units of simulated inventory after independent human approval.",
        "schema": INVENTORY_SCHEMA,
    },
]
