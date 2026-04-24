// frontend/components/NotificationSettings.tsx — Notification Channel Configuration
'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bell, Slack, Mail, Webhook, MessageCircle, Plus, Trash2, Send, CheckCircle, XCircle, Loader2, Clock } from 'lucide-react';

interface Channel {
  id: number; channel_type: string; name: string;
  events: string[]; is_active: boolean;
}

interface Log {
  id: number; event_type: string; status: string;
  message: string; sent_at: string;
}

const EVENT_OPTIONS = [
  { id: 'audit_complete', label: 'Audit Complete', desc: 'When an audit finishes' },
  { id: 'fix_applied', label: 'Fix Applied', desc: 'When auto-fixes are applied' },
  { id: 'ranking_drop', label: 'Ranking Drop', desc: 'When keyword drops >5 positions' },
  { id: 'cwv_poor', label: 'CWV Alert', desc: 'When Core Web Vitals go poor' },
];

const CHANNEL_TYPES = [
  { id: 'slack', label: 'Slack', icon: Slack, placeholder: 'Webhook URL' },
  { id: 'discord', label: 'Discord', icon: MessageCircle, placeholder: 'Webhook URL' },
  { id: 'email', label: 'Email', icon: Mail, placeholder: 'Email address' },
  { id: 'webhook', label: 'Webhook', icon: Webhook, placeholder: 'Endpoint URL' },
];

interface Props { websiteId: number; }

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

