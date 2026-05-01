// frontend/components/AIOptimizer.tsx
'use client';

import { useState } from 'react';
import { Brain, Sparkles, Target, Loader2, AlertCircle } from 'lucide-react';

interface ClusterResult {
  clusters: Record<string, string[]>;
  representatives: Record<string, string>;
  total_keywords: number;
  total_clusters: number;
}

interface IntentItem { query: string; intent: string; confidence: number; }
interface IntentResult { results: IntentItem[]; distribution: Record<string, number>; total: number; }

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

const intentColor = (intent: string) => ({
  informational: 'text-sky-300 bg-sky-500/10 border-sky-500/20',
  navigational: 'text-purple-300 bg-purple-500/10 border-purple-500/20',
  transactional: 'text-emerald-300 bg-emerald-500/10 border-emerald-500/20',
  commercial: 'text-amber-300 bg-amber-500/10 border-amber-500/20',
}[intent] || 'text-[#a1a1aa] bg-white/5 border-white/10');

export default function AIOptimizer({ websiteId: _websiteId }: { websiteId?: number }) {
  const [activeTab, setActiveTab] = useState<'cluster' | 'intent'>('cluster');
  const [keywords, setKeywords] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clusters, setClusters] = useState<ClusterResult | null>(null);
  const [intent, setIntent] = useState<IntentResult | null>(null);

  const parseList = () => keywords.split('\n').map(k => k.trim()).filter(Boolean);

  const runCluster = async () => {
    const list = parseList();
    if (list.length < 2) { setError('Enter at least 2 keywords (one per line).'); return; }
    setLoading(true); setError(null); setClusters(null);
    try {
      const r = await fetch(`${API_URL}/api/keywords/cluster`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keywords: list }),
      });
      if (!r.ok) throw new Error((await r.json()).detail || `HTTP ${r.status}`);
      setClusters(await r.json());
    } catch (e: any) { setError(e.message || 'Failed to cluster'); }
    finally { setLoading(false); }
  };

  const runIntent = async () => {
    const list = parseList();
    if (list.length < 1) { setError('Enter at least 1 keyword (one per line).'); return; }
    setLoading(true); setError(null); setIntent(null);
    try {
      const r = await fetch(`${API_URL}/api/keywords/intent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ queries: list }),
      });
      if (!r.ok) throw new Error((await r.json()).detail || `HTTP ${r.status}`);
      setIntent(await r.json());
    } catch (e: any) { setError(e.message || 'Failed to classify'); }
    finally { setLoading(false); }
  };

  const run = () => activeTab === 'cluster' ? runCluster() : runIntent();

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-5">
        <div className="flex items-center gap-2 mb-3">
          <Brain className="w-4 h-4 text-[#7c6cf9]" />
          <h3 className="text-[#f5f5f7] text-sm font-semibold">AI Keyword Tools</h3>
        </div>

        <div className="flex gap-1.5 mb-4">
          {(['cluster', 'intent'] as const).map(tab => (
            <button
              key={tab}
              onClick={() => { setActiveTab(tab); setError(null); }}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${
                activeTab === tab
                  ? 'bg-[#7c6cf9]/15 text-[#f5f5f7] border-[#7c6cf9]/30'
                  : 'bg-white/[0.02] text-[#52525b] border-white/[0.06] hover:text-[#a1a1aa]'
              }`}
            >
              {tab === 'cluster' ? 'Topic Clusters' : 'Search Intent'}
            </button>
          ))}
        </div>

        <textarea
          value={keywords}
          onChange={e => setKeywords(e.target.value)}
          placeholder={activeTab === 'cluster'
            ? 'Paste keywords, one per line.\nGroups them into topic clusters with a representative head term.'
            : 'Paste queries, one per line.\nClassifies each as informational, navigational, transactional, or commercial.'}
          className="w-full h-36 bg-white/[0.03] border border-white/[0.06] rounded-xl px-3 py-2 text-[#f5f5f7] text-sm placeholder-[#52525b] focus:outline-none focus:border-[#7c6cf9]/40 resize-y"
        />

        <div className="flex items-center gap-3 mt-3">
          <button
            onClick={run}
            disabled={loading || !keywords.trim()}
            className="px-4 py-2 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {activeTab === 'cluster' ? 'Cluster Keywords' : 'Classify Intent'}
          </button>
          <span className="text-[#52525b] text-xs">{parseList().length} keyword{parseList().length === 1 ? '' : 's'}</span>
        </div>

        {error && (
          <div className="mt-3 rounded-xl border border-red-500/20 bg-red-500/5 px-3 py-2 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
            <p className="text-red-300 text-xs">{error}</p>
          </div>
        )}
      </div>

      {/* Cluster results */}
      {activeTab === 'cluster' && clusters && (
        <div className="space-y-2">
          <p className="text-[#52525b] text-xs">
            {clusters.total_keywords} keywords grouped into {clusters.total_clusters} clusters
          </p>
          {Object.entries(clusters.clusters).map(([id, kws]) => (
            <div key={id} className="rounded-xl border border-white/[0.06] bg-[#0a0a0c]/60 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Target className="w-3.5 h-3.5 text-[#7c6cf9]" />
                <span className="text-[#f5f5f7] text-sm font-medium">
                  {clusters.representatives[id] || `Cluster ${parseInt(id) + 1}`}
                </span>
                <span className="text-[#52525b] text-xs">· {kws.length} keyword{kws.length === 1 ? '' : 's'}</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {kws.map((kw, i) => (
                  <span key={i} className="text-xs px-2 py-1 rounded-lg bg-white/[0.03] text-[#a1a1aa] border border-white/[0.06]">
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Intent results */}
      {activeTab === 'intent' && intent && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(intent.distribution).map(([k, v]) => (
              <div key={k} className={`rounded-xl border px-3 py-2 ${intentColor(k)}`}>
                <p className="text-[10px] uppercase tracking-wider opacity-70">{k}</p>
                <p className="text-lg font-semibold">{v}</p>
              </div>
            ))}
          </div>
          <div className="rounded-xl border border-white/[0.06] bg-[#0a0a0c]/60 divide-y divide-white/[0.06]">
            {intent.results.map((r, i) => (
              <div key={i} className="px-4 py-2.5 flex items-center justify-between gap-3">
                <span className="text-[#f5f5f7] text-sm truncate">{r.query}</span>
                <span className={`shrink-0 text-xs px-2 py-0.5 rounded-lg border ${intentColor(r.intent)}`}>
                  {r.intent}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
