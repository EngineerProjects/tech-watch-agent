import React, { useState, useEffect } from 'react';
import {
  Plus,
  Search,
  Settings2,
  Play,
  Clock,
  BarChart3,
  Pencil,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Trash2,
  X,
  Save,
} from 'lucide-react';
import { ApiService } from '../services/api';
import type { WatchProfile } from '../types';

interface TopicsPageProps {
  onOpenSettings?: () => void;
}

interface TopicCardProps {
  profile: WatchProfile;
  onToggle: (id: string, isActive: boolean) => Promise<void>;
  onRun: (id: string) => Promise<void>;
  onEdit: (profile: WatchProfile) => void;
  onDelete: (profile: WatchProfile) => Promise<void>;
}

type Depth = 'brief' | 'standard' | 'deep';
type ReportFormat = 'digest' | 'report' | 'newsletter';
type ScheduleType = 'weekly' | 'once' | 'monthly' | 'custom';

type EditorState = {
  name: string;
  subject: string;
  topicsInput: string;
  depth: Depth;
  format: ReportFormat;
  language: 'fr' | 'en';
  angle: string;
  focus: string;
  scheduleType: ScheduleType;
  scheduleTime: string;
  scheduleDays: string[];
  scheduleDate: string;
  scheduleIntervalMonths: number;
  isActive: boolean;
};

const DAYS: Array<{ key: string; short: string; label: string }> = [
  { key: 'monday', short: 'Lu', label: 'Lundi' },
  { key: 'tuesday', short: 'Ma', label: 'Mardi' },
  { key: 'wednesday', short: 'Me', label: 'Mercredi' },
  { key: 'thursday', short: 'Je', label: 'Jeudi' },
  { key: 'friday', short: 'Ve', label: 'Vendredi' },
  { key: 'saturday', short: 'Sa', label: 'Samedi' },
  { key: 'sunday', short: 'Di', label: 'Dimanche' },
];

const DEFAULT_EDITOR: EditorState = {
  name: '',
  subject: '',
  topicsInput: '',
  depth: 'standard',
  format: 'report',
  language: 'fr',
  angle: 'both',
  focus: '',
  scheduleType: 'weekly',
  scheduleTime: '08:00',
  scheduleDays: ['monday'],
  scheduleDate: '',
  scheduleIntervalMonths: 3,
  isActive: true,
};

function toEditorState(profile?: WatchProfile | null): EditorState {
  if (!profile) return { ...DEFAULT_EDITOR };
  return {
    name: profile.name,
    subject: profile.subject || profile.name,
    topicsInput: profile.topics.join(', '),
    depth: profile.depth,
    format: profile.format,
    language: profile.language === 'en' ? 'en' : 'fr',
    angle: profile.angle || 'both',
    focus: profile.focus || '',
    scheduleType: profile.schedule_type || 'weekly',
    scheduleTime: profile.schedule_time || '08:00',
    scheduleDays: profile.schedule_days?.length ? profile.schedule_days : ['monday'],
    scheduleDate: profile.schedule_date || '',
    scheduleIntervalMonths: profile.schedule_interval_months || 3,
    isActive: profile.is_active,
  };
}

function parseTopics(value: string): string[] {
  return value
    .split(',')
    .map(topic => topic.trim().toLowerCase())
    .filter(Boolean)
    .filter((topic, index, arr) => arr.indexOf(topic) === index);
}

