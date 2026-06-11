import React, { useEffect, useMemo, useState } from 'react';
import { CalendarDays, Clock, Play, Plus, Save, Trash2 } from 'lucide-react';
import { ApiService } from '../services/api';
import type { EmailGroup, WatchProfile } from '../types';

type DepthOption = 'brief' | 'standard' | 'deep';
type FormatOption = 'digest' | 'report' | 'newsletter';
type ScheduleType = 'none' | 'once' | 'weekly' | 'monthly';

type DraftProfile = {
  id?: string;
  name: string;
  subject: string;
  topics: string;
  depth: DepthOption;
  format: FormatOption;
  language: string;
  is_active: boolean;
  schedule_type: ScheduleType;
  schedule_time: string;
  schedule_days: string[];
  email_group_ids: string[];
};

const WEEK_DAYS = [
  { id: 'lun', label: 'Lun' },
  { id: 'mar', label: 'Mar' },
  { id: 'mer', label: 'Mer' },
  { id: 'jeu', label: 'Jeu' },
  { id: 'ven', label: 'Ven' },
  { id: 'sam', label: 'Sam' },
  { id: 'dim', label: 'Dim' },
];

const emptyDraft = (): DraftProfile => ({
  name: '',
  subject: '',
  topics: '',
  depth: 'standard',
  format: 'digest',
  language: 'fr',
  is_active: true,
  schedule_type: 'none',
  schedule_time: '08:00',
  schedule_days: [],
  email_group_ids: [],
});

