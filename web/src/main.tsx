import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { AuthConfig, AuthSession } from "./auth";
import { ApiClient, Me, errorMessage } from "./client";
import { Workspace } from "./workspace";
import "./styles.css";
interface Config extends AuthConfig {
  apiOrigin: string;
}
function App({ config }: { config: Config }) {
  const [session] = useState(() => new AuthSession(config, sessionStorage));
  const [api] = useState(() => new ApiClient(config.apiOrigin, session));
  const [me, setMe] = useState<Me>();
  const [busy, setBusy] = useState(
    location.search.includes("code=") || location.search.includes("error=")
  );
  const [error, setError] = useState("");
  useEffect(() => {
    if (!location.search) return;
    (async () => {
      try {
        if (new URLSearchParams(location.search).has("error"))
          throw new Error("Sign-in was cancelled. Please try again.");
        await session.finish(location.href);
        setMe(await api.get<Me>("/api/me"));
      } catch (failure) {
        session.clear();
        setError(errorMessage(failure));
      } finally {
        history.replaceState(null, "", "/");
        setBusy(false);
      }
    })();
  }, [api, session]);
  const signIn = async () => {
    setBusy(true);
    setError("");
    try {
      location.assign(await session.begin());
    } catch (failure) {
      setError(errorMessage(failure));
      setBusy(false);
    }
  };
  if (me)
    return (
      <Workspace
        api={api}
        me={me}
        signOut={() => location.assign(session.signOut())}
      />
    );
  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand">
          <span className="brand-mark">K</span> keel
          <span className="brand-dot">.</span>
        </div>
        <p className="eyebrow">THE ACTION CONTROL DESK</p>
        <h1>
          Give tools a job.
          <br />
          Keep people
          <br />
          in control.
        </h1>
        <p className="lead">
          A clear path from intent to approval to a verified execution record.
        </p>
        <div className="login-steps">
          <span>01 · Request</span>
          <span>02 · Review</span>
          <span>03 · Verify</span>
        </div>
      </section>
      <section className="login-panel">
        <p className="eyebrow">YOUR WORKSPACE</p>
        <h2>Welcome to Keel</h2>
        <p>
          Sign in with your organization account to review and manage tool
          actions.
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button className="primary" disabled={busy} onClick={signIn}>
          {busy ? "Verifying your session…" : "Sign in to workspace →"}
        </button>
        <p className="muted small">
          Your permissions determine which actions you can request, approve or
          administer.
        </p>
      </section>
    </main>
  );
}
fetch("/config.json")
  .then((response) => {
    if (!response.ok) throw new Error("Console configuration is unavailable.");
    return response.json();
  })
  .then((config) =>
    createRoot(document.getElementById("root")!).render(<App config={config} />)
  )
  .catch(() => {
    document.getElementById("root")!.textContent =
      "The console could not start. Reload the page or contact your operator.";
  });
