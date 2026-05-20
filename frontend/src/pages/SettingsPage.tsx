import React, { useState, useEffect, useCallback } from 'react';
import {
  Save, Eye, EyeOff, CheckCircle2, AlertCircle, Loader2, Activity, ChevronDown,
  Edit2, Database, Info, Calendar, Globe, Clock, Layers, Cpu, Search, MessageSquare,
  Moon, Type, Bell, Shield, Monitor, Trash2
} from 'lucide-react';
import { ApiService } from '../services/api';

// ── Types ─────────────────────────────────────────────────────────────────────
type Tab = 'general' | 'agent' | 'sources' | 'notifications' | 'integrations' | 'security' | 'system';

const TABS: { id: Tab; label: string }[] = [
  { id: 'general',       label: 'Général' },
  { id: 'agent',         label: 'Agent' },
  { id: 'sources',       label: 'Sources' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'integrations',  label: 'Intégrations' },
  { id: 'security',      label: 'Sécurité' },
  { id: 'system',        label: 'Système' },
];

// ── Primitive inputs ──────────────────────────────────────────────────────────
const iStyle: React.CSSProperties = {
  width: '100%', padding: '9px 12px',
  backgroundColor: 'rgba(255,255,255,0.04)',
  border: '1px solid var(--border-color)',
  borderRadius: '8px', color: 'var(--text-primary)',
  fontSize: '0.875rem', outline: 'none', fontFamily: 'inherit',
};

const Field = ({ label, hint, full, children }: { label: string; hint?: string; full?: boolean; children: React.ReactNode }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', gridColumn: full ? '1 / -1' : undefined }}>
    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)' }}>{label}</label>
    {children}
    {hint && <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{hint}</span>}
  </div>
);

const TxtInput = ({ value, onChange, placeholder, disabled }: { value: string; onChange:(v:string)=>void; placeholder?: string; disabled?: boolean }) => (
  <input type="text" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} disabled={disabled}
    style={{ ...iStyle, opacity: disabled ? 0.5 : 1 }} />
);

const NumInput = ({ value, onChange, min, max, step }: { value: number; onChange:(v:number)=>void; min?: number; max?: number; step?: number }) => (
  <input type="number" value={value} min={min} max={max} step={step} onChange={e => onChange(Number(e.target.value))} style={iStyle} />
);

const Sel = ({ value, onChange, options }: { value: string; onChange:(v:string)=>void; options:{value:string;label:string}[] }) => (
  <select value={value} onChange={e => onChange(e.target.value)} style={{ ...iStyle, cursor: 'pointer' }}>
    {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
  </select>
);

const TA = ({ value, onChange, placeholder, rows = 3 }: { value: string; onChange:(v:string)=>void; placeholder?: string; rows?: number }) => (
  <textarea value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} rows={rows}
    style={{ ...iStyle, resize: 'vertical', lineHeight: '1.5' }} />
);

const Secret = ({ value, onChange, placeholder }: { value: string; onChange:(v:string)=>void; placeholder?: string }) => {
  const [show, setShow] = useState(false);
  return (
    <div style={{ position: 'relative' }}>
      <input type={show ? 'text' : 'password'} value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder ?? 'sk-••••••••••••'} style={{ ...iStyle, paddingRight: '40px' }} />
      <button onClick={() => setShow(v => !v)}
        style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}>
        {show ? <EyeOff size={14} /> : <Eye size={14} />}
      </button>
    </div>
  );
};

const Toggle = ({ value, onChange, label, hint }: { value: boolean; onChange:(v:boolean)=>void; label: string; hint?: string }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
    <div>
      <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)' }}>{label}</div>
      {hint && <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>{hint}</div>}
    </div>
    <button onClick={() => onChange(!value)} style={{
      width: '38px', height: '21px', borderRadius: '11px', flexShrink: 0, marginLeft: '16px',
      backgroundColor: value ? 'var(--accent-primary)' : 'rgba(255,255,255,0.1)',
      position: 'relative', transition: 'background 0.2s',
    }}>
      <div style={{ width: '15px', height: '15px', borderRadius: '50%', backgroundColor: 'white',
        position: 'absolute', top: '3px', left: value ? '20px' : '3px', transition: 'left 0.2s' }} />
    </button>
  </div>
);

