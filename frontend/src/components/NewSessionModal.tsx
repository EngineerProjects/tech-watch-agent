import React, { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Zap, CalendarDays, Hash, ChevronLeft, ChevronRight,
  Clock, Repeat, RotateCcw, Send, Plus,
} from 'lucide-react';
import { ApiService } from '../services/api';

// ── Types ─────────────────────────────────────────────────────────────────────

type Mode = 'immediate' | 'scheduled';
type FreqType = 'once' | 'weekly' | 'monthly' | 'custom';

interface NewSessionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onRunImmediate: (task: string, topics: string[]) => void;
  onScheduled?: () => void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const DAYS_FR = ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di'];
const DAYS_EN = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
const MONTHS_FR = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number) {
  const d = new Date(year, month, 1).getDay();
  return d === 0 ? 6 : d - 1; // Mon=0 … Sun=6
}

function isoDate(year: number, month: number, day: number) {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}

// ── Mini Calendar ─────────────────────────────────────────────────────────────

interface CalendarProps {
  selected: string | null;
  onChange: (d: string) => void;
  minToday?: boolean;
}

function MiniCalendar({ selected, onChange, minToday = true }: CalendarProps) {
  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());

  const days = getDaysInMonth(viewYear, viewMonth);
  const firstDay = getFirstDayOfMonth(viewYear, viewMonth);
  const todayStr = isoDate(today.getFullYear(), today.getMonth(), today.getDate());

  const prev = () => {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11); }
    else setViewMonth(m => m - 1);
  };
  const next = () => {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0); }
    else setViewMonth(m => m + 1);
  };

  const cells: (number | null)[] = [
    ...Array(firstDay).fill(null),
    ...Array.from({ length: days }, (_, i) => i + 1),
  ];

  return (
    <div style={{ userSelect: 'none' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
        <button onClick={prev} style={{ padding: '4px', borderRadius: '6px', color: 'var(--text-muted)', backgroundColor: 'transparent' }}>
          <ChevronLeft size={16} />
        </button>
        <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)' }}>
          {MONTHS_FR[viewMonth]} {viewYear}
        </span>
        <button onClick={next} style={{ padding: '4px', borderRadius: '6px', color: 'var(--text-muted)', backgroundColor: 'transparent' }}>
          <ChevronRight size={16} />
        </button>
      </div>

      {/* Day labels */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '2px', marginBottom: '4px' }}>
        {DAYS_FR.map(d => (
          <div key={d} style={{ textAlign: 'center', fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', padding: '4px 0' }}>{d}</div>
        ))}
      </div>

      {/* Day cells */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '2px' }}>
        {cells.map((day, i) => {
          if (!day) return <div key={`empty-${i}`} />;
          const dateStr = isoDate(viewYear, viewMonth, day);
          const isToday = dateStr === todayStr;
          const isSelected = dateStr === selected;
          const isPast = minToday && dateStr < todayStr;

          return (
            <button
              key={dateStr}
              onClick={() => !isPast && onChange(dateStr)}
              disabled={isPast}
              style={{
                padding: '6px 4px',
                borderRadius: '6px',
                fontSize: '0.82rem',
                fontWeight: isSelected ? 700 : isToday ? 600 : 400,
                color: isSelected ? 'white' : isPast ? 'var(--text-muted)' : isToday ? 'var(--accent-primary)' : 'var(--text-primary)',
                backgroundColor: isSelected ? 'var(--accent-primary)' : isToday && !isSelected ? 'rgba(124,140,255,0.12)' : 'transparent',
                border: isToday && !isSelected ? '1px solid rgba(124,140,255,0.3)' : '1px solid transparent',
                cursor: isPast ? 'not-allowed' : 'pointer',
                opacity: isPast ? 0.35 : 1,
                textAlign: 'center',
              }}
            >
              {day}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Time Picker ───────────────────────────────────────────────────────────────

interface TimePickerProps {
  value: string; // "HH:MM"
  onChange: (v: string) => void;
}

function TimePicker({ value, onChange }: TimePickerProps) {
  const [h, m] = value.split(':').map(Number);
  const setH = (n: number) => onChange(`${String(Math.max(0, Math.min(23, n))).padStart(2, '0')}:${String(m).padStart(2, '0')}`);
  const setM = (n: number) => onChange(`${String(h).padStart(2, '0')}:${String(Math.max(0, Math.min(59, n))).padStart(2, '0')}`);

  const spinStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '6px',
  };
  const numStyle: React.CSSProperties = {
    fontSize: '2rem',
    fontWeight: 700,
    color: 'var(--text-primary)',
    width: '60px',
    textAlign: 'center',
    backgroundColor: 'var(--bg-primary)',
    border: '1px solid var(--border-color)',
    borderRadius: '10px',
    padding: '8px 0',
  };
  const arrBtn: React.CSSProperties = {
    color: 'var(--text-muted)',
    backgroundColor: 'transparent',
    padding: '2px',
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div style={spinStyle}>
        <button style={arrBtn} onClick={() => setH(h + 1)}><ChevronLeft size={14} style={{ transform: 'rotate(90deg)' }} /></button>
        <div style={numStyle}>{String(h).padStart(2, '0')}</div>
        <button style={arrBtn} onClick={() => setH(h - 1)}><ChevronLeft size={14} style={{ transform: 'rotate(-90deg)' }} /></button>
      </div>
      <span style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '2px' }}>:</span>
      <div style={spinStyle}>
        <button style={arrBtn} onClick={() => setM(m + 1)}><ChevronLeft size={14} style={{ transform: 'rotate(90deg)' }} /></button>
        <div style={numStyle}>{String(m).padStart(2, '0')}</div>
        <button style={arrBtn} onClick={() => setM(m - 1)}><ChevronLeft size={14} style={{ transform: 'rotate(-90deg)' }} /></button>
      </div>
    </div>
  );
}

// ── Main Modal ────────────────────────────────────────────────────────────────

export const NewSessionModal: React.FC<NewSessionModalProps> = ({
  isOpen, onClose, onRunImmediate, onScheduled,
}) => {
  // Task fields
  const [name, setName] = useState('');
  const [brief, setBrief] = useState('');
  const [topicsInput, setTopicsInput] = useState('');
  const [topics, setTopics] = useState<string[]>([]);
  const [depth, setDepth] = useState<'brief' | 'standard' | 'deep'>('standard');
  const [format, setFormat] = useState<'digest' | 'report' | 'newsletter'>('report');
  const [sendEmail, setSendEmail] = useState(false);

  // Scheduling
  const [mode, setMode] = useState<Mode>('immediate');
  const [freqType, setFreqType] = useState<FreqType>('weekly');
  const [scheduleTime, setScheduleTime] = useState('08:00');
  const [selectedDays, setSelectedDays] = useState<string[]>(['monday']);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [intervalMonths, setIntervalMonths] = useState(1);

  // UI state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addTopic = useCallback(() => {
    const t = topicsInput.trim().toLowerCase();
    if (t && !topics.includes(t)) setTopics(prev => [...prev, t]);
    setTopicsInput('');
  }, [topicsInput, topics]);

  const toggleDay = (day: string) => {
    setSelectedDays(prev =>
      prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day]
    );
  };

  const reset = () => {
    setName(''); setBrief(''); setTopicsInput(''); setTopics([]);
    setDepth('standard'); setFormat('report'); setSendEmail(false);
    setMode('immediate'); setFreqType('weekly');
    setScheduleTime('08:00'); setSelectedDays(['monday']);
    setSelectedDate(null); setIntervalMonths(1);
    setError(null); setSubmitting(false);
  };

  const handleClose = () => { reset(); onClose(); };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const allTopics = [...topics];
    if (topicsInput.trim()) allTopics.push(topicsInput.trim().toLowerCase());

    if (mode === 'immediate') {
      const task = brief.trim() || name.trim();
      if (!task) { setError('Le sujet de recherche est requis.'); return; }
      onRunImmediate(task, allTopics);
      handleClose();
      return;
    }

    // Scheduled
    if (!name.trim()) { setError('Le nom de la session est requis.'); return; }
    if (freqType === 'weekly' && selectedDays.length === 0) {
      setError('Sélectionnez au moins un jour de répétition.'); return;
    }
    if ((freqType === 'once' || freqType === 'monthly' || freqType === 'custom') && !selectedDate) {
      setError('Sélectionnez une date de départ.'); return;
    }

    setSubmitting(true);
    try {
      await ApiService.createWatchProfile({
        name: name.trim(),
        topics: allTopics,
        depth,
        format,
        focus: brief.trim() || undefined,
        schedule_type: freqType,
        schedule_time: scheduleTime,
        schedule_days: freqType === 'weekly' ? selectedDays : [],
        schedule_date: selectedDate || undefined,
        schedule_interval_months: freqType === 'custom' ? intervalMonths : freqType === 'monthly' ? 1 : undefined,
        is_active: true,
      });
      onScheduled?.();
      handleClose();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  const freqLabel: Record<FreqType, string> = {
    once: 'Une fois',
    weekly: 'Hebdomadaire',
    monthly: 'Mensuel',
    custom: 'Personnalisé',
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          width: '100vw', height: '100vh',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '16px',
          boxSizing: 'border-box',
        }}>
          {/* Backdrop */}
          <div
            onClick={handleClose}
            style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(6px)' }}
          />

          {/* Dialog */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 12 }}
            transition={{ duration: 0.18, ease: [0.4, 0, 0.2, 1] }}
            style={{
              position: 'relative',
              width: '100%',
              maxWidth: '980px',
              maxHeight: 'calc(100vh - 32px)',
              overflowY: 'auto',
              backgroundColor: 'var(--bg-surface)',
              borderRadius: '16px',
              border: '1px solid var(--border-color)',
              boxShadow: '0 32px 80px rgba(0,0,0,0.6)',
              zIndex: 1,
            }}
          >
            <form onSubmit={handleSubmit}>
              {/* Header */}
              <div className="modal-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '24px 28px', borderBottom: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'linear-gradient(135deg,var(--accent-primary),var(--accent-purple))', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Zap size={16} color="white" fill="white" />
                  </div>
                  <h2 style={{ fontSize: '1.25rem', fontWeight: 700, margin: 0 }}>Nouvelle session</h2>
                </div>
                <button type="button" onClick={handleClose} style={{ color: 'var(--text-muted)', padding: '6px', borderRadius: '8px', backgroundColor: 'rgba(255,255,255,0.04)' }}>
                  <X size={20} />
                </button>
              </div>

              {/* Mode tabs */}
              <div className="modal-tabs" style={{ display: 'flex', padding: '20px 28px 0', gap: '8px', flexWrap: 'wrap' }}>
                {([['immediate', '⚡ Immédiat'], ['scheduled', '📅 Programmer']] as const).map(([m, label]) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMode(m as Mode)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: '8px',
                      padding: '9px 18px',
                      borderRadius: '10px',
                      fontSize: '0.9rem',
                      fontWeight: mode === m ? 700 : 400,
                      color: mode === m ? 'var(--text-primary)' : 'var(--text-secondary)',
                      backgroundColor: mode === m ? 'rgba(124,140,255,0.15)' : 'transparent',
                      border: mode === m ? '1px solid rgba(124,140,255,0.3)' : '1px solid transparent',
                    }}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {/* Body */}
              <div className={mode === 'scheduled' ? 'modal-body-grid' : ''} style={mode !== 'scheduled' ? { padding: '24px 28px' } : undefined}>
                {/* Left — Task */}
                <div className={mode === 'scheduled' ? 'modal-left-panel' : ''} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

                  {mode === 'scheduled' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <label style={labelStyle}>Nom de la session</label>
                      <input
                        type="text"
                        value={name}
                        onChange={e => setName(e.target.value)}
                        placeholder="Ex: Veille IA hebdomadaire"
                        style={inputStyle}
                      />
                    </div>
                  )}

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={labelStyle}>Sujet de recherche</label>
                    <textarea
                      autoFocus={mode === 'immediate'}
                      value={brief}
                      onChange={e => setBrief(e.target.value)}
                      placeholder={mode === 'immediate'
                        ? 'Ex: Dernières avancées sur les modèles de raisonnement (O1, DeepSeek) en mai 2026...'
                        : 'Instructions optionnelles pour guider la recherche...'}
                      style={{ ...inputStyle, minHeight: '90px', resize: 'none' }}
                    />
                  </div>

                  {/* Topics */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <label style={labelStyle}>Topics</label>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <div style={{ position: 'relative', flex: 1 }}>
                        <Hash size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                        <input
                          type="text"
                          value={topicsInput}
                          onChange={e => setTopicsInput(e.target.value)}
                          onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTopic(); } }}
                          placeholder="ia, llm, devops..."
                          style={{ ...inputStyle, paddingLeft: '36px' }}
                        />
                      </div>
                      <button type="button" onClick={addTopic} style={{ padding: '10px 14px', backgroundColor: 'rgba(124,140,255,0.1)', borderRadius: '8px', color: 'var(--accent-primary)', border: '1px solid rgba(124,140,255,0.2)' }}>
                        <Plus size={16} />
                      </button>
                    </div>
                    {topics.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
                        {topics.map(t => (
                          <span
                            key={t}
                            onClick={() => setTopics(prev => prev.filter(x => x !== t))}
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '3px 10px', backgroundColor: 'rgba(124,140,255,0.12)', color: 'var(--accent-primary)', borderRadius: '20px', fontSize: '0.8rem', cursor: 'pointer', border: '1px solid rgba(124,140,255,0.2)' }}
                          >
                            #{t} <X size={11} />
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Options row */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <label style={labelStyle}>Profondeur</label>
                      <select value={depth} onChange={e => setDepth(e.target.value as any)} style={selectStyle}>
                        <option value="brief">Rapide</option>
                        <option value="standard">Standard</option>
                        <option value="deep">Approfondie</option>
                      </select>
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <label style={labelStyle}>Format</label>
                      <select value={format} onChange={e => setFormat(e.target.value as any)} style={selectStyle}>
                        <option value="digest">Digest</option>
                        <option value="report">Rapport</option>
                        <option value="newsletter">Newsletter</option>
                      </select>
                    </div>
                  </div>

                  {mode === 'immediate' && (
                    <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                      <div
                        onClick={() => setSendEmail(v => !v)}
                        style={{
                          width: '40px', height: '22px', borderRadius: '11px',
                          backgroundColor: sendEmail ? 'var(--accent-primary)' : 'rgba(255,255,255,0.1)',
                          position: 'relative', transition: 'background-color 0.2s', flexShrink: 0,
                        }}
                      >
                        <div style={{
                          position: 'absolute', top: '3px', left: sendEmail ? '21px' : '3px',
                          width: '16px', height: '16px', borderRadius: '50%', backgroundColor: 'white',
                          transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
                        }} />
                      </div>
                      Envoyer par email
                    </label>
                  )}
                </div>

                {/* Right — Schedule (only in scheduled mode) */}
                {mode === 'scheduled' && (
                  <div className="modal-right-panel" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

                    {/* Freq selector */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <label style={labelStyle}><Repeat size={13} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />Fréquence</label>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        {(['once', 'weekly', 'monthly', 'custom'] as FreqType[]).map(f => (
                          <button
                            key={f}
                            type="button"
                            onClick={() => setFreqType(f)}
                            style={{
                              padding: '6px 14px',
                              borderRadius: '20px',
                              fontSize: '0.82rem',
                              fontWeight: freqType === f ? 600 : 400,
                              color: freqType === f ? 'white' : 'var(--text-secondary)',
                              backgroundColor: freqType === f ? 'var(--accent-primary)' : 'rgba(255,255,255,0.04)',
                              border: '1px solid',
                              borderColor: freqType === f ? 'var(--accent-primary)' : 'var(--border-color)',
                            }}
                          >
                            {freqLabel[f]}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Time */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <label style={labelStyle}><Clock size={13} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />Heure d'exécution</label>
                      <TimePicker value={scheduleTime} onChange={setScheduleTime} />
                    </div>

                    {/* Weekly day chips */}
                    {freqType === 'weekly' && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <label style={labelStyle}>Jours de répétition</label>
                        <div style={{ display: 'flex', gap: '6px' }}>
                          {DAYS_FR.map((d, i) => {
                            const en = DAYS_EN[i];
                            const active = selectedDays.includes(en);
                            return (
                              <button
                                key={en}
                                type="button"
                                onClick={() => toggleDay(en)}
                                style={{
                                  width: '36px', height: '36px',
                                  borderRadius: '50%',
                                  fontSize: '0.78rem',
                                  fontWeight: active ? 700 : 400,
                                  color: active ? 'white' : 'var(--text-secondary)',
                                  backgroundColor: active ? 'var(--accent-primary)' : 'rgba(255,255,255,0.05)',
                                  border: '1px solid',
                                  borderColor: active ? 'var(--accent-primary)' : 'var(--border-color)',
                                }}
                              >
                                {d}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Date picker for once/monthly/custom */}
                    {(freqType === 'once' || freqType === 'monthly' || freqType === 'custom') && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <label style={labelStyle}>
                          {freqType === 'once' ? 'Date d\'exécution' : 'Date de départ'}
                        </label>
                        <div style={{ backgroundColor: 'var(--bg-primary)', borderRadius: '10px', border: '1px solid var(--border-color)', padding: '16px' }}>
                          <MiniCalendar selected={selectedDate} onChange={setSelectedDate} />
                        </div>
                        {selectedDate && (
                          <p style={{ fontSize: '0.8rem', color: 'var(--accent-primary)', fontWeight: 500 }}>
                            {freqType === 'once' ? '📅 ' : '🔁 À partir du '}
                            {new Date(selectedDate + 'T12:00:00').toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
                          </p>
                        )}
                      </div>
                    )}

                    {/* Custom interval */}
                    {freqType === 'custom' && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <label style={labelStyle}>Intervalle de répétition</label>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Tous les</span>
                          <input
                            type="number"
                            min={1} max={60}
                            value={intervalMonths}
                            onChange={e => setIntervalMonths(Math.max(1, parseInt(e.target.value) || 1))}
                            style={{ ...inputStyle, width: '60px', textAlign: 'center' }}
                          />
                          <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>mois</span>
                        </div>
                      </div>
                    )}

                    {/* Summary */}
                    <div style={{ marginTop: 'auto', padding: '12px 14px', backgroundColor: 'rgba(124,140,255,0.06)', borderRadius: '10px', border: '1px solid rgba(124,140,255,0.15)', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                      <RotateCcw size={13} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle', color: 'var(--accent-primary)' }} />
                      {freqType === 'once' && selectedDate && `Exécution unique le ${new Date(selectedDate + 'T12:00:00').toLocaleDateString('fr-FR')} à ${scheduleTime}`}
                      {freqType === 'weekly' && selectedDays.length > 0 && `Chaque ${selectedDays.map(d => DAYS_FR[DAYS_EN.indexOf(d)]).join(', ')} à ${scheduleTime}`}
                      {freqType === 'monthly' && selectedDate && `Le ${new Date(selectedDate + 'T12:00:00').getDate()} de chaque mois à ${scheduleTime}`}
                      {freqType === 'custom' && selectedDate && `Tous les ${intervalMonths} mois à partir du ${new Date(selectedDate + 'T12:00:00').toLocaleDateString('fr-FR')} à ${scheduleTime}`}
                      {!selectedDate && freqType !== 'weekly' && 'Sélectionnez une date pour voir le résumé'}
                      {freqType === 'weekly' && selectedDays.length === 0 && 'Sélectionnez au moins un jour'}
                    </div>
                  </div>
                )}
              </div>

              {/* Error */}
              {error && (
                <div style={{ margin: '0 28px 16px', padding: '12px 16px', backgroundColor: 'var(--status-error-bg)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '8px', color: 'var(--status-error)', fontSize: '0.85rem' }}>
                  {error}
                </div>
              )}

              {/* Footer */}
              <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', padding: '16px 28px 24px', borderTop: '1px solid var(--border-color)', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={handleClose}
                  style={{ padding: '10px 20px', borderRadius: '8px', color: 'var(--text-secondary)', backgroundColor: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-color)', fontSize: '0.9rem' }}
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '8px',
                    padding: '10px 22px',
                    borderRadius: '8px',
                    backgroundColor: submitting ? 'rgba(124,140,255,0.5)' : 'var(--accent-primary)',
                    color: 'white',
                    fontWeight: 600,
                    fontSize: '0.9rem',
                    boxShadow: submitting ? 'none' : '0 4px 16px rgba(124,140,255,0.3)',
                  }}
                >
                  {submitting ? (
                    <><div className="animate-spin" style={{ width: '16px', height: '16px', border: '2px solid rgba(255,255,255,0.3)', borderTop: '2px solid white', borderRadius: '50%' }} /> Création...</>
                  ) : mode === 'immediate' ? (
                    <><Send size={16} /> Lancer maintenant</>
                  ) : (
                    <><CalendarDays size={16} /> Programmer</>
                  )}
                </button>
              </div>
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

// ── Shared styles ─────────────────────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  fontSize: '0.82rem',
  fontWeight: 600,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
};

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 14px',
  backgroundColor: 'var(--bg-primary)',
  border: '1px solid var(--border-color)',
  borderRadius: '8px',
  color: 'var(--text-primary)',
  fontSize: '0.9rem',
  outline: 'none',
  fontFamily: 'inherit',
};

const selectStyle: React.CSSProperties = {
  ...inputStyle,
  cursor: 'pointer',
};
