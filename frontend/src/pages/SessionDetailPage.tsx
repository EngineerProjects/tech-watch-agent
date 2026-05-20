import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { useOrchestratorStream } from '../hooks/useOrchestratorStream';
import { StepStatus } from '../types';
import type { ResearchSession, PlanStep } from '../types';
import { ApiService } from '../services/api';
import {
  CheckCircle2,
  Circle,
  ChevronRight,
  Download,
  ExternalLink,
  Globe,
  AlertCircle,
  Loader2
} from 'lucide-react';

interface SessionDetailPageProps {
  sessionId?: string;
  streamUrl?: string | null;
}

type Tab = 'report' | 'overview' | 'metadata';

const PlanStepRow = ({ step, index, total }: { step: PlanStep; index: number; total: number }) => (
  <div style={{ display: 'flex', gap: '16px', position: 'relative' }}>
    {index !== total - 1 && (
      <div style={{ position: 'absolute', left: '11px', top: '24px', bottom: '-40px', width: '2px', backgroundColor: 'var(--border-color)' }} />
    )}
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', zIndex: 1 }}>
      {step.status === StepStatus.DONE ? (
        <CheckCircle2 size={24} color="var(--status-success)" />
      ) : step.status === StepStatus.RUNNING ? (
        <div style={{ width: '24px', height: '24px', borderRadius: '50%', border: '2px solid var(--status-running)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: 'var(--status-running)' }} />
        </div>
      ) : step.status === StepStatus.FAILED ? (
        <AlertCircle size={24} color="var(--status-error)" />
      ) : (
        <Circle size={24} color="var(--text-muted)" strokeWidth={1.5} />
      )}
    </div>
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px', paddingBottom: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        {step.started_at && (
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
            {new Date(step.started_at).toLocaleTimeString()}
          </span>
        )}
        {step.completed_at && step.started_at && (
          <span style={{ fontSize: '0.7rem', color: 'var(--status-success)' }}>
            {Math.round((new Date(step.completed_at).getTime() - new Date(step.started_at).getTime()) / 1000)}s
          </span>
        )}
      </div>
      <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: step.status === StepStatus.PENDING ? 'var(--text-muted)' : 'var(--text-primary)' }}>
        {step.name}
      </h4>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>{step.description}</p>
      {step.result && (
        <div style={{ alignSelf: 'flex-end', fontSize: '0.75rem', color: 'var(--status-success)', fontWeight: 600, backgroundColor: 'rgba(34, 197, 94, 0.05)', padding: '2px 8px', borderRadius: '4px', marginTop: '4px' }}>
          {step.result}
        </div>
      )}
      {step.error && (
        <div style={{ fontSize: '0.75rem', color: 'var(--status-error)', backgroundColor: 'rgba(239, 68, 68, 0.05)', padding: '4px 8px', borderRadius: '4px', marginTop: '4px' }}>
          {step.error}
        </div>
      )}
    </div>
  </div>
);

const SourceCard = ({ result }: { result: any }) => {
  const title = result.title || result.url || 'Source';
  const url = result.url || '';
  const domain = url ? new URL(url).hostname.replace('www.', '') : result.source || '—';
  const date = result.published_date ? new Date(result.published_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', year: 'numeric' }) : '';
  const relevance = result.relevance_score != null ? `${Math.round(result.relevance_score * 100)}%` : '—';

  return (
    <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', backgroundColor: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-color)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', gap: '12px' }}>
          <div style={{ width: '32px', height: '32px', borderRadius: '6px', backgroundColor: 'rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', flexShrink: 0 }}>
            <Globe size={18} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', lineHeight: '1.3' }}>{title}</h4>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
              <span>{domain}</span>
              {date && <><span>•</span><span>{date}</span></>}
            </div>
          </div>
        </div>
        {url && (
          <a href={url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
            <ExternalLink size={14} />
          </a>
        )}
      </div>
      <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
        Pertinence: <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{relevance}</span>
      </div>
    </div>
  );
};