const G = ({ cols = 2, children }: { cols?: number; children: React.ReactNode }) => (
  <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`, gap: '16px' }}>{children}</div>
);

const Card = ({ title, icon: Icon, children }: { title?: string; icon?: any; children: React.ReactNode }) => (
  <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px', backgroundColor: 'rgba(17,24,39,0.4)' }}>
    {title && (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingBottom: '12px', borderBottom: '1px solid var(--border-color)' }}>
        {Icon && <Icon size={16} color="var(--accent-primary)" />}
        <h3 style={{ fontSize: '0.9rem', fontWeight: 700 }}>{title}</h3>
      </div>
    )}
    {children}
  </div>
);

const Stat = ({ icon: Icon, label, value, color }: any) => (
  <div className="card" style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: '12px', backgroundColor: 'rgba(255,255,255,0.01)' }}>
    <div style={{ width: '32px', height: '32px', borderRadius: '8px', backgroundColor: 'rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center', color }}>
      <Icon size={16} />
    </div>
    <div>
      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{label}</div>
      <div style={{ fontSize: '0.95rem', fontWeight: 700 }}>{value}</div>
    </div>
  </div>
);

const SettingRow = ({ icon: Icon, label, desc, iconColor = 'var(--text-muted)', children }: any) => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
    <div style={{ display: 'flex', gap: '14px', alignItems: 'center' }}>
      <div style={{ width: '30px', height: '30px', borderRadius: '7px', backgroundColor: 'rgba(255,255,255,0.04)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: iconColor }}>
        <Icon size={15} />
      </div>
      <div>
        <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{label}</div>
        {desc && <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{desc}</div>}
      </div>
    </div>
    <div style={{ minWidth: '140px', display: 'flex', justifyContent: 'flex-end' }}>{children}</div>
  </div>
);

// ── Search provider test component ────────────────────────────────────────────
const SearchTestBtn = ({ provider, query = 'IA news 2025' }: { provider: string; query?: string }) => {
  const [status, setStatus] = useState<'idle' | 'loading' | 'ok' | 'error'>('idle');
  const [result, setResult] = useState<{ results: any[]; error?: string } | null>(null);

  const test = async () => {
    setStatus('loading');
    setResult(null);
    try {
      const res = await ApiService.testSearchProvider(provider, query);
      setResult(res);
      setStatus(res.ok ? 'ok' : 'error');
    } catch (e: any) {
      setResult({ results: [], error: e.message });
      setStatus('error');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <button
        onClick={test}
        disabled={status === 'loading'}
        style={{
          display: 'flex', alignItems: 'center', gap: '6px', alignSelf: 'flex-start',
          padding: '6px 14px', borderRadius: '7px', fontSize: '0.8rem', fontWeight: 600,
          border: '1px solid var(--border-color)', color: 'var(--text-secondary)',
          backgroundColor: 'rgba(255,255,255,0.03)',
        }}
      >
        {status === 'loading' ? <Loader2 size={13} className="animate-spin" /> : <Activity size={13} />}
        {status === 'loading' ? 'Test en cours...' : 'Tester la connexion'}
      </button>

      {status !== 'idle' && status !== 'loading' && (
        <div style={{
          padding: '10px 12px', borderRadius: '8px', fontSize: '0.78rem',
          backgroundColor: status === 'ok' ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
          border: `1px solid ${status === 'ok' ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}`,
        }}>
          {status === 'ok' ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--status-success)', fontWeight: 600, marginBottom: result?.results?.length ? '6px' : 0 }}>
                <CheckCircle2 size={13} /> Connecté — {result?.results?.length ?? 0} résultat(s)
              </div>
              {result?.results?.slice(0, 2).map((r: any, i: number) => (
                <div key={i} style={{ color: 'var(--text-muted)', paddingLeft: '19px', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {r.title || r.url}
                </div>
              ))}
            </>
          ) : (
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', color: 'var(--status-error)' }}>
              <AlertCircle size={13} style={{ marginTop: '1px', flexShrink: 0 }} />
              <span>{result?.error ?? 'Connexion échouée'}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

// ── Provider row for Sources tab ──────────────────────────────────────────────
const ProviderBlock = ({
  name, badge, badgeBg, description, providerKey,
  keyField, urlField, cfg, setCfg,
}: any) => (
  <Card>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.9rem', fontWeight: 700 }}>{name}</span>
          <span style={{ fontSize: '0.63rem', padding: '2px 7px', borderRadius: '4px', backgroundColor: badgeBg, fontWeight: 700 }}>{badge}</span>
        </div>
        <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '3px', lineHeight: '1.4' }}>{description}</p>
      </div>
    </div>
    {keyField && (
      <Field label="Clé API">
        <Secret value={cfg[keyField] ?? ''} onChange={v => setCfg(keyField, v)} />
      </Field>
    )}
    {urlField && (
      <Field label="URL du serveur">
        <TxtInput value={cfg[urlField] ?? ''} onChange={v => setCfg(urlField, v)} placeholder="http://localhost:8080" />
      </Field>
    )}
    <SearchTestBtn provider={providerKey} />
  </Card>
);

// ── EMBEDDING model options ───────────────────────────────────────────────────
const EMB_MODELS: Record<string, { value: string; label: string }[]> = {
  openai:      [{ value: 'text-embedding-3-small', label: 'text-embedding-3-small (1536d)' }, { value: 'text-embedding-3-large', label: 'text-embedding-3-large (3072d)' }, { value: 'text-embedding-ada-002', label: 'text-embedding-ada-002' }],
  ollama:      [{ value: 'nomic-embed-text', label: 'nomic-embed-text (768d)' }, { value: 'mxbai-embed-large', label: 'mxbai-embed-large (1024d)' }, { value: 'all-minilm', label: 'all-minilm (384d)' }],
  zai:         [{ value: 'embedding-2', label: 'embedding-2' }],
  openrouter:  [{ value: 'text-embedding-3-small', label: 'text-embedding-3-small (via OpenAI)' }],
};

// ── TAB CONTENTS ──────────────────────────────────────────────────────────────

const TabGeneral = () => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '24px', alignItems: 'start' }}>
    {/* Left */}
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card title="Profil" icon={Edit2}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ width: '56px', height: '56px', borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-purple))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.4rem', fontWeight: 700, color: 'white', flexShrink: 0 }}>A</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', flex: 1 }}>
            {[['Nom', 'Alexandre'], ['Email', 'alexandre@localhost'], ['Rôle', 'Admin'], ['Depuis', 'Jan. 2024']].map(([l, v]) => (
              <div key={l}>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '2px' }}>{l}</div>
                <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
        <button style={{ alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 14px', borderRadius: '7px', border: '1px solid var(--border-color)', fontSize: '0.82rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
          <Edit2 size={13} /> Modifier
        </button>
      </Card>

      <Card title="Préférences d'interface" icon={Moon}>
        <SettingRow icon={Moon} label="Thème" desc="Apparence de l'interface" iconColor="var(--accent-purple)">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: '7px', border: '1px solid var(--border-color)', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            Sombre <ChevronDown size={13} />
          </div>
        </SettingRow>
        <SettingRow icon={Globe} label="Langue" desc="Langue de l'interface" iconColor="var(--accent-secondary)">
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: '7px', border: '1px solid var(--border-color)', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            Français <ChevronDown size={13} />
          </div>
        </SettingRow>
        <SettingRow icon={Clock} label="Fuseau horaire" desc="Dates et heures" iconColor="var(--status-success)">
          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Europe/Paris</div>
        </SettingRow>
        <Toggle value={true} onChange={() => {}} label="Animations" hint="Transitions et effets visuels" />
        <Toggle value={false} onChange={() => {}} label="Mode compact" hint="Réduire les espaces" />
      </Card>
    </div>

    {/* Right */}
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <Card title="Aperçu de la configuration" icon={Info}>
        <div className="r-grid-2-tight">
          <Stat icon={Layers} label="Topics actifs" value="—" color="var(--accent-purple)" />
          <Stat icon={CheckCircle2} label="Sessions" value="—" color="#22C55E" />
          <Stat icon={Bell} label="Notifications" value="—" color="#F59E0B" />
          <Stat icon={Calendar} label="Prochain run" value="—" color="var(--accent-secondary)" />
        </div>
      </Card>

      <Card title="Export & Données" icon={Database}>
        {[
          { label: 'Exporter les sessions', desc: 'Export JSON de toutes vos sessions', action: 'Exporter', color: 'var(--accent-primary)' },
          { label: 'Exporter les topics', desc: 'Liste de vos profils de veille', action: 'Exporter', color: 'var(--accent-purple)' },
        ].map(({ label, desc, action, color }) => (
          <div key={label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
            <div>
              <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{label}</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{desc}</div>
            </div>
            <button style={{ padding: '6px 14px', borderRadius: '7px', border: `1px solid ${color}33`, fontSize: '0.8rem', fontWeight: 600, color }}>
              {action}
            </button>
          </div>
        ))}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0' }}>
          <div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--status-error)' }}>Supprimer les données</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Suppression définitive</div>
          </div>
          <button style={{ padding: '6px 14px', borderRadius: '7px', border: '1px solid var(--status-error)', fontSize: '0.8rem', fontWeight: 600, color: 'var(--status-error)', display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Trash2 size={13} /> Supprimer
          </button>
        </div>
      </Card>
    </div>
  </div>
);

const TabAgent = ({ cfg, setCfg, providers, health, onCheckHealth }: any) => {
  const embModels = EMB_MODELS[cfg.embedding_provider ?? 'openai'] ?? EMB_MODELS.openai;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', alignItems: 'start' }}>
      {/* LLM */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <Card title="Provider LLM" icon={Cpu}>
          <G><Field label="Provider">
            <Sel value={cfg.llm_provider ?? 'openrouter'} onChange={v => setCfg('llm_provider', v)} options={
              providers.length
                ? providers.map((p: any) => ({ value: p.name, label: p.name.charAt(0).toUpperCase() + p.name.slice(1) }))
                : [{ value: 'openrouter', label: 'OpenRouter' }, { value: 'openai', label: 'OpenAI' }, { value: 'ollama', label: 'Ollama (local)' }, { value: 'zai', label: 'Z.ai' }]
            } />
          </Field>
          <Field label="Modèle" hint={`Défaut : ${providers.find((p: any) => p.name === cfg.llm_provider)?.default_model ?? ''}`}>
            <TxtInput value={cfg.llm_model ?? ''} onChange={v => setCfg('llm_model', v)} placeholder="openai/gpt-4.1-mini" />
          </Field></G>
          <Field label="Clé API" hint="Vide = sans authentification (Ollama)">
            <Secret value={cfg.llm_api_key ?? ''} onChange={v => setCfg('llm_api_key', v)} />
          </Field>
          <Field label="Base URL" hint="Override l'URL du provider">
            <TxtInput value={cfg.llm_base_url ?? ''} onChange={v => setCfg('llm_base_url', v)} placeholder="https://openrouter.ai/api/v1" />
          </Field>
          <Field label={`Température : ${cfg.llm_temperature ?? 0.3}`} hint="0 = déterministe, 1 = créatif">
            <input type="range" min={0} max={1} step={0.05} value={cfg.llm_temperature ?? 0.3}
              onChange={e => setCfg('llm_temperature', parseFloat(e.target.value))}
              style={{ width: '100%', accentColor: 'var(--accent-primary)', cursor: 'pointer' }} />
          </Field>
          <G><Field label="Max tokens">
            <NumInput value={cfg.llm_max_tokens ?? 2000} onChange={v => setCfg('llm_max_tokens', v)} min={256} max={32000} step={256} />
          </Field>
          <div /></G>
          <Field label="Modèles de fallback" hint="Séparés par des virgules">
            <TxtInput value={Array.isArray(cfg.llm_fallback_models) ? cfg.llm_fallback_models.join(', ') : (cfg.llm_fallback_models ?? '')}
              onChange={v => setCfg('llm_fallback_models', v.split(',').map((s: string) => s.trim()).filter(Boolean))}
              placeholder="openai/gpt-4o-mini, mistralai/mistral-7b" />
          </Field>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button onClick={() => onCheckHealth(cfg.llm_provider)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 14px', borderRadius: '7px', border: '1px solid var(--border-color)', color: 'var(--text-secondary)', fontSize: '0.8rem', fontWeight: 600 }}>
              <Activity size={13} /> Tester
            </button>
            {health[cfg.llm_provider] != null && (
              <span style={{ fontSize: '0.8rem', color: health[cfg.llm_provider]!.healthy ? 'var(--status-success)' : 'var(--status-error)', display: 'flex', alignItems: 'center', gap: '5px' }}>
                {health[cfg.llm_provider]!.healthy
                  ? <><CheckCircle2 size={13} /> Connecté · {health[cfg.llm_provider]!.latency_ms}ms</>
                  : <><AlertCircle size={13} /> Inaccessible</>}
              </span>
            )}
          </div>
        </Card>
      </div>

      {/* Right column */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <Card title="Embeddings" icon={Layers}>
          <G><Field label="Provider d'embedding">
            <Sel value={cfg.embedding_provider ?? 'openai'} onChange={v => setCfg('embedding_provider', v)} options={[
              { value: 'openai', label: 'OpenAI' }, { value: 'ollama', label: 'Ollama' },
              { value: 'zai', label: 'Z.ai' }, { value: 'openrouter', label: 'OpenRouter' }
            ]} />
          </Field>
          <Field label="Modèle">
            <Sel value={cfg.embedding_model ?? embModels[0]?.value ?? ''} onChange={v => setCfg('embedding_model', v)} options={embModels} />
          </Field></G>
          <div style={{ padding: '10px 12px', backgroundColor: 'rgba(124,140,255,0.04)', border: '1px solid rgba(124,140,255,0.12)', borderRadius: '7px', fontSize: '0.76rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
            Utilise la clé API du provider LLM. Requiert pgvector dans PostgreSQL.
          </div>
        </Card>

        <Card title="Comportement de l'agent" icon={Search}>
          <SettingRow icon={Search} label="Profondeur d'analyse" desc="Niveau par recherche" iconColor="var(--accent-primary)">
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '5px 10px', backgroundColor: 'rgba(255,255,255,0.04)', borderRadius: '7px', border: '1px solid var(--border-color)', fontSize: '0.8rem' }}>
              Approfondie <ChevronDown size={12} />
            </div>
          </SettingRow>
          <SettingRow icon={Type} label="Langue des rapports" desc="Langue de génération" iconColor="var(--accent-secondary)">
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Français</div>
          </SettingRow>
          <SettingRow icon={MessageSquare} label="Ton des rapports" desc="Style d'écriture" iconColor="var(--accent-primary)">
            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Neutre & technique</div>
          </SettingRow>
          <Toggle value={true} onChange={() => {}} label="Synthèse multi-modèles" hint="Combine plusieurs modèles" />
          <Toggle value={true} onChange={() => {}} label="Déduplication agressive" hint="Éliminer les doublons" />
        </Card>
      </div>
    </div>
  );
};

const TabSources = ({ cfg, setCfg }: any) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
    <div style={{ padding: '12px 16px', backgroundColor: 'rgba(124,140,255,0.04)', border: '1px solid rgba(124,140,255,0.12)', borderRadius: '8px', fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
      Chaîne de fallback de recherche : <strong>SearXNG → Tavily → Exa → LangSearch</strong>. Configurez au moins un provider.
    </div>

    <div className="r-grid-2">
      <ProviderBlock name="SearXNG" badge="GRATUIT" badgeBg="rgba(34,197,94,0.12)" providerKey="searxng"
        description="Métamoteur open-source auto-hébergé. Aucune clé requise."
        urlField="searxng_url" cfg={cfg} setCfg={setCfg} />
      <ProviderBlock name="Tavily" badge="PAYANT" badgeBg="rgba(245,158,11,0.12)" providerKey="tavily"
        description="Moteur de recherche IA haute qualité, optimisé pour les agents."
        keyField="tavily_api_key" cfg={cfg} setCfg={setCfg} />
      <ProviderBlock name="Serper" badge="FREEMIUM" badgeBg="rgba(179,136,255,0.12)" providerKey="serper"
        description="API Google Search avec 2500 requêtes/mois gratuites."
        keyField="serper_api_key" cfg={cfg} setCfg={setCfg} />
      <ProviderBlock name="Exa" badge="PAYANT" badgeBg="rgba(245,158,11,0.12)" providerKey="exa"
        description="Recherche neurale pour documents techniques et académiques."
        keyField="exa_api_key" cfg={cfg} setCfg={setCfg} />
      <ProviderBlock name="LangSearch" badge="FREEMIUM" badgeBg="rgba(179,136,255,0.12)" providerKey="langsearch"
        description="Moteur de recherche IA avec tier gratuit sans carte bancaire."
        keyField="langsearch_api_key" cfg={cfg} setCfg={setCfg} />
      <ProviderBlock name="Jina Reader" badge="GRATUIT" badgeBg="rgba(34,197,94,0.12)" providerKey="jina"
        description="Convertit n'importe quelle URL en Markdown propre pour les LLMs."
        keyField="jina_api_key" cfg={cfg} setCfg={setCfg} />
    </div>

    <h3 style={{ fontSize: '1rem', fontWeight: 700, marginTop: '8px' }}>Extraction de contenu</h3>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
      <Card title="Scrapling">
        <Field label="Fetcher">
          <Sel value={cfg.scrapling_fetcher ?? 'basic'} onChange={v => setCfg('scrapling_fetcher', v)} options={[
            { value: 'basic', label: 'Basic (httpx)' }, { value: 'camoufox', label: 'Camoufox (anti-bot)' }, { value: 'playwright', label: 'Playwright (JS)' }
          ]} />
        </Field>
        <Field label="Timeout (s)"><NumInput value={cfg.scrapling_timeout ?? 30} onChange={v => setCfg('scrapling_timeout', v)} min={5} max={120} /></Field>
        <Field label="Longueur max"><NumInput value={cfg.scrapling_max_content_length ?? 50000} onChange={v => setCfg('scrapling_max_content_length', v)} min={1000} max={500000} step={5000} /></Field>
      </Card>
      <Card title="Crawl4AI">
        <Field label="Filtre">
          <Sel value={cfg.crawl4ai_filter ?? 'pruning'} onChange={v => setCfg('crawl4ai_filter', v)} options={[
            { value: 'pruning', label: 'Pruning' }, { value: 'bm25', label: 'BM25' }, { value: 'none', label: 'Aucun' }
          ]} />
        </Field>
        <Field label={`Seuil : ${cfg.crawl4ai_threshold ?? 0.48}`}>
          <input type="range" min={0} max={1} step={0.01} value={cfg.crawl4ai_threshold ?? 0.48}
            onChange={e => setCfg('crawl4ai_threshold', parseFloat(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--accent-primary)' }} />
        </Field>
        <Field label="Timeout (s)"><NumInput value={cfg.crawl4ai_timeout ?? 30} onChange={v => setCfg('crawl4ai_timeout', v)} min={5} max={120} /></Field>
        <Toggle value={cfg.crawl4ai_headless ?? true} onChange={v => setCfg('crawl4ai_headless', v)} label="Headless" hint="Navigateur sans UI" />
      </Card>
      <Card title="Extracteur unifié">
        <Field label="Stratégie">
          <Sel value={cfg.content_extractor_strategy ?? 'markdown'} onChange={v => setCfg('content_extractor_strategy', v)} options={[
            { value: 'markdown', label: 'Markdown (recommandé)' }, { value: 'raw', label: 'Texte brut' }, { value: 'html', label: 'HTML nettoyé' }
          ]} />
        </Field>
        <Field label="Timeout (s)"><NumInput value={cfg.content_extractor_timeout ?? 60} onChange={v => setCfg('content_extractor_timeout', v)} min={10} max={300} /></Field>
        <Field label="Longueur max"><NumInput value={cfg.content_extractor_max_length ?? 50000} onChange={v => setCfg('content_extractor_max_length', v)} min={1000} max={500000} step={5000} /></Field>
      </Card>
    </div>
  </div>
);

const TabNotifications = ({ cfg, setCfg }: any) => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', alignItems: 'start' }}>
    <Card title="Livraison email — Gmail" icon={Globe}>
      <Field label="Email expéditeur" hint="Compte Gmail autorisé OAuth2">
        <TxtInput value={cfg.sender_email ?? ''} onChange={v => setCfg('sender_email', v)} placeholder="votre.compte@gmail.com" />
      </Field>
      <Field label="Destinataires" hint="Un email par ligne">
        <TA value={Array.isArray(cfg.recipient_emails) ? cfg.recipient_emails.join('\n') : (cfg.recipient_emails ?? '')}
          onChange={v => setCfg('recipient_emails', v.split('\n').map((s: string) => s.trim()).filter(Boolean))}
          placeholder={"alice@example.com\nbob@example.com"} rows={4} />
      </Field>
      <div style={{ padding: '10px 12px', backgroundColor: 'rgba(245,158,11,0.05)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: '7px', fontSize: '0.76rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
        Requiert un fichier <code style={{ color: 'var(--accent-secondary)', fontFamily: 'monospace' }}>credentials.json</code> OAuth2 monté dans Docker. Consultez la documentation Google Cloud Console.
      </div>
    </Card>

    <Card title="Préférences de notification" icon={Bell}>
      <Toggle value={true} onChange={() => {}} label="Notification à la fin d'une session" hint="Email quand l'orchestrateur termine" />
      <Toggle value={false} onChange={() => {}} label="Notification en cas d'échec" hint="Email si une session échoue" />
      <Toggle value={true} onChange={() => {}} label="Newsletter automatique" hint="Envoi selon la planification" />
    </Card>
  </div>
);

const TabIntegrations = ({ cfg, setCfg }: any) => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', alignItems: 'start' }}>
    <Card title="Newsletter" icon={Monitor}>
      <Field label="Titre de la newsletter">
        <TxtInput value={cfg.newsletter_title ?? ''} onChange={v => setCfg('newsletter_title', v)} placeholder="Tech Watch Agent" />
      </Field>
      <Field label="Topics par défaut" hint="Un par ligne">
        <TA value={Array.isArray(cfg.newsletter_topics) ? cfg.newsletter_topics.join('\n') : (cfg.newsletter_topics ?? '')}
          onChange={v => setCfg('newsletter_topics', v.split('\n').map((s: string) => s.trim()).filter(Boolean))}
          placeholder={"AI news\nMachine Learning\nTech startups"} rows={5} />
      </Field>
      <Field label="Articles max par topic">
        <NumInput value={cfg.max_articles_per_topic ?? 5} onChange={v => setCfg('max_articles_per_topic', v)} min={1} max={50} />
      </Field>
    </Card>

    <Card title="Planification" icon={Calendar}>
      <Field label="Heures de déclenchement" hint="Séparées par des virgules — ex : 08:00, 18:00">
        <TxtInput value={Array.isArray(cfg.schedule_times) ? cfg.schedule_times.join(', ') : (cfg.schedule_times ?? '08:00, 18:00')}
          onChange={v => setCfg('schedule_times', v.split(',').map((s: string) => s.trim()).filter(Boolean))}
          placeholder="08:00, 18:00" />
      </Field>
      <Field label="Fuseau horaire" hint="IANA timezone — ex : Europe/Paris, UTC">
        <TxtInput value={cfg.timezone ?? 'Europe/Paris'} onChange={v => setCfg('timezone', v)} placeholder="Europe/Paris" />
      </Field>
      <div style={{ padding: '10px 12px', backgroundColor: 'rgba(124,140,255,0.04)', border: '1px solid rgba(124,140,255,0.12)', borderRadius: '7px', fontSize: '0.76rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
        Le scheduler tourne en arrière-plan. Les modifications prennent effet immédiatement après sauvegarde.
      </div>
    </Card>
  </div>
);

const TabSecurity = ({ cfg }: any) => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', alignItems: 'start' }}>
    <Card title="Chiffrement de la configuration" icon={Shield}>
      <div style={{ padding: '14px 16px', borderRadius: '8px', border: '1px solid var(--border-color)', backgroundColor: 'rgba(255,255,255,0.02)', display: 'flex', alignItems: 'center', gap: '12px' }}>
        {cfg._encryption_active
          ? <><CheckCircle2 size={20} color="var(--status-success)" /><div><div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--status-success)' }}>Chiffrement actif</div><div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Clés API chiffrées en base (AES-128 Fernet)</div></div></>
          : <><AlertCircle size={20} color="var(--status-warning)" /><div><div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--status-warning)' }}>Chiffrement inactif</div><div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Définissez CONFIG_ENCRYPTION_KEY dans .env</div></div></>
        }
      </div>
      <Field label="Générer une clé de chiffrement" hint="Copiez cette commande dans votre terminal, puis ajoutez la valeur dans .env">
        <div style={{ padding: '10px 12px', backgroundColor: 'rgba(0,0,0,0.3)', borderRadius: '7px', border: '1px solid var(--border-color)', fontFamily: 'monospace', fontSize: '0.76rem', color: 'var(--accent-secondary)', userSelect: 'all', lineHeight: '1.5' }}>
          python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
        </div>
      </Field>
      <div style={{ padding: '10px 12px', backgroundColor: 'rgba(124,140,255,0.04)', border: '1px solid rgba(124,140,255,0.12)', borderRadius: '7px', fontSize: '0.76rem', color: 'var(--text-muted)', lineHeight: '1.5' }}>
        La clé reste dans <code style={{ fontFamily: 'monospace', color: 'var(--accent-secondary)' }}>.env</code> (non répliqué en DB). Les valeurs sensibles sont chiffrées avec Fernet (AES-128-CBC + HMAC-SHA256).
      </div>
    </Card>

    <Card title="Gestion des accès" icon={Shield}>
      <Toggle value={false} onChange={() => {}} label="Authentification requise" hint="Protéger l'interface par mot de passe (à venir)" />
      <Toggle value={true} onChange={() => {}} label="CORS strict" hint="Restreindre les origines autorisées" />
      <Toggle value={false} onChange={() => {}} label="Mode lecture seule" hint="Désactiver les modifications via l'UI" />
    </Card>
  </div>
);

const TabSystem = ({ cfg, setCfg }: any) => (
  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', alignItems: 'start' }}>
    <Card title="Informations système" icon={Info}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        {[
          ['Version API', '0.3.0'], ['Environnement', cfg.app_env ?? '—'],
          ['Port', String(cfg.app_port ?? 8000)], ['Base de données', 'PostgreSQL + pgvector'],
          ['Runtime', 'Python 3.11'], ['Framework', 'FastAPI + LangGraph'],
        ].map(([l, v]) => (
          <div key={l} className="card" style={{ padding: '12px 14px', backgroundColor: 'rgba(255,255,255,0.01)' }}>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '3px' }}>{l}</div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600 }}>{v}</div>
          </div>
        ))}
      </div>
    </Card>

    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <Card title="Logs" icon={Monitor}>
        <Field label="Niveau de log" hint="Verbosité du serveur">
          <Sel value={cfg.log_level ?? 'INFO'} onChange={v => setCfg('log_level', v)} options={[
            { value: 'DEBUG', label: 'DEBUG — très verbeux' },
            { value: 'INFO', label: 'INFO — standard' },
            { value: 'WARNING', label: 'WARNING — alertes' },
            { value: 'ERROR', label: 'ERROR — erreurs uniquement' },
          ]} />
        </Field>
      </Card>

      <Card title="Danger Zone" icon={Trash2}>
        <div style={{ padding: '14px', border: '1px solid rgba(239,68,68,0.2)', borderRadius: '8px', backgroundColor: 'rgba(239,68,68,0.03)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--status-error)' }}>Réinitialiser la config DB</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Recharge depuis les variables d'environnement</div>
          </div>
          <button style={{ padding: '6px 14px', borderRadius: '7px', border: '1px solid var(--status-error)', color: 'var(--status-error)', fontSize: '0.8rem', fontWeight: 600, flexShrink: 0 }}>
            Réinitialiser
          </button>
        </div>
      </Card>
    </div>
  </div>
);

// ── Main page ─────────────────────────────────────────────────────────────────
export const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('general');
  const [cfg, setRawCfg] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'ok' | 'error'>('idle');
  const [providers, setProviders] = useState<any[]>([]);
  const [health, setHealth] = useState<Record<string, { healthy: boolean; latency_ms: number } | null>>({});
  const [dirty, setDirty] = useState<Record<string, any>>({});

  const setCfg = useCallback((key: string, value: any) => {
    setRawCfg(prev => ({ ...prev, [key]: value }));
    setDirty(prev => ({ ...prev, [key]: value }));
    setSaveStatus('idle');
  }, []);

  useEffect(() => {
    Promise.all([
      ApiService.getConfig(),
      ApiService.getLLMProviders().catch(() => ({ providers: [] })),
    ]).then(([config, providerData]) => {
      setRawCfg(config);
      setProviders((providerData as any).providers ?? []);
    }).finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!Object.keys(dirty).length) return;
    setSaving(true);
    try {
      await ApiService.updateConfig(dirty);
      setDirty({});
      setSaveStatus('ok');
      setTimeout(() => setSaveStatus('idle'), 3000);
    } catch {
      setSaveStatus('error');
    } finally {
      setSaving(false);
    }
  };

  const handleCheckHealth = async (provider: string) => {
    try {
      const res = await ApiService.checkProviderHealth(provider);
      setHealth(prev => ({ ...prev, [provider]: res }));
    } catch {
      setHealth(prev => ({ ...prev, [provider]: { healthy: false, latency_ms: 0 } }));
    }
  };

  const hasDirty = Object.keys(dirty).length > 0;

  return (
    <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      {/* ── Sticky header ── */}
      <div style={{ padding: '32px clamp(20px,4vw,60px) 0', maxWidth: '1600px', margin: '0 auto', width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
          <div>
            <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '4px' }}>Paramètres</h1>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>Personnalisez votre expérience et configurez votre agent de veille.</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {saveStatus === 'ok' && <span style={{ fontSize: '0.82rem', color: 'var(--status-success)', display: 'flex', alignItems: 'center', gap: '5px' }}><CheckCircle2 size={14} /> Sauvegardé</span>}
            {saveStatus === 'error' && <span style={{ fontSize: '0.82rem', color: 'var(--status-error)', display: 'flex', alignItems: 'center', gap: '5px' }}><AlertCircle size={14} /> Erreur</span>}
            {hasDirty && <span style={{ fontSize: '0.75rem', padding: '3px 10px', borderRadius: '6px', backgroundColor: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)', color: '#F59E0B' }}>{Object.keys(dirty).length} non sauvegardée{Object.keys(dirty).length > 1 ? 's' : ''}</span>}
            <button
              onClick={handleSave}
              disabled={saving || !hasDirty}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '10px 20px', borderRadius: '10px', fontWeight: 600, fontSize: '0.9rem',
                backgroundColor: hasDirty ? 'var(--accent-primary)' : 'var(--bg-surface)',
                color: hasDirty ? 'white' : 'var(--text-muted)',
                border: hasDirty ? 'none' : '1px solid var(--border-color)',
                boxShadow: hasDirty ? '0 4px 20px rgba(124,140,255,0.25)' : 'none',
                opacity: saving ? 0.7 : 1, transition: 'all 0.2s',
              }}
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              Enregistrer les modifications
            </button>
          </div>
        </div>

        {/* Horizontal tabs */}
        <nav style={{ display: 'flex', gap: '4px', borderBottom: '1px solid var(--border-color)' }}>
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '10px 16px', fontSize: '0.9rem',
                color: activeTab === tab.id ? 'var(--accent-primary)' : 'var(--text-secondary)',
                borderBottom: activeTab === tab.id ? '2px solid var(--accent-primary)' : '2px solid transparent',
                fontWeight: activeTab === tab.id ? 600 : 400,
                transition: 'all 0.15s', whiteSpace: 'nowrap',
              }}
            >{tab.label}</button>
          ))}
        </nav>
      </div>

      {/* ── Tab content ── */}
      <div style={{ padding: 'clamp(20px,3vw,40px) clamp(20px,4vw,60px)', maxWidth: '1600px', margin: '0 auto', width: '100%', flex: 1 }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '60px', justifyContent: 'center', color: 'var(--text-muted)' }}>
            <Loader2 size={24} className="animate-spin" /> Chargement de la configuration...
          </div>
        ) : (
          <>
            {activeTab === 'general'       && <TabGeneral />}
            {activeTab === 'agent'         && <TabAgent cfg={cfg} setCfg={setCfg} providers={providers} health={health} onCheckHealth={handleCheckHealth} />}
            {activeTab === 'sources'       && <TabSources cfg={cfg} setCfg={setCfg} />}
            {activeTab === 'notifications' && <TabNotifications cfg={cfg} setCfg={setCfg} />}
            {activeTab === 'integrations'  && <TabIntegrations cfg={cfg} setCfg={setCfg} />}
            {activeTab === 'security'      && <TabSecurity cfg={cfg} />}
            {activeTab === 'system'        && <TabSystem cfg={cfg} setCfg={setCfg} />}
          </>
        )}
      </div>

      <style>{`select option { background: #1a2035; color: white; }`}</style>
    </div>
  );
};
