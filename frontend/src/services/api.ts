import type {
  ResearchSession,
  WatchProfile,
  WatchProfileRunResponse,
  EmailGroup,
  NewsletterRun,
  Article,
  CollectedSource,
  SessionLaunchPayload,
  SystemStats,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const ADMIN_TOKEN_KEY = 'tech-watch-admin-token';
const ADMIN_COOKIE_NAME = 'admin_token';
const ADMIN_TOKEN_EVENT = 'admin-token-changed';

export type ModelCatalogItem = {
  id: string;
  label: string;
  description?: string | null;
  context_window?: number | null;
  max_output_tokens?: number | null;
  dimensions?: number | null;
  capabilities: string[];
  recommended_role?: string | null;
  source: string;
  available?: boolean | null;
  family?: string | null;
  parameter_size?: string | null;
  quantization?: string | null;
  size_bytes?: number | null;
};

export type LLMProviderCatalog = {
  name: string;
  label?: string | null;
  base_url: string;
  default_model: string;
  requires_api_key: boolean;
  supports_dynamic_discovery?: boolean;
  discovery_error?: string | null;
  chat_models: ModelCatalogItem[];
  embedding_models: ModelCatalogItem[];
};

export type LLMProviderListResponse = {
  providers: LLMProviderCatalog[];
  current_provider: string;
  current_model: string;
  current_embedding_provider?: string | null;
  current_embedding_model?: string | null;
};

export class ApiService {
  private static readAdminToken(): string {
    if (typeof window === 'undefined') return '';
    return window.localStorage.getItem(ADMIN_TOKEN_KEY)?.trim() ?? '';
  }

  private static writeAdminCookie(token: string): void {
    if (typeof document === 'undefined') return;
    if (!token) {
      document.cookie = `${ADMIN_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`;
      return;
    }
    document.cookie = `${ADMIN_COOKIE_NAME}=${encodeURIComponent(token)}; path=/; max-age=2592000; SameSite=Lax`;
  }

  static getAdminToken(): string {
    return this.readAdminToken();
  }

  static hasAdminToken(): boolean {
    return Boolean(this.readAdminToken());
  }

  static setAdminToken(token: string): void {
    if (typeof window === 'undefined') return;
    const trimmed = token.trim();
    if (!trimmed) {
      this.clearAdminToken();
      return;
    }
    window.localStorage.setItem(ADMIN_TOKEN_KEY, trimmed);
    this.writeAdminCookie(trimmed);
    window.dispatchEvent(new CustomEvent(ADMIN_TOKEN_EVENT));
  }

  static clearAdminToken(): void {
    if (typeof window === 'undefined') return;
    window.localStorage.removeItem(ADMIN_TOKEN_KEY);
    this.writeAdminCookie('');
    window.dispatchEvent(new CustomEvent(ADMIN_TOKEN_EVENT));
  }

  static onAdminTokenChange(callback: () => void): () => void {
    if (typeof window === 'undefined') return () => {};
    window.addEventListener(ADMIN_TOKEN_EVENT, callback);
    return () => window.removeEventListener(ADMIN_TOKEN_EVENT, callback);
  }

  private static async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const adminToken = this.readAdminToken();
    const headers = {
      'Content-Type': 'application/json',
      ...(adminToken ? { 'X-Admin-Token': adminToken } : {}),
      ...options.headers,
    };

    let response: Response;
    try {
      response = await fetch(url, { ...options, headers, credentials: 'include' });
    } catch {
      throw new Error(`Connexion impossible au serveur (${API_BASE_URL}). Vérifiez que le backend est démarré.`);
    }

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      let msg = error?.detail || error?.message || `Erreur ${response.status} — ${response.statusText}`;
      if (response.status === 401 && !adminToken) {
        msg = 'Authentification admin requise. Configurez un token admin dans Paramètres > Sécurité.';
      }
      throw new Error(msg);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const raw = await response.text();
    if (!raw) {
      return undefined as T;
    }

    return JSON.parse(raw) as T;
  }

  static async getSessions(limit = 20): Promise<{ sessions: ResearchSession[]; total: number }> {
    return this.request(`/sessions?limit=${limit}`);
  }

  static async getSession(id: string): Promise<ResearchSession> {
    return this.request(`/sessions/${id}`);
  }

  static async deleteSession(id: string): Promise<void> {
    await this.request(`/sessions/${id}`, {
      method: 'DELETE',
    });
  }

  static async approveSession(sessionId: string): Promise<void> {
    await this.request(`/orchestrator/sessions/${sessionId}/approve`, { method: 'POST' });
  }

  static async rejectSession(sessionId: string): Promise<{ session_id: string; status: string }> {
    return this.request(`/orchestrator/sessions/${sessionId}/reject`, { method: 'POST' });
  }

  static async getWatchProfiles(activeOnly = false): Promise<WatchProfile[]> {
    return this.request(`/watch-profiles/?active_only=${activeOnly}`);
  }

  static async updateWatchProfile(id: string, data: Partial<WatchProfile> & { email_group_ids?: string[] }): Promise<WatchProfile> {
    return this.request(`/watch-profiles/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  static async deleteWatchProfile(id: string): Promise<void> {
    await this.request(`/watch-profiles/${id}`, {
      method: 'DELETE',
    });
  }

  static async createWatchProfile(data: {
    name: string;
    subject: string;
    topics: string[];
    depth?: string;
    format?: string;
    angle?: string;
    sources?: string[];
    language?: string;
    audience?: string;
    focus?: string;
    schedule_type?: string;
    schedule_time?: string;
    schedule_days?: string[];
    schedule_date?: string;
    schedule_interval_months?: number;
    email_group_ids?: string[];
    is_active?: boolean;
  }): Promise<WatchProfile> {
    return this.request('/watch-profiles/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async runProfile(id: string, options: { send_email?: boolean } = {}): Promise<WatchProfileRunResponse> {
    return this.request(`/watch-profiles/${id}/run`, {
      method: 'POST',
      body: JSON.stringify(options),
    });
  }

  static async getEmailGroups(activeOnly = false): Promise<EmailGroup[]> {
    return this.request(`/email-groups/?active_only=${activeOnly}`);
  }

  static async createEmailGroup(data: {
    name: string;
    description?: string;
    is_active?: boolean;
    recipients: Array<{ email: string; label?: string | null }>;
  }): Promise<EmailGroup> {
    return this.request('/email-groups/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async updateEmailGroup(id: string, data: {
    name?: string;
    description?: string | null;
    is_active?: boolean;
    recipients?: Array<{ email: string; label?: string | null }>;
  }): Promise<EmailGroup> {
    return this.request(`/email-groups/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  static async deleteEmailGroup(id: string): Promise<void> {
    await this.request(`/email-groups/${id}`, {
      method: 'DELETE',
    });
  }

  static async getSystemStats(): Promise<SystemStats> {
    return this.request('/stats');
  }

  static async getNewsletterHistory(limit = 10): Promise<NewsletterRun[]> {
    return this.request(`/newsletter/history?limit=${limit}`);
  }

  static async generateNewsletter(topics: string[], sendEmail = false): Promise<{
    run_id: string;
    subject: string;
    article_count: number;
    status: string;
    preview: string;
    email_sent: boolean;
    delivery_message: string;
  }> {
    return this.request('/newsletter/generate', {
      method: 'POST',
      body: JSON.stringify({ topics, send_email: sendEmail }),
    });
  }

  static async getSources(params: { limit?: number; sessionId?: string; query?: string; source?: string } = {}): Promise<CollectedSource[]> {
    const search = new URLSearchParams();
    if (params.limit) search.set('limit', String(params.limit));
    if (params.sessionId) search.set('session_id', params.sessionId);
    if (params.query) search.set('query', params.query);
    if (params.source) search.set('source', params.source);
    const qs = search.toString();
    return this.request(`/sources${qs ? `?${qs}` : ''}`);
  }

  static async getArticles(limit = 20, topic?: string): Promise<Article[]> {
    const params = new URLSearchParams({ limit: String(limit) });
    if (topic) params.set('topic', topic);
    return this.request(`/articles?${params.toString()}`);
  }

  static async getConfig(): Promise<Record<string, any>> {
    return this.request('/config');
  }

  static async updateConfig(updates: Record<string, any>): Promise<{ status: string; updated: string[] }> {
    return this.request('/config', {
      method: 'PATCH',
      body: JSON.stringify(updates),
    });
  }

  static async resetConfig(keys?: string[]): Promise<{ status: string; reset: string[] | string }> {
    return this.request('/config/reset', {
      method: 'POST',
      body: JSON.stringify(keys?.length ? { keys } : {}),
    });
  }

  static async getLLMProviders(): Promise<LLMProviderListResponse> {
    return this.request('/llm/providers');
  }

  static async checkProviderHealth(provider: string): Promise<{ provider: string; healthy: boolean; latency_ms: number }> {
    return this.request(`/llm/providers/${provider}/health`);
  }

  static async pullOllamaModel(model: string): Promise<{ status: string; provider: string; model: string; message: string }> {
    return this.request('/llm/ollama/pull', {
      method: 'POST',
      body: JSON.stringify({ model }),
    });
  }

  static async testSearchProvider(provider: string, query: string): Promise<{ ok: boolean; provider: string; results: any[]; error?: string }> {
    return this.request('/config/search/test', {
      method: 'POST',
      body: JSON.stringify({ provider, query }),
    });
  }

  static async createSession(payload: SessionLaunchPayload): Promise<{ session_id: string; stream_url: string }> {
    return this.request('/orchestrator/sessions', {
      method: 'POST',
      body: JSON.stringify({
        subject: payload.subject,
        title: payload.title || undefined,
        research_instructions: payload.researchInstructions || undefined,
        topics: payload.topics,
        send_email: false,
        autonomous: true,
      }),
    });
  }

  static getStreamUrl(payload: SessionLaunchPayload, sessionId?: string): string {
    const params = new URLSearchParams({ subject: payload.subject });
    if (payload.title) params.set('title', payload.title);
    if (payload.researchInstructions) params.set('research_instructions', payload.researchInstructions);
    payload.topics.forEach(t => params.append('topics', t));
    if (sessionId) params.set('session_id', sessionId);
    return `${API_BASE_URL}/orchestrator/stream?${params.toString()}`;
  }

  static openStream(payload: SessionLaunchPayload, sessionId?: string): EventSource {
    return new EventSource(ApiService.getStreamUrl(payload, sessionId));
  }
}
