import React, { useState, useEffect } from 'react';
import {
  Plus,
  Search,
  Settings2,
  Play,
  Clock,
  BarChart3,
  MoreVertical,
  CheckCircle2,
  Loader2,
  AlertCircle
} from 'lucide-react';
import { ApiService } from '../services/api';
import type { WatchProfile } from '../types';

interface TopicCardProps {
  profile: WatchProfile;
  onToggle: (id: string, isActive: boolean) => void;
  onRun: (id: string) => void;
}

const TopicCard = ({ profile, onToggle, onRun }: TopicCardProps) => {
  const [enabled, setEnabled] = useState(profile.is_active);
  const [toggling, setToggling] = useState(false);
  const [running, setRunning] = useState(false);

  const handleToggle = async () => {
    setToggling(true);
    try {
      await onToggle(profile.id, !enabled);
      setEnabled(prev => !prev);
    } finally {
      setToggling(false);
    }
  };

  const handleRun = async () => {
    setRunning(true);
    try {
      await onRun(profile.id);
    } finally {
      setRunning(false);
    }
  };

  const lastRunLabel = profile.last_run_at
    ? new Date(profile.last_run_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
    : 'Jamais';

  const cadenceLabel = profile.schedule_days.length > 0
    ? `${profile.schedule_days.join(', ')} ${profile.schedule_time ?? ''}`
    : 'Manuelle';

  return (
    <div className="card" style={{
      padding: '24px',
      display: 'flex',
      flexDirection: 'column',
      gap: '20px',
      backgroundColor: enabled ? 'rgba(124, 140, 255, 0.02)' : 'rgba(17, 24, 39, 0.2)',
      borderColor: enabled ? 'rgba(124, 140, 255, 0.2)' : 'var(--border-color)',
      opacity: enabled ? 1 : 0.7
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, marginRight: '16px' }}>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)' }}>{profile.name}</h3>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
            {profile.topics.slice(0, 4).map(t => (
              <span key={t} style={{ fontSize: '0.72rem', color: 'var(--text-muted)', backgroundColor: 'rgba(255,255,255,0.04)', padding: '2px 8px', borderRadius: '4px' }}>
                {t}
              </span>
            ))}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={handleToggle}
            disabled={toggling}
            style={{
              width: '36px',
              height: '20px',
              borderRadius: '10px',
              backgroundColor: enabled ? 'var(--accent-primary)' : 'rgba(255,255,255,0.1)',
              position: 'relative',
              transition: 'all 0.3s ease',
              opacity: toggling ? 0.6 : 1
            }}
          >
            <div style={{
              width: '14px',
              height: '14px',
              borderRadius: '50%',
              backgroundColor: 'white',
              position: 'absolute',
              top: '3px',
              left: enabled ? '19px' : '3px',
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
            }} />
          </button>
          <button style={{ color: 'var(--text-muted)' }}><MoreVertical size={20} /></button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          <Clock size={14} />
          <span>{cadenceLabel}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: enabled ? 'var(--status-success)' : 'var(--text-muted)', fontSize: '0.85rem' }}>
          <Play size={14} />
          <span>{enabled ? 'Active' : 'Inactive'}</span>
        </div>
      </div>

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '16px',
        backgroundColor: 'rgba(255,255,255,0.02)',
        borderRadius: '12px',
        border: '1px solid var(--border-color)'
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Dernier Run</span>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{lastRunLabel}</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Format</span>
          <span style={{ fontSize: '0.85rem', color: 'var(--accent-secondary)', fontWeight: 600, textTransform: 'capitalize' }}>{profile.format}</span>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '4px' }}>
        <div style={{ display: 'flex', gap: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
            <BarChart3 size={14} color="var(--accent-primary)" />
            <span style={{ fontSize: '0.85rem', textTransform: 'capitalize' }}>{profile.depth}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
            <CheckCircle2 size={14} color="var(--status-success)" />
            <span style={{ fontSize: '0.85rem' }}>{profile.topics.length} topics</span>
          </div>
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '6px 14px',
            borderRadius: '8px',
            backgroundColor: 'rgba(124, 140, 255, 0.1)',
            border: '1px solid rgba(124, 140, 255, 0.2)',
            color: 'var(--accent-primary)',
            fontSize: '0.85rem',
            fontWeight: 600,
            opacity: running ? 0.6 : 1
          }}
        >
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {running ? 'Lancement...' : 'Lancer'}
        </button>
      </div>
    </div>
  );
};

export const TopicsPage: React.FC = () => {
  const [profiles, setProfiles] = useState<WatchProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    ApiService.getWatchProfiles()
      .then(setProfiles)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleToggle = async (id: string, isActive: boolean) => {
    await ApiService.updateWatchProfile(id, { is_active: isActive });
  };

  const handleRun = async (id: string) => {
    await ApiService.runProfile(id);
  };

  const filtered = profiles.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.topics.some(t => t.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="fade-in page-container" style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '4px' }}>Topics</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>Gérez vos axes de veille et thématiques récurrentes</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ position: 'relative' }}>
            <Search size={18} style={{ position: 'absolute', left: '16px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Rechercher un topic..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                width: '280px',
                padding: '10px 16px 10px 44px',
                backgroundColor: 'rgba(255,255,255,0.03)',
                border: '1px solid var(--border-color)',
                borderRadius: '10px',
                color: 'var(--text-primary)',
                fontSize: '0.9rem',
                outline: 'none'
              }}
            />
          </div>
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
            <Settings2 size={18} /> Configurer
          </button>
          <button style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 20px',
            backgroundColor: 'var(--accent-primary)',
            borderRadius: '10px',
            color: 'white',
            fontWeight: 600,
            fontSize: '0.95rem'
          }}>
            <Plus size={18} /> Nouveau topic
          </button>
        </div>
      </header>

      {loading ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '60px', justifyContent: 'center', color: 'var(--text-muted)' }}>
          <Loader2 size={24} className="animate-spin" />
          <span>Chargement des profils...</span>
        </div>
      ) : error ? (
        <div className="card" style={{ padding: '24px', backgroundColor: 'var(--status-error-bg)', borderColor: 'var(--status-error)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', color: 'var(--status-error)' }}>
            <AlertCircle size={24} />
            <div>
              <h3 style={{ color: 'var(--status-error)' }}>Erreur de chargement</h3>
              <p style={{ fontSize: '0.9rem', opacity: 0.8 }}>{error}</p>
            </div>
          </div>
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '80px 0' }}>
          <p style={{ color: 'var(--text-muted)', marginBottom: '16px' }}>
            {profiles.length === 0 ? 'Aucun profil de veille configuré.' : 'Aucun profil correspond à votre recherche.'}
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '24px' }}>
          {filtered.map(profile => (
            <TopicCard
              key={profile.id}
              profile={profile}
              onToggle={handleToggle}
              onRun={handleRun}
            />
          ))}
        </div>
      )}

      <style>{`
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};
