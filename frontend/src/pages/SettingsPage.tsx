import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Cpu,
  Database,
  Eye,
  EyeOff,
  Globe,
  KeyRound,
  Loader2,
  Mail,
  RotateCcw,
  Search,
  Settings2,
  Shield,
} from 'lucide-react';
import { ApiService, type LLMProviderCatalog, type ModelCatalogItem as ApiModelCatalogItem } from '../services/api';

// ── Types ─────────────────────────────────────────────────────────────────────
type Tab = 'models' | 'search' | 'delivery' | 'security' | 'system';

type RuntimeConfig = Record<string, any> & {
  app_env?: string;
  app_port?: number;
  llm_provider?: string;
  llm_model?: string;
  llm_fallback_models?: string[];
  llm_provider_models?: Record<string, { primary_model?: string; fallback_models?: string[] }>;
  embedding_provider?: string;
  embedding_model?: string;
  embedding_provider_models?: Record<string, string>;
  semantic_scholar_api_key?: string;
  github_api_token?: string;
  search_web_providers?: string[];
  search_free_providers?: string[];
  search_academic_providers?: string[];
  search_code_providers?: string[];
  timezone?: string;
  log_level?: string;
  sender_email?: string;
  recipient_emails?: string[];
  gmail_credentials_json?: string;
  gmail_token_json?: string;
  gmail_credentials_path?: string;
  gmail_token_path?: string;
  schedule_times?: string[];
  newsletter_topics?: string[];
  _encryption_active?: boolean;
  _sensitive_configured?: Record<string, boolean>;
};

type CatalogModel = ApiModelCatalogItem;

type ProviderCatalog = LLMProviderCatalog & {
  chat_models?: CatalogModel[];
  embedding_models?: CatalogModel[];
};

const TABS: Array<{ id: Tab; label: string }> = [
  { id: 'models', label: 'Models' },
  { id: 'search', label: 'Search & Crawl' },
  { id: 'delivery', label: 'Email & Newsletter' },
  { id: 'security', label: 'Sécurité' },
  { id: 'system', label: 'Runtime' },
];

const OLLAMA_PULL_SUGGESTIONS = {
  chat: [
    { id: "llama3.2", label: "Llama 3.2" },
    { id: "nemotron-3-nano", label: "Nemotron 3 Nano" },
  ],
  embedding: [
    { id: "embeddinggemma", label: "EmbeddingGemma" },
    { id: "all-minilm", label: "all-minilm" },
  ],
};

const SECRET_LABELS: Record<string, string> = {
  llm_api_key: 'LLM principal',
  zai_api_key: 'Z.ai dédié',
  tavily_api_key: 'Tavily',
  serper_api_key: 'Serper',
  semantic_scholar_api_key: 'Semantic Scholar',
  github_api_token: 'GitHub',
  exa_api_key: 'Exa',
  langsearch_api_key: 'LangSearch',
  jina_api_key: 'Jina',
  gmail_credentials_json: 'Gmail OAuth client',
  gmail_token_json: 'Gmail OAuth token',
};

const gridColumns = 'repeat(auto-fit, minmax(320px, 1fr))';
const twoColGrid: React.CSSProperties = { display: 'grid', gridTemplateColumns: gridColumns, gap: '24px', alignItems: 'start' };
const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  backgroundColor: 'rgba(255,255,255,0.04)',
  border: '1px solid var(--border-color)',
  borderRadius: '10px',
  color: 'var(--text-primary)',
  fontSize: '0.875rem',
  outline: 'none',
  fontFamily: 'inherit',
};

// ── Primitives ────────────────────────────────────────────────────────────────
const Field = ({ label, hint, children, full }: { label: string; hint?: string; children: React.ReactNode; full?: boolean }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', gridColumn: full ? '1 / -1' : undefined }}>
    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>{label}</label>
    {children}
    {hint && <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>{hint}</span>}
  </div>
);

const Card = ({ title, icon: Icon, children, accent }: { title: string; icon?: any; children: React.ReactNode; accent?: string }) => (
  <div
    className="card"
    style={{
      padding: '22px',
      display: 'flex',
      flexDirection: 'column',
      gap: '16px',
      background: accent
        ? `linear-gradient(180deg, ${accent}08 0%, rgba(17,24,39,0.42) 100%)`
        : 'rgba(17,24,39,0.42)',
    }}
  >
    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', paddingBottom: '12px', borderBottom: '1px solid var(--border-color)' }}>
      {Icon && <Icon size={16} color="var(--accent-primary)" />}
      <h3 style={{ fontSize: '0.95rem', fontWeight: 700 }}>{title}</h3>
    </div>
    {children}
  </div>
);

const TxtInput = ({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) => (
  <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} style={inputStyle} />
);

const NumInput = ({ value, onChange, min, max, step }: { value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number }) => (
  <input
    type="number"
    value={Number.isFinite(value) ? value : 0}
    min={min}
    max={max}
    step={step}
    onChange={(e) => onChange(Number(e.target.value))}
    style={inputStyle}
  />
);

const Sel = ({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: Array<{ value: string; label: string }> }) => (
  <select value={value} onChange={(e) => onChange(e.target.value)} style={{ ...inputStyle, cursor: 'pointer' }}>
    {options.map((option) => (
      <option key={option.value} value={option.value}>{option.label}</option>
    ))}
  </select>
);

const TA = ({ value, onChange, placeholder, rows = 4 }: { value: string; onChange: (v: string) => void; placeholder?: string; rows?: number }) => (
  <textarea
    value={value}
    onChange={(e) => onChange(e.target.value)}
    placeholder={placeholder}
    rows={rows}
    style={{ ...inputStyle, resize: 'vertical', lineHeight: '1.55' }}
  />
);

const Secret = ({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) => {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <input
        type={show ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? 'sk-••••••••'}
        style={{ ...inputStyle, paddingRight: '42px' }}
      />
      <button
        type="button"
        onClick={() => setShow((prev) => !prev)}
        style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
      >
        {show ? <EyeOff size={14} /> : <Eye size={14} />}
      </button>
    </div>
  );
};

const SecretArea = ({ value, onChange, placeholder, rows = 6 }: { value: string; onChange: (v: string) => void; placeholder?: string; rows?: number }) => {
  const [show, setShow] = useState(false);
  const masked = value && !show ? '••••••••' : value;

  return (
    <div style={{ position: 'relative' }}>
      <textarea
        value={masked}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        readOnly={Boolean(value) && !show}
        style={{ ...inputStyle, resize: 'vertical', lineHeight: '1.55', paddingRight: '42px', fontFamily: 'monospace' }}
      />
      <button
        type="button"
        onClick={() => setShow((prev) => !prev)}
        style={{ position: 'absolute', right: '10px', top: '12px', color: 'var(--text-muted)' }}
      >
        {show ? <EyeOff size={14} /> : <Eye size={14} />}
      </button>
    </div>
  );
};

const Pill = ({ children, tone = 'default' }: { children: React.ReactNode; tone?: 'default' | 'success' | 'warning' }) => {
  const styles: Record<string, React.CSSProperties> = {
    default: {
      color: 'var(--text-secondary)',
      backgroundColor: 'rgba(255,255,255,0.04)',
      border: '1px solid var(--border-color)',
    },
    success: {
      color: 'var(--status-success)',
      backgroundColor: 'rgba(34,197,94,0.08)',
      border: '1px solid rgba(34,197,94,0.18)',
    },
    warning: {
      color: '#F59E0B',
      backgroundColor: 'rgba(245,158,11,0.08)',
      border: '1px solid rgba(245,158,11,0.18)',
    },
  };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '6px 10px', borderRadius: '999px', fontSize: '0.74rem', fontWeight: 600, ...styles[tone] }}>
      {children}
    </span>
  );
};

