import React, { useEffect, useRef, useState, useCallback } from 'react';
import { ApiService } from '../services/api';
import type { EmailGroupSummary, ResearchSession, WatchProfile, ActiveSessionInfo, SessionLaunchPayload } from '../types';
import { SessionCard } from '../components/SessionCard';
import { NewSessionModal } from '../components/NewSessionModal';
import {
  Plus, Search, LayoutGrid, List, ChevronDown, Command, AlertCircle,
  CalendarDays, Clock, Repeat, ToggleLeft, ToggleRight, Trash2,
  Zap, FileSearch, MoreVertical, Eye, Play, Mail,
} from 'lucide-react';

interface SessionsPageProps {
  onSessionClick: (id: string) => void;
  onRunImmediate: (payload: SessionLaunchPayload) => void;
  onDeleteSession: (sessionId: string) => Promise<void>;
  onRerunSession: (session: ResearchSession) => void;
  activeSessions: Map<string, ActiveSessionInfo>;
}

const DAYS_FR: Record<string, string> = {
  monday: 'Lun', tuesday: 'Mar', wednesday: 'Mer', thursday: 'Jeu',
  friday: 'Ven', saturday: 'Sam', sunday: 'Dim',
};

function profileScheduleLabel(p: WatchProfile): string {
  const type = p.schedule_type || 'weekly';
  const time = p.schedule_time || '—';
  if (type === 'once') return `Le ${p.schedule_date} à ${time}`;
  if (type === 'weekly') {
    const days = (p.schedule_days || []).map(d => DAYS_FR[d] ?? d).join(', ');
    return `Chaque ${days} à ${time}`;
  }
  if (type === 'monthly') return `Mensuellement à ${time}`;
  if (type === 'custom') return `Tous les ${p.schedule_interval_months ?? 1} mois à ${time}`;
  return time;
}

const phaseLabel: Record<string, string> = {
  initializing: 'Initialisation…',
  planner: 'Génération du plan…',
  supervisor: 'Supervision…',
  dispatcher: 'Recherche…',
  dispatcher_parallel: 'Recherche parallèle…',
  synthesizer: 'Synthèse…',
  emailer: 'Envoi email…',
  mailer: 'Envoi email…',
  completed: 'Terminé',
  done: 'Terminé',
};

const activeMenuItemStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: '10px', width: '100%', padding: '10px 12px',
  borderRadius: '8px', color: 'var(--text-primary)', backgroundColor: 'transparent', fontSize: '0.88rem', textAlign: 'left',
};