export default function NotificationSettings({ websiteId }: Props) {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [logs, setLogs] = useState<Log[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [testing, setTesting] = useState<number | null>(null);
  const [form, setForm] = useState({
    channel_type: 'slack', name: '', config: '', events: [] as string[],
  });

  const fetchData = async () => {
    setLoading(true);
    try {
      const [chRes, logRes] = await Promise.all([
        fetch(`${API_URL}/api/notifications/${websiteId}/channels`),
        fetch(`${API_URL}/api/notifications/${websiteId}/logs?limit=20`),
      ]);
      if (chRes.ok) setChannels((await chRes.json()).channels);
      if (logRes.ok) setLogs((await logRes.json()).logs);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const addChannel = async () => {
    try {
      let config: any = { url: form.config };
      if (form.channel_type === 'email') config = { email: form.config };

      await fetch(`${API_URL}/api/notifications/${websiteId}/channels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel_type: form.channel_type,
          name: form.name,
          config,
          events: form.events,
        }),
      });
      setShowAdd(false);
      setForm({ channel_type: 'slack', name: '', config: '', events: [] });
      fetchData();
    } catch (e) { console.error(e); }
  };

  const deleteChannel = async (id: number) => {
    if (!confirm('Delete this notification channel?')) return;
    try {
      await fetch(`${API_URL}/api/notifications/channels/${id}`, { method: 'DELETE' });
      fetchData();
    } catch (e) { console.error(e); }
  };

  const testChannel = async (id: number) => {
    setTesting(id);
    try {
      await fetch(`${API_URL}/api/notifications/channels/${id}/test`, { method: 'POST' });
    } catch (e) { console.error(e); }
    setTesting(null);
  };

  useEffect(() => { fetchData(); }, [websiteId]);

  const toggleEvent = (eventId: string) => {
    setForm(prev => ({
      ...prev,
      events: prev.events.includes(eventId)
        ? prev.events.filter(e => e !== eventId)
        : [...prev.events, eventId],
    }));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-[#f5f5f7]">Notifications</h2>
          <p className="text-[#52525b] text-sm mt-1">Get alerted when important SEO events happen</p>
        </div>
        <button onClick={() => setShowAdd(true)} className="px-4 py-2 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors flex items-center gap-2">
          <Plus className="w-4 h-4" /> Add Channel
        </button>
      </div>

      {/* Add Channel Form */}
      <AnimatePresence>
        {showAdd && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-6 space-y-4"
          >
            <h3 className="text-[#f5f5f7] text-sm font-medium">Add Notification Channel</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-[#52525b] text-xs uppercase tracking-wider">Channel Type</label>
                <div className="flex gap-2 flex-wrap">
                  {CHANNEL_TYPES.map(t => (
                    <button
                      key={t.id}
                      onClick={() => setForm({ ...form, channel_type: t.id })}
                      className={`px-3 py-2 rounded-lg text-xs font-medium flex items-center gap-1.5 transition-colors ${form.channel_type === t.id ? 'bg-[#7c6cf9]/20 text-[#7c6cf9]' : 'bg-[#0f0f12] text-[#52525b]'}`}
                    >
                      <t.icon className="w-3.5 h-3.5" /> {t.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="text-[#52525b] text-xs uppercase tracking-wider">Channel Name</label>
                <input
                  type="text" placeholder="e.g. Team Slack"
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50"
                />
              </div>
              <div className="space-y-1.5 md:col-span-2">
                <label className="text-[#52525b] text-xs uppercase tracking-wider">
                  {CHANNEL_TYPES.find(t => t.id === form.channel_type)?.placeholder}
                </label>
                <input
                  type="text"
                  value={form.config}
                  onChange={e => setForm({ ...form, config: e.target.value })}
                  placeholder={form.channel_type === 'email' ? 'alerts@company.com' : 'https://hooks.slack.com/services/...'}
                  className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50"
                />
              </div>
              <div className="space-y-1.5 md:col-span-2">
                <label className="text-[#52525b] text-xs uppercase tracking-wider">Events to Notify</label>
                <div className="grid grid-cols-2 gap-3">
                  {EVENT_OPTIONS.map(evt => (
                    <button
                      key={evt.id}
                      onClick={() => toggleEvent(evt.id)}
                      className={`flex items-start gap-3 p-3 rounded-xl border text-left transition-colors ${form.events.includes(evt.id) ? 'border-[#7c6cf9]/30 bg-[#7c6cf9]/10' : 'border-white/[0.06] bg-[#0f0f12]'}`}
                    >
                      <div className={`w-5 h-5 rounded-md border flex items-center justify-center flex-shrink-0 mt-0.5 ${form.events.includes(evt.id) ? 'bg-[#7c6cf9] border-[#7c6cf9]' : 'border-[#52525b]'}`}>
                        {form.events.includes(evt.id) && <CheckCircle className="w-3 h-3 text-white" />}
                      </div>
                      <div>
                        <p className="text-[#f5f5f7] text-sm">{evt.label}</p>
                        <p className="text-[#52525b] text-xs">{evt.desc}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={addChannel} className="px-5 py-2.5 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors">
                Add Channel
              </button>
              <button onClick={() => setShowAdd(false)} className="px-5 py-2.5 rounded-xl border border-white/[0.06] text-[#52525b] text-sm hover:text-[#f5f5f7] transition-colors">
                Cancel
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Channels List */}
      {loading ? (
        <div className="flex items-center justify-center h-32">
          <Loader2 className="w-8 h-8 text-[#7c6cf9] animate-spin" />
        </div>
      ) : channels.length === 0 ? (
        <div className="text-center py-12">
          <Bell className="w-10 h-10 text-[#52525b] mx-auto mb-3" />
          <p className="text-[#f5f5f7] font-medium">No notification channels</p>
          <p className="text-[#52525b] text-sm mt-1">Add a channel to get alerts</p>
        </div>
      ) : (
        <div className="space-y-3">
          {channels.map(ch => {
            const TypeIcon = CHANNEL_TYPES.find(t => t.id === ch.channel_type)?.icon || Webhook;
            return (
              <motion.div
                key={ch.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-5"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-[#7c6cf9]/10 flex items-center justify-center">
                      <TypeIcon className="w-4 h-4 text-[#7c6cf9]" />
                    </div>
                    <div>
                      <p className="text-[#f5f5f7] text-sm font-medium">{ch.name}</p>
                      <p className="text-[#52525b] text-xs capitalize">{ch.channel_type} • {ch.events.length} events</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => testChannel(ch.id)}
                      disabled={testing === ch.id}
                      className="p-2 rounded-lg bg-[#4ade80]/10 text-[#4ade80] hover:bg-[#4ade80]/20 transition-colors disabled:opacity-50"
                      title="Test channel"
                    >
                      {testing === ch.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => deleteChannel(ch.id)}
                      className="p-2 rounded-lg bg-[#f87171]/10 text-[#f87171] hover:bg-[#f87171]/20 transition-colors"
                      title="Delete channel"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 mt-3">
                  {ch.events.map(evt => (
                    <span key={evt} className="text-xs px-2 py-1 rounded-lg bg-[#7c6cf9]/10 text-[#7c6cf9]">
                      {EVENT_OPTIONS.find(e => e.id === evt)?.label || evt}
                    </span>
                  ))}
                </div>
              </motion.div>
            );
          })}
        </div>
      )}

      {/* Notification Logs */}
      {logs.length > 0 && (
        <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-6">
          <h3 className="text-[#f5f5f7] text-sm font-medium mb-4 flex items-center gap-2">
            <Clock className="w-4 h-4 text-[#52525b]" /> Recent Notifications
          </h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {logs.map(log => (
              <div key={log.id} className="flex items-center gap-3 p-3 rounded-xl bg-[#0f0f12]">
                {log.status === 'sent' ? <CheckCircle className="w-4 h-4 text-[#4ade80] flex-shrink-0" /> : <XCircle className="w-4 h-4 text-[#f87171] flex-shrink-0" />}
                <div className="min-w-0 flex-1">
                  <p className="text-[#f5f5f7] text-xs truncate">{log.message}</p>
                  <p className="text-[#52525b] text-[10px]">{log.event_type} • {new Date(log.sent_at).toLocaleString()}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
