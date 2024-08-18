import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ApiClient, Me, RequestRecord, errorMessage, statusLabel, timeLabel } from './client';
export function Workspace({ api, me, signOut }: { api: ApiClient; me: Me; signOut: () => void }) {
  const [requests, setRequests] = useState<RequestRecord[]>([]);
  const [selected, setSelected] = useState<string>();
  const [view, setView] = useState<RequestRecord>();
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const selection = useRef<string>();
  const generation = useRef(0);
  const refresh = useCallback(async () => {
    const current = generation.current;
    try {
      const rows = await api.get<RequestRecord[]>('/api/requests?limit=200');
      if (current !== generation.current) return;
      setRequests(rows.sort((a,b) => b.created_at - a.created_at)); setError(''); setLoading(false);
      if (selection.current) setView(rows.find(row => row.id === selection.current));
    } catch (failure) { if (current === generation.current) { setError(errorMessage(failure)); setLoading(false); } }
  }, [api]);
  useEffect(() => {
    let stopped = false;
    const poll = async () => { await refresh(); if (!stopped) timer = setTimeout(poll, 1800); };
    let timer: ReturnType<typeof setTimeout>;
    void poll();
    return () => { stopped = true; clearTimeout(timer); generation.current++; };
  }, [refresh]);
  const choose = (row: RequestRecord) => { generation.current++; selection.current = row.id; setSelected(row.id); setView(row); };
  return <div className="app-shell">
    <aside className="sidebar"><div className="brand"><span className="brand-mark">K</span> keel<span className="brand-dot">.</span></div>
      <p className="sidebar-caption">WORKSPACE</p><div className="tenant-name">{me.tenant.toUpperCase()} <span className="online-dot" /></div>
      <nav aria-label="Main navigation"><button className="nav-item active">◫ <span>Action desk</span></button></nav>
      <div className="sidebar-bottom"><span className="online-dot" /> Approval before impact<p>Each effect has a request,<br />a reviewer and a receipt.</p></div>
    </aside>
    <div className="app-main"><header className="topbar"><span>CONTROL DESK <span className="crumb">/ Actions</span></span><div className="identity"><div><strong>{me.display_name}</strong><small>{me.roles.join(' · ')}</small></div><button className="quiet" onClick={signOut}>Sign out</button></div></header>
      <main className="workspace"><div className="page-heading"><div><p className="eyebrow">TRACEABLE BY DESIGN</p><h1>Action desk</h1><p className="muted">Review the details. Follow the outcome.</p></div></div>
        <div className="stats"><div><span>Needs review</span><strong>{requests.filter(r=>r.status==='awaiting_approval').length}</strong></div><div><span>In progress</span><strong>{requests.filter(r=>['queued','running','retry_wait'].includes(r.status)).length}</strong></div><div><span>Completed</span><strong>{requests.filter(r=>r.status==='completed').length}</strong></div><p>Only actions available<br />to your account are shown.</p></div>
        {error && <div role="alert" className="error">{error} <button onClick={()=>void refresh()}>Retry</button></div>}
        <div className="workbench"><section className="queue"><div className="section-heading"><h2>Requests</h2><span className="count">{requests.length}</span></div>
          <div className="request-list">{requests.map(row=><button key={row.id} className={`request-item ${selected===row.id?'selected':''}`} aria-pressed={selected===row.id} onClick={()=>choose(row)}>
            <span className={`badge ${row.status}`}>{statusLabel(row.status)}</span><strong>{row.tool.name}</strong><span>{row.caller_name} · {timeLabel(row.created_at)}</span><code>{row.id.slice(0,8)}</code>
          </button>)}{!requests.length&&<p className="empty">{loading?'Loading requests…':'No requests yet. Your next action starts here.'}</p>}</div></section>
          <section className="detail">{view?<><p className="eyebrow">REQUEST {view.id.slice(0,8)}</p><h2>{view.tool.name}</h2><p className="muted">Version {view.tool.version} · Requested by {view.caller_name}</p><span className={`badge ${view.status}`}>{statusLabel(view.status)}</span><h3>Exact arguments</h3><pre>{JSON.stringify(view.arguments,null,2)}</pre><p className="muted small">Expires {timeLabel(view.expires_at)}</p></>:<div className="empty-detail"><span className="detail-symbol">↗</span><h2>Every action starts with context.</h2><p>Select a request to inspect its arguments,<br />approval and execution record.</p></div>}</section>
        </div>
      </main>
    </div>
  </div>;
}