const TopicCard = ({ profile, onToggle, onRun, onEdit, onDelete }: TopicCardProps) => {
  const [enabled, setEnabled] = useState(profile.is_active);
  const [toggling, setToggling] = useState(false);
  const [running, setRunning] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setEnabled(profile.is_active);
  }, [profile.is_active]);

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

  const handleDelete = async () => {
    if (!window.confirm(`Supprimer le profil "${profile.name}" ?`)) return;
    setDeleting(true);
    try {
      await onDelete(profile);
    } finally {
      setDeleting(false);
    }
  };

  const lastRunLabel = profile.last_run_at
    ? new Date(profile.last_run_at).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
    : 'Jamais';

  const cadenceLabel = profile.schedule_type === 'weekly'
    ? (profile.schedule_days.length > 0 ? `${profile.schedule_days.join(', ')} ${profile.schedule_time ?? ''}` : 'Hebdomadaire')
    : profile.schedule_type === 'once'
      ? `Le ${profile.schedule_date || '—'} à ${profile.schedule_time ?? '—'}`
      : profile.schedule_type === 'monthly'
        ? `Mensuel à ${profile.schedule_time ?? '—'}`
        : profile.schedule_type === 'custom'
          ? `Tous les ${profile.schedule_interval_months ?? 1} mois à ${profile.schedule_time ?? '—'}`
          : 'Manuelle';

  return (
    <div className="card" style={{
      padding: '24px',
      display: 'flex',
      flexDirection: 'column',
      gap: '20px',
      backgroundColor: enabled ? 'rgba(124, 140, 255, 0.02)' : 'rgba(17, 24, 39, 0.2)',
      borderColor: enabled ? 'rgba(124, 140, 255, 0.2)' : 'var(--border-color)',
      opacity: enabled ? 1 : 0.7,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: 1, marginRight: '16px', minWidth: 0 }}>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{profile.name}</h3>
          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', margin: 0, lineHeight: '1.45', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as const }}>{profile.subject || profile.name}</p>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
            {profile.topics.slice(0, 4).map(t => (
              <span key={t} style={{ fontSize: '0.72rem', color: 'var(--text-muted)', backgroundColor: 'rgba(255,255,255,0.04)', padding: '2px 8px', borderRadius: '4px' }}>
                {t}
              </span>
            ))}
            {profile.topics.length > 4 && (
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>+{profile.topics.length - 4}</span>
            )}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={handleToggle}
            disabled={toggling}
            title={enabled ? 'Désactiver' : 'Activer'}
            style={{
              width: '36px',
              height: '20px',
              borderRadius: '10px',
              backgroundColor: enabled ? 'var(--accent-primary)' : 'rgba(255,255,255,0.1)',
              position: 'relative',
              transition: 'all 0.3s ease',
              opacity: toggling ? 0.6 : 1,
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
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
            }} />
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
          <Clock size={14} />
          <span>{cadenceLabel}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: enabled ? 'var(--status-success)' : 'var(--text-muted)', fontSize: '0.85rem' }}>
          <Play size={14} />
          <span>{enabled ? 'Actif' : 'Inactif'}</span>
        </div>
      </div>

      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        padding: '16px',
        backgroundColor: 'rgba(255,255,255,0.02)',
        borderRadius: '12px',
        border: '1px solid var(--border-color)',
        gap: '16px',
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Dernier run</span>
          <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{lastRunLabel}</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', textAlign: 'right' }}>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Format</span>
          <span style={{ fontSize: '0.85rem', color: 'var(--accent-secondary)', fontWeight: 600, textTransform: 'capitalize' }}>{profile.format}</span>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap', paddingTop: '4px' }}>
        <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
            <BarChart3 size={14} color="var(--accent-primary)" />
            <span style={{ fontSize: '0.85rem', textTransform: 'capitalize' }}>{profile.depth}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)' }}>
            <CheckCircle2 size={14} color="var(--status-success)" />
            <span style={{ fontSize: '0.85rem' }}>{profile.topics.length} topics</span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <button
            onClick={() => onEdit(profile)}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '8px',
              border: '1px solid var(--border-color)', backgroundColor: 'rgba(255,255,255,0.03)', color: 'var(--text-secondary)',
              fontSize: '0.82rem', fontWeight: 600,
            }}
          >
            <Pencil size={14} /> Modifier
          </button>
          <button
            onClick={handleDelete}
            disabled={deleting}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', borderRadius: '8px',
              border: '1px solid rgba(239,68,68,0.22)', backgroundColor: 'rgba(239,68,68,0.08)', color: '#ef4444',
              fontSize: '0.82rem', fontWeight: 600, opacity: deleting ? 0.6 : 1,
            }}
          >
            {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />} Supprimer
          </button>
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
              opacity: running ? 0.6 : 1,
            }}
          >
            {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
            {running ? 'Lancement...' : 'Lancer'}
          </button>
        </div>
      </div>
    </div>
  );
};