export const SessionDetailPage: React.FC<SessionDetailPageProps> = ({ streamUrl, sessionId }) => {
  const {
    report: streamedReport,
    plan: streamedPlan,
    articles: streamedArticles,
    phase,
    status,
    error: streamError,
    sessionId: streamedSessionId,
  } = useOrchestratorStream(streamUrl || null);

  const [activeTab, setActiveTab] = useState<Tab>('report');
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingSession, setLoadingSession] = useState(false);

  // Load session from DB when given a sessionId prop (history view)
  useEffect(() => {
    if (!sessionId || streamUrl) return;
    setLoadingSession(true);
    setLoadError(null);
    ApiService.getSession(sessionId)
      .then(s => setSession(s))
      .catch(err => setLoadError(err.message))
      .finally(() => setLoadingSession(false));
  }, [sessionId, streamUrl]);

  // Auto-reload from DB when stream completes to get full report + sources
  useEffect(() => {
    const resolvedId = streamedSessionId || sessionId;
    if (status !== 'completed' || !resolvedId) return;
    const timer = setTimeout(() => {
      setLoadingSession(true);
      ApiService.getSession(resolvedId)
        .then(s => setSession(s))
        .catch(() => {})
        .finally(() => setLoadingSession(false));
    }, 1500); // small delay for DB write to settle
    return () => clearTimeout(timer);
  }, [status, streamedSessionId, sessionId]);

  const planSteps: PlanStep[] = streamedPlan?.length ? streamedPlan : (session?.plan ?? []);
  const reportContent = streamedReport || session?.final_report || null;

  // During streaming: show live articles; after completion: show full DB results
  const sources: any[] = session?.research_results?.length
    ? session.research_results
    : streamedArticles;

  const title = session?.research_brief || 'Session en cours...';
  const isStreaming = !!streamUrl && status === 'running';

  // Phase label for the live indicator
  const phaseLabels: Record<string, string> = {
    idle: 'En attente',
    initializing: 'Initialisation…',
    planner: 'Génération du plan…',
    dispatcher: 'Recherche en cours…',
    dispatcher_parallel: 'Recherche parallèle…',
    synthesizer: 'Synthèse du rapport…',
    mailer: 'Envoi par email…',
    completed: 'Terminé',
    done: 'Terminé',
    failed: 'Échec',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: 'var(--bg-primary)' }}>

      {/* Header Bar */}
      <header style={{
        height: 'var(--header-height)',
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 24px',
        justifyContent: 'space-between',
        flexShrink: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '0.9rem', minWidth: 0 }}>
          <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>Sessions</span>
          <ChevronRight size={14} color="var(--text-muted)" style={{ flexShrink: 0 }} />
          <span style={{ color: 'var(--text-primary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</span>
        </div>
        {isStreaming && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--status-running)', backgroundColor: 'var(--status-running-bg)', padding: '4px 12px', borderRadius: '20px', border: '1px solid rgba(59,130,246,0.2)' }}>
            <div className="animate-pulse" style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: 'var(--status-running)', flexShrink: 0 }} />
            {phaseLabels[phase] ?? phase}
          </div>
        )}
        {status === 'completed' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.82rem', color: 'var(--status-success)', backgroundColor: 'var(--status-success-bg)', padding: '4px 12px', borderRadius: '20px' }}>
            <CheckCircle2 size={13} /> Terminé
          </div>
        )}
        {streamError && (
          <div style={{ fontSize: '0.82rem', color: 'var(--status-error)', backgroundColor: 'var(--status-error-bg)', padding: '4px 12px', borderRadius: '20px' }}>
            {streamError}
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          {reportContent && (
            <button
              onClick={() => {
                const blob = new Blob([reportContent], { type: 'text/markdown' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'rapport.md';
                a.click();
                URL.revokeObjectURL(url);
              }}
              style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: 500 }}
            >
              <Download size={16} /> Exporter
            </button>
          )}
        </div>
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Column 1: Execution Plan */}
        <aside style={{
          width: '300px',
          borderRight: '1px solid var(--border-color)',
          padding: '24px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px'
        }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Plan d'exécution</h2>
          {planSteps.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {planSteps.map((step, idx) => (
                <PlanStepRow key={step.step_id || idx} step={step} index={idx} total={planSteps.length} />
              ))}
            </div>
          ) : isStreaming ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              <Loader2 size={14} className="animate-spin" /> En attente du plan…
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Aucun plan disponible.</p>
          )}
        </aside>

        {/* Column 2: Agent Report */}
        <main style={{ flex: 1, overflowY: 'auto', padding: '0 40px', display: 'flex', flexDirection: 'column' }}>
          <nav style={{ display: 'flex', gap: '32px', marginBottom: '40px', paddingTop: '24px', position: 'sticky', top: 0, backgroundColor: 'var(--bg-primary)', zIndex: 10 }}>
            {(['Rapport', 'Aperçu', 'Métadonnées'] as const).map(label => {
              const tabKey = label === 'Rapport' ? 'report' : label === 'Aperçu' ? 'overview' : 'metadata';
              return (
                <button
                  key={label}
                  onClick={() => setActiveTab(tabKey as Tab)}
                  style={{
                    paddingBottom: '12px',
                    fontSize: '0.95rem',
                    color: activeTab === tabKey ? 'var(--accent-primary)' : 'var(--text-secondary)',
                    borderBottom: activeTab === tabKey ? '2px solid var(--accent-primary)' : '2px solid transparent',
                    fontWeight: activeTab === tabKey ? 600 : 400
                  }}
                >
                  {label}
                </button>
              );
            })}
          </nav>

          <article className="markdown-report" style={{ maxWidth: '800px', margin: '0 auto', width: '100%', paddingBottom: '100px' }}>
            {activeTab === 'report' && (
              <>
                {loadingSession ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '80px 0', gap: '16px' }}>
                    <Loader2 size={32} className="animate-spin" color="var(--accent-primary)" />
                    <p style={{ color: 'var(--text-secondary)' }}>Chargement de la session...</p>
                  </div>
                ) : loadError ? (
                  <div className="card" style={{ padding: '24px', backgroundColor: 'var(--status-error-bg)', borderColor: 'var(--status-error)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--status-error)' }}>
                      <AlertCircle size={24} />
                      <div>
                        <h3 style={{ color: 'var(--status-error)' }}>Erreur de chargement</h3>
                        <p style={{ fontSize: '0.9rem', opacity: 0.8 }}>{loadError}</p>
                      </div>
                    </div>
                  </div>
                ) : reportContent ? (
                  <>
                    <ReactMarkdown>{reportContent}</ReactMarkdown>
                    {isStreaming && (
                      <span style={{ display: 'inline-block', width: '2px', height: '1.2em', backgroundColor: 'var(--accent-primary)', verticalAlign: 'text-bottom', marginLeft: '2px', animation: 'blink 1s step-end infinite' }} />
                    )}
                  </>
                ) : isStreaming ? (
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '60px 0', gap: '16px' }}>
                    <Loader2 size={28} className="animate-spin" color="var(--accent-primary)" />
                    <p style={{ color: 'var(--text-secondary)' }}>{phaseLabels[phase] ?? 'Traitement en cours…'}</p>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '80px 0' }}>
                    <p style={{ color: 'var(--text-muted)' }}>Aucun rapport disponible pour cette session.</p>
                  </div>
                )}
              </>
            )}

            {activeTab === 'overview' && session && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <div className="card" style={{ padding: '24px' }}>
                  <h3 style={{ marginBottom: '16px', fontSize: '1.1rem', fontWeight: 600 }}>Informations générales</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '0.9rem' }}>
                    {[
                      ['Statut', session.status],
                      ['Phase', session.phase],
                      ['Créée le', new Date(session.created_at).toLocaleString('fr-FR')],
                      ['Mise à jour', new Date(session.updated_at).toLocaleString('fr-FR')],
                      ...(session.completed_at ? [['Terminée le', new Date(session.completed_at).toLocaleString('fr-FR')]] : []),
                      ['Sources collectées', String(session.research_results?.length ?? '—')],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <span style={{ color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>{label}</span>
                        <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{value}</span>
                      </div>
                    ))}
                  </div>
                </div>
                {session.analysis_results && (
                  <div className="card" style={{ padding: '24px' }}>
                    <h3 style={{ marginBottom: '16px', fontSize: '1.1rem', fontWeight: 600 }}>Analyse</h3>
                    <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6', fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>
                      {session.analysis_results}
                    </p>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'metadata' && session && (
              <div className="card" style={{ padding: '24px' }}>
                <h3 style={{ marginBottom: '16px', fontSize: '1.1rem', fontWeight: 600 }}>Métadonnées</h3>
                <pre style={{ color: 'var(--text-secondary)', fontSize: '0.8rem', overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(session.meta_data ?? {}, null, 2)}
                </pre>
              </div>
            )}
          </article>
        </main>

        {/* Column 3: Sources */}
        <aside style={{
          width: '380px',
          borderLeft: '1px solid var(--border-color)',
          padding: '24px',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px',
          backgroundColor: 'rgba(17, 24, 39, 0.3)'
        }}>
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>
            Sources{sources.length > 0 ? ` (${sources.length})` : ''}
            {isStreaming && sources.length > 0 && (
              <span style={{ marginLeft: '8px', fontSize: '0.7rem', color: 'var(--status-running)', fontWeight: 400 }}>live</span>
            )}
          </h2>

          {sources.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {sources.slice(0, 30).map((result: any, idx: number) => (
                <SourceCard key={result.url || result.id || idx} result={result} />
              ))}
              {sources.length > 30 && (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center' }}>
                  + {sources.length - 30} autres sources
                </p>
              )}
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              {isStreaming ? 'Collecte en cours…' : 'Aucune source collectée.'}
            </p>
          )}
        </aside>

      </div>

      <style>{`
        .markdown-report h1 { font-size: 2.5rem; margin-bottom: 2rem; color: #fff; }
        .markdown-report h2 { font-size: 1.5rem; margin: 2.5rem 0 1.25rem; color: #fff; }
        .markdown-report h3 { font-size: 1.2rem; margin: 1.5rem 0 1rem; color: #fff; }
        .markdown-report p { margin-bottom: 1.5rem; line-height: 1.7; color: var(--text-secondary); }
        .markdown-report ul, .markdown-report ol { padding-left: 1.5rem; margin-bottom: 1.5rem; color: var(--text-secondary); }
        .markdown-report li { margin-bottom: 0.5rem; }
        .markdown-report code { background: rgba(255,255,255,0.05); padding: 2px 6px; border-radius: 4px; font-size: 0.85em; }
        .markdown-report pre { background: rgba(255,255,255,0.03); padding: 16px; border-radius: 8px; overflow-x: auto; margin-bottom: 1.5rem; }
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }
      `}</style>
    </div>
  );
};
