import React, { useEffect, useMemo, useState } from 'react';
import { Mail, Plus, Save, Trash2, Users } from 'lucide-react';
import { ApiService } from '../services/api';
import type { EmailGroup, EmailGroupRecipient } from '../types';

type DraftGroup = {
  id?: string;
  name: string;
  description: string;
  is_active: boolean;
  recipients: EmailGroupRecipient[];
};

const emptyDraft = (): DraftGroup => ({
  name: '',
  description: '',
  is_active: true,
  recipients: [{ email: '', label: '' }],
});

export const EmailGroupsPage: React.FC = () => {
  const [groups, setGroups] = useState<EmailGroup[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [draft, setDraft] = useState<DraftGroup>(emptyDraft());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedGroup = useMemo(
    () => groups.find((group) => group.id === selectedId) ?? null,
    [groups, selectedId],
  );

  const loadGroups = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await ApiService.getEmailGroups();
      setGroups(data);
      if (selectedId) {
        const next = data.find((group) => group.id === selectedId);
        if (next) {
          setDraft({
            id: next.id,
            name: next.name,
            description: next.description ?? '',
            is_active: next.is_active,
            recipients: next.recipients.length ? next.recipients : [{ email: '', label: '' }],
          });
        }
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void loadGroups(); }, []);

  useEffect(() => {
    if (!selectedGroup) return;
    setDraft({
      id: selectedGroup.id,
      name: selectedGroup.name,
      description: selectedGroup.description ?? '',
      is_active: selectedGroup.is_active,
      recipients: selectedGroup.recipients.length ? selectedGroup.recipients : [{ email: '', label: '' }],
    });
  }, [selectedGroup]);

  const setRecipient = (index: number, field: keyof EmailGroupRecipient, value: string) => {
    setDraft((current) => ({
      ...current,
      recipients: current.recipients.map((recipient, recipientIndex) => (
        recipientIndex === index ? { ...recipient, [field]: value } : recipient
      )),
    }));
  };

  const addRecipient = () => {
    setDraft((current) => ({
      ...current,
      recipients: [...current.recipients, { email: '', label: '' }],
    }));
  };

  const removeRecipient = (index: number) => {
    setDraft((current) => ({
      ...current,
      recipients: current.recipients.length === 1
        ? [{ email: '', label: '' }]
        : current.recipients.filter((_, recipientIndex) => recipientIndex !== index),
    }));
  };

  const handleNew = () => {
    setSelectedId(null);
    setDraft(emptyDraft());
    setError(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    const payload = {
      name: draft.name.trim(),
      description: draft.description.trim() || undefined,
      is_active: draft.is_active,
      recipients: draft.recipients
        .map((recipient) => ({ email: recipient.email.trim(), label: recipient.label?.trim() || null }))
        .filter((recipient) => recipient.email),
    };

    if (!payload.name) {
      setSaving(false);
      setError('Le nom du groupe est requis.');
      return;
    }

    try {
      const saved = draft.id
        ? await ApiService.updateEmailGroup(draft.id, payload)
        : await ApiService.createEmailGroup(payload);
      await loadGroups();
      setSelectedId(saved.id);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!draft.id) return;
    if (!window.confirm(`Supprimer le groupe email "${draft.name}" ?`)) return;
    setSaving(true);
    setError(null);
    try {
      await ApiService.deleteEmailGroup(draft.id);
      await loadGroups();
      setSelectedId(null);
      setDraft(emptyDraft());
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fade-in page-container" style={{ display: 'flex', flexDirection: 'column', gap: '28px' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '4px' }}>Email Groups</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>Préparez des listes de diffusion réutilisables pour vos profils de veille.</p>
        </div>
        <button
          onClick={handleNew}
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', borderRadius: '10px', backgroundColor: 'var(--accent-primary)', color: 'white', fontWeight: 600 }}
        >
          <Plus size={16} /> Nouveau groupe
        </button>
      </header>

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: '10px', backgroundColor: 'var(--status-error-bg)', color: 'var(--status-error)', border: '1px solid rgba(239,68,68,0.25)' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(260px, 320px) minmax(0, 1fr)', gap: '20px' }}>
        <section className="card" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px', minHeight: '480px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Users size={16} color="var(--accent-primary)" />
              <strong>Groupes</strong>
            </div>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{groups.length}</span>
          </div>

          {loading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Chargement…</div>
          ) : groups.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem', lineHeight: 1.6 }}>
              Aucun groupe pour le moment. Créez-en un puis rattachez-le à un profil dans la page Sessions.
            </div>
          ) : (
            groups.map((group) => {
              const active = group.id === selectedId;
              return (
                <button
                  key={group.id}
                  onClick={() => setSelectedId(group.id)}
                  style={{
                    textAlign: 'left',
                    padding: '14px',
                    borderRadius: '12px',
                    border: active ? '1px solid rgba(124,140,255,0.35)' : '1px solid var(--border-color)',
                    backgroundColor: active ? 'rgba(124,140,255,0.10)' : 'rgba(255,255,255,0.03)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                    <strong style={{ color: 'var(--text-primary)' }}>{group.name}</strong>
                    <span style={{ fontSize: '0.72rem', padding: '3px 8px', borderRadius: '999px', backgroundColor: group.is_active ? 'rgba(34,197,94,0.14)' : 'rgba(148,163,184,0.14)', color: group.is_active ? '#22c55e' : 'var(--text-muted)' }}>
                      {group.is_active ? 'Actif' : 'Pause'}
                    </span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '0.83rem', lineHeight: 1.5 }}>
                    {group.description || 'Sans description'}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                    <Mail size={13} /> {group.recipient_count} destinataire{group.recipient_count > 1 ? 's' : ''}
                  </div>
                </button>
              );
            })
          )}
        </section>

        <section className="card" style={{ padding: '22px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>{draft.id ? 'Modifier le groupe' : 'Nouveau groupe'}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.88rem', marginTop: '4px' }}>
                Ce groupe pourra être sélectionné dans les profils programmés pour l’envoi automatique.
              </div>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              <input type="checkbox" checked={draft.is_active} onChange={(event) => setDraft((current) => ({ ...current, is_active: event.target.checked }))} />
              Groupe actif
            </label>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={labelStyle}>Nom</label>
              <input value={draft.name} onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))} placeholder="Equipe produit" style={inputStyle} />
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={labelStyle}>Description</label>
              <input value={draft.description} onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))} placeholder="Destinataires du digest hebdo" style={inputStyle} />
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <label style={labelStyle}>Destinataires</label>
              <button type="button" onClick={addRecipient} style={ghostButtonStyle}><Plus size={14} /> Ajouter</button>
            </div>
            {draft.recipients.map((recipient, index) => (
              <div key={`${draft.id ?? 'new'}-${index}`} style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(0, 1fr) auto', gap: '10px', alignItems: 'center' }}>
                <input value={recipient.email} onChange={(event) => setRecipient(index, 'email', event.target.value)} placeholder="team@example.com" style={inputStyle} />
                <input value={recipient.label ?? ''} onChange={(event) => setRecipient(index, 'label', event.target.value)} placeholder="Equipe produit" style={inputStyle} />
                <button type="button" onClick={() => removeRecipient(index)} style={{ ...ghostButtonStyle, paddingInline: '10px' }}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>

          {selectedGroup && selectedGroup.linked_watch_profiles.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={labelStyle}>Profils liés</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {selectedGroup.linked_watch_profiles.map((profile) => (
                  <span key={profile.id} style={{ padding: '6px 10px', borderRadius: '999px', backgroundColor: 'rgba(124,140,255,0.10)', color: 'var(--accent-primary)', fontSize: '0.82rem' }}>
                    {profile.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', marginTop: 'auto', flexWrap: 'wrap' }}>
            {draft.id ? (
              <button type="button" onClick={handleDelete} disabled={saving} style={{ ...ghostButtonStyle, color: '#fca5a5', borderColor: 'rgba(239,68,68,0.25)' }}>
                <Trash2 size={14} /> Supprimer
              </button>
            ) : <span />}
            <button type="button" onClick={handleSave} disabled={saving} style={primaryButtonStyle}>
              <Save size={15} /> {saving ? 'Enregistrement...' : 'Enregistrer le groupe'}
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
