import type { ResearchSession, WatchProfile, NewsletterRun, Article } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export class ApiService {
  private static async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    let response: Response;
    try {
      response = await fetch(url, { ...options, headers });
    } catch {
      throw new Error(`Connexion impossible au serveur (${API_BASE_URL}). Vérifiez que le backend est démarré.`);
    }

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      const msg = error?.detail || error?.message || `Erreur ${response.status} — ${response.statusText}`;
      throw new Error(msg);
    }

    return response.json();
  }

  static async getSessions(limit = 20): Promise<{ sessions: ResearchSession[]; total: number }> {
    return this.request(`/sessions?limit=${limit}`);
  }

  static async getSession(id: string): Promise<ResearchSession> {
    return this.request(`/sessions/${id}`);
  }

  static async getWatchProfiles(activeOnly = false): Promise<WatchProfile[]> {
    return this.request(`/watch-profiles/?active_only=${activeOnly}`);
  }

  static async updateWatchProfile(id: string, data: Partial<WatchProfile>): Promise<WatchProfile> {
    return this.request(`/watch-profiles/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  static async createWatchProfile(data: {
    name: string;
    topics: string[];
    depth?: string;
    format?: string;
    angle?: string;
    language?: string;
    focus?: string;
    schedule_type?: string;
    schedule_time?: string;
    schedule_days?: string[];
    schedule_date?: string;
    schedule_interval_months?: number;
    is_active?: boolean;
  }): Promise<{ id: string; name: string }> {
    return this.request('/watch-profiles/', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  static async runProfile(id: string, options: { send_email?: boolean } = {}): Promise<{ session_id: string }> {
    return this.request(`/watch-profiles/${id}/run`, {
      method: 'POST',
      body: JSON.stringify(options),
    });
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

  static async getLLMProviders(): Promise<{
    providers: Array<{ name: string; base_url: string; default_model: string; requires_api_key: boolean }>;
    current_provider: string;
    current_model: string;
  }> {
    return this.request('/llm/providers');
  }

  static async checkProviderHealth(provider: string): Promise<{ provider: string; healthy: boolean; latency_ms: number }> {
    return this.request(`/llm/providers/${provider}/health`);
  }

  static async testSearchProvider(provider: string, query: string): Promise<{ ok: boolean; provider: string; results: any[]; error?: string }> {
    return this.request('/config/search/test', {
      method: 'POST',
      body: JSON.stringify({ provider, query }),
    });
  }

  static getStreamUrl(task: string, topics?: string[]): string {
    const params = new URLSearchParams({ task });
    if (topics) topics.forEach(t => params.append('topics', t));
    return `${API_BASE_URL}/orchestrator/stream?${params.toString()}`;
  }

  static openStream(task: string, topics?: string[]): EventSource {
    return new EventSource(ApiService.getStreamUrl(task, topics));
  }
}
