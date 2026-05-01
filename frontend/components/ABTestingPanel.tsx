// frontend/components/ABTestingPanel.tsx — A/B Testing for Meta Titles/Descriptions
'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Split, Plus, Play, Square, Trophy, Loader2, ChevronRight, Clock, AlertTriangle, Sparkles } from 'lucide-react';

interface ABTest {
  id: number; page_url: string; element_type: string;
  status: string; winner: string | null;
  variant_a_preview: string; variant_b_preview: string;
  created_at: string;
}

interface Props { websiteId: number; }

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

export default function ABTestingPanel({ websiteId }: Props) {
  const [tests, setTests] = useState<ABTest[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [selectedTest, setSelectedTest] = useState<ABTest | null>(null);
  const [form, setForm] = useState({ page_url: '', element_type: 'title', variant_a: '', keywords: '' });

  const fetchTests = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/ab-test/${websiteId}/list`);
      if (res.ok) {
        const data = await res.json();
        setTests(data.tests || []);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const createTest = async () => {
    setCreating(true);
    try {
      const res = await fetch(`${API_URL}/api/ab-test/${websiteId}/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          page_url: form.page_url,
          element_type: form.element_type,
          variant_a: form.variant_a,
          keywords: form.keywords.split(',').map(k => k.trim()).filter(Boolean),
        }),
      });
      if (res.ok) {
        setShowCreate(false);
        setForm({ page_url: '', element_type: 'title', variant_a: '', keywords: '' });
        fetchTests();
      }
    } catch (e) { console.error(e); }
    setCreating(false);
  };

  const startTest = async (testId: number) => {
    try {
      await fetch(`${API_URL}/api/ab-test/${testId}/start`, { method: 'POST' });
      fetchTests();
    } catch (e) { console.error(e); }
  };

  const endTest = async (testId: number, winner: string) => {
    try {
      await fetch(`${API_URL}/api/ab-test/${testId}/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ winner }),
      });
      fetchTests();
      setSelectedTest(null);
    } catch (e) { console.error(e); }
  };

  useEffect(() => { fetchTests(); }, [websiteId]);

  const statusBadge = (status: string) => {
    const styles: Record<string, string> = {
      draft: 'bg-[#52525b]/20 text-[#52525b]',
      running: 'bg-[#7c6cf9]/20 text-[#7c6cf9]',
      completed: 'bg-[#4ade80]/20 text-[#4ade80]',
    };
    return <span className={`text-xs px-2 py-1 rounded-lg ${styles[status] || styles.draft}`}>{status}</span>;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-[#f5f5f7]">A/B Testing</h2>
          <p className="text-[#52525b] text-sm mt-1">Test meta titles and descriptions against AI-generated variants</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="px-4 py-2 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Test
        </button>
      </div>

      <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 px-4 py-3 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
        <div>
          <p className="text-amber-300 text-xs font-medium">Preview — metrics are simulated</p>
          <p className="text-[#a1a1aa] text-xs mt-0.5">A/B test creation, variants, and winner selection are functional. Click-through rate and impression numbers shown on results are placeholder data; real GSC CTR integration is not yet wired.</p>
        </div>
      </div>

      {/* Create Form */}
      <AnimatePresence>
        {showCreate && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-6 space-y-4"
          >
            <h3 className="text-[#f5f5f7] text-sm font-medium">Create New A/B Test</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-[#52525b] text-xs uppercase tracking-wider">Page URL</label>
                <input
                  type="text" placeholder="/products/my-product"
                  value={form.page_url}
                  onChange={e => setForm({ ...form, page_url: e.target.value })}
                  className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-[#52525b] text-xs uppercase tracking-wider">Element Type</label>
                <select
                  value={form.element_type}
                  onChange={e => setForm({ ...form, element_type: e.target.value })}
                  className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm focus:outline-none focus:border-[#7c6cf9]/50"
                >
                  <option value="title">Meta Title</option>
                  <option value="description">Meta Description</option>
                </select>
              </div>
              <div className="space-y-1.5 md:col-span-2">
                <label className="text-[#52525b] text-xs uppercase tracking-wider">Current {form.element_type === 'title' ? 'Title' : 'Description'} (Variant A)</label>
                <input
                  type="text"
                  value={form.variant_a}
                  onChange={e => setForm({ ...form, variant_a: e.target.value })}
                  placeholder={form.element_type === 'title' ? 'My Product - Best Quality Online' : 'Discover our amazing product...'}
                  className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50"
                />
              </div>
              <div className="space-y-1.5 md:col-span-2">
                <label className="text-[#52525b] text-xs uppercase tracking-wider">Target Keywords (comma separated)</label>
                <input
                  type="text" placeholder="keyword1, keyword2, keyword3"
                  value={form.keywords}
                  onChange={e => setForm({ ...form, keywords: e.target.value })}
                  className="w-full bg-[#0f0f12] border border-white/[0.06] rounded-xl px-4 py-3 text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50"
                />
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={createTest} disabled={creating} className="px-5 py-2.5 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors flex items-center gap-2 disabled:opacity-50">
                {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                {creating ? 'Generating...' : 'Generate Variant B'}
              </button>
              <button onClick={() => setShowCreate(false)} className="px-5 py-2.5 rounded-xl border border-white/[0.06] text-[#52525b] text-sm hover:text-[#f5f5f7] transition-colors">
                Cancel
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Tests List */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-[#7c6cf9] animate-spin" />
        </div>
      ) : tests.length === 0 ? (
        <div className="text-center py-16">
          <Split className="w-12 h-12 text-[#52525b] mx-auto mb-4" />
          <p className="text-[#f5f5f7] font-medium">No A/B tests yet</p>
          <p className="text-[#52525b] text-sm mt-1">Create your first test to optimize meta tags</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tests.map(test => (
            <motion.div
              key={test.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-5 cursor-pointer hover:border-[#7c6cf9]/20 transition-colors"
              onClick={() => setSelectedTest(selectedTest?.id === test.id ? null : test)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Split className="w-5 h-5 text-[#7c6cf9]" />
                  <div>
                    <p className="text-[#f5f5f7] text-sm font-medium">{test.page_url}</p>
                    <p className="text-[#52525b] text-xs capitalize">{test.element_type} test • {statusBadge(test.status)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {test.status === 'draft' && (
                    <button
                      onClick={e => { e.stopPropagation(); startTest(test.id); }}
                      className="p-2 rounded-lg bg-[#7c6cf9]/20 text-[#7c6cf9] hover:bg-[#7c6cf9]/30 transition-colors"
                    >
                      <Play className="w-4 h-4" />
                    </button>
                  )}
                  <ChevronRight className={`w-4 h-4 text-[#52525b] transition-transform ${selectedTest?.id === test.id ? 'rotate-90' : ''}`} />
                </div>
              </div>

              <AnimatePresence>
                {selectedTest?.id === test.id && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-4 pt-4 border-t border-white/[0.06] space-y-4"
                  >
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="rounded-xl border border-white/[0.06] bg-[#0f0f12] p-4">
                        <p className="text-[#52525b] text-xs uppercase tracking-wider mb-2">Variant A (Original)</p>
                        <p className="text-[#f5f5f7] text-sm">{test.variant_a_preview}</p>
                      </div>
                      <div className="rounded-xl border border-[#7c6cf9]/20 bg-[#7c6cf9]/5 p-4">
                        <p className="text-[#7c6cf9] text-xs uppercase tracking-wider mb-2">Variant B (AI)</p>
                        <p className="text-[#f5f5f7] text-sm">{test.variant_b_preview}</p>
                      </div>
                    </div>

                    {test.status === 'running' && (
                      <div className="flex items-center gap-3">
                        <p className="text-[#52525b] text-sm">Which variant performed better?</p>
                        <button onClick={() => endTest(test.id, 'a')} className="px-3 py-1.5 rounded-lg bg-[#52525b]/20 text-[#f5f5f7] text-xs hover:bg-[#52525b]/30 transition-colors">
                          A Won
                        </button>
                        <button onClick={() => endTest(test.id, 'b')} className="px-3 py-1.5 rounded-lg bg-[#7c6cf9]/20 text-[#7c6cf9] text-xs hover:bg-[#7c6cf9]/30 transition-colors">
                          B Won
                        </button>
                        <button onClick={() => endTest(test.id, 'tie')} className="px-3 py-1.5 rounded-lg bg-[#fbbf24]/20 text-[#fbbf24] text-xs hover:bg-[#fbbf24]/30 transition-colors">
                          Tie
                        </button>
                      </div>
                    )}

                    {test.status === 'completed' && test.winner && (
                      <div className="flex items-center gap-2">
                        <Trophy className="w-4 h-4 text-[#fbbf24]" />
                        <p className="text-[#f5f5f7] text-sm">
                          Winner: <span className="font-medium text-[#fbbf24]">Variant {test.winner.toUpperCase()}</span>
                        </p>
                      </div>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
