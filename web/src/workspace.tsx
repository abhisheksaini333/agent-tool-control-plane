import React, { useCallback, useEffect, useRef, useState } from "react";
import { Registry } from "./registry";
import { AuditTrail } from "./audit";
import { RequestDetail } from "./request-detail";
import { Compose } from "./compose";
import {
  ApiClient,
  Me,
  RequestRecord,
  errorMessage,
  statusLabel,
  timeLabel,
} from "./client";
export function Workspace({
  api,
  me,
  signOut,
}: {
  api: ApiClient;
  me: Me;
  signOut: () => void;
}) {
  const [tab, setTab] = useState<"desk" | "registry" | "audit">("desk");
  const administrative = me.roles.some((role) =>
    ["administrator", "auditor"].includes(role)
  );
  const [composing, setComposing] = useState(false);
  const [requests, setRequests] = useState<RequestRecord[]>([]);
  const [selected, setSelected] = useState<string>();
  const [view, setView] = useState<RequestRecord>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const selection = useRef<string>();
  const generation = useRef(0);
  const refresh = useCallback(async () => {
    const current = generation.current;
    try {
      const rows = await api.get<RequestRecord[]>("/api/requests?limit=200");
      if (current !== generation.current) return;
      setRequests(rows.sort((a, b) => b.created_at - a.created_at));
      setError("");
      setLoading(false);
      if (selection.current)
        setView(rows.find((row) => row.id === selection.current));
    } catch (failure) {
      if (current === generation.current) {
        setError(errorMessage(failure));
        setLoading(false);
      }
    }
  }, [api]);
  useEffect(() => {
    let stopped = false;
    const poll = async () => {
      await refresh();
      if (!stopped) timer = setTimeout(poll, 1800);
    };
    let timer: ReturnType<typeof setTimeout>;
    void poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
      generation.current++;
    };
  }, [refresh]);
  const choose = (row: RequestRecord) => {
    setComposing(false);
    generation.current++;
    selection.current = row.id;
    setSelected(row.id);
    setView(row);
  };
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">K</span> keel
          <span className="brand-dot">.</span>
        </div>
        <p className="sidebar-caption">WORKSPACE</p>
        <div className="tenant-name">
          {me.tenant.toUpperCase()} <span className="online-dot" />
        </div>
        <nav aria-label="Main navigation">
          <button
            className={`nav-item ${tab === "desk" ? "active" : ""}`}
            onClick={() => setTab("desk")}
          >
            ◫ <span>Action desk</span>
          </button>
          {administrative && (
            <>
              <button
                className={`nav-item ${tab === "registry" ? "active" : ""}`}
                onClick={() => setTab("registry")}
              >
                ⊞ <span>Tool registry</span>
              </button>
              <button
                className={`nav-item ${tab === "audit" ? "active" : ""}`}
                onClick={() => setTab("audit")}
              >
                ≡ <span>Workspace audit</span>
              </button>
            </>
          )}
        </nav>
        <div className="sidebar-bottom">
          <span className="online-dot" /> Approval before impact
          <p>
            Each effect has a request,
            <br />a reviewer and a receipt.
          </p>
        </div>
      </aside>
      <div className="app-main">
        <header className="topbar">
          <span>
            CONTROL DESK <span className="crumb">/ Actions</span>
          </span>
          <div className="identity">
            <div>
              <strong>{me.display_name}</strong>
              <small>{me.roles.join(" · ")}</small>
            </div>
            <button className="quiet" onClick={signOut}>
              Sign out
            </button>
          </div>
        </header>
        <main className="workspace">
          {tab === "registry" ? (
            <Registry api={api} me={me} />
          ) : tab === "audit" ? (
            <section className="registry-panel">
              <AuditTrail api={api} />
            </section>
          ) : (
            <>
              <div className="page-heading">
                <div>
                  <p className="eyebrow">TRACEABLE BY DESIGN</p>
                  <h1>Action desk</h1>
                  <p className="muted">
                    Review the details. Follow the outcome.
                  </p>
                </div>
                {me.roles.includes("operator") && (
                  <button
                    className="primary"
                    onClick={() => {
                      generation.current++;
                      selection.current = undefined;
                      setSelected(undefined);
                      setView(undefined);
                      setComposing(true);
                    }}
                  >
                    + New request
                  </button>
                )}
              </div>
              <div className="stats">
                <div>
                  <span>Needs review</span>
                  <strong>
                    {
                      requests.filter((r) => r.status === "awaiting_approval")
                        .length
                    }
                  </strong>
                </div>
                <div>
                  <span>In progress</span>
                  <strong>
                    {
                      requests.filter((r) =>
                        ["queued", "running", "retry_wait"].includes(r.status)
                      ).length
                    }
                  </strong>
                </div>
                <div>
                  <span>Completed</span>
                  <strong>
                    {requests.filter((r) => r.status === "completed").length}
                  </strong>
                </div>
                <p>
                  Only actions available
                  <br />
                  to your account are shown.
                </p>
              </div>
              {error && (
                <div role="alert" className="error">
                  {error} <button onClick={() => void refresh()}>Retry</button>
                </div>
              )}
              <div className="workbench">
                <section className="queue">
                  <div className="section-heading">
                    <h2>Requests</h2>
                    <span className="count">{requests.length}</span>
                  </div>
                  <div className="request-list">
                    {requests.map((row) => (
                      <button
                        key={row.id}
                        className={`request-item ${
                          selected === row.id ? "selected" : ""
                        }`}
                        aria-pressed={selected === row.id}
                        onClick={() => choose(row)}
                      >
                        <span className={`badge ${row.status}`}>
                          {statusLabel(row.status)}
                        </span>
                        <strong>{row.tool.name}</strong>
                        <span>
                          {row.caller_name} · {timeLabel(row.created_at)}
                        </span>
                        <code>{row.id.slice(0, 8)}</code>
                      </button>
                    ))}
                    {!requests.length && (
                      <p className="empty">
                        {loading
                          ? "Loading requests…"
                          : "No requests yet. Your next action starts here."}
                      </p>
                    )}
                  </div>
                </section>
                <section className="detail">
                  {composing ? (
                    <Compose
                      api={api}
                      cancel={() => setComposing(false)}
                      done={(request) => {
                        choose(request);
                        void refresh();
                      }}
                    />
                  ) : view ? (
                    <RequestDetail
                      key={view.id}
                      api={api}
                      me={me}
                      request={view}
                      changed={(row) => {
                        if (selection.current === row.id) {
                          generation.current++;
                          setView(row);
                          void refresh();
                        }
                      }}
                    />
                  ) : (
                    <div className="empty-detail">
                      <span className="detail-symbol">↗</span>
                      <h2>Every action starts with context.</h2>
                      <p>
                        Select a request to inspect its arguments,
                        <br />
                        approval and execution record.
                      </p>
                    </div>
                  )}
                </section>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
