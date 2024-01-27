package keel

# Increment revision for policy changes that should invalidate earlier approvals.
revision := "keel-2024.1"
default allow := false
default requires_approval := false

trusted_risk := {"sha256": "read", "sign_report": "read", "reserve_inventory": "effect"}

valid_context {
    input.actor.tenant == input.tenant
    input.tool.enabled == true
    trusted_risk[input.tool.handler] == input.tool.risk
}

allow {
    valid_context
    input.action == "invoke"
    input.actor.roles[_] == "operator"
}

allow {
    valid_context
    input.action == "approve"
    input.actor.roles[_] == "approver"
    input.actor.subject != input.requester
    input.tool.risk == "effect"
}

requires_approval {
    input.tool.risk == "effect"
}

decision := {"allow": allow, "requires_approval": requires_approval, "revision": revision}