function TopicEditorModal({
  profile,
  value,
  saving,
  error,
  onClose,
  onChange,
  onSubmit,
}: {
  profile: WatchProfile | null;
  value: EditorState;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onChange: (patch: Partial<EditorState>) => void;
  onSubmit: () => void;
}) {
  const isEdit = !!profile;

  const toggleDay = (day: string) => {
    const next = value.scheduleDays.includes(day)
      ? value.scheduleDays.filter(entry => entry !== day)
      : [...value.scheduleDays, day];
    onChange({ scheduleDays: next });
  };

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1100, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.72)', backdropFilter: 'blur(6px)' }} />
      <div className="card" style={{ position: 'relative', width: '100%', maxWidth: '760px', maxHeight: 'calc(100vh - 40px)', overflowY: 'auto', padding: '28px', display: 'flex', flexDirection: 'column', gap: '24px', backgroundColor: 'var(--bg-surface)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
          <div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '4px' }}>{isEdit ? 'Modifier le profil' : 'Nouveau topic'}</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>Créez ou ajustez un profil de veille exécutable par le scheduler.</p>
          </div>
          <button onClick={onClose} style={{ color: 'var(--text-muted)', padding: '6px', borderRadius: '8px', backgroundColor: 'rgba(255,255,255,0.04)' }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', gridColumn: '1 / -1' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Nom</span>
            <input value={value.name} onChange={e => onChange({ name: e.target.value })} placeholder="Veille IA open-source" style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }} />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', gridColumn: '1 / -1' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Subject</span>
            <textarea value={value.subject} onChange={e => onChange({ subject: e.target.value })} placeholder="What happened this week in open-source LLMs and reasoning models?" rows={3} style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)', resize: 'vertical' }} />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', gridColumn: '1 / -1' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Topics</span>
            <textarea value={value.topicsInput} onChange={e => onChange({ topicsInput: e.target.value })} placeholder="llm, ai agents, open source" rows={3} style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)', resize: 'vertical' }} />
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Sépare les topics par des virgules.</span>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Profondeur</span>
            <select value={value.depth} onChange={e => onChange({ depth: e.target.value as Depth })} style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }}>
              <option value="brief">Brief</option>
              <option value="standard">Standard</option>
              <option value="deep">Deep</option>
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Format</span>
            <select value={value.format} onChange={e => onChange({ format: e.target.value as ReportFormat })} style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }}>
              <option value="digest">Digest</option>
              <option value="report">Report</option>
              <option value="newsletter">Newsletter</option>
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Langue</span>
            <select value={value.language} onChange={e => onChange({ language: e.target.value as 'fr' | 'en' })} style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }}>
              <option value="fr">Français</option>
              <option value="en">English</option>
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Angle</span>
            <select value={value.angle} onChange={e => onChange({ angle: e.target.value })} style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }}>
              <option value="both">Technique + business</option>
              <option value="technical">Technique</option>
              <option value="business">Business</option>
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', gridColumn: '1 / -1' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Research Instructions</span>
            <textarea value={value.focus} onChange={e => onChange({ focus: e.target.value })} placeholder="Clarifications optionnelles, angle de recherche, plan attendu, comparaisons à faire..." rows={4} style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)', resize: 'vertical' }} />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Cadence</span>
            <select value={value.scheduleType} onChange={e => onChange({ scheduleType: e.target.value as ScheduleType })} style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }}>
              <option value="weekly">Hebdomadaire</option>
              <option value="once">Une fois</option>
              <option value="monthly">Mensuel</option>
              <option value="custom">Personnalisé</option>
            </select>
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Heure</span>
            <input type="time" value={value.scheduleTime} onChange={e => onChange({ scheduleTime: e.target.value })} style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }} />
          </label>

          {(value.scheduleType === 'once' || value.scheduleType === 'monthly' || value.scheduleType === 'custom') && (
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Date de départ</span>
              <input type="date" value={value.scheduleDate} onChange={e => onChange({ scheduleDate: e.target.value })} style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }} />
            </label>
          )}

          {value.scheduleType === 'custom' && (
            <label style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Intervalle (mois)</span>
              <input type="number" min={1} max={60} value={value.scheduleIntervalMonths} onChange={e => onChange({ scheduleIntervalMonths: Number(e.target.value) || 1 })} style={{ width: '100%', padding: '10px 12px', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', borderRadius: '8px', color: 'var(--text-primary)' }} />
            </label>
          )}

          {value.scheduleType === 'weekly' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', gridColumn: '1 / -1' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Jours</span>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {DAYS.map(day => {
                  const active = value.scheduleDays.includes(day.key);
                  return (
                    <button
                      key={day.key}
                      onClick={() => toggleDay(day.key)}
                      type="button"
                      style={{
                        padding: '8px 10px', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 600,
                        color: active ? 'white' : 'var(--text-secondary)',
                        backgroundColor: active ? 'var(--accent-primary)' : 'rgba(255,255,255,0.04)',
                        border: active ? '1px solid transparent' : '1px solid var(--border-color)',
                      }}
                      title={day.label}
                    >
                      {day.short}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <label style={{ display: 'flex', alignItems: 'center', gap: '10px', gridColumn: '1 / -1', color: 'var(--text-secondary)' }}>
            <input type="checkbox" checked={value.isActive} onChange={e => onChange({ isActive: e.target.checked })} />
            <span>Profil actif dès la sauvegarde</span>
          </label>
        </div>

        {error && (
          <div style={{ padding: '12px 14px', borderRadius: '10px', backgroundColor: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#ef4444', fontSize: '0.85rem' }}>
            {error}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button onClick={onClose} type="button" style={{ padding: '10px 16px', borderRadius: '10px', border: '1px solid var(--border-color)', backgroundColor: 'transparent', color: 'var(--text-secondary)', fontWeight: 600 }}>
            Annuler
          </button>
          <button onClick={onSubmit} type="button" disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 18px', borderRadius: '10px', backgroundColor: 'var(--accent-primary)', color: 'white', fontWeight: 700, opacity: saving ? 0.7 : 1 }}>
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {saving ? 'Enregistrement...' : isEdit ? 'Enregistrer' : 'Créer le topic'}
          </button>
        </div>
      </div>
    </div>
  );
}

export const TopicsPage: React.FC<TopicsPageProps> = ({ onOpenSettings }) => {
  const [profiles, setProfiles] = useState<WatchProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isEditorOpen, setIsEditorOpen] = useState(false);
  const [editingProfile, setEditingProfile] = useState<WatchProfile | null>(null);
  const [editor, setEditor] = useState<EditorState>(DEFAULT_EDITOR);
  const [saving, setSaving] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);

  const loadProfiles = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await ApiService.getWatchProfiles();
      setProfiles(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfiles();
  }, []);

  const openCreate = () => {
    setEditingProfile(null);
    setEditor({ ...DEFAULT_EDITOR });
    setEditorError(null);
    setIsEditorOpen(true);
  };

  const openEdit = (profile: WatchProfile) => {
    setEditingProfile(profile);
    setEditor(toEditorState(profile));
    setEditorError(null);
    setIsEditorOpen(true);
  };

  const closeEditor = () => {
    setIsEditorOpen(false);
    setEditingProfile(null);
    setEditor({ ...DEFAULT_EDITOR });
    setEditorError(null);
    setSaving(false);
  };

  const handleToggle = async (id: string, isActive: boolean) => {
    const updated = await ApiService.updateWatchProfile(id, { is_active: isActive });
    setProfiles(prev => prev.map(profile => profile.id === id ? updated : profile));
  };

  const handleRun = async (id: string) => {
    await ApiService.runProfile(id);
    setProfiles(prev => prev.map(profile => profile.id === id ? { ...profile, last_run_at: new Date().toISOString() } : profile));
  };

  const handleDelete = async (profile: WatchProfile) => {
    await ApiService.deleteWatchProfile(profile.id);
    setProfiles(prev => prev.filter(entry => entry.id !== profile.id));
  };

  const handleSubmit = async () => {
    const topics = parseTopics(editor.topicsInput);
    if (!editor.name.trim()) {
      setEditorError('Le nom du profil est requis.');
      return;
    }
    if (!editor.subject.trim()) {
      setEditorError('Le subject est requis.');
      return;
    }
    if (topics.length === 0) {
      setEditorError('Ajoute au moins un topic.');
      return;
    }
    if (editor.scheduleType === 'weekly' && editor.scheduleDays.length === 0) {
      setEditorError('Sélectionne au moins un jour.');
      return;
    }
    if ((editor.scheduleType === 'once' || editor.scheduleType === 'monthly' || editor.scheduleType === 'custom') && !editor.scheduleDate) {
      setEditorError('Sélectionne une date de départ.');
      return;
    }

    setSaving(true);
    setEditorError(null);
    const payload = {
      name: editor.name.trim(),
      subject: editor.subject.trim(),
      topics,
      depth: editor.depth,
      format: editor.format,
      language: editor.language,
      angle: editor.angle,
      focus: editor.focus.trim() || undefined,
      schedule_type: editor.scheduleType,
      schedule_time: editor.scheduleTime,
      schedule_days: editor.scheduleType === 'weekly' ? editor.scheduleDays : [],
      schedule_date: editor.scheduleType === 'weekly' ? undefined : editor.scheduleDate || undefined,
      schedule_interval_months: editor.scheduleType === 'custom' ? editor.scheduleIntervalMonths : editor.scheduleType === 'monthly' ? 1 : undefined,
      is_active: editor.isActive,
    };

    try {
      if (editingProfile) {
        const updated = await ApiService.updateWatchProfile(editingProfile.id, payload);
        setProfiles(prev => prev.map(profile => profile.id === editingProfile.id ? updated : profile));
      } else {
        await ApiService.createWatchProfile(payload);
        await loadProfiles();
      }
      closeEditor();
    } catch (err: any) {
      setEditorError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const filtered = profiles.filter(p =>
    p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (p.subject || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
    p.topics.some(t => t.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="fade-in page-container" style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '4px' }}>Topics</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>Gérez vos axes de veille et thématiques récurrentes</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
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
                outline: 'none',
              }}
            />
          </div>
          <button onClick={onOpenSettings} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 16px',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-color)',
            borderRadius: '10px',
            color: 'var(--text-primary)',
            fontSize: '0.9rem',
          }}>
            <Settings2 size={18} /> Configurer
          </button>
          <button onClick={openCreate} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 20px',
            backgroundColor: 'var(--accent-primary)',
            borderRadius: '10px',
            color: 'white',
            fontWeight: 600,
            fontSize: '0.95rem',
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
          {!searchQuery && (
            <button onClick={openCreate} style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '10px 20px', backgroundColor: 'var(--accent-primary)', borderRadius: '8px', color: 'white', fontWeight: 600 }}>
              <Plus size={16} /> Créer un profil
            </button>
          )}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '24px' }}>
          {filtered.map(profile => (
            <TopicCard
              key={profile.id}
              profile={profile}
              onToggle={handleToggle}
              onRun={handleRun}
              onEdit={openEdit}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {isEditorOpen && (
        <TopicEditorModal
          profile={editingProfile}
          value={editor}
          saving={saving}
          error={editorError}
          onClose={closeEditor}
          onChange={patch => setEditor(prev => ({ ...prev, ...patch }))}
          onSubmit={handleSubmit}
        />
      )}

      <style>{`
        .animate-spin { animation: spin 1s linear infinite; }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
};