const ScheduledProfileCard: React.FC<{
  profile: WatchProfile;
  availableEmailGroups: EmailGroupSummary[];
  onToggle: (profile: WatchProfile) => Promise<void>;
  onRun: (profile: WatchProfile) => Promise<void>;
  onDelete: (profile: WatchProfile) => Promise<void>;
  onSetEmailGroups: (profile: WatchProfile, groupIds: string[]) => Promise<void>;
}> = ({ profile, availableEmailGroups, onToggle, onRun, onDelete, onSetEmailGroups }) => {
  const [menuOpen, setMenuOpen] = useState(false);
  const [emailPanelOpen, setEmailPanelOpen] = useState(false);
  const [updatingGroups, setUpdatingGroups] = useState(false);
  const [busyAction, setBusyAction] = useState<'toggle' | 'run' | 'delete' | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDocClick = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [menuOpen]);

  const runToggle = async () => {
    setBusyAction('toggle');
    try {
      await onToggle(profile);
    } finally {
      setBusyAction(null);
      setMenuOpen(false);
    }
  };

  const runProfile = async () => {
    setBusyAction('run');
    try {
      await onRun(profile);
    } finally {
      setBusyAction(null);
      setMenuOpen(false);
    }
  };


  const toggleEmailGroup = async (groupId: string) => {
    setUpdatingGroups(true);
    const nextIds = profile.email_groups.some((group) => group.id === groupId)
      ? profile.email_groups.filter((group) => group.id !== groupId).map((group) => group.id)
      : [...profile.email_groups.map((group) => group.id), groupId];
    try {
      await onSetEmailGroups(profile, nextIds);
    } finally {
      setUpdatingGroups(false);
    }
  };

  const runDelete = async () => {
    setBusyAction('delete');
    try {
      await onDelete(profile);
    } finally {
      setBusyAction(null);
      setMenuOpen(false);
    }
  };

  return (
    <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px', position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{profile.name}</h4>
          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', margin: 0, lineHeight: '1.45', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as const }}>
            {profile.subject || 'Sujet non défini'}
          </p>
        </div>

        <div ref={menuRef} style={{ position: 'relative', flexShrink: 0 }}>
          <button
            onClick={() => setMenuOpen(v => !v)}
            style={{ color: 'var(--text-muted)', width: '32px', height: '32px', borderRadius: '8px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <MoreVertical size={16} />
          </button>
          {menuOpen && (
            <div style={{ position: 'absolute', top: '40px', right: 0, minWidth: '190px', backgroundColor: 'rgba(15,23,42,0.98)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '8px', boxShadow: '0 20px 40px rgba(0,0,0,0.35)', zIndex: 10, display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <button onClick={runProfile} disabled={busyAction !== null} style={activeMenuItemStyle}><Play size={15} /> Lancer maintenant</button>
              <button onClick={runToggle} disabled={busyAction !== null} style={activeMenuItemStyle}>
                {profile.is_active ? <ToggleRight size={15} /> : <ToggleLeft size={15} />}
                {profile.is_active ? 'Désactiver' : 'Activer'}
              </button>
              <button onClick={runDelete} disabled={busyAction !== null} style={{ ...activeMenuItemStyle, color: '#fca5a5' }}><Trash2 size={15} /> Supprimer</button>
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
        {profile.topics.slice(0, 4).map(t => (
          <span key={t} style={{ fontSize: '0.72rem', padding: '2px 8px', borderRadius: '12px', backgroundColor: 'rgba(124,140,255,0.1)', color: 'var(--accent-primary)' }}>#{t}</span>
        ))}
        {profile.topics.length > 4 && <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>+{profile.topics.length - 4}</span>}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
          <Repeat size={13} />
          <span>{profileScheduleLabel(profile)}</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
        {profile.email_groups.length > 0 ? profile.email_groups.map((group) => (
          <span key={group.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 10px', borderRadius: '999px', backgroundColor: 'rgba(59,130,246,0.10)', color: '#93c5fd', fontSize: '0.78rem' }}>
            <Mail size={12} /> {group.name}
          </span>
        )) : (
          <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Aucun groupe email</span>
        )}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-color)', paddingTop: '12px', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '6px', backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}>{profile.depth}</span>
          <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '6px', backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}>{profile.format}</span>
        </div>
        <button
          type="button"
          onClick={() => setEmailPanelOpen((value) => !value)}
          style={{ fontSize: '0.75rem', color: 'var(--accent-primary)', backgroundColor: 'transparent', border: 'none' }}
        >
          {emailPanelOpen ? 'Fermer les groupes' : 'Gérer les groupes'}
        </button>
        {profile.last_run_at ? (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <Clock size={11} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle' }} />
            {new Date(profile.last_run_at).toLocaleDateString('fr-FR')}
          </span>
        ) : (
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Jamais exécutée</span>
        )}
      </div>

      {emailPanelOpen && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '12px', borderTop: '1px dashed var(--border-color)' }}>
          {availableEmailGroups.length === 0 ? (
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.5 }}>
              Aucun groupe disponible. Créez d'abord un groupe dans la page Email Groups.
            </div>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {availableEmailGroups.map((group) => {
                const active = profile.email_groups.some((item) => item.id === group.id);
                return (
                  <button
                    key={group.id}
                    type="button"
                    disabled={updatingGroups}
                    onClick={() => void toggleEmailGroup(group.id)}
                    style={{
                      padding: '7px 11px',
                      borderRadius: '999px',
                      border: active ? '1px solid rgba(124,140,255,0.35)' : '1px solid var(--border-color)',
                      backgroundColor: active ? 'rgba(124,140,255,0.10)' : 'rgba(255,255,255,0.03)',
                      color: active ? 'var(--accent-primary)' : 'var(--text-secondary)',
                      fontSize: '0.78rem',
                      fontWeight: 600,
                    }}
                  >
                    {group.name} · {group.recipient_count}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const ActiveSessionCard: React.FC<{ info: ActiveSessionInfo; onClick: () => void; onDelete: () => void }> = ({ info, onClick, onDelete }) => {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div
      className="card"
      style={{
        padding: '20px',
        position: 'relative',
        border: info.status === 'running'
          ? '1px solid rgba(34,197,94,0.35)'
          : info.status === 'completed'
            ? '1px solid rgba(167,139,250,0.35)'
            : '1px solid rgba(239,68,68,0.35)',
        backgroundColor: info.status === 'running'
          ? 'rgba(34,197,94,0.04)'
          : info.status === 'completed'
            ? 'rgba(167,139,250,0.04)'
            : 'rgba(239,68,68,0.04)',
        transition: 'box-shadow 0.2s',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px', gap: '12px' }}>
        <div onClick={onClick} style={{ cursor: 'pointer', flex: 1, minWidth: 0 }}>
          <h4 style={{
            fontSize: '0.95rem', fontWeight: 600,
            overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as any,
            lineHeight: '1.4',
          }}>
            {info.task}
          </h4>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', flexShrink: 0 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            fontSize: '0.72rem', fontWeight: 700, padding: '4px 10px', borderRadius: '20px',
            backgroundColor: info.status === 'running'
              ? 'rgba(34,197,94,0.15)' : info.status === 'completed'
              ? 'rgba(167,139,250,0.15)' : 'rgba(239,68,68,0.15)',
            color: info.status === 'running' ? '#22C55E' : info.status === 'completed' ? '#a78bfa' : '#ef4444',
          }}>
            {info.status === 'running' && (
              <div style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#22C55E', animation: 'pulse 1.5s ease-in-out infinite' }} />
            )}
            {info.status === 'running' ? 'EN COURS' : info.status === 'completed' ? 'TERMINE' : 'ECHEC'}
          </div>
          <button onClick={() => setMenuOpen(v => !v)} style={{ color: 'var(--text-muted)', width: '32px', height: '32px', borderRadius: '8px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <MoreVertical size={16} />
          </button>
          {menuOpen && (
            <div style={{ position: 'absolute', top: '54px', right: '20px', minWidth: '170px', backgroundColor: 'rgba(15,23,42,0.98)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '8px', boxShadow: '0 20px 40px rgba(0,0,0,0.35)', zIndex: 10, display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <button onClick={() => { setMenuOpen(false); onClick(); }} style={activeMenuItemStyle}><Eye size={15} /> Ouvrir</button>
              <button onClick={() => { setMenuOpen(false); void onDelete(); }} style={{ ...activeMenuItemStyle, color: '#fca5a5' }}><Trash2 size={15} /> Supprimer</button>
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
        {info.status === 'running' && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <Zap size={12} color="#22C55E" />
            <span style={{ color: 'var(--text-secondary)' }}>{phaseLabel[info.phase] ?? info.phase}</span>
          </div>
        )}
        {info.articleCount > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
            <FileSearch size={12} />
            <span>{info.articleCount} article{info.articleCount > 1 ? 's' : ''} trouve{info.articleCount > 1 ? 's' : ''}</span>
          </div>
        )}
      </div>
      <style>{`@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }`}</style>
    </div>
  );
};

export const SessionsPage: React.FC<SessionsPageProps> = ({ onSessionClick, onRunImmediate, onDeleteSession, onRerunSession, activeSessions }) => {
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const [profiles, setProfiles] = useState<WatchProfile[]>([]);
  const [emailGroups, setEmailGroups] = useState<EmailGroupSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [viewGrid, setViewGrid] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sessionData, profileData, emailGroupData] = await Promise.all([
        ApiService.getSessions(50),
        ApiService.getWatchProfiles(),
        ApiService.getEmailGroups(true),
      ]);
      setSessions(sessionData.sessions);
      setProfiles(profileData);
      setEmailGroups(emailGroupData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Poll DB every 5s while any session is running
  useEffect(() => {
    const hasBufferedActive = activeSessions.size > 0;
    const hasRunningInDb = sessions.some(s => s.status === 'running');
    if (!hasBufferedActive && !hasRunningInDb) return;
    const id = setInterval(() => {
      ApiService.getSessions(50)
        .then(data => setSessions(data.sessions))
        .catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, [activeSessions, sessions]);

  // Active sessions: only keep actually running sessions in the live section.
  const runningActiveSessionsList = Array.from(activeSessions.values())
    .filter(info => info.status === 'running');
  const runningActiveIds = new Set(runningActiveSessionsList.map(info => info.sessionId));

  // DB sessions: hide ones that are currently running live.
  const dbSessions = sessions.filter(s => !runningActiveIds.has(s.id));

  // Derived counts
  const countOf = (status: string) => sessions.filter(s => s.status === status).length;
  const scheduledProfiles = profiles.filter(p => p.is_active);

  const filters = [
    { id: 'all', label: 'Toutes', count: sessions.length },
    { id: 'running', label: 'En cours', count: countOf('running'), color: '#22C55E' },
    { id: 'scheduled', label: 'Programmées', count: scheduledProfiles.length, color: '#3B82F6' },
    { id: 'completed', label: 'Terminées', count: countOf('completed'), color: '#A78BFA' },
    { id: 'failed', label: 'Échouées', count: countOf('failed'), color: '#EF4444' },
  ];

  const filteredSessions = dbSessions.filter(s => {
    const q = searchQuery.toLowerCase();
    const haystack = `${s.title || ''} ${s.subject || ''} ${s.research_brief}`.toLowerCase();
    const matchesSearch = haystack.includes(q);
    if (activeFilter === 'all') return matchesSearch;
    if (activeFilter === 'scheduled') return false;
    return matchesSearch && s.status === activeFilter;
  });

  const filteredProfiles = activeFilter === 'all' || activeFilter === 'scheduled'
    ? profiles.filter(p => {
        const q = searchQuery.toLowerCase();
        return p.name.toLowerCase().includes(q) || (p.subject || '').toLowerCase().includes(q) || p.topics.some(t => t.toLowerCase().includes(q));
      })
    : [];

  const handleToggleProfile = async (p: WatchProfile) => {
    try {
      await ApiService.updateWatchProfile(p.id, { is_active: !p.is_active });
      setProfiles(prev => prev.map(x => x.id === p.id ? { ...x, is_active: !x.is_active } : x));
    } catch {}
  };

  const handleRunProfile = async (p: WatchProfile) => {
    try {
      await ApiService.runProfile(p.id);
      setProfiles(prev => prev.map(x => x.id === p.id ? { ...x, last_run_at: new Date().toISOString() } : x));
    } catch {}
  };


  const handleSetProfileEmailGroups = async (profile: WatchProfile, groupIds: string[]) => {
    try {
      const updated = await ApiService.updateWatchProfile(profile.id, { email_group_ids: groupIds });
      setProfiles((prev) => prev.map((item) => item.id === profile.id ? updated : item));
    } catch {}
  };

  const handleDeleteProfile = async (id: string) => {
    if (!window.confirm('Supprimer cette session programmée ?')) return;
    try {
      await ApiService.deleteWatchProfile(id);
      setProfiles(prev => prev.filter(p => p.id !== id));
    } catch {}
  };

  const handleDeleteSessionClick = async (session: ResearchSession) => {
    const title = session.title || session.subject || session.research_brief;
    if (!window.confirm(`Supprimer définitivement la session "${title}" ?`)) return;
    await onDeleteSession(session.id);
    setSessions(prev => prev.filter(s => s.id !== session.id));
  };

  const handleDeleteActiveSession = async (sessionId: string, title: string) => {
    if (!window.confirm(`Supprimer définitivement la session "${title}" ?`)) return;
    await onDeleteSession(sessionId);
    setSessions(prev => prev.filter(s => s.id !== sessionId));
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="fade-in page-container" style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>

      {/* Header */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '4px' }}>Sessions</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>Gérez vos veilles technologiques</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <div style={{ position: 'relative' }}>
            <Search size={16} style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Rechercher une session..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                width: 'clamp(180px, 28vw, 300px)',
                padding: '10px 40px 10px 40px',
                backgroundColor: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                color: 'var(--text-primary)',
                fontSize: '0.88rem',
                outline: 'none',
              }}
            />
            <div style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', display: 'flex', alignItems: 'center', gap: '3px', color: 'var(--text-muted)', fontSize: '0.72rem', backgroundColor: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
              <Command size={9} /><span>K</span>
            </div>
          </div>

          <button
            onClick={() => setIsModalOpen(true)}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              padding: '10px 18px',
              backgroundColor: 'var(--accent-primary)',
              borderRadius: '10px',
              color: 'white',
              fontWeight: 600,
              fontSize: '0.92rem',
              boxShadow: '0 4px 20px rgba(124,140,255,0.3)',
              whiteSpace: 'nowrap',
            }}
          >
            <Plus size={16} /> Nouvelle session
          </button>
        </div>
      </header>

      {/* Filter bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {filters.map(f => (
            <button
              key={f.id}
              onClick={() => setActiveFilter(f.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '7px 14px',
                borderRadius: '8px',
                backgroundColor: activeFilter === f.id ? 'rgba(124,140,255,0.15)' : 'transparent',
                color: activeFilter === f.id ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontSize: '0.88rem',
                fontWeight: activeFilter === f.id ? 600 : 400,
                border: activeFilter === f.id ? '1px solid rgba(124,140,255,0.3)' : '1px solid transparent',
              }}
            >
              {f.color && <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: f.color }} />}
              {f.label}
              <span style={{ opacity: 0.5, fontSize: '0.78rem' }}>{f.count}</span>
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
            <span>Trier par</span>
            <button style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-primary)', fontWeight: 600 }}>
              Plus récentes <ChevronDown size={14} />
            </button>
          </div>
          <div style={{ display: 'flex', backgroundColor: 'rgba(255,255,255,0.03)', padding: '3px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            <button onClick={() => setViewGrid(true)} style={{ padding: '5px', borderRadius: '6px', backgroundColor: viewGrid ? 'rgba(124,140,255,0.2)' : 'transparent', color: viewGrid ? 'var(--accent-primary)' : 'var(--text-muted)' }}>
              <LayoutGrid size={16} />
            </button>
            <button onClick={() => setViewGrid(false)} style={{ padding: '5px', borderRadius: '6px', backgroundColor: !viewGrid ? 'rgba(124,140,255,0.2)' : 'transparent', color: !viewGrid ? 'var(--accent-primary)' : 'var(--text-muted)' }}>
              <List size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '80px', gap: '16px' }}>
          <div className="animate-spin" style={{ width: '36px', height: '36px', border: '3px solid var(--bg-surface)', borderTop: '3px solid var(--accent-primary)', borderRadius: '50%' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Chargement des sessions...</p>
        </div>
      ) : error ? (
        <div className="card" style={{ padding: '24px', backgroundColor: 'var(--status-error-bg)', borderColor: 'var(--status-error)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
            <AlertCircle size={22} color="var(--status-error)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <h3 style={{ color: 'var(--status-error)', marginBottom: '4px' }}>Erreur de chargement</h3>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>{error}</p>
              <button
                onClick={fetchAll}
                style={{ marginTop: '12px', padding: '6px 14px', backgroundColor: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '6px', color: 'var(--status-error)', fontSize: '0.82rem', fontWeight: 600 }}
              >
                Réessayer
              </button>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Live / active sessions section */}
          {runningActiveSessionsList.length > 0 && (activeFilter === 'all' || activeFilter === 'running') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: '#22C55E', animation: 'pulse 1.5s ease-in-out infinite' }} />
                <h3 style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  En cours
                </h3>
                <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-color)' }} />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '16px' }}>
                {runningActiveSessionsList.map(info => (
                  <ActiveSessionCard key={info.sessionId} info={info} onClick={() => onSessionClick(info.sessionId)} onDelete={() => handleDeleteActiveSession(info.sessionId, info.task)} />
                ))}
              </div>
            </div>
          )}

          {/* Scheduled profiles section */}
          {filteredProfiles.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {(activeFilter === 'all' || activeFilter === 'scheduled') && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <CalendarDays size={16} color="var(--accent-primary)" />
                  <h3 style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Sessions programmées
                  </h3>
                  <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-color)' }} />
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '16px' }}>
                {filteredProfiles.map(p => (
                  <ScheduledProfileCard
                    key={p.id}
                    profile={p}
                    availableEmailGroups={emailGroups}
                    onToggle={handleToggleProfile}
                    onRun={handleRunProfile}
                    onDelete={async (profile) => handleDeleteProfile(profile.id)}
                    onSetEmailGroups={handleSetProfileEmailGroups}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Past sessions section */}
          {activeFilter !== 'scheduled' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {filteredProfiles.length > 0 && activeFilter === 'all' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <h3 style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Historique
                  </h3>
                  <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--border-color)' }} />
                </div>
              )}

              {filteredSessions.length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: viewGrid ? 'repeat(auto-fill, minmax(400px, 1fr))' : '1fr', gap: viewGrid ? '20px' : '10px' }}>
                  {filteredSessions.map(s => (
                    <SessionCard key={s.id} session={s} onClick={onSessionClick} onDelete={handleDeleteSessionClick} onRerun={onRerunSession} />
                  ))}
                </div>
              ) : (
                <div style={{ textAlign: 'center', padding: '80px 0' }}>
                  <p style={{ color: 'var(--text-muted)', marginBottom: '16px' }}>
                    {searchQuery ? 'Aucune session ne correspond à votre recherche.' : 'Aucune session pour le moment.'}
                  </p>
                  {!searchQuery && (
                    <button
                      onClick={() => setIsModalOpen(true)}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '10px 20px', backgroundColor: 'var(--accent-primary)', borderRadius: '8px', color: 'white', fontWeight: 600 }}
                    >
                      <Plus size={16} /> Créer une session
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Modal */}
      <NewSessionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onRunImmediate={(payload) => {
          setIsModalOpen(false);
          onRunImmediate(payload);
        }}
        onScheduled={() => fetchAll()}
      />
    </div>
  );
};
