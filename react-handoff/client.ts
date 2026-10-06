// Framework-independent reference client; import into your React service layer.
// Keep tokens in application memory and clear them when refresh fails.
export type Tokens = { access: string; refresh: string };
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type Role = 'GENERAL_USER' | 'ADMIN' | 'SUPER_ADMIN';
export class SmartLeadClient {
  private tokens: Tokens | null = null;
  constructor(private base = 'http://127.0.0.1:8000/api') { this.base = base.replace(/\/$/, ''); }
  async login(username: string, password: string) {
    this.tokens = await this.request<Tokens>('auth/login/', 'POST', { username, password });
    return this.request('auth/profile/');
  }
  async logout() {
    try { if (this.tokens) await this.request('auth/logout/', 'POST', { refresh: this.tokens.refresh }); }
    finally { this.tokens = null; }
  }
  async request<T = unknown>(path: string, method = 'GET', body?: unknown, retry = true, extra: Record<string, string> = {}): Promise<T> {
    if (/^(https?:)?\/\//.test(path)) throw new Error('Use API-relative paths.');
    const headers: Record<string,string> = { ...extra };
    if (this.tokens) headers.Authorization = `Bearer ${this.tokens.access}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const response = await fetch(`${this.base}/${path.replace(/^\//,'')}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    if (response.status === 401 && this.tokens && retry && !path.startsWith('auth/login/')) {
      const refreshResponse = await fetch(`${this.base}/auth/refresh/`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({refresh:this.tokens.refresh}) });
      if (refreshResponse.ok) {
        this.tokens.access = (await refreshResponse.json()).access;
        return this.request<T>(path, method, body, false, extra);
      }
      this.tokens = null;
    }
    const payload = response.status === 204 ? null : await response.json().catch(() => ({detail:'Unexpected server response'}));
    if (!response.ok) throw Object.assign(new Error(payload?.detail || payload?.error || 'Request failed'), {status:response.status, payload});
    return payload as T;
  }
}
