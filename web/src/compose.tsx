import React, { useEffect, useRef, useState } from "react";
import {
  ApiClient,
  Inventory,
  RequestRecord,
  Tool,
  errorMessage,
} from "./client";
export function Compose({
  api,
  done,
  cancel,
}: {
  api: ApiClient;
  done: (request: RequestRecord) => void;
  cancel: () => void;
}) {
  const [tools, setTools] = useState<Tool[]>([]);
  const [stock, setStock] = useState<Inventory[]>([]);
  const [chosen, setChosen] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const key = useRef(crypto.randomUUID());
  const tool = tools.find((item) => `${item.name}@${item.version}` === chosen);
  useEffect(() => {
    let active = true;
    Promise.all([
      api.get<Tool[]>("/api/tools"),
      api.get<Inventory[]>("/api/inventory"),
    ])
      .then(([catalog, inventory]) => {
        if (!active) return;
        setTools(catalog);
        setStock(inventory);
        setLoaded(true);
        const first =
          catalog.find((item) => item.name === "inventory.reserve") ||
          catalog[0];
        if (first) setChosen(`${first.name}@${first.version}`);
      })
      .catch((failure) => {
        if (active) {
          setError(errorMessage(failure));
          setLoaded(true);
        }
      });
    return () => {
      active = false;
    };
  }, [api]);
  const update = (field: string, value: string) => {
    key.current = crypto.randomUUID();
    setValues((previous) => ({ ...previous, [field]: value }));
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!tool || busy) return;
    setBusy(true);
    setError("");
    try {
      const args: Record<string, unknown> = {};
      for (const [name, schema] of Object.entries(
        tool.schema.properties || {}
      )) {
        const value = values[name];
        if (value === undefined || value === "") continue;
        args[name] = schema.type === "string" ? value : JSON.parse(value);
      }
      done(
        await api.post<RequestRecord>(
          "/api/requests",
          { tool: tool.name, version: tool.version, arguments: args },
          key.current
        )
      );
    } catch (failure) {
      setError(errorMessage(failure));
      setBusy(false);
    }
  };
  return (
    <form onSubmit={submit} className="composer">
      <div className="section-heading plain">
        <div>
          <p className="eyebrow">NEW ACTION</p>
          <h2>Choose a tool. Define the job.</h2>
        </div>
        <button
          type="button"
          className="quiet"
          onClick={cancel}
          disabled={busy}
        >
          Close
        </button>
      </div>
      <p className="muted small">
        The selected version and these arguments become the exact request that
        will be reviewed and executed.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!loaded ? (
        <p>Loading available tools…</p>
      ) : !tools.length ? (
        <p>No active tools are available. Contact your administrator.</p>
      ) : (
        <>
          <label className="field">
            Tool
            <select
              aria-label="Tool"
              value={chosen}
              disabled={busy}
              onChange={(event) => {
                setChosen(event.target.value);
                setValues({});
                key.current = crypto.randomUUID();
                setError("");
              }}
            >
              {tools.map((item) => (
                <option
                  key={`${item.name}@${item.version}`}
                  value={`${item.name}@${item.version}`}
                >
                  {item.name} · v{item.version}
                </option>
              ))}
            </select>
          </label>
          {tool && (
            <>
              <p className="tool-description">{tool.description}</p>
              {Object.entries(tool.schema.properties || {}).map(
                ([name, schema]) => (
                  <label className="field" key={`${chosen}:${name}`}>
                    {name === "sku"
                      ? "Inventory item"
                      : name.charAt(0).toUpperCase() + name.slice(1)}
                    {schema.type === "string" && name === "sku" ? (
                      <select
                        aria-label="Inventory item"
                        required={tool.schema.required?.includes(name)}
                        value={values[name] || ""}
                        disabled={busy}
                        onChange={(e) => update(name, e.target.value)}
                      >
                        <option value="">Choose an inventory item</option>
                        {stock.map((item) => (
                          <option key={item.sku} value={item.sku}>
                            {item.sku} · {item.available} available
                          </option>
                        ))}
                      </select>
                    ) : schema.type === "string" ? (
                      <textarea
                        aria-label={
                          name.charAt(0).toUpperCase() + name.slice(1)
                        }
                        rows={6}
                        required={tool.schema.required?.includes(name)}
                        minLength={schema.minLength}
                        maxLength={schema.maxLength}
                        value={values[name] || ""}
                        disabled={busy}
                        onChange={(e) => update(name, e.target.value)}
                      />
                    ) : ["integer", "number"].includes(schema.type) ? (
                      <input
                        aria-label={
                          name.charAt(0).toUpperCase() + name.slice(1)
                        }
                        type="number"
                        step={schema.type === "integer" ? "1" : "any"}
                        min={schema.minimum}
                        max={schema.maximum}
                        required={tool.schema.required?.includes(name)}
                        value={values[name] || ""}
                        disabled={busy}
                        onChange={(e) => update(name, e.target.value)}
                      />
                    ) : (
                      <textarea
                        aria-label={
                          name.charAt(0).toUpperCase() + name.slice(1)
                        }
                        rows={4}
                        placeholder="Enter a JSON value"
                        required={tool.schema.required?.includes(name)}
                        value={values[name] || ""}
                        disabled={busy}
                        onChange={(e) => update(name, e.target.value)}
                      />
                    )}
                    {schema.type === "integer" && (
                      <span className="muted small">
                        Whole units, from {schema.minimum ?? "the minimum"} to{" "}
                        {schema.maximum ?? "the maximum"}.
                      </span>
                    )}
                  </label>
                )
              )}
              <div className="notice">
                {tool.risk === "effect"
                  ? "Independent approval required. This action changes simulated inventory only after a reviewer approves the exact request."
                  : "This tool can run without human approval. Its output will be recorded with the request."}
              </div>
              <div className="form-actions">
                <button className="primary" disabled={busy}>
                  {busy
                    ? "Sending request…"
                    : tool.risk === "effect"
                    ? "Send for approval"
                    : "Run tool"}
                </button>
                <span className="muted small">
                  Version {tool.version} is fixed for this request.
                </span>
              </div>
            </>
          )}
        </>
      )}
    </form>
  );
}