const formatTokenCount = (value?: number | null) => {
  if (!value || value <= 0) return '—';
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(value % 1_000_000 === 0 ? 0 : 1)}M`;
  if (value >= 1_000) return `${(value / 1_000).toFixed(value % 1_000 === 0 ? 0 : 1)}K`;
  return String(value);
};

const formatBytes = (value?: number | null) => {
  if (!value || value <= 0) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = value;
  let idx = 0;
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024;
    idx += 1;
  }
  return `${size.toFixed(size >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
};

const ModelCatalogCard = ({
  model,
  active,
  inFallback,
  onUse,
  onToggleFallback,
  canFallback = true,
}: {
  model: CatalogModel;
  active: boolean;
  inFallback: boolean;
  onUse: () => void;
  onToggleFallback?: () => void;
  canFallback?: boolean;
}) => {
  const tone = active ? 'rgba(34,197,94,0.08)' : 'rgba(255,255,255,0.02)';
  const border = active ? '1px solid rgba(34,197,94,0.22)' : '1px solid var(--border-color)';
  return (
    <div style={{ padding: '12px 14px', borderRadius: '12px', border, backgroundColor: tone, display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <strong style={{ fontSize: '0.84rem' }}>{model.label}</strong>
            {model.recommended_role && <Pill tone={active ? 'success' : 'default'}>{model.recommended_role}</Pill>}
            {model.source === 'ollama-discovered' && <Pill tone="success">local</Pill>}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'monospace', marginTop: '4px' }}>{model.id}</div>
        </div>
        {active && <Pill tone="success">principal</Pill>}
      </div>

      {model.description && <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>{model.description}</div>}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
        <Pill>ctx {formatTokenCount(model.context_window)}</Pill>
        {typeof model.max_output_tokens === 'number' && <Pill>out {formatTokenCount(model.max_output_tokens)}</Pill>}
        {typeof model.dimensions === 'number' && <Pill>{model.dimensions}d</Pill>}
        {model.parameter_size && <Pill>{model.parameter_size}</Pill>}
        {model.quantization && <Pill>{model.quantization}</Pill>}
        {typeof model.size_bytes === 'number' && <Pill>{formatBytes(model.size_bytes)}</Pill>}
      </div>

      {model.capabilities?.length ? (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {model.capabilities.join(' · ')}
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button type="button" onClick={onUse} style={{ padding: '7px 12px', borderRadius: '9px', backgroundColor: 'var(--accent-primary)', color: 'white', fontSize: '0.78rem', fontWeight: 700 }}>
          {active ? 'Sélectionné' : 'Utiliser'}
        </button>
        {canFallback && onToggleFallback && (
          <button type="button" onClick={onToggleFallback} style={{ padding: '7px 12px', borderRadius: '9px', border: '1px solid var(--border-color)', color: inFallback ? 'var(--accent-secondary)' : 'var(--text-secondary)', backgroundColor: inFallback ? 'rgba(56,189,248,0.1)' : 'rgba(255,255,255,0.03)', fontSize: '0.78rem', fontWeight: 700 }}>
            {inFallback ? 'Retirer fallback' : 'Ajouter fallback'}
          </button>
        )}
      </div>
    </div>
  );
};

const SearchTestBtn = ({ provider, query = 'IA news 2026' }: { provider: string; query?: string }) => {
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle');
  const [result, setResult] = useState<{ results: any[]; error?: string } | null>(null);

  const test = async () => {
    setStatus('loading');
    setResult(null);
    try {
      const res = await ApiService.testSearchProvider(provider, query);
      setResult(res);
      setStatus(res.ok ? 'ok' : 'error');
    } catch (error: any) {
      setResult({ results: [], error: error.message });
      setStatus('error');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <button
        type="button"
        onClick={test}
        disabled={status === 'loading'}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          alignSelf: 'flex-start',
          padding: '7px 14px',
          borderRadius: '8px',
          border: '1px solid var(--border-color)',
          color: 'var(--text-secondary)',
          fontSize: '0.8rem',
          fontWeight: 600,
          backgroundColor: 'rgba(255,255,255,0.03)',
        }}
      >
        {status === 'loading' ? <Loader2 size={13} className="animate-spin" /> : <Activity size={13} />}
        {status === 'loading' ? 'Test en cours...' : 'Tester'}
      </button>

      {status !== 'idle' && status !== 'loading' && (
        <div
          style={{
            padding: '10px 12px',
            borderRadius: '8px',
            fontSize: '0.78rem',
            backgroundColor: status === 'ok' ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
            border: `1px solid ${status === 'ok' ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
          }}
        >
          {status === 'ok' ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--status-success)', fontWeight: 600, marginBottom: result?.results?.length ? '6px' : 0 }}>
                <CheckCircle2 size={13} /> Connecté — {result?.results?.length ?? 0} résultat(s)
              </div>
              {result?.results?.slice(0, 2).map((item: any, index: number) => (
                <div key={index} style={{ color: 'var(--text-muted)', paddingLeft: '19px', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {item.title || item.url}
                </div>
              ))}
            </>
          ) : (
            <div style={{ display: 'flex', gap: '6px', color: 'var(--status-error)' }}>
              <AlertCircle size={13} style={{ marginTop: '1px', flexShrink: 0 }} />
              <span>{result?.error ?? 'Connexion échouée'}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const ProviderToggleGroup = ({
  label,
  hint,
  value,
  options,
  onChange,
}: {
  label: string;
  hint?: string;
  value: string[];
  options: Array<{ value: string; label: string }>;
  onChange: (next: string[]) => void;
}) => {
  const current = Array.isArray(value) ? value : [];
  const toggle = (provider: string) => {
    if (current.includes(provider)) {
      onChange(current.filter((item) => item !== provider));
      return;
    }
    onChange([...current, provider]);
  };

  return (
    <Field label={label} hint={hint} full>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
        {options.map((option) => {
          const active = current.includes(option.value);
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => toggle(option.value)}
              style={{
                padding: '8px 12px',
                borderRadius: '999px',
                border: active ? '1px solid rgba(56,189,248,0.36)' : '1px solid var(--border-color)',
                backgroundColor: active ? 'rgba(56,189,248,0.12)' : 'rgba(255,255,255,0.03)',
                color: active ? 'var(--accent-secondary)' : 'var(--text-secondary)',
                fontSize: '0.78rem',
                fontWeight: 700,
              }}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </Field>
  );
};

const ProviderBlock = ({
  name,
  badge,
  badgeBg,
  description,
  providerKey,
  keyField,
  urlField,
  cfg,
  setCfg,
}: any) => (
  <Card title={name} icon={Search}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', margin: 0, lineHeight: '1.45' }}>{description}</p>
      <span style={{ fontSize: '0.63rem', padding: '2px 7px', borderRadius: '999px', backgroundColor: badgeBg, fontWeight: 700, whiteSpace: 'nowrap' }}>{badge}</span>
    </div>
    {keyField && (
      <Field label="Clé API">
        <Secret value={cfg[keyField] ?? ''} onChange={(value) => setCfg(keyField, value)} />
      </Field>
    )}
    {urlField && (
      <Field label="URL du serveur">
        <TxtInput value={cfg[urlField] ?? ''} onChange={(value) => setCfg(urlField, value)} placeholder="http://localhost:8080" />
      </Field>
    )}
    <SearchTestBtn provider={providerKey} />
  </Card>
);

const BootstrappingState = ({
  loadError,
  adminToken,
  setAdminToken,
  onRetry,
  onClearAdminToken,
}: {
  loadError: string;
  adminToken: string;
  setAdminToken: (value: string) => void;
  onRetry: () => void;
  onClearAdminToken: () => void;
}) => (
  <div style={{ display: 'grid', placeItems: 'center', minHeight: '60vh' }}>
    <div style={{ width: 'min(760px, 100%)', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <Card title="Accès requis" icon={Shield} accent="rgba(245,158,11,0.2)">
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start', padding: '14px 16px', borderRadius: '10px', border: '1px solid rgba(245,158,11,0.18)', backgroundColor: 'rgba(245,158,11,0.06)' }}>
          <AlertCircle size={18} color="#F59E0B" style={{ marginTop: '1px', flexShrink: 0 }} />
          <div>
            <div style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: '4px' }}>Impossible de charger la configuration</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>{loadError}</div>
          </div>
        </div>
        <Field label="Token admin" hint="Configurez le token puis relancez le chargement.">
          <Secret value={adminToken} onChange={setAdminToken} placeholder="Collez votre token admin" />
        </Field>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button type="button" onClick={() => ApiService.setAdminToken(adminToken)} style={{ padding: '10px 14px', borderRadius: '10px', backgroundColor: 'var(--accent-primary)', color: 'white', fontSize: '0.85rem', fontWeight: 700 }}>
            Enregistrer le token
          </button>
          <button type="button" onClick={onRetry} style={{ padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: 700 }}>
            Réessayer
          </button>
          <button type="button" onClick={onClearAdminToken} style={{ padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: 700 }}>
            Effacer
          </button>
        </div>
      </Card>
    </div>
  </div>
);

// ── Main page ─────────────────────────────────────────────────────────────────
export const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('models');
  const [cfg, setRawCfg] = useState<RuntimeConfig>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'ok' | 'error'>('idle');
  const [providers, setProviders] = useState<any[]>([]);
  const [health, setHealth] = useState<Record<string, { healthy: boolean; latency_ms: number } | null>>({});
  const [dirty, setDirty] = useState<Record<string, any>>({});
  const [adminToken, setAdminToken] = useState(() => ApiService.getAdminToken());
  const [ollamaPullModel, setOllamaPullModel] = useState('');
  const [ollamaPulling, setOllamaPulling] = useState(false);
  const [ollamaPullStatus, setOllamaPullStatus] = useState<string | null>(null);
  const [ollamaPullError, setOllamaPullError] = useState<string | null>(null);
  const [autoSaveError, setAutoSaveError] = useState<string | null>(null);

  const loadConfig = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [config, providerData] = await Promise.all([
        ApiService.getConfig(),
        ApiService.getLLMProviders().catch(() => ({ providers: [] })),
      ]);
      setRawCfg(config as RuntimeConfig);
      setProviders((providerData as any).providers ?? []);
    } catch (error: any) {
      setLoadError(error?.message ?? 'Chargement impossible');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadConfig();
  }, []);

  useEffect(() => ApiService.onAdminTokenChange(() => setAdminToken(ApiService.getAdminToken())), []);

  const setCfg = (key: string, value: any) => {
    setRawCfg((prev) => ({ ...prev, [key]: value }));
    setDirty((prev) => ({ ...prev, [key]: value }));
    setSaveStatus('idle');
    setAutoSaveError(null);
  };

  const handleSave = async (snapshot: Record<string, any> = dirty) => {
    if (!Object.keys(snapshot).length) return;
    setSaving(true);
    setAutoSaveError(null);
    try {
      await ApiService.updateConfig(snapshot);
      setDirty((prev) => {
        const next = { ...prev };
        for (const [key, value] of Object.entries(snapshot)) {
          if (JSON.stringify(next[key]) === JSON.stringify(value)) {
            delete next[key];
          }
        }
        return next;
      });
      setSaveStatus('ok');
      window.setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error: any) {
      setSaveStatus('error');
      setAutoSaveError(error?.message ?? 'Sauvegarde automatique impossible');
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    if (loading || saving || !Object.keys(dirty).length) return;

    const snapshot = { ...dirty };
    const timeout = window.setTimeout(() => {
      void handleSave(snapshot);
    }, 700);

    return () => window.clearTimeout(timeout);
  }, [dirty, loading, saving]);

  const handleResetOverrides = async () => {
    if (!window.confirm('Réinitialiser tous les overrides runtime stockés en base ?')) return;
    setSaving(true);
    try {
      await ApiService.resetConfig();
      setDirty({});
      await loadConfig();
      setSaveStatus('ok');
      window.setTimeout(() => setSaveStatus('idle'), 3000);
    } catch {
      setSaveStatus('error');
    } finally {
      setSaving(false);
    }
  };

  const handleCheckHealth = async (provider: string) => {
    try {
      const result = await ApiService.checkProviderHealth(provider);
      setHealth((prev) => ({ ...prev, [provider]: result }));
    } catch {
      setHealth((prev) => ({ ...prev, [provider]: { healthy: false, latency_ms: 0 } }));
    }
  };

  const handleClearAdminToken = () => {
    ApiService.clearAdminToken();
    setAdminToken('');
  };

  const providerCatalogs = providers as ProviderCatalog[];
  const providerOptions = providerCatalogs.length
    ? providerCatalogs.map((provider) => ({ value: provider.name, label: provider.label ?? provider.name }))
    : [
        { value: 'ollama', label: 'Ollama (local)' },
        { value: 'openrouter', label: 'OpenRouter' },
        { value: 'openai', label: 'OpenAI' },
        { value: 'zai', label: 'Z.ai' },
      ];

  const activeLLMProvider = cfg.llm_provider ?? 'ollama';
  const activeEmbeddingProvider = cfg.embedding_provider ?? 'openai';
  const llmProviderModels = cfg.llm_provider_models ?? {};
  const embeddingProviderModels = cfg.embedding_provider_models ?? {};

  const currentProviderMeta = providerCatalogs.find((provider) => provider.name === activeLLMProvider);
  const currentEmbeddingProviderMeta = providerCatalogs.find((provider) => provider.name === activeEmbeddingProvider);
  const savedProviderModels = llmProviderModels[activeLLMProvider] ?? {};
  const savedEmbeddingModel = embeddingProviderModels[activeEmbeddingProvider] ?? '';
  const rawActiveLLMModel = cfg.llm_model ?? savedProviderModels.primary_model ?? currentProviderMeta?.default_model ?? '';
  const llmFallbacks = Array.isArray(cfg.llm_fallback_models)
    ? cfg.llm_fallback_models
    : (Array.isArray(savedProviderModels.fallback_models) ? savedProviderModels.fallback_models : []);
  const rawActiveEmbeddingModel = cfg.embedding_model ?? savedEmbeddingModel ?? '';
  const chatModels = currentProviderMeta?.chat_models ?? [];
  const embeddingModels = currentEmbeddingProviderMeta?.embedding_models ?? [];
  const chatModelOptions = chatModels.map((model) => ({ value: model.id, label: model.label ? `${model.label} (${model.id})` : model.id }));
  const embeddingModelOptions = embeddingModels.map((model) => ({ value: model.id, label: model.label ? `${model.label} (${model.id})` : model.id }));
  const showOllamaManager = activeLLMProvider === 'ollama' || activeEmbeddingProvider === 'ollama';
  const activeLLMModel = chatModels.some((model) => model.id === rawActiveLLMModel)
    ? rawActiveLLMModel
    : (chatModels[0]?.id ?? '');
  const activeEmbeddingModel = embeddingModels.some((model) => model.id === rawActiveEmbeddingModel)
    ? rawActiveEmbeddingModel
    : (embeddingModels[0]?.id ?? '');
  const showLLMCatalog = activeLLMProvider !== 'ollama';
  const showEmbeddingCatalog = activeEmbeddingProvider !== 'ollama';

  const sensitiveConfigured = cfg._sensitive_configured ?? {};
  const configuredSecrets = useMemo(
    () => Object.entries(SECRET_LABELS).filter(([key]) => sensitiveConfigured[key]),
    [sensitiveConfigured],
  );
  const sensitiveCount = configuredSecrets.length;
  const hasDirty = Object.keys(dirty).length > 0;
  const topicCount = Array.isArray(cfg.newsletter_topics) ? cfg.newsletter_topics.length : 0;
  const emailGroupsLabel = 'Email groups via profils';

const setProviderModelPreferences = (provider: string, primaryModel: string, fallbackModels: string[]) => {
  setCfg('llm_provider_models', {
    ...llmProviderModels,
    [provider]: {
      primary_model: primaryModel,
      fallback_models: fallbackModels,
    },
  });
};

const setEmbeddingProviderPreference = (provider: string, modelId: string) => {
  setCfg('embedding_provider_models', {
    ...embeddingProviderModels,
    [provider]: modelId,
  });
};

const handleLLMProviderChange = (provider: string) => {
  const nextProviderMeta = providerCatalogs.find((item) => item.name === provider);
  const nextPrefs = llmProviderModels[provider] ?? {};
  const nextPrimary = nextPrefs.primary_model ?? nextProviderMeta?.default_model ?? '';
  const nextFallbacks = Array.isArray(nextPrefs.fallback_models) ? nextPrefs.fallback_models : [];
  const shouldSyncBaseUrl = !cfg.llm_base_url || cfg.llm_base_url === (currentProviderMeta?.base_url ?? '');

  setCfg('llm_provider', provider);
  setCfg('llm_model', nextPrimary);
  setCfg('llm_fallback_models', nextFallbacks);
  if (shouldSyncBaseUrl && nextProviderMeta?.base_url) {
    setCfg('llm_base_url', nextProviderMeta.base_url);
  }
};

const handleEmbeddingProviderChange = (provider: string) => {
  const nextProviderMeta = providerCatalogs.find((item) => item.name === provider);
  const nextModel = embeddingProviderModels[provider] ?? nextProviderMeta?.embedding_models?.[0]?.id ?? '';

  setCfg('embedding_provider', provider);
  setCfg('embedding_model', nextModel);
};

const setFallbackModelsValue = (models: string[]) => {
  const cleaned = models.filter(Boolean);
  setCfg('llm_fallback_models', cleaned);
  setProviderModelPreferences(activeLLMProvider, activeLLMModel, cleaned);
};

const toggleFallbackModel = (modelId: string) => {
  const next = llmFallbacks.includes(modelId)
    ? llmFallbacks.filter((item) => item !== modelId)
    : [...llmFallbacks, modelId];
  setFallbackModelsValue(next.filter((item) => item !== activeLLMModel));
};

const selectPrimaryModel = (modelId: string) => {
  const nextFallbacks = llmFallbacks.filter((item) => item !== modelId);
  setCfg('llm_model', modelId);
  setCfg('llm_fallback_models', nextFallbacks);
  setProviderModelPreferences(activeLLMProvider, modelId, nextFallbacks);
};

const selectEmbeddingModel = (modelId: string) => {
  setCfg('embedding_model', modelId);
  setEmbeddingProviderPreference(activeEmbeddingProvider, modelId);
};

const handlePullOllamaModel = async (modelId: string) => {
  const targetModel = modelId.trim();
  if (!targetModel) return;

  setOllamaPulling(true);
  setOllamaPullError(null);
  setOllamaPullStatus(null);
  try {
    const result = await ApiService.pullOllamaModel(targetModel);
    setOllamaPullStatus(result.message);
    setOllamaPullModel('');
    await loadConfig();
  } catch (error: any) {
    setOllamaPullError(error?.message ?? 'Pull Ollama impossible');
  } finally {
    setOllamaPulling(false);
  }
};

  const ModelsTab = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={twoColGrid}>
        <Card title="LLM principal" icon={Cpu} accent="rgba(124,140,255,0.18)">
          <div style={twoColGrid}>
            <Field label="Provider">
              <Sel value={activeLLMProvider} onChange={handleLLMProviderChange} options={providerOptions} />
            </Field>
            <Field label="Modèle actif" hint={`Défaut provider : ${currentProviderMeta?.default_model || '—'}`}>
              {chatModelOptions.length > 0 ? (
                <Sel value={activeLLMModel} onChange={selectPrimaryModel} options={chatModelOptions} />
              ) : (
                <div style={{ ...inputStyle, minHeight: '42px', display: 'flex', alignItems: 'center', color: 'var(--text-muted)' }}>
                  None
                </div>
              )}
            </Field>
            <Field label="Clé API principale" full hint="Utilisée pour OpenAI / OpenRouter. Vide si provider local sans auth.">
              <Secret value={cfg.llm_api_key ?? ''} onChange={(value) => setCfg('llm_api_key', value)} />
            </Field>
            <Field label="Base URL" full hint="Le runtime l'utilise maintenant réellement pour le provider actif.">
              <TxtInput value={cfg.llm_base_url ?? ''} onChange={(value) => setCfg('llm_base_url', value)} placeholder={currentProviderMeta?.base_url ?? 'http://localhost:11434/v1'} />
            </Field>
            <Field label={`Température : ${cfg.llm_temperature ?? 0.3}`} full hint="0 = déterministe, 1 = plus créatif.">
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={cfg.llm_temperature ?? 0.3}
                onChange={(e) => setCfg('llm_temperature', parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent-primary)', cursor: 'pointer' }}
              />
            </Field>
            <Field label="Max tokens">
              <NumInput value={cfg.llm_max_tokens ?? 2000} onChange={(value) => setCfg('llm_max_tokens', value)} min={256} max={128000} step={256} />
            </Field>
            <Field label="Fallbacks" hint="Utilise les cartes ci-dessous pour activer ou retirer les fallbacks disponibles pour ce provider.">
              <div style={{ ...inputStyle, minHeight: '42px', display: 'flex', alignItems: 'center', color: llmFallbacks.length ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                {llmFallbacks.length ? llmFallbacks.join(', ') : 'Aucun fallback sélectionné'}
              </div>
            </Field>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => handleCheckHealth(activeLLMProvider)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 14px', borderRadius: '8px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.82rem', fontWeight: 600 }}
            >
              <Activity size={13} /> Tester le provider
            </button>
            {health[activeLLMProvider] && (
              <Pill tone={health[activeLLMProvider]?.healthy ? 'success' : 'warning'}>
                {health[activeLLMProvider]?.healthy ? 'Connecté' : 'Inaccessible'}
                {health[activeLLMProvider]?.healthy ? ` · ${health[activeLLMProvider]?.latency_ms}ms` : ''}
              </Pill>
            )}
            {currentProviderMeta?.supports_dynamic_discovery && (
              <Pill tone={currentProviderMeta?.discovery_error ? 'warning' : 'success'}>
                {currentProviderMeta?.discovery_error ? 'Découverte Ollama indisponible' : 'Découverte Ollama active'}
              </Pill>
            )}
          </div>

          {currentProviderMeta?.discovery_error && (
            <div style={{ padding: '12px 14px', borderRadius: '10px', border: '1px solid rgba(245,158,11,0.18)', backgroundColor: 'rgba(245,158,11,0.06)', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
              {currentProviderMeta.discovery_error}
            </div>
          )}
        </Card>

        <Card title="Embeddings & clés dédiées" icon={Database}>
          <div style={twoColGrid}>
            <Field label="Provider d'embedding">
              <Sel
                value={activeEmbeddingProvider}
                onChange={handleEmbeddingProviderChange}
                options={providerOptions}
              />
            </Field>
            <Field label="Modèle d'embedding actif">
              {embeddingModelOptions.length > 0 ? (
                <Sel value={activeEmbeddingModel} onChange={selectEmbeddingModel} options={embeddingModelOptions} />
              ) : (
                <div style={{ ...inputStyle, minHeight: '42px', display: 'flex', alignItems: 'center', color: 'var(--text-muted)' }}>
                  None
                </div>
              )}
            </Field>
            <Field label="Clé dédiée Z.ai" full hint="Optionnelle. Si vide, le runtime retombe sur la clé LLM principale.">
              <Secret value={cfg.zai_api_key ?? ''} onChange={(value) => setCfg('zai_api_key', value)} />
            </Field>
          </div>
          <div style={{ padding: '12px 14px', borderRadius: '10px', border: '1px solid rgba(124,140,255,0.12)', backgroundColor: 'rgba(124,140,255,0.04)', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
            Les embeddings utilisent maintenant leur propre provider/runtime. OpenRouter est maintenant supporté comme vrai provider d'embedding, et Ollama sépare automatiquement les modèles de chat et d'embedding quand il est disponible.
          </div>
        </Card>
      </div>

      {(showLLMCatalog || showEmbeddingCatalog) && (
        <div style={twoColGrid}>
          {showLLMCatalog && (
            <Card title={`Catalogue LLM · ${currentProviderMeta?.label ?? cfg.llm_provider ?? 'provider'}`} icon={Cpu} accent="rgba(124,140,255,0.12)">
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
                Choisis un modèle principal et construis les fallbacks par clic.
              </div>
              <div style={{ display: 'grid', gap: '12px' }}>
                {chatModels.length > 0 ? chatModels.map((model) => (
                  <ModelCatalogCard
                    key={model.id}
                    model={model}
                    active={activeLLMModel === model.id}
                    inFallback={llmFallbacks.includes(model.id)}
                    onUse={() => selectPrimaryModel(model.id)}
                    onToggleFallback={() => toggleFallbackModel(model.id)}
                  />
                )) : (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.55' }}>Aucun modèle remonté pour ce provider.</div>
                )}
              </div>
            </Card>
          )}

          {showEmbeddingCatalog && (
            <Card title={`Catalogue Embeddings · ${currentEmbeddingProviderMeta?.label ?? cfg.embedding_provider ?? 'provider'}`} icon={Database}>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
                Sélection rapide des modèles d'embedding pertinents.
              </div>
              <div style={{ display: 'grid', gap: '12px' }}>
                {embeddingModels.length > 0 ? embeddingModels.map((model) => (
                  <ModelCatalogCard
                    key={model.id}
                    model={model}
                    active={activeEmbeddingModel === model.id}
                    inFallback={false}
                    onUse={() => selectEmbeddingModel(model.id)}
                    canFallback={false}
                  />
                )) : (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.55' }}>Aucun modèle d'embedding remonté pour ce provider.</div>
                )}
              </div>
            </Card>
          )}
        </div>
      )}

      {showOllamaManager && (
        <Card title="Gestion Ollama" icon={Database} accent="rgba(16,185,129,0.12)">
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
            Pull des modèles locaux depuis l'UI. Une fois le téléchargement terminé, le catalogue Ollama est rechargé automatiquement.
          </div>

          <div style={twoColGrid}>
            <Field label="LLM suggérés">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                {OLLAMA_PULL_SUGGESTIONS.chat.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handlePullOllamaModel(item.id)}
                    disabled={ollamaPulling}
                    style={{ padding: '8px 12px', borderRadius: '999px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', backgroundColor: 'rgba(255,255,255,0.03)', fontSize: '0.78rem', fontWeight: 700, opacity: ollamaPulling ? 0.7 : 1 }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </Field>

            <Field label="Embeddings suggérés">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
                {OLLAMA_PULL_SUGGESTIONS.embedding.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handlePullOllamaModel(item.id)}
                    disabled={ollamaPulling}
                    style={{ padding: '8px 12px', borderRadius: '999px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', backgroundColor: 'rgba(255,255,255,0.03)', fontSize: '0.78rem', fontWeight: 700, opacity: ollamaPulling ? 0.7 : 1 }}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </Field>

            <Field label="Pull custom" full hint="Exemples: qwen3:8b, mistral-small, nomic-embed-text">
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <div style={{ flex: '1 1 320px' }}>
                  <TxtInput value={ollamaPullModel} onChange={setOllamaPullModel} placeholder="nom_du_modele[:tag]" />
                </div>
                <button
                  type="button"
                  onClick={() => handlePullOllamaModel(ollamaPullModel)}
                  disabled={ollamaPulling || !ollamaPullModel.trim()}
                  style={{ padding: '10px 14px', borderRadius: '10px', backgroundColor: 'var(--accent-primary)', color: 'white', fontSize: '0.82rem', fontWeight: 700, opacity: ollamaPulling || !ollamaPullModel.trim() ? 0.7 : 1 }}
                >
                  {ollamaPulling ? 'Pull en cours...' : 'Pull model'}
                </button>
              </div>
            </Field>
          </div>

          {ollamaPullStatus && (
            <div style={{ padding: '12px 14px', borderRadius: '10px', border: '1px solid rgba(34,197,94,0.2)', backgroundColor: 'rgba(34,197,94,0.06)', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
              {ollamaPullStatus}
            </div>
          )}
          {ollamaPullError && (
            <div style={{ padding: '12px 14px', borderRadius: '10px', border: '1px solid rgba(239,68,68,0.2)', backgroundColor: 'rgba(239,68,68,0.06)', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
              {ollamaPullError}
            </div>
          )}
        </Card>
      )}
    </div>
  );

  const SearchTab = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ padding: '14px 16px', borderRadius: '10px', border: '1px solid rgba(124,140,255,0.12)', backgroundColor: 'rgba(124,140,255,0.04)', fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
        La recherche est maintenant séparée par mode. <code style={{ fontFamily: 'monospace', color: 'var(--accent-secondary)' }}>free_search</code> garde un chemin gratuit et auto-hébergé via SearXNG. <code style={{ fontFamily: 'monospace', color: 'var(--accent-secondary)' }}>web_search</code> utilise uniquement les providers API activés. <code style={{ fontFamily: 'monospace', color: 'var(--accent-secondary)' }}>research_search</code> démarre sur SearXNG puis ouvre les sources académiques ou GitHub si nécessaire.
      </div>

      <div style={twoColGrid}>
        <Card title="Modes de recherche" icon={Search} accent="rgba(56,189,248,0.14)">
          <ProviderToggleGroup
            label="free_search"
            hint="Chemin gratuit et quota-light. En pratique: SearXNG en priorité."
            value={cfg.search_free_providers ?? ['searxng']}
            onChange={(value) => setCfg('search_free_providers', value)}
            options={[{ value: 'searxng', label: 'SearXNG' }]}
          />
          <ProviderToggleGroup
            label="web_search"
            hint="Providers API parallélisés. SearXNG n'entre plus dans ce tool."
            value={cfg.search_web_providers ?? ['tavily', 'exa', 'langsearch']}
            onChange={(value) => setCfg('search_web_providers', value)}
            options={[
              { value: 'tavily', label: 'Tavily' },
              { value: 'exa', label: 'Exa' },
              { value: 'langsearch', label: 'LangSearch' },
            ]}
          />
          <ProviderToggleGroup
            label="research_search · academic"
            hint="SearXNG d'abord, puis fan-out parallèle sur les sources académiques activées."
            value={cfg.search_academic_providers ?? ['searxng', 'arxiv', 'semantic_scholar', 'openalex']}
            onChange={(value) => setCfg('search_academic_providers', value)}
            options={[
              { value: 'searxng', label: 'SearXNG' },
              { value: 'arxiv', label: 'arXiv' },
              { value: 'semantic_scholar', label: 'Semantic Scholar' },
              { value: 'openalex', label: 'OpenAlex' },
            ]}
          />
          <ProviderToggleGroup
            label="research_search · code"
            hint="SearXNG garde la découverte large, GitHub intervient pour la validation code/repos."
            value={cfg.search_code_providers ?? ['searxng', 'github']}
            onChange={(value) => setCfg('search_code_providers', value)}
            options={[
              { value: 'searxng', label: 'SearXNG' },
              { value: 'github', label: 'GitHub' },
            ]}
          />
        </Card>

        <ProviderBlock name="SearXNG" badge="AUTO-HÉBERGÉ" badgeBg="rgba(34,197,94,0.12)" providerKey="searxng" description="Source gratuite principale. Sert à la découverte web, science et code avant les fallbacks spécialisés." urlField="searxng_url" cfg={cfg} setCfg={setCfg} />
      </div>

      <div style={twoColGrid}>
        <ProviderBlock name="Tavily" badge="API" badgeBg="rgba(245,158,11,0.12)" providerKey="tavily" description="Recherche agent-friendly de haute qualité pour le tool web_search." keyField="tavily_api_key" cfg={cfg} setCfg={setCfg} />
        <ProviderBlock name="Exa" badge="API" badgeBg="rgba(245,158,11,0.12)" providerKey="exa" description="Recherche neurale pour documents techniques et contenus longs dans web_search." keyField="exa_api_key" cfg={cfg} setCfg={setCfg} />
        <ProviderBlock name="LangSearch" badge="API" badgeBg="rgba(179,136,255,0.12)" providerKey="langsearch" description="Provider API secondaire pour web_search, activable si tu veux plus de recall." keyField="langsearch_api_key" cfg={cfg} setCfg={setCfg} />
        <ProviderBlock name="Jina Reader" badge="LECTURE" badgeBg="rgba(34,197,94,0.12)" providerKey="jina" description="Améliore la récupération Markdown de pages complexes avant synthèse." keyField="jina_api_key" cfg={cfg} setCfg={setCfg} />
      </div>

      <div style={twoColGrid}>
        <ProviderBlock name="Semantic Scholar" badge="ACADÉMIQUE" badgeBg="rgba(56,189,248,0.12)" providerKey="semantic_scholar" description="Recherche académique structurée. Optionnel sans clé, plus stable avec clé si tu en as une." keyField="semantic_scholar_api_key" cfg={cfg} setCfg={setCfg} />
        <ProviderBlock name="OpenAlex" badge="ACADÉMIQUE" badgeBg="rgba(16,185,129,0.12)" providerKey="openalex" description="Index académique ouvert. Aucun secret requis, bon fallback gratuit pour research_search." cfg={cfg} setCfg={setCfg} />
        <ProviderBlock name="arXiv" badge="ACADÉMIQUE" badgeBg="rgba(16,185,129,0.12)" providerKey="arxiv" description="Préprints et recherche cutting-edge. Utilisé comme fallback gratuit spécialisé." cfg={cfg} setCfg={setCfg} />
        <ProviderBlock name="GitHub" badge="CODE" badgeBg="rgba(245,158,11,0.12)" providerKey="github" description="Recherche de repos et validation terrain pour les sujets dev, agents, OSS et frameworks." keyField="github_api_token" cfg={cfg} setCfg={setCfg} />
        <ProviderBlock name="Serper / Scholar" badge="OPTIONNEL" badgeBg="rgba(179,136,255,0.12)" providerKey="serper" description="Toujours disponible comme helper séparé, mais volontairement retiré des flows gratuits par défaut." keyField="serper_api_key" cfg={cfg} setCfg={setCfg} />
      </div>

      <div style={twoColGrid}>
        <Card title="Extraction HTML / anti-bot" icon={Globe}>
          <Field label="Fetcher Scrapling">
            <Sel
              value={cfg.scrapling_fetcher ?? 'basic'}
              onChange={(value) => setCfg('scrapling_fetcher', value)}
              options={[
                { value: 'basic', label: 'Basic (httpx)' },
                { value: 'camoufox', label: 'Camoufox' },
                { value: 'playwright', label: 'Playwright' },
              ]}
            />
          </Field>
          <Field label="Timeout Scrapling (s)">
            <NumInput value={cfg.scrapling_timeout ?? 30} onChange={(value) => setCfg('scrapling_timeout', value)} min={5} max={120} />
          </Field>
          <Field label="Longueur max Scrapling">
            <NumInput value={cfg.scrapling_max_content_length ?? 50000} onChange={(value) => setCfg('scrapling_max_content_length', value)} min={1000} max={500000} step={5000} />
          </Field>
        </Card>

        <Card title="Crawl4AI & extracteur unifié" icon={Search}>
          <div style={twoColGrid}>
            <Field label="Filtre Crawl4AI">
              <Sel
                value={cfg.crawl4ai_filter ?? 'pruning'}
                onChange={(value) => setCfg('crawl4ai_filter', value)}
                options={[
                  { value: 'pruning', label: 'Pruning' },
                  { value: 'bm25', label: 'BM25' },
                  { value: 'none', label: 'Aucun' },
                ]}
              />
            </Field>
            <Field label={`Seuil Crawl4AI : ${cfg.crawl4ai_threshold ?? 0.48}`}>
              <input
                type="range"
                min={0}
                max={1}
                step={0.01}
                value={cfg.crawl4ai_threshold ?? 0.48}
                onChange={(e) => setCfg('crawl4ai_threshold', parseFloat(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent-primary)' }}
              />
            </Field>
            <Field label="Timeout Crawl4AI (s)">
              <NumInput value={cfg.crawl4ai_timeout ?? 30} onChange={(value) => setCfg('crawl4ai_timeout', value)} min={5} max={120} />
            </Field>
            <Field label="Headless">
              <Sel
                value={String(cfg.crawl4ai_headless ?? true)}
                onChange={(value) => setCfg('crawl4ai_headless', value === 'true')}
                options={[{ value: 'true', label: 'Oui' }, { value: 'false', label: 'Non' }]}
              />
            </Field>
            <Field label="Stratégie extracteur" full>
              <Sel
                value={cfg.content_extractor_strategy ?? 'markdown'}
                onChange={(value) => setCfg('content_extractor_strategy', value)}
                options={[
                  { value: 'markdown', label: 'Markdown' },
                  { value: 'raw', label: 'Texte brut' },
                  { value: 'html', label: 'HTML nettoyé' },
                ]}
              />
            </Field>
            <Field label="Timeout extracteur (s)">
              <NumInput value={cfg.content_extractor_timeout ?? 60} onChange={(value) => setCfg('content_extractor_timeout', value)} min={10} max={300} />
            </Field>
            <Field label="Longueur max extracteur">
              <NumInput value={cfg.content_extractor_max_length ?? 50000} onChange={(value) => setCfg('content_extractor_max_length', value)} min={1000} max={500000} step={5000} />
            </Field>
          </div>
        </Card>
      </div>
    </div>
  );

  const DeliveryTab = (
    <div style={twoColGrid}>
      <Card title="Newsletter par défaut" icon={Mail} accent="rgba(79,209,197,0.15)">
        <Field label="Titre de la newsletter">
          <TxtInput value={cfg.newsletter_title ?? ''} onChange={(value) => setCfg('newsletter_title', value)} placeholder="Tech Watch Agent" />
        </Field>
        <Field label="Topics par défaut" hint="Un sujet par ligne pour les runs libres ou les fallbacks.">
          <TA
            value={Array.isArray(cfg.newsletter_topics) ? cfg.newsletter_topics.join('\n') : ''}
            onChange={(value) => setCfg('newsletter_topics', value.split('\n').map((item) => item.trim()).filter(Boolean))}
            placeholder={'AI news\nMachine learning\nDeveloper tools'}
            rows={6}
          />
        </Field>
        <Field label="Articles max par topic">
          <NumInput value={cfg.max_articles_per_topic ?? 5} onChange={(value) => setCfg('max_articles_per_topic', value)} min={1} max={50} />
        </Field>
        <div style={{ padding: '12px 14px', borderRadius: '10px', border: '1px solid rgba(59,130,246,0.18)', backgroundColor: 'rgba(59,130,246,0.06)', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
          La planification et les destinataires ne se pilotent plus ici. Les horaires vivent dans les profils de veille, et les envois automatiques utilisent désormais les groupes définis dans la page <strong>Email Groups</strong>.
        </div>
      </Card>

      <Card title="Transport Gmail" icon={Mail}>
        <Field label="Fuseau horaire" hint="Toujours utilisé par le scheduler des profils programmés.">
          <TxtInput value={cfg.timezone ?? 'Europe/Paris'} onChange={(value) => setCfg('timezone', value)} placeholder="Europe/Paris" />
        </Field>
        <Field label="Email expéditeur" hint="Adresse utilisée dans le champ From de Gmail.">
          <TxtInput value={cfg.sender_email ?? ''} onChange={(value) => setCfg('sender_email', value)} placeholder="veille@exemple.com" />
        </Field>
        <Field label="OAuth client JSON" hint="Collez ici le contenu du fichier OAuth Google. Il sera chiffré en base quand CONFIG_ENCRYPTION_KEY est actif." full>
          <SecretArea
            value={cfg.gmail_credentials_json ?? ''}
            onChange={(value) => setCfg('gmail_credentials_json', value)}
            placeholder={'{\n  "installed": { ... }\n}'}
            rows={7}
          />
        </Field>
        <Field label="OAuth token JSON" hint="Optionnel. Si vide, le premier flow OAuth peut le générer puis le réécrire côté runtime." full>
          <SecretArea
            value={cfg.gmail_token_json ?? ''}
            onChange={(value) => setCfg('gmail_token_json', value)}
            placeholder={'{\n  "token": "...",\n  "refresh_token": "..."\n}'}
            rows={6}
          />
        </Field>
        <div style={{ padding: '14px 16px', borderRadius: '12px', border: '1px solid rgba(16,185,129,0.18)', backgroundColor: 'rgba(16,185,129,0.06)', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
          Mode recommande : stocker le client OAuth et le token en <strong>runtime DB chiffre</strong>. Les chemins fichiers ci-dessous restent uniquement en compatibilite legacy ou pour un bootstrap local tres simple.
        </div>
        <div style={twoColGrid}>
          <Field label="Legacy credentials path" hint="Fallback seulement si vous montez encore des fichiers côté backend.">
            <TxtInput value={cfg.gmail_credentials_path ?? ''} onChange={(value) => setCfg('gmail_credentials_path', value)} placeholder="credentials.json" />
          </Field>
          <Field label="Legacy token path" hint="Fallback optionnel pour persister aussi le token sur disque.">
            <TxtInput value={cfg.gmail_token_path ?? ''} onChange={(value) => setCfg('gmail_token_path', value)} placeholder="token.json" />
          </Field>
        </div>
      </Card>
    </div>
  );

  const SecurityTab = (
    <div style={twoColGrid}>
      <Card title="Secrets & chiffrement" icon={Shield} accent="rgba(16,185,129,0.16)">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
          <Pill tone={cfg._encryption_active ? 'success' : 'warning'}>
            {cfg._encryption_active ? 'Chiffrement actif' : 'Chiffrement inactif'}
          </Pill>
          <Pill>{sensitiveCount} secret{ sensitiveCount > 1 ? 's' : '' } configuré{ sensitiveCount > 1 ? 's' : '' }</Pill>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {configuredSecrets.length ? configuredSecrets.map(([key, label]) => (
            <span key={key} style={{ padding: '6px 10px', borderRadius: '999px', fontSize: '0.74rem', fontWeight: 600, color: 'var(--text-secondary)', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)' }}>
              {label}
            </span>
          )) : <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Aucun secret runtime stocké.</span>}
        </div>

        {!cfg._encryption_active && (
          <>
            <Field label="Générer une clé Fernet" hint="Cette valeur reste bootstrap infra et ne doit pas être stockée en DB.">
              <div style={{ padding: '12px 14px', borderRadius: '10px', border: '1px solid var(--border-color)', backgroundColor: 'rgba(0,0,0,0.25)', fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--accent-secondary)', userSelect: 'all' }}>
                python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
              </div>
            </Field>
            <div style={{ padding: '12px 14px', borderRadius: '10px', border: '1px solid rgba(245,158,11,0.18)', backgroundColor: 'rgba(245,158,11,0.06)', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
              En production/staging, les écritures sensibles doivent être chiffrées. Configurez <code style={{ fontFamily: 'monospace', color: 'var(--accent-secondary)' }}>CONFIG_ENCRYPTION_KEY</code> côté serveur avant de sauver des clés API.
            </div>
          </>
        )}
      </Card>

      <Card title="Accès admin" icon={KeyRound}>
        <Field label="Token admin" hint="Stocké dans le navigateur. Il alimente l'API React et le cookie du dashboard legacy.">
          <Secret value={adminToken} onChange={setAdminToken} placeholder="Collez votre token admin" />
        </Field>
        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button type="button" onClick={() => ApiService.setAdminToken(adminToken)} style={{ padding: '10px 14px', borderRadius: '10px', backgroundColor: 'var(--accent-primary)', color: 'white', fontSize: '0.84rem', fontWeight: 700 }}>
            Enregistrer le token
          </button>
          <button type="button" onClick={handleClearAdminToken} style={{ padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.84rem', fontWeight: 700 }}>
            Supprimer
          </button>
          <a href="/ui/" target="_blank" rel="noreferrer" style={{ padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.84rem', fontWeight: 700, textDecoration: 'none' }}>
            Ouvrir /ui
          </a>
        </div>
        <div style={{ padding: '12px 14px', borderRadius: '10px', border: '1px solid rgba(124,140,255,0.12)', backgroundColor: 'rgba(124,140,255,0.04)', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
          `ADMIN_API_TOKEN` reste un secret d'infrastructure. L'UI ne le crée pas; elle se contente de l'utiliser pour piloter les surfaces d'administration.
        </div>
      </Card>
    </div>
  );

  const SystemTab = (
    <div style={twoColGrid}>
      <Card title="Vue runtime" icon={Settings2} accent="rgba(56,189,248,0.16)">
        <div style={{ display: 'grid', gridTemplateColumns: gridColumns, gap: '12px' }}>
          {[
            ['Environnement', cfg.app_env ?? 'development'],
            ['Provider LLM', cfg.llm_provider ?? '—'],
            ['Embeddings', cfg.embedding_provider ?? '—'],
            ['Fuseau', cfg.timezone ?? 'Europe/Paris'],
            ['Port API', String(cfg.app_port ?? 8000)],
            ['Logs', cfg.log_level ?? 'INFO'],
          ].map(([label, value]) => (
            <div key={label} className="card" style={{ padding: '12px 14px', backgroundColor: 'rgba(255,255,255,0.01)' }}>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>{label}</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 700 }}>{value}</div>
            </div>
          ))}
        </div>
        <Field label="Niveau de log">
          <Sel
            value={cfg.log_level ?? 'INFO'}
            onChange={(value) => setCfg('log_level', value)}
            options={[
              { value: 'DEBUG', label: 'DEBUG' },
              { value: 'INFO', label: 'INFO' },
              { value: 'WARNING', label: 'WARNING' },
              { value: 'ERROR', label: 'ERROR' },
            ]}
          />
        </Field>
      </Card>

      <Card title="Bootstrap vs runtime" icon={Database}>
        <div style={{ padding: '12px 14px', borderRadius: '10px', border: '1px solid rgba(124,140,255,0.12)', backgroundColor: 'rgba(124,140,255,0.04)', fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
          Les valeurs métier et providers sont maintenant pensées pour vivre en <strong>overrides DB</strong>. Les variables d'environnement gardent un rôle de bootstrap infra ou de fallback minimal au démarrage.
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {['DATABASE_URL', 'DATABASE_SYNC_URL', 'CONFIG_ENCRYPTION_KEY', 'ADMIN_API_TOKEN'].map((item) => (
            <span key={item} style={{ padding: '6px 10px', borderRadius: '999px', fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-secondary)', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', fontFamily: 'monospace' }}>
              {item}
            </span>
          ))}
        </div>
      </Card>

      <Card title="Réinitialiser les overrides DB" icon={RotateCcw}>
        <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
          Cette action supprime les valeurs runtime stockées en base pour revenir au bootstrap serveur. Elle ne touche ni la base de données elle-même, ni les contenus métiers.
        </div>
        <button
          type="button"
          onClick={handleResetOverrides}
          style={{ alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '10px 14px', borderRadius: '10px', border: '1px solid rgba(239,68,68,0.25)', backgroundColor: 'rgba(239,68,68,0.06)', color: 'var(--status-error)', fontSize: '0.84rem', fontWeight: 700 }}
        >
          <RotateCcw size={14} /> Réinitialiser les overrides
        </button>
      </Card>
    </div>
  );

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <div style={{ padding: '32px clamp(20px,4vw,60px) 0', maxWidth: '1600px', margin: '0 auto', width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '20px', marginBottom: '24px', flexWrap: 'wrap' }}>
          <div style={{ maxWidth: '920px' }}>
            <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '6px' }}>Configuration runtime</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: '1.6', margin: 0 }}>
              Les providers, API keys et réglages d'exécution sont pilotés ici puis stockés en base. Le serveur lit encore un bootstrap minimal au démarrage, mais les overrides DB sont la source de vérité runtime.
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            {saving && <Pill tone="warning"><Loader2 size={13} className="animate-spin" /> Sauvegarde...</Pill>}
            {saveStatus === 'ok' && <Pill tone="success"><CheckCircle2 size={13} /> Sauvegardé</Pill>}
            {saveStatus === 'error' && <Pill tone="warning"><AlertCircle size={13} /> Erreur</Pill>}
            {hasDirty && !saving && <Pill tone="warning">{Object.keys(dirty).length} modification{Object.keys(dirty).length > 1 ? 's' : ''} en attente</Pill>}
            <Pill>Auto-save</Pill>
          </div>
        </div>

        <div style={{ padding: '16px 18px', borderRadius: '16px', border: '1px solid rgba(124,140,255,0.15)', background: 'linear-gradient(135deg, rgba(124,140,255,0.12) 0%, rgba(79,209,197,0.06) 100%)', marginBottom: '22px' }}>
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '10px' }}>
            <Pill>{cfg.app_env ?? 'development'}</Pill>
            <Pill tone={cfg._encryption_active ? 'success' : 'warning'}>{cfg._encryption_active ? 'Secrets chiffrés' : 'Chiffrement à activer'}</Pill>
            <Pill>{topicCount} topic{topicCount > 1 ? 's' : ''}</Pill>
            <Pill>{emailGroupsLabel}</Pill>
          </div>
          <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
            Env-only côté infrastructure : <code style={{ fontFamily: 'monospace', color: 'var(--accent-secondary)' }}>DATABASE_URL</code>, <code style={{ fontFamily: 'monospace', color: 'var(--accent-secondary)' }}>DATABASE_SYNC_URL</code>, <code style={{ fontFamily: 'monospace', color: 'var(--accent-secondary)' }}>CONFIG_ENCRYPTION_KEY</code>, <code style={{ fontFamily: 'monospace', color: 'var(--accent-secondary)' }}>ADMIN_API_TOKEN</code>. Tout le reste doit vivre ici côté runtime.
          </div>
          {autoSaveError && (
            <div style={{ marginTop: '12px', padding: '12px 14px', borderRadius: '10px', border: '1px solid rgba(239,68,68,0.2)', backgroundColor: 'rgba(239,68,68,0.06)', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: '1.55' }}>
              {autoSaveError}
            </div>
          )}
        </div>

        <nav style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', borderBottom: '1px solid var(--border-color)' }}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '10px 16px',
                fontSize: '0.9rem',
                color: activeTab === tab.id ? 'var(--accent-primary)' : 'var(--text-secondary)',
                borderBottom: activeTab === tab.id ? '2px solid var(--accent-primary)' : '2px solid transparent',
                fontWeight: activeTab === tab.id ? 700 : 500,
                whiteSpace: 'nowrap',
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div style={{ padding: 'clamp(20px,3vw,40px) clamp(20px,4vw,60px)', maxWidth: '1600px', margin: '0 auto', width: '100%', flex: 1 }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '60px', justifyContent: 'center', color: 'var(--text-muted)' }}>
            <Loader2 size={24} className="animate-spin" /> Chargement de la configuration...
          </div>
        ) : loadError ? (
          <BootstrappingState loadError={loadError} adminToken={adminToken} setAdminToken={setAdminToken} onRetry={() => void loadConfig()} onClearAdminToken={handleClearAdminToken} />
        ) : (
          <>
            {activeTab === 'models' && ModelsTab}
            {activeTab === 'search' && SearchTab}
            {activeTab === 'delivery' && DeliveryTab}
            {activeTab === 'security' && SecurityTab}
            {activeTab === 'system' && SystemTab}
          </>
        )}
      </div>

      <style>{`select option { background: #1a2035; color: white; }`}</style>
    </div>
  );
};
