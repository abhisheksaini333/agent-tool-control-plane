import React, { useCallback, useEffect, useState } from "react";
import { ApiClient, Me, Tool, errorMessage } from "./client";
interface Activation {
  name: string;
  version: string;
  enabled: boolean;
  generation: number;
}
interface Catalog {
  versions: Tool[];
  activations: Activation[];
  handlers: string[];
}
export function Registry({ api, me }: { api: ApiClient; me: Me }) {
  const [catalog, setCatalog] = useState<Catalog>();
  const [draft, setDraft] = useState({
    name: "",
    version: "",
    handler: "sha256",
    description: "",
    schema: "",
  });
  const [publishing, setPublishing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [confirm, setConfirm] = useState<{
    tool: Tool;
    action: "activate" | "disable";
  }>();
  const admin = me.roles.includes("administrator");
  const refresh = useCallback(
    async () => setCatalog(await api.get<Catalog>("/api/registry")),
    [api]
  );
  useEffect(() => {
    void refresh().catch((failure) => setError(errorMessage(failure)));
  }, [refresh]);
  const mutate = async (path: string, body: unknown, success: string) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.post(path, body);
      await refresh();
      setMessage(success);
      setConfirm(undefined);
      setPublishing(false);
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  };
  const clone = (tool: Tool) => {
    setDraft({
      name: tool.name,
      version: "",
      handler: tool.handler!,
      description: tool.description,
      schema: JSON.stringify(tool.schema, null, 2),
    });
    setPublishing(true);
    setError("");
    setMessage("");
  };
  const publish = (event: React.FormEvent) => {
    event.preventDefault();
    let schema;
    try {
      schema = JSON.parse(draft.schema);
    } catch {
      setError("The input schema must be valid JSON.");
      return;
    }
    void mutate(
      "/api/registry",
      { ...draft, schema },
      `Published ${draft.name} v${draft.version}. Activate it when ready.`
    );
  };
  return (
    <section className="registry-panel">
      <div className="section-heading plain">
        <div>
          <h2>Tool registry</h2>
          <p className="muted small">
            Immutable contracts. Explicit activation. Trusted handlers only.
          </p>
        </div>
        <button
          onClick={() =>
            void refresh().catch((failure) => setError(errorMessage(failure)))
          }
          disabled={busy}
        >
          Refresh
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      {confirm && (
        <section className="approval-card">
          <h3>
            {confirm.action === "disable" ? "Disable" : "Activate"}{" "}
            {confirm.tool.name}
            {confirm.action === "activate" ? ` v${confirm.tool.version}` : ""}?
          </h3>
          <p>
            This changes the active contract generation. Existing requests for
            this tool will fail authorization before their next dispatch or
            effect commit, even if already approved.
          </p>
          <div className="form-actions">
            <button
              className="primary"
              disabled={busy}
              onClick={() =>
                void mutate(
                  `/api/registry/${encodeURIComponent(confirm.tool.name)}/${
                    confirm.action
                  }`,
                  confirm.action === "activate"
                    ? { version: confirm.tool.version }
                    : {},
                  `${confirm.tool.name} ${
                    confirm.action === "disable" ? "disabled" : "activated"
                  }.`
                )
              }
            >
              Confirm {confirm.action === "disable" ? "disable" : "activation"}
            </button>
            <button disabled={busy} onClick={() => setConfirm(undefined)}>
              Keep current state
            </button>
          </div>
        </section>
      )}
      {publishing && (
        <form className="publish-form" onSubmit={publish}>
          <h3>Publish a new version</h3>
          <p className="muted small">
            Start from an installed contract. Publishing does not activate it.
          </p>
          <div className="field-grid">
            <label className="field">
              Tool name
              <input
                aria-label="Tool name"
                required
                maxLength={128}
                value={draft.name}
                disabled={busy}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </label>
            <label className="field">
              Version
              <input
                aria-label="Version"
                required
                pattern="[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}"
                placeholder="1.0.1"
                value={draft.version}
                disabled={busy}
                onChange={(e) =>
                  setDraft({ ...draft, version: e.target.value })
                }
              />
            </label>
          </div>
          <label className="field">
            Installed handler
            <select
              aria-label="Installed handler"
              value={draft.handler}
              disabled={busy}
              onChange={(e) => setDraft({ ...draft, handler: e.target.value })}
            >
              {catalog?.handlers.map((name) => (
                <option key={name}>{name}</option>
              ))}
            </select>
          </label>
          <label className="field">
            Description
            <textarea
              aria-label="Description"
              rows={2}
              required
              maxLength={2000}
              value={draft.description}
              disabled={busy}
              onChange={(e) =>
                setDraft({ ...draft, description: e.target.value })
              }
            />
          </label>
          <label className="field">
            Input JSON schema
            <textarea
              aria-label="Input JSON schema"
              className="code-input"
              rows={12}
              required
              value={draft.schema}
              disabled={busy}
              onChange={(e) => setDraft({ ...draft, schema: e.target.value })}
            />
          </label>
          <p className="muted small">
            Schemas may narrow the installed handler contract. They cannot add
            code, network access or credentials.
          </p>
          <div className="form-actions">
            <button className="primary" disabled={busy}>
              Publish version
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setPublishing(false)}
            >
              Cancel publishing
            </button>
          </div>
        </form>
      )}
      {!catalog && <p className="muted">Loading registry…</p>}
      <div className="registry-list">
        {catalog?.versions.map((tool) => {
          const active = catalog.activations.find(
            (item) => item.name === tool.name
          );
          const enabled = active?.enabled && active.version === tool.version;
          return (
            <article
              className="registry-tool"
              key={`${tool.name}@${tool.version}`}
            >
              <div className="request-title">
                <div>
                  <h3>
                    {tool.name}{" "}
                    <span className="muted small">v{tool.version}</span>
                  </h3>
                  <p className="muted small">{tool.description}</p>
                </div>
                <span className={`badge ${enabled ? "completed" : ""}`}>
                  {enabled ? "Active" : "Inactive"}
                </span>
              </div>
              <p className="small muted">
                Handler: {tool.handler} ·{" "}
                {tool.risk === "effect"
                  ? "Independent approval required"
                  : "No business effect"}
              </p>
              <details className="schema-view">
                <summary>Inspect input contract</summary>
                <pre>{JSON.stringify(tool.schema, null, 2)}</pre>
              </details>
              {admin && (
                <div className="form-actions">
                  <button disabled={busy} onClick={() => clone(tool)}>
                    New version from this
                  </button>
                  <button
                    disabled={busy}
                    onClick={() =>
                      setConfirm({
                        tool,
                        action: enabled ? "disable" : "activate",
                      })
                    }
                  >
                    {enabled ? "Disable tool" : "Activate version"}
                  </button>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
