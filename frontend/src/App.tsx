import { useState, useRef, useCallback, useMemo, Component } from 'react';
import type { ReactNode, ErrorInfo } from 'react';
import { Sidebar } from './components/Sidebar';
import { HomePage } from './pages/HomePage';
import { SessionsPage } from './pages/SessionsPage';
import { SessionDetailPage } from './pages/SessionDetailPage';
import { NewsletterPage } from './pages/NewsletterPage';
import { SettingsPage } from './pages/SettingsPage';
import { SourcesPage } from './pages/SourcesPage';
import { EmailGroupsPage } from './pages/EmailGroupsPage';
import { WatchProfilesPage } from './pages/WatchProfilesPage';
import { LiveRunModal } from './components/LiveRunModal';
import { ApiService } from './services/api';
import type { ActiveSessionInfo, ResearchSession, SessionLaunchPayload } from './types';
import type { BusEvent, SubscribeFn } from './hooks/useOrchestratorStream';

class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] React crash:', error, info.componentStack);
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100vh', gap: '16px', padding: '40px', backgroundColor: 'var(--bg-primary)', color: 'var(--text-primary)', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem' }}>⚠️</div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#ef4444' }}>Une erreur est survenue</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '480px' }}>
            {this.state.error.message || 'Erreur inconnue'}
          </p>
          <button
            onClick={() => this.setState({ error: null })}
            style={{ padding: '10px 24px', backgroundColor: 'var(--accent-primary)', color: 'white', borderRadius: '8px', fontWeight: 600, fontSize: '0.9rem' }}
          >
            Réessayer
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

type Page = 'home' | 'sessions' | 'watch-profiles' | 'newsletter' | 'sources' | 'email-groups' | 'settings' | 'detail';

const SESSION_EVENT_TYPES = [
  'session_created', 'phase_transition', 'plan_updated',
  'research_result', 'report_chunk', 'report_completed',
  'session_completed', 'session_failed',
] as const;

