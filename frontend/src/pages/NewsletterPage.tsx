import React, { useState, useEffect } from 'react';
import {
  Send,
  Settings2,
  Eye,
  ChevronRight,
  Sparkles,
  Users,
  MousePointer2,
  Loader2,
  CheckCircle2,
  AlertCircle
} from 'lucide-react';
import { ApiService } from '../services/api';
import type { NewsletterRun } from '../types';

const NewsletterStat = ({ icon: Icon, label, value, color }: any) => (
  <div className="card" style={{ padding: '20px', flex: 1, display: 'flex', alignItems: 'center', gap: '16px' }}>
    <div style={{
      width: '40px',
      height: '40px',
      borderRadius: '10px',
      backgroundColor: 'rgba(255,255,255,0.03)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: color
    }}>
      <Icon size={20} />
    </div>
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
      <span style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>{value}</span>
    </div>
  </div>
);

export const NewsletterPage: React.FC = () => {
  const [history, setHistory] = useState<NewsletterRun[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generateResult, setGenerateResult] = useState<{ subject: string; preview: string; email_sent: boolean } | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [topics, setTopics] = useState('LLM, Agents IA, Open Source');

  useEffect(() => {
    ApiService.getNewsletterHistory(10)
      .then(setHistory)
      .catch(() => {})
      .finally(() => setHistoryLoading(false));
  }, []);

  const handleGenerate = async () => {
    setGenerating(true);
    setGenerateError(null);
    setGenerateResult(null);
    try {
      const topicsList = topics.split(',').map(t => t.trim()).filter(Boolean);
      const result = await ApiService.generateNewsletter(topicsList, false);
      setGenerateResult({ subject: result.subject, preview: result.preview, email_sent: result.email_sent });
      // Refresh history
      ApiService.getNewsletterHistory(10).then(setHistory).catch(() => {});
    } catch (err: any) {
      setGenerateError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  const sentCount = history.filter(r => r.delivery_success).length;
  const lastSent = history.find(r => r.delivery_success);
  const lastSentLabel = lastSent?.completed_at
    ? `Il y a ${Math.floor((Date.now() - new Date(lastSent.completed_at).getTime()) / 86400000)}j`
    : '—';

  return (
    <div className="fade-in page-container" style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '4px' }}>Newsletter</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>Diffusez vos insights et analyses consolidés</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 16px',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-color)',
            borderRadius: '10px',
            color: 'var(--text-primary)',
            fontSize: '0.9rem'
          }}>
            <Settings2 size={18} /> Configuration
          </button>
          <button
            onClick={handleGenerate}
            disabled={generating}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 20px',
              backgroundColor: generating ? 'rgba(124, 140, 255, 0.5)' : 'var(--accent-primary)',
              borderRadius: '10px',
              color: 'white',
              fontWeight: 600,
              fontSize: '0.95rem',
              boxShadow: '0 4px 20px rgba(124, 140, 255, 0.3)'
            }}
          >
            {generating ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
            {generating ? 'Génération...' : "Générer l'édition"}
          </button>
        </div>
      </header>

      {/* Quick Stats */}
      <section style={{ display: 'flex', gap: '20px' }}>
        <NewsletterStat icon={Users} label="Éditions générées" value={String(history.length)} color="var(--accent-primary)" />
        <NewsletterStat icon={Eye} label="Éditions envoyées" value={String(sentCount)} color="var(--status-success)" />
        <NewsletterStat icon={MousePointer2} label="Taux de succès" value={history.length > 0 ? `${Math.round(sentCount / history.length * 100)}%` : '—'} color="var(--accent-secondary)" />
        <NewsletterStat icon={Send} label="Dernier envoi" value={lastSentLabel} color="var(--accent-purple)" />
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '32px' }}>
        {/* Main Block */}
        <div className="card" style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Générer une nouvelle édition</h2>
          </div>

          {/* Topics input */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Topics à inclure (séparés par des virgules)</label>
            <input
              type="text"
              value={topics}
              onChange={e => setTopics(e.target.value)}
              placeholder="LLM, Agents IA, Open Source..."
              style={{
                padding: '12px 16px',
                backgroundColor: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
                outline: 'none'
              }}
            />
          </div>

          {/* Result or placeholder */}
          {generateError && (
            <div style={{ padding: '16px', backgroundColor: 'var(--status-error-bg)', borderRadius: '12px', border: '1px solid var(--status-error)', display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
              <AlertCircle size={18} color="var(--status-error)" style={{ flexShrink: 0, marginTop: '2px' }} />
              <p style={{ color: 'var(--status-error)', fontSize: '0.9rem' }}>{generateError}</p>
            </div>
          )}

          {generateResult ? (
            <div style={{ padding: '24px', backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-color)', borderRadius: '12px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CheckCircle2 size={18} color="var(--status-success)" />
                <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{generateResult.subject}</h3>
              </div>
              <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6', fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>
                {generateResult.preview}
              </p>
              {generateResult.email_sent && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--status-success)', fontSize: '0.85rem' }}>
                  <Send size={14} /> Email envoyé avec succès
                </div>
              )}
            </div>
          ) : !generating && !generateError ? (
            <div style={{ padding: '24px', backgroundColor: 'rgba(255,255,255,0.01)', border: '1px dashed var(--border-color)', borderRadius: '12px', textAlign: 'center' }}>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                Cliquez sur "Générer l'édition" pour créer une nouvelle newsletter à partir de vos articles récents.
              </p>
            </div>
          ) : generating ? (
            <div style={{ padding: '40px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px' }}>
              <Loader2 size={32} className="animate-spin" color="var(--accent-primary)" />
              <p style={{ color: 'var(--text-secondary)' }}>Génération en cours, cela peut prendre quelques minutes...</p>
            </div>
          ) : null}
        </div>

        {/* History Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Historique</h2>
          {historyLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)' }}>
              <Loader2 size={16} className="animate-spin" /> Chargement...
            </div>
          ) : history.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Aucune édition générée pour l'instant.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {history.map(item => {
                const dateLabel = item.completed_at
                  ? new Date(item.completed_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
                  : '—';
                return (
                  <div key={item.id} className="card" style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, minWidth: 0, marginRight: '12px' }}>
                      <span style={{ fontSize: '0.9rem', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.subject || 'Newsletter'}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {item.articles_count ? `${item.articles_count} articles • ` : ''}{dateLabel}
                      </span>
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      {item.delivery_success ? (
                        <div style={{ fontSize: '0.85rem', color: 'var(--status-success)', fontWeight: 600 }}>Envoyé</div>
                      ) : (
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{item.status}</div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <button style={{ color: 'var(--text-muted)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center', marginTop: '8px' }}>
            Voir tout l'historique <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <style>{`
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};
