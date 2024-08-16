import type { AuthSession } from './auth';
export interface Me { tenant: string; subject: string; display_name: string; roles: string[] }
export interface Schema { type: string; properties?: Record<string, Schema>; required?: string[]; enum?: (string | number)[]; minimum?: number; maximum?: number; minLength?: number; maxLength?: number }
export interface Tool { name: string; version: string; description: string; risk: string; digest: string; schema: Schema; handler?: string }
export interface AuditEvent { sequence: number; at: number; actor: string; action: string; details: Record<string, unknown>; request_id: string | null; hash: string }
export interface Inventory { sku: string; available: number }
export interface RequestRecord {
  id: string; tenant: string; caller: string; caller_name: string; approver_name?: string;
  tool: Tool; arguments: Record<string, unknown>; arguments_digest: string; binding: string;
  status: string; revision: number; created_at: number; expires_at: number; attempts: number;
  requires_approval: boolean; error: string | null;
  approval: { subject: string; expires_at: number; revoked: boolean } | null;
  receipt: { id: string; completed_at: number; attempt: number; effect: Record<string, unknown> | null; output: Record<string, unknown> } | null;
}
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
export class ApiClient {
  constructor(private origin: string, private session: Pick<AuthSession, 'accessToken'>) {}
  get<T>(path: string): Promise<T> { return this.request<T>(path); }
  post<T>(path: string, body: unknown, idempotencyKey?: string): Promise<T> { return this.request<T>(path, body, idempotencyKey); }
  private async request<T>(path: string, body?: unknown, key?: string): Promise<T> {
    const token = await this.session.accessToken();
    let response: Response;
    try {
      response = await fetch(`${this.origin}${path}`, { method: body === undefined ? 'GET' : 'POST',
        credentials: 'omit', headers: { Authorization: `Bearer ${token}`, ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
          ...(key ? { 'Idempotency-Key': key } : {}) }, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch { throw new Error('The service could not be reached. Check your connection and retry.'); }
    const result = await response.json();
    if (!response.ok) throw new ApiError(response.status, result.message || 'The request could not be completed.');
    return result;
  }
}
export const statusLabel = (value: string): string => ({ awaiting_approval: 'Needs review', queued: 'Queued', running: 'Running',
  retry_wait: 'Retry scheduled', completed: 'Completed', cancelled: 'Cancelled', revoked: 'Approval revoked',
  rejected: 'Authorization changed', expired: 'Expired', failed: 'Failed' }[value] || value.replace(/_/g, ' '));
export const timeLabel = (seconds: number): string => new Date(seconds * 1000).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
export const errorMessage = (error: unknown): string => error instanceof Error ? error.message : 'Something went wrong. Please retry.';
