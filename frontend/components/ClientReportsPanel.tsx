'use client';

import { useState, useEffect, useCallback } from 'react';
import { Mail, Plus, Trash2, Send, CheckCircle, XCircle, Clock, Loader2, Power } from 'lucide-react';

interface Recipient {
  id: number;
  email: string;
  name: string | null;
  is_active: boolean;
  send_hour_utc: number;
  last_sent_at: string | null;
  created_at: string | null;
}

interface LogEntry {
  id: number;
  email: string;
  status: string;
  error: string | null;
  keywords_count: number;
  sent_at: string | null;
}

interface Props { websiteId: number; }

export default function ClientReportsPanel({ websiteId }: Props) {
  const [recipients, setRecipients] = useState<Recipient[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newName, setNewName] = useState('');
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState<number | null>(null);
  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchAll = useCallback(async () => {
    try {
      const [r1, r2] = await Promise.all([
        fetch(`${API_URL}/api/client-reports/${websiteId}/recipients`),
        fetch(`${API_URL}/api/client-reports/${websiteId}/logs`),
      ]);
      if (r1.ok) setRecipients((await r1.json()).recipients || []);
      if (r2.ok) setLogs((await r2.json()).logs || []);
    } finally { setLoading(false); }
  }, [API_URL, websiteId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const addRecipient = async () => {
    setError('');
    if (!newEmail.includes('@')) { setError('Enter a valid email'); return; }
    setAdding(true);
    try {
      const r = await fetch(`${API_URL}/api/client-reports/${websiteId}/recipients`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: newEmail.trim(), name: newName.trim() || null }),
      });
      if (!r.ok) { const d = await r.json(); throw new Error(d.detail || 'Failed'); }
      setNewEmail(''); setNewName('');
      await fetchAll();
    } catch (e: any) { setError(e.message || 'Failed to add'); }
    finally { setAdding(false); }
  };

  const toggleActive = async (rec: Recipient) => {
    setBusyId(rec.id);
    await fetch(`${API_URL}/api/client-reports/recipients/${rec.id}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: !rec.is_active }),
    });
    await fetchAll();
    setBusyId(null);
  };

  const removeRecipient = async (id: number) => {
    if (!confirm('Remove this recipient?')) return;
    setBusyId(id);
    await fetch(`${API_URL}/api/client-reports/recipients/${id}`, { method: 'DELETE' });
    await fetchAll();
    setBusyId(null);
  };

  const sendNow = async (id: number) => {
    setBusyId(id);
    const r = await fetch(`${API_URL}/api/client-reports/recipients/${id}/send-now`, { method: 'POST' });
    const d = await r.json();
    if (d.success) {
      alert(`Sent. ${d.keywords ?? 0} keywords included.`);
    } else {
      alert(`Send failed: ${d.error || d.reason || 'unknown error'}`);
    }
    await fetchAll();
    setBusyId(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[40vh]">
        <Loader2 className="w-6 h-6 text-[var(--accent)] animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] tracking-tight">Daily Client Reports</h1>
        <p className="text-[var(--text-muted)] text-sm mt-1">
          Send a daily ranking-update email at 8 AM UTC to clients. They get a clean summary with day-over-day movement on every tracked keyword.
        </p>
      </header>

      {/* Add recipient */}
      <section className="card-liquid p-5">
        <div className="flex items-center gap-2 mb-4">
          <Mail className="w-4 h-4 text-[var(--accent)]" />
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">Add a recipient</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-[1.4fr_1fr_auto] gap-2">
          <input value={newEmail} onChange={e => setNewEmail(e.target.value)}
            placeholder="client@example.com" className="w-full" type="email" />
          <input value={newName} onChange={e => setNewName(e.target.value)}
            placeholder="Name (optional)" className="w-full" />
          <button onClick={addRecipient} disabled={adding} className="btn-premium disabled:opacity-50">
            {adding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Add
          </button>
        </div>
        {error && <p className="text-[var(--bad)] text-xs mt-2">{error}</p>}
      </section>

      {/* Recipients list */}
      <section className="card-liquid overflow-hidden">
        <header className="px-5 py-4 border-b border-white/[0.06] flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text-primary)]">
            Recipients <span className="text-[var(--text-muted)] font-normal">({recipients.length})</span>
          </h2>
        </header>
        {recipients.length === 0 ? (
          <div className="p-12 text-center">
            <Mail className="w-10 h-10 text-[var(--text-muted)] mx-auto mb-3" />
            <p className="text-[var(--text-muted)] text-sm">No recipients yet. Add one above to start sending daily updates.</p>
          </div>
        ) : (
          <ul className="divide-y divide-white/[0.06]">
            {recipients.map(rec => (
              <li key={rec.id} className="px-5 py-4 flex items-center gap-4">
                <div className={`w-2 h-2 rounded-full shrink-0 ${rec.is_active ? 'bg-[var(--good)]' : 'bg-[var(--text-muted)]'}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-[var(--text-primary)] font-medium truncate">{rec.email}</p>
                  <p className="text-xs text-[var(--text-muted)] truncate">
                    {rec.name || 'No name'} · sends at {String(rec.send_hour_utc).padStart(2,'0')}:00 UTC
                    {rec.last_sent_at && ` · last sent ${new Date(rec.last_sent_at).toLocaleString()}`}
                  </p>
                </div>
                <button onClick={() => sendNow(rec.id)} disabled={busyId === rec.id}
                  title="Send now"
                  className="text-[var(--text-muted)] hover:text-[var(--accent)] p-2 rounded-lg hover:bg-white/[0.04] transition disabled:opacity-50">
                  {busyId === rec.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
                <button onClick={() => toggleActive(rec)} disabled={busyId === rec.id}
                  title={rec.is_active ? 'Pause' : 'Resume'}
                  className={`p-2 rounded-lg hover:bg-white/[0.04] transition disabled:opacity-50 ${rec.is_active ? 'text-[var(--good)]' : 'text-[var(--text-muted)]'}`}>
                  <Power className="w-4 h-4" />
                </button>
                <button onClick={() => removeRecipient(rec.id)} disabled={busyId === rec.id}
                  title="Remove"
                  className="text-[var(--text-muted)] hover:text-[var(--bad)] p-2 rounded-lg hover:bg-white/[0.04] transition disabled:opacity-50">
                  <Trash2 className="w-4 h-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Recent logs */}
      {logs.length > 0 && (
        <section className="card-liquid overflow-hidden">
          <header className="px-5 py-4 border-b border-white/[0.06]">
            <h2 className="text-sm font-semibold text-[var(--text-primary)]">Recent send activity</h2>
          </header>
          <ul className="divide-y divide-white/[0.06]">
            {logs.slice(0, 12).map(log => (
              <li key={log.id} className="px-5 py-3 flex items-center gap-3 text-sm">
                {log.status === 'sent'
                  ? <CheckCircle className="w-4 h-4 text-[var(--good)] shrink-0" />
                  : <XCircle className="w-4 h-4 text-[var(--bad)] shrink-0" />}
                <span className="text-[var(--text-primary)] truncate flex-1">{log.email}</span>
                <span className="text-[var(--text-muted)] text-xs">{log.keywords_count} keywords</span>
                <span className="text-[var(--text-muted)] text-xs flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {log.sent_at ? new Date(log.sent_at).toLocaleString() : '—'}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
