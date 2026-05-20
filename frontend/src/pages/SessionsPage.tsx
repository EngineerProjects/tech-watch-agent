import React, { useEffect, useState, useCallback } from 'react';
import { ApiService } from '../services/api';
import type { ResearchSession, WatchProfile } from '../types';
import { SessionCard } from '../components/SessionCard';
import { NewSessionModal } from '../components/NewSessionModal';
import {
  Plus, Search, LayoutGrid, List, ChevronDown, Command, AlertCircle,
  CalendarDays, Clock, Repeat, ToggleLeft, ToggleRight, Trash2,
} from 'lucide-react';

interface SessionsPageProps {
  onSessionClick: (id: string) => void;
  onRunImmediate: (task: string, topics: string[]) => void;
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

export const SessionsPage: React.FC<SessionsPageProps> = ({ onSessionClick, onRunImmediate }) => {
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const [profiles, setProfiles] = useState<WatchProfile[]>([]);
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
      const [sessionData, profileData] = await Promise.all([
        ApiService.getSessions(50),
        ApiService.getWatchProfiles(),
      ]);
      setSessions(sessionData.sessions);
      setProfiles(profileData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

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

  const filteredSessions = sessions.filter(s => {
    const q = searchQuery.toLowerCase();
    const matchesSearch = s.research_brief.toLowerCase().includes(q);
    if (activeFilter === 'all') return matchesSearch;
    if (activeFilter === 'scheduled') return false;
    return matchesSearch && s.status === activeFilter;
  });

  const filteredProfiles = activeFilter === 'all' || activeFilter === 'scheduled'
    ? profiles.filter(p => {
        const q = searchQuery.toLowerCase();
        return p.name.toLowerCase().includes(q) || p.topics.some(t => t.toLowerCase().includes(q));
      })
    : [];

  const handleToggleProfile = async (p: WatchProfile) => {
    try {
      await ApiService.updateWatchProfile(p.id, { is_active: !p.is_active });
      setProfiles(prev => prev.map(x => x.id === p.id ? { ...x, is_active: !x.is_active } : x));
    } catch {}
  };

  const handleDeleteProfile = async (id: string) => {
    if (!window.confirm('Supprimer cette session programmée ?')) return;
    try {
      await fetch(`${(ApiService as any)['API_BASE_URL'] || 'http://localhost:8000'}/watch-profiles/${id}`, { method: 'DELETE' });
      setProfiles(prev => prev.filter(p => p.id !== id));
    } catch {}
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
                  <div key={p.id} className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <h4 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</h4>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
                          {p.topics.slice(0, 4).map(t => (
                            <span key={t} style={{ fontSize: '0.72rem', padding: '2px 8px', borderRadius: '12px', backgroundColor: 'rgba(124,140,255,0.1)', color: 'var(--accent-primary)' }}>#{t}</span>
                          ))}
                          {p.topics.length > 4 && <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>+{p.topics.length - 4}</span>}
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0, marginLeft: '12px' }}>
                        <button
                          onClick={() => handleToggleProfile(p)}
                          style={{ color: p.is_active ? 'var(--status-success)' : 'var(--text-muted)', backgroundColor: 'transparent' }}
                          title={p.is_active ? 'Désactiver' : 'Activer'}
                        >
                          {p.is_active ? <ToggleRight size={22} /> : <ToggleLeft size={22} />}
                        </button>
                        <button
                          onClick={() => handleDeleteProfile(p.id)}
                          style={{ color: 'var(--text-muted)', backgroundColor: 'transparent', padding: '2px' }}
                          title="Supprimer"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                        <Repeat size={13} />
                        <span>{profileScheduleLabel(p)}</span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-color)', paddingTop: '12px' }}>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '6px', backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}>{p.depth}</span>
                        <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '6px', backgroundColor: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' }}>{p.format}</span>
                      </div>
                      {p.last_run_at ? (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          <Clock size={11} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'middle' }} />
                          {new Date(p.last_run_at).toLocaleDateString('fr-FR')}
                        </span>
                      ) : (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Jamais exécutée</span>
                      )}
                    </div>
                  </div>
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
                    <SessionCard key={s.id} session={s} onClick={onSessionClick} />
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
        onRunImmediate={(task, topics) => {
          setIsModalOpen(false);
          onRunImmediate(task, topics);
        }}
        onScheduled={() => fetchAll()}
      />
    </div>
  );
};