function formatDate(iso?: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export const WatchProfilesPage: React.FC = () => {
  const [profiles, setProfiles] = useState<WatchProfile[]>([]);
  const [emailGroups, setEmailGroups] = useState<EmailGroup[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftProfile>(emptyDraft());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const selectedProfile = useMemo(
    () => profiles.find((p) => p.id === selectedId) ?? null,
    [profiles, selectedId],
  );

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [profilesData, groupsData] = await Promise.all([
        ApiService.getWatchProfiles(),
        ApiService.getEmailGroups(),
      ]);
      setProfiles(profilesData);
      setEmailGroups(groupsData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadData(); }, []);

  useEffect(() => {
    if (!selectedProfile) return;
    const rawSchedule = selectedProfile.schedule_type ?? 'none';
    const scheduleType: ScheduleType =
      rawSchedule === 'weekly' || rawSchedule === 'once' || rawSchedule === 'monthly'
        ? rawSchedule
        : rawSchedule === 'none'
          ? 'none'
          : 'weekly'; // map 'custom' or unknown → 'weekly'
    setDraft({
      id: selectedProfile.id,
      name: selectedProfile.name,
      subject: selectedProfile.subject ?? '',
      topics: selectedProfile.topics.join(', '),
      depth: selectedProfile.depth,
      format: selectedProfile.format,
      language: selectedProfile.language ?? 'fr',
      is_active: selectedProfile.is_active,
      schedule_type: scheduleType,
      schedule_time: selectedProfile.schedule_time ?? '08:00',
      schedule_days: selectedProfile.schedule_days ?? [],
      email_group_ids: selectedProfile.email_groups.map((g) => g.id),
    });
  }, [selectedProfile]);

  const handleNew = () => {
    setSelectedId(null);
    setDraft(emptyDraft());
    setError(null);
    setSuccessMessage(null);
  };

  const showSuccess = (msg: string) => {
    setSuccessMessage(msg);
    window.setTimeout(() => setSuccessMessage(null), 4000);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    const name = draft.name.trim();
    const subject = draft.subject.trim();
    if (!name) {
      setError('Le nom du profil est requis.');
      setSaving(false);
      return;
    }
    if (!subject) {
      setError('Le sujet est requis.');
      setSaving(false);
      return;
    }

    const topics = draft.topics
      .split(',')
      .map((t) => t.trim())
      .filter(Boolean);

    const payload = {
      name,
      subject,
      topics,
      depth: draft.depth,
      format: draft.format,
      language: draft.language || undefined,
      is_active: draft.is_active,
      schedule_type: draft.schedule_type === 'none' ? undefined : draft.schedule_type,
      schedule_time: draft.schedule_type !== 'none' ? draft.schedule_time : undefined,
      schedule_days: draft.schedule_type === 'weekly' ? draft.schedule_days : [],
      email_group_ids: draft.email_group_ids,
    };

    try {
      const saved = draft.id
        ? await ApiService.updateWatchProfile(draft.id, payload)
        : await ApiService.createWatchProfile({ ...payload, subject });
      await loadData();
      setSelectedId(saved.id);
      showSuccess(draft.id ? 'Profil mis à jour.' : 'Profil créé.');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!draft.id) return;
    if (!window.confirm(`Supprimer le profil "${draft.name}" ?`)) return;
    setSaving(true);
    setError(null);
    try {
      await ApiService.deleteWatchProfile(draft.id);
      await loadData();
      setSelectedId(null);
      setDraft(emptyDraft());
      showSuccess('Profil supprimé.');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRun = async () => {
    if (!draft.id) return;
    setRunning(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const result = await ApiService.runProfile(draft.id, { send_email: draft.email_group_ids.length > 0 });
      if (result.success) {
        const parts: string[] = ['Analyse lancée avec succès.'];
        if (result.session_id) parts.push(`Session : ${result.session_id.slice(0, 8)}…`);
        if (result.email_sent) parts.push('Email envoyé.');
        showSuccess(parts.join(' '));
        await loadData();
      } else {
        setError(result.error ?? 'Échec du lancement.');
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  };

  const toggleDay = (day: string) => {
    setDraft((current) => ({
      ...current,
      schedule_days: current.schedule_days.includes(day)
        ? current.schedule_days.filter((d) => d !== day)
        : [...current.schedule_days, day],
    }));
  };

  const toggleEmailGroup = (groupId: string) => {
    setDraft((current) => ({
      ...current,
      email_group_ids: current.email_group_ids.includes(groupId)
        ? current.email_group_ids.filter((id) => id !== groupId)
        : [...current.email_group_ids, groupId],
    }));
  };

  return (
    <div className="fade-in page-container" style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '4px' }}>Profils de veille</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>
            Configurez et planifiez vos analyses de veille technologique automatiques.
          </p>
        </div>
        <button onClick={handleNew} style={primaryButtonStyle}>
          <Plus size={16} /> Nouveau profil
        </button>
      </header>

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: '10px', backgroundColor: 'var(--status-error-bg)', color: 'var(--status-error)', border: '1px solid rgba(239,68,68,0.25)' }}>
          {error}
        </div>
      )}

      {successMessage && (
        <div style={{ padding: '12px 16px', borderRadius: '10px', backgroundColor: 'var(--status-success-bg)', color: 'var(--status-success)', border: '1px solid rgba(34,197,94,0.25)' }}>
          {successMessage}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 320px) minmax(0, 1fr)', gap: '20px' }}>
        {/* Left panel — profile list */}
        <section className="card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px', minHeight: '520px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CalendarDays size={16} color="var(--accent-primary)" />
              <strong>Profils</strong>
            </div>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{profiles.length}</span>
          </div>

          {loading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Chargement…</div>
          ) : profiles.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: 1.6 }}>
              Aucun profil pour le moment. Créez-en un pour automatiser vos analyses.
            </div>
          ) : (
            profiles.map((profile) => {
              const active = profile.id === selectedId;
              return (
                <button
                  key={profile.id}
                  onClick={() => setSelectedId(profile.id)}
                  style={{
                    textAlign: 'left',
                    padding: '14px',
                    borderRadius: '12px',
                    border: active ? '1px solid rgba(124,140,255,0.35)' : '1px solid var(--border-color)',
                    backgroundColor: active ? 'rgba(124,140,255,0.10)' : 'rgba(255,255,255,0.03)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                    <strong style={{ color: 'var(--text-primary)', fontSize: '0.92rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {profile.name}
                    </strong>
                    <span style={{
                      fontSize: '0.72rem',
                      padding: '3px 8px',
                      borderRadius: '999px',
                      flexShrink: 0,
                      backgroundColor: profile.is_active ? 'rgba(34,197,94,0.14)' : 'rgba(148,163,184,0.14)',
                      color: profile.is_active ? '#22c55e' : 'var(--text-muted)',
                    }}>
                      {profile.is_active ? 'Actif' : 'Inactif'}
                    </span>
                  </div>

                  {profile.subject && (
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', lineHeight: 1.4, overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                      {profile.subject}
                    </div>
                  )}

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '2px' }}>
                    {profile.schedule_type && (
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={12} /> {profile.schedule_type}
                      </span>
                    )}
                    {profile.last_run_at && (
                      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {formatDate(profile.last_run_at)}
                      </span>
                    )}
                  </div>
                </button>
              );
            })
          )}
        </section>

        {/* Right panel — form */}
        <section className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px', overflowY: 'auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>{draft.id ? 'Modifier le profil' : 'Nouveau profil'}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginTop: '4px' }}>
                {draft.id ? 'Modifiez les paramètres de ce profil de veille.' : 'Définissez un profil pour automatiser vos analyses.'}
              </div>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '0.9rem', flexShrink: 0 }}>
              <input
                type="checkbox"
                checked={draft.is_active}
                onChange={(e) => setDraft((c) => ({ ...c, is_active: e.target.checked }))}
              />
              Profil actif
            </label>
          </div>

          {/* Basic fields */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
              <div style={fieldGroupStyle}>
                <label style={labelStyle}>Nom *</label>
                <input
                  value={draft.name}
                  onChange={(e) => setDraft((c) => ({ ...c, name: e.target.value }))}
                  placeholder="Veille IA hebdomadaire"
                  style={inputStyle}
                />
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                <div style={fieldGroupStyle}>
                  <label style={labelStyle}>Profondeur</label>
                  <select
                    value={draft.depth}
                    onChange={(e) => setDraft((c) => ({ ...c, depth: e.target.value as DepthOption }))}
                    style={selectStyle}
                  >
                    <option value="brief">Brief</option>
                    <option value="standard">Standard</option>
                    <option value="deep">Deep</option>
                  </select>
                </div>
                <div style={fieldGroupStyle}>
                  <label style={labelStyle}>Format</label>
                  <select
                    value={draft.format}
                    onChange={(e) => setDraft((c) => ({ ...c, format: e.target.value as FormatOption }))}
                    style={selectStyle}
                  >
                    <option value="digest">Digest</option>
                    <option value="report">Rapport</option>
                    <option value="newsletter">Newsletter</option>
                  </select>
                </div>
                <div style={fieldGroupStyle}>
                  <label style={labelStyle}>Langue</label>
                  <select
                    value={draft.language}
                    onChange={(e) => setDraft((c) => ({ ...c, language: e.target.value }))}
                    style={selectStyle}
                  >
                    <option value="fr">FR</option>
                    <option value="en">EN</option>
                  </select>
                </div>
              </div>
            </div>

            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Sujet *</label>
              <textarea
                value={draft.subject}
                onChange={(e) => setDraft((c) => ({ ...c, subject: e.target.value }))}
                placeholder="Intelligence artificielle générative, LLMs, applications industrielles…"
                rows={3}
                style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.5 }}
              />
            </div>

            <div style={fieldGroupStyle}>
              <label style={labelStyle}>Topics <span style={{ color: 'var(--text-muted)', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>(séparés par des virgules)</span></label>
              <input
                value={draft.topics}
                onChange={(e) => setDraft((c) => ({ ...c, topics: e.target.value }))}
                placeholder="LLM, RAG, agents, fine-tuning"
                style={inputStyle}
              />
            </div>
          </div>

          {/* Schedule section */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={sectionTitleStyle}>Planification</div>

            <div style={{ display: 'grid', gridTemplateColumns: draft.schedule_type !== 'none' ? '1fr 1fr' : '1fr', gap: '14px' }}>
              <div style={fieldGroupStyle}>
                <label style={labelStyle}>Fréquence</label>
                <select
                  value={draft.schedule_type}
                  onChange={(e) => setDraft((c) => ({ ...c, schedule_type: e.target.value as ScheduleType }))}
                  style={selectStyle}
                >
                  <option value="none">Aucune</option>
                  <option value="once">Une fois</option>
                  <option value="weekly">Hebdomadaire</option>
                  <option value="monthly">Mensuel</option>
                </select>
              </div>

              {draft.schedule_type !== 'none' && (
                <div style={fieldGroupStyle}>
                  <label style={labelStyle}>Heure (HH:MM)</label>
                  <input
                    type="text"
                    value={draft.schedule_time}
                    onChange={(e) => setDraft((c) => ({ ...c, schedule_time: e.target.value }))}
                    placeholder="08:00"
                    style={inputStyle}
                  />
                </div>
              )}
            </div>

            {draft.schedule_type === 'weekly' && (
              <div style={fieldGroupStyle}>
                <label style={labelStyle}>Jours</label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '4px' }}>
                  {WEEK_DAYS.map((day) => {
                    const checked = draft.schedule_days.includes(day.id);
                    return (
                      <button
                        key={day.id}
                        type="button"
                        onClick={() => toggleDay(day.id)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '8px',
                          fontSize: '0.82rem',
                          fontWeight: 600,
                          border: checked ? '1px solid rgba(124,140,255,0.45)' : '1px solid var(--border-color)',
                          backgroundColor: checked ? 'rgba(124,140,255,0.18)' : 'rgba(255,255,255,0.03)',
                          color: checked ? 'var(--accent-primary)' : 'var(--text-secondary)',
                        }}
                      >
                        {day.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Email groups section */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={sectionTitleStyle}>Groupes email</div>
            {emailGroups.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>
                Aucun groupe email disponible. Créez-en un depuis la page Email Groups.
              </div>
            ) : (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {emailGroups.map((group) => {
                  const selected = draft.email_group_ids.includes(group.id);
                  return (
                    <button
                      key={group.id}
                      type="button"
                      onClick={() => toggleEmailGroup(group.id)}
                      style={{
                        padding: '7px 12px',
                        borderRadius: '8px',
                        fontSize: '0.83rem',
                        fontWeight: 600,
                        border: selected ? '1px solid rgba(124,140,255,0.45)' : '1px solid var(--border-color)',
                        backgroundColor: selected ? 'rgba(124,140,255,0.18)' : 'rgba(255,255,255,0.03)',
                        color: selected ? 'var(--accent-primary)' : 'var(--text-secondary)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      {group.name}
                      <span style={{ fontSize: '0.72rem', opacity: 0.7 }}>({group.recipient_count})</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', marginTop: 'auto', flexWrap: 'wrap', paddingTop: '8px', borderTop: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
              {draft.id && (
                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={saving || running}
                  style={{ ...ghostButtonStyle, color: '#fca5a5', borderColor: 'rgba(239,68,68,0.25)' }}
                >
                  <Trash2 size={14} /> Supprimer
                </button>
              )}
              {draft.id && (
                <button
                  type="button"
                  onClick={handleRun}
                  disabled={saving || running}
                  style={{ ...ghostButtonStyle, color: 'var(--accent-secondary)', borderColor: 'rgba(79,209,255,0.25)' }}
                >
                  <Play size={14} /> {running ? 'Lancement…' : 'Lancer maintenant'}
                </button>
              )}
            </div>
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || running}
              style={primaryButtonStyle}
            >
              <Save size={15} /> {saving ? 'Enregistrement…' : 'Sauvegarder'}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
};

const labelStyle: React.CSSProperties = {
  fontSize: '0.78rem',
  fontWeight: 700,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
};

const fieldGroupStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: '6px',
};

const sectionTitleStyle: React.CSSProperties = {
  fontSize: '0.82rem',
  fontWeight: 700,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.1em',
  paddingBottom: '4px',
  borderBottom: '1px solid var(--border-color)',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: '10px',
  border: '1px solid var(--border-color)',
  backgroundColor: 'var(--bg-primary)',
  color: 'var(--text-primary)',
  fontSize: '0.9rem',
  fontFamily: 'inherit',
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  appearance: 'auto',
};

const ghostButtonStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '8px 12px',
  borderRadius: '10px',
  border: '1px solid var(--border-color)',
  color: 'var(--text-secondary)',
  backgroundColor: 'rgba(255,255,255,0.03)',
  fontSize: '0.84rem',
  fontWeight: 600,
};

const primaryButtonStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '8px',
  padding: '10px 16px',
  borderRadius: '10px',
  border: '1px solid transparent',
  backgroundColor: 'var(--accent-primary)',
  color: 'white',
  fontWeight: 700,
  boxShadow: '0 10px 30px rgba(124,140,255,0.22)',
};
