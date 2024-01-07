# Keel — agent tool control plane

Keel gives operators a controlled execution path for agent tool requests. It binds identity, versioned schemas, policy, approval and durable execution records independently of model output.

The local demonstration uses typed HTTP requests, OPA policy decisions and constrained Docker workers. Inventory reservations are simulated business effects committed with their receipts in the control-plane database.

Implementation follows a staged acceptance plan: registry and identity, exact approvals, durable worker execution, operator console, then integration and recovery evidence.