function App() {
  const [currentPage, setCurrentPage] = useState<Page>('home');
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeSessions, setActiveSessions] = useState<Map<string, ActiveSessionInfo>>(new Map());

  // Event bus infrastructure (refs = no re-renders on mutation)
  const esRefs = useRef<Map<string, EventSource>>(new Map());
  const buffers = useRef<Map<string, BusEvent[]>>(new Map());
  const subscribers = useRef<Map<string, Set<(evt: BusEvent) => void>>>(new Map());

  // Emit an event to buffer + all current subscribers, and update session UI state
  const emit = useCallback((sessionId: string, type: string, data: any) => {
    const evt: BusEvent = { type, data };
    buffers.current.get(sessionId)?.push(evt);
    subscribers.current.get(sessionId)?.forEach(cb => cb(evt));

    setActiveSessions(prev => {
      const info = prev.get(sessionId);
      if (!info) return prev;
      const next = new Map(prev);
      if (type === 'session_completed') {
        esRefs.current.get(sessionId)?.close();
        esRefs.current.delete(sessionId);
        next.set(sessionId, { ...info, status: 'completed' });
        window.setTimeout(() => {
          setActiveSessions(current => {
            const delayed = new Map(current);
            if (delayed.get(sessionId)?.status === 'completed') delayed.delete(sessionId);
            return delayed;
          });
        }, 10000);
      } else if (type === 'session_failed') {
        esRefs.current.get(sessionId)?.close();
        esRefs.current.delete(sessionId);
        next.set(sessionId, { ...info, status: 'failed' });
        window.setTimeout(() => {
          setActiveSessions(current => {
            const delayed = new Map(current);
            if (delayed.get(sessionId)?.status === 'failed') delayed.delete(sessionId);
            return delayed;
          });
        }, 10000);
      } else if (type === 'phase_transition' && data.phase) {
        next.set(sessionId, { ...info, phase: data.phase });
      } else if (type === 'research_result') {
        next.set(sessionId, { ...info, articleCount: info.articleCount + (data.count ?? 0) });
      } else {
        return prev;
      }
      return next;
    });
  }, []);

  // Stable subscribe function: replays buffer then registers for future events
  const subscribeToSession = useCallback((
    sessionId: string,
    cb: (evt: BusEvent) => void,
  ): () => void => {
    (buffers.current.get(sessionId) ?? []).forEach(evt => {
      try { cb(evt); } catch { /* noop — prevent buffered-event error from crashing React tree */ }
    });
    if (!subscribers.current.has(sessionId)) subscribers.current.set(sessionId, new Set());
    subscribers.current.get(sessionId)!.add(cb);
    return () => subscribers.current.get(sessionId)?.delete(cb);
  }, []);

  // Start a new session: pre-create DB record to get a stable ID, navigate to its
  // detail page immediately, then open the SSE stream so events start flowing.
  const handleRunLive = useCallback(async (payload: SessionLaunchPayload) => {
    // Optimistic local ID while the POST is in flight
    let sessionId: string = crypto.randomUUID();
    try {
      const created = await ApiService.createSession(payload);
      sessionId = created.session_id;
    } catch {
      // Fall back to client-generated UUID — stream will still create the record
    }

    const streamUrl = ApiService.getStreamUrl(payload, sessionId);

    buffers.current.set(sessionId, []);
    subscribers.current.set(sessionId, new Set());

    const es = new EventSource(streamUrl);
    esRefs.current.set(sessionId, es);

    for (const type of SESSION_EVENT_TYPES) {
      es.addEventListener(type, (e: Event) => {
        try { emit(sessionId, type, JSON.parse((e as MessageEvent).data)); } catch { /* noop */ }
      });
    }
    es.onerror = () => emit(sessionId, 'session_failed', { error: 'Connexion SSE perdue' });

    setActiveSessions(prev => new Map(prev).set(sessionId, {
      sessionId,
      task: payload.title || payload.subject,
      status: 'running',
      phase: 'initializing',
      articleCount: 0,
    }));
    setIsModalOpen(false);
    // Navigate directly to the session detail page with the known ID
    setSelectedSessionId(sessionId);
    setCurrentPage('detail');
  }, [emit]);

  const handleSessionClick = useCallback((id: string) => {
    setSelectedSessionId(id);
    setCurrentPage('detail');
  }, []);

  const handleDeleteSession = useCallback(async (sessionId: string) => {
    esRefs.current.get(sessionId)?.close();
    esRefs.current.delete(sessionId);
    buffers.current.delete(sessionId);
    subscribers.current.delete(sessionId);
    setActiveSessions(prev => {
      const next = new Map(prev);
      next.delete(sessionId);
      return next;
    });
    if (selectedSessionId === sessionId) {
      setSelectedSessionId(null);
      setCurrentPage('sessions');
    }
    await ApiService.deleteSession(sessionId);
  }, [selectedSessionId]);

  const handleRerunSession = useCallback((session: ResearchSession) => {
    handleRunLive({
      title: session.title || session.subject || session.research_brief,
      subject: session.subject || session.title || session.research_brief,
      researchInstructions: session.research_instructions || undefined,
      topics: Array.isArray(session.meta_data?.topics) ? session.meta_data?.topics.filter((topic): topic is string => typeof topic === 'string') : [],
    });
  }, [handleRunLive]);

  const handlePageChange = (page: Page) => {
    setCurrentPage(page);
    if (page !== 'detail') setSelectedSessionId(null);
  };

  // Stable bound-subscribe for the currently selected session (if it's active)
  const boundSubscribe: SubscribeFn | undefined = useMemo(() => {
    if (!selectedSessionId || !buffers.current.has(selectedSessionId)) return undefined;
    return (cb: (evt: BusEvent) => void) => subscribeToSession(selectedSessionId, cb);
  }, [selectedSessionId, subscribeToSession]);

  return (
    <ErrorBoundary>
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--bg-primary)' }}>
      <Sidebar currentPage={currentPage === 'detail' ? 'sessions' : currentPage} onPageChange={handlePageChange} />

      <main style={{
        flex: 1,
        marginLeft: 'var(--sidebar-width)',
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {currentPage === 'home' && (
          <HomePage onNewAnalysis={() => setIsModalOpen(true)} onSessionClick={handleSessionClick} />
        )}

        {currentPage === 'sessions' && (
          <SessionsPage
            onSessionClick={handleSessionClick}
            onRunImmediate={handleRunLive}
            onDeleteSession={handleDeleteSession}
            onRerunSession={handleRerunSession}
            activeSessions={activeSessions}
          />
        )}

        {currentPage === 'detail' && (
          <div className="fade-in" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <SessionDetailPage
              sessionId={selectedSessionId || undefined}
              subscribe={boundSubscribe}
            />
          </div>
        )}

        {currentPage === 'watch-profiles' && <WatchProfilesPage />}
        {currentPage === 'newsletter' && <NewsletterPage />}
        {currentPage === 'settings' && <SettingsPage />}
        {currentPage === 'email-groups' && <EmailGroupsPage />}

        {currentPage === 'sources' && <SourcesPage />}
      </main>

      <LiveRunModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onRun={handleRunLive}
      />
    </div>
    </ErrorBoundary>
  );
}

export default App;
