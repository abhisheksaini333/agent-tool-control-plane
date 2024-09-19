import React, { useEffect, useState } from 'react';
import { ApiClient, Me, RequestRecord, errorMessage, statusLabel, timeLabel } from './client';
const stoppable = new Set(['awaiting_approval','queued','running','retry_wait']);
export function RequestDetail({ api, me, request, changed }: { api: ApiClient; me: Me; request: RequestRecord; changed: (request: RequestRecord) => void }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setAcknowledged(false); }, [request.id, request.revision]);
  const approve = request.status==='awaiting_approval' && me.roles.includes('approver') && request.caller!==me.subject;
  const cancel = stoppable.has(request.status) && (request.caller===me.subject || me.roles.includes('administrator'));
  const revoke = ['queued','running','retry_wait'].includes(request.status) && request.approval &&
    ((request.approval.subject===me.subject && me.roles.includes('approver')) || me.roles.includes('administrator'));
  const act = async (action: string) => {
    if (busy) return; setBusy(true); setError('');
    try { changed(await api.post<RequestRecord>(`/api/requests/${request.id}/${action}`,
      { revision: request.revision, ...(action==='approval'?{binding:request.binding}:{}) })); }
    catch (failure) {
      setError(errorMessage(failure)); setAcknowledged(false);
      try { changed(await api.get<RequestRecord>(`/api/requests/${request.id}`)); } catch { /* Keep the actionable original error visible. */ }
    } finally { setBusy(false); }
  };
  return <>
    <div className="request-title"><p className="eyebrow">REQUEST {request.id.slice(0,8)}</p><span className={`badge ${request.status}`}>{statusLabel(request.status)}</span></div>
    <h2>{request.tool.name}</h2><p className="muted small">Version {request.tool.version} · Requested by {request.caller_name}</p>
    <p className="tool-description">{request.tool.description}</p>
    {error && <p role="alert" className="error">{error}</p>}
    <div className="request-meta"><div><span>Created</span><strong>{timeLabel(request.created_at)}</strong></div><div><span>Request expires</span><strong>{timeLabel(request.expires_at)}</strong></div><div><span>Impact</span><strong>{request.requires_approval?'Changes inventory':'Read-only tool'}</strong></div></div>
    <h3>Exact arguments</h3><pre aria-label="Exact arguments">{JSON.stringify(request.arguments,null,2)}</pre>
    {approve && <section className="approval-card"><h3>Your review is required</h3><p>You are approving this caller, tool version and the exact arguments shown above. Approval remains valid for up to five minutes and can be revoked before the effect commits.</p>
      <label className="check"><input type="checkbox" checked={acknowledged} disabled={busy} onChange={event=>setAcknowledged(event.target.checked)} />I have reviewed these exact arguments.</label>
      <button className="primary" disabled={!acknowledged||busy} onClick={()=>void act('approval')}>{busy?'Approving…':'Approve and queue'}</button>
    </section>}
    {request.status==='awaiting_approval'&&!approve&&<div className="notice">Waiting for an independent reviewer. The person who requested this action cannot approve it.</div>}
    {request.approval&&<div className="approval-note">{request.approval.revoked?'Approval revoked':'Approved'} by <strong>{request.approver_name||request.approval.subject}</strong><span>Approval expires {timeLabel(request.approval.expires_at)}</span></div>}
    {request.error&&<div className="error" role="status">{failureExplanation(request.error,request.status)}</div>}
    {(cancel||revoke)&&<div className="form-actions">{cancel&&<button disabled={busy} onClick={()=>void act('cancel')}>Cancel request</button>}{revoke&&<button disabled={busy} onClick={()=>void act('revoke')}>Revoke approval</button>}<span className="muted small">Stops work that has not committed.</span></div>}
    <details className="integrity"><summary>Request identity and approval binding</summary><dl><dt>Request ID</dt><dd>{request.id}</dd><dt>Argument digest</dt><dd>{request.arguments_digest}</dd><dt>Approval binding</dt><dd>{request.binding}</dd></dl></details>
  </>;
}
function failureExplanation(code: string, status: string): string {
  const reasons: Record<string,string> = { policy_unavailable:'The policy service is unavailable.', worker_unavailable:'An execution worker is unavailable.', worker_timeout:'The tool exceeded its time limit.', worker_exit:'The tool stopped before returning a valid result.', resource_limit:'The tool exceeded a resource limit.', authorization_changed:'The account, tool, policy or approval changed before execution completed.', invalid_output:'The worker returned an invalid or unverified result.', insufficient_inventory:'There is not enough simulated inventory for this request.', internal_failure:'The worker could not complete this action.' };
  return `${reasons[code]||'This request could not complete.'} ${status==='retry_wait'?'A bounded retry is scheduled automatically.':'Inspect the request and create a new one if appropriate.'}`;
}
