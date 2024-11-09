import React, { useEffect, useState } from "react";
import { ApiClient, AuditEvent, errorMessage, timeLabel } from "./client";
const names: Record<string, string> = {
  "request.created": "Request created",
  "request.approved": "Exact request approved",
  "request.cancelled": "Request cancelled",
  "request.revoked": "Approval revoked",
  "execution.claimed": "Worker acquired the request",
  "execution.completed": "Execution completed",
  "execution.retry_scheduled": "Retry scheduled",
  "execution.failed": "Execution failed",
  "tool.published": "Tool version published",
  "tool.activated": "Tool version activated",
  "tool.disabled": "Tool disabled",
};
export function AuditTrail({
  api,
  requestId,
  revision,
}: {
  api: ApiClient;
  requestId?: string;
  revision?: number;
}) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api
      .get<AuditEvent[]>(
        requestId ? `/api/requests/${requestId}/audit` : "/api/audit"
      )
      .then((rows) => {
        if (active) {
          setEvents(rows.reverse());
          setLoading(false);
        }
      })
      .catch((failure) => {
        if (active) {
          setError(errorMessage(failure));
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [api, requestId, revision]);
  return (
    <section className="audit-trail">
      <div className="section-heading plain">
        <h3>{requestId ? "Activity trail" : "Workspace audit"}</h3>
        <span className="muted small">{events.length} events</span>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {loading && !events.length && (
        <p className="muted small">Loading activity…</p>
      )}
      {events.map((event) => (
        <details className="audit-event" key={event.sequence}>
          <summary>
            <span className="audit-dot" />
            <span>
              <strong>
                {names[event.action] || event.action.replace(/[._]/g, " ")}
              </strong>
              <small>
                {timeLabel(event.at)} · Event {event.sequence}
              </small>
            </span>
          </summary>
          <dl>
            <dt>Actor</dt>
            <dd>{event.actor}</dd>
            {event.request_id && (
              <>
                <dt>Request</dt>
                <dd>{event.request_id}</dd>
              </>
            )}
            <dt>Details</dt>
            <dd>
              <pre>{JSON.stringify(event.details, null, 2)}</pre>
            </dd>
            <dt>Integrity hash</dt>
            <dd>{event.hash}</dd>
          </dl>
        </details>
      ))}
      {!loading && !events.length && !error && (
        <p className="muted">No activity to show.</p>
      )}
    </section>
  );
}
