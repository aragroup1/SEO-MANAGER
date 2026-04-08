// frontend/components/RoadToOne.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Trophy, Star, Target, Loader2, RefreshCw, ExternalLink,
  ChevronRight, AlertTriangle, Trash2, Edit3, Check, X,
  Search, BarChart3, Globe, FileText, Zap, Shield, Users,
  TrendingUp, ArrowRight, Link, Copy
} from 'lucide-react';

interface TrackedKW {
  id: number;
  keyword: string;
  current_position: number | null;
  current_clicks: number;
  current_impressions: number;
  current_ctr: number;
  ranking_url: string | null;
  target_url: string | null;
  target_position: number;
  has_strategy: boolean;
  status: string;
  notes: string;
  updated_at: string | null;
}

interface Strategy {
  keyword: string;
  current_position: number | null;
  strategy: any;
  competitors: any[];
  your_page: any;
  generated_at: string;
}

interface Cannibalization {
  keyword: string;
  pages: { page: string; position: number; clicks: number; impressions: number }[];
  page_count: number;
}

export default function RoadToOne({ websiteId }: { websiteId: number }) {
  const [tracked, setTracked] = useState<TrackedKW[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedKW, setSelectedKW] = useState<TrackedKW | null>(null);
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [loadingStrategy, setLoadingStrategy] = useState(false);
  const [generatingStrategy, setGeneratingStrategy] = useState<number | null>(null);
  const [cannibalization, setCannibalization] = useState<Cannibalization[]>([]);
  const [editingUrl, setEditingUrl] = useState<number | null>(null);
  const [urlInput, setUrlInput] = useState('');

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchTracked = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/api/keywords/${websiteId}/tracked`);
      if (r.ok) {
        const data = await r.json();
        setTracked(data.tracked || []);
      }
    } catch {}
    finally { setLoading(false); }
  }, [API_URL, websiteId]);

  const fetchCannibalization = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/api/strategist/${websiteId}/cannibalization`);
      if (r.ok) {
        const data = await r.json();
        setCannibalization(data.cannibalization || []);
      }
    } catch {}
  }, [API_URL, websiteId]);

  useEffect(() => {
    setLoading(true);
    setTracked([]);
    setSelectedKW(null);
    setStrategy(null);
    setCannibalization([]);
    fetchTracked();
    fetchCannibalization();
  }, [websiteId]);

  const generateStrategy = async (tk: TrackedKW) => {
    setGeneratingStrategy(tk.id);
    try {
      await fetch(`${API_URL}/api/keywords/${websiteId}/track/${tk.id}/strategy`, { method: 'POST' });
      // Poll for result
      const poll = setInterval(async () => {
        const r = await fetch(`${API_URL}/api/keywords/${websiteId}/track/${tk.id}/strategy`);
        if (r.ok) {
          const data = await r.json();
          if (data.strategy) {
            clearInterval(poll);
            setGeneratingStrategy(null);
            fetchTracked(); // Refresh to show has_strategy
            if (selectedKW?.id === tk.id) {
              setStrategy(data);
            }
          }
        }
      }, 5000);
      setTimeout(() => { clearInterval(poll); setGeneratingStrategy(null); }, 120000);
    } catch {
      setGeneratingStrategy(null);
    }
  };

  const loadStrategy = async (tk: TrackedKW) => {
    setSelectedKW(tk);
    setLoadingStrategy(true);
    setStrategy(null);
    try {
      const r = await fetch(`${API_URL}/api/keywords/${websiteId}/track/${tk.id}/strategy`);
      if (r.ok) {
        const data = await r.json();
        if (data.strategy) setStrategy(data);
      }
    } catch {}
    finally { setLoadingStrategy(false); }
  };

  const updateTargetUrl = async (tkId: number) => {
    try {
      await fetch(`${API_URL}/api/keywords/${websiteId}/track/${tkId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_url: urlInput })
      });
      setEditingUrl(null);
      fetchTracked();
    } catch {}
  };

  const removeKeyword = async (tkId: number) => {
    if (!confirm('Remove this keyword from tracking?')) return;
    try {
      await fetch(`${API_URL}/api/keywords/${websiteId}/track/${tkId}`, { method: 'DELETE' });
      setTracked(prev => prev.filter(t => t.id !== tkId));
      if (selectedKW?.id === tkId) { setSelectedKW(null); setStrategy(null); }
    } catch {}
  };

  const posColor = (p: number | null) => !p ? 'text-gray-500' : p <= 3 ? 'text-green-400' : p <= 10 ? 'text-emerald-400' : p <= 20 ? 'text-yellow-400' : p <= 50 ? 'text-orange-400' : 'text-red-400';

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 text-purple-400 animate-spin" /></div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
          <Trophy className="w-6 h-6 text-yellow-400" /> Road to #1
        </h2>
        <p className="text-purple-300 mt-1 text-sm">Track primary keywords, analyze competitors, and execute your strategy to rank #1</p>
      </div>

      {tracked.length === 0 && (
        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
          <Trophy className="w-16 h-16 text-yellow-400/30 mx-auto mb-4" />
          <h3 className="text-xl font-bold text-white mb-2">No Keywords Tracked Yet</h3>
          <p className="text-purple-300 mb-4">Go to the Keywords tab, find keywords you want to rank for, and click the star to track them.</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Keyword List */}
        <div className="lg:col-span-1 space-y-3">
          {tracked.map(tk => (
            <div key={tk.id}
              className={`bg-white/10 backdrop-blur-md rounded-xl border transition-all cursor-pointer ${
                selectedKW?.id === tk.id ? 'border-yellow-500/50 bg-yellow-500/5' : 'border-white/20 hover:border-white/30'
              }`}
              onClick={() => loadStrategy(tk)}>
              <div className="p-4">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <Star className="w-4 h-4 text-yellow-400 fill-yellow-400 shrink-0" />
                    <h4 className="text-white font-medium text-sm truncate">{tk.keyword}</h4>
                  </div>
                  <span className={`text-lg font-bold shrink-0 ml-2 ${posColor(tk.current_position)}`}>
                    {tk.current_position ? `#${tk.current_position}` : 'N/R'}
                  </span>
                </div>

                {/* Target URL */}
                <div className="mb-2">
                  {editingUrl === tk.id ? (
                    <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                      <input value={urlInput} onChange={e => setUrlInput(e.target.value)} placeholder="https://..."
                        className="flex-1 bg-white/10 border border-white/20 rounded px-2 py-1 text-xs text-white" />
                      <button onClick={() => updateTargetUrl(tk.id)} className="text-green-400 p-1"><Check className="w-3 h-3" /></button>
                      <button onClick={() => setEditingUrl(null)} className="text-gray-400 p-1"><X className="w-3 h-3" /></button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1">
                      <Link className="w-3 h-3 text-gray-500 shrink-0" />
                      <span className="text-gray-500 text-xs truncate">{tk.target_url || tk.ranking_url || 'No target URL set'}</span>
                      <button onClick={e => { e.stopPropagation(); setEditingUrl(tk.id); setUrlInput(tk.target_url || tk.ranking_url || ''); }}
                        className="text-gray-600 hover:text-white p-0.5 shrink-0"><Edit3 className="w-2.5 h-2.5" /></button>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-3 text-xs text-gray-400">
                  <span>{tk.current_clicks} clicks</span>
                  <span>{tk.current_impressions} impr</span>
                  {tk.has_strategy && <span className="text-green-400">Strategy ✓</span>}
                </div>

                <div className="flex items-center gap-2 mt-2" onClick={e => e.stopPropagation()}>
                  <button onClick={() => generateStrategy(tk)} disabled={generatingStrategy === tk.id}
                    className="flex-1 bg-gradient-to-r from-yellow-500/20 to-orange-500/20 text-yellow-400 px-2 py-1.5 rounded-lg text-xs font-medium hover:from-yellow-500/30 hover:to-orange-500/30 transition-all border border-yellow-500/30 flex items-center justify-center gap-1 disabled:opacity-50">
                    {generatingStrategy === tk.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                    {generatingStrategy === tk.id ? 'Generating...' : tk.has_strategy ? 'Refresh Strategy' : 'Generate Strategy'}
                  </button>
                  <button onClick={() => removeKeyword(tk.id)} className="text-gray-600 hover:text-red-400 p-1.5"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Right: Strategy Detail */}
        <div className="lg:col-span-2">
          {!selectedKW && tracked.length > 0 && (
            <div className="bg-white/10 backdrop-blur-md rounded-xl p-8 border border-white/20 text-center">
              <Target className="w-10 h-10 text-purple-400 mx-auto mb-3" />
              <p className="text-gray-400">Select a keyword from the left to view its strategy</p>
            </div>
          )}

          {selectedKW && loadingStrategy && (
            <div className="bg-white/10 backdrop-blur-md rounded-xl p-8 border border-white/20 text-center">
              <Loader2 className="w-8 h-8 text-purple-400 animate-spin mx-auto mb-3" />
              <p className="text-gray-400">Loading strategy...</p>
            </div>
          )}

          {selectedKW && !loadingStrategy && !strategy && (
            <div className="bg-white/10 backdrop-blur-md rounded-xl p-8 border border-white/20 text-center">
              <Zap className="w-10 h-10 text-yellow-400 mx-auto mb-3" />
              <h3 className="text-white font-semibold mb-2">No Strategy Generated Yet</h3>
              <p className="text-gray-400 text-sm mb-4">Click "Generate Strategy" to analyze your page vs top competitors.</p>
              <button onClick={() => generateStrategy(selectedKW)}
                className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white px-6 py-2.5 rounded-lg font-medium hover:shadow-lg transition-all">
                Generate Strategy for "{selectedKW.keyword}"
              </button>
            </div>
          )}

          {strategy?.strategy && (
            <div className="space-y-4">
              {/* Summary */}
              <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 backdrop-blur-md rounded-xl p-5 border border-yellow-500/20">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-white font-semibold flex items-center gap-2"><Trophy className="w-5 h-5 text-yellow-400" /> Strategy: "{strategy.keyword}"</h3>
                  {strategy.strategy.confidence_score && (
                    <span className="text-xs bg-white/10 text-gray-300 px-2 py-1 rounded">{strategy.strategy.confidence_score}% confidence</span>
                  )}
                </div>
                <p className="text-gray-300 text-sm">{strategy.strategy.summary}</p>
                {strategy.strategy.estimated_timeline && (
                  <p className="text-yellow-400 text-xs mt-2">Timeline: {strategy.strategy.estimated_timeline}</p>
                )}
              </div>

              {/* Competitors */}
              {strategy.competitors?.length > 0 && (
                <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20">
                  <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2"><Users className="w-4 h-4 text-purple-400" /> Competitor Analysis</h4>
                  <div className="space-y-2">
                    {strategy.competitors.map((c: any, i: number) => (
                      <div key={i} className="bg-white/5 rounded-lg p-3 flex items-center justify-between">
                        <div className="min-w-0 flex-1">
                          <p className="text-white text-sm font-medium truncate">{c.title || c.url}</p>
                          <a href={c.url} target="_blank" rel="noopener noreferrer" className="text-purple-400 text-xs hover:text-purple-300 flex items-center gap-1">
                            {c.url} <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                        <div className="flex items-center gap-3 shrink-0 ml-3">
                          <span className="text-xs text-gray-400">{c.word_count} words</span>
                          <span className="text-xs text-emerald-400 font-bold">#{c.position}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Gaps */}
              {strategy.strategy.current_gaps?.length > 0 && (
                <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20">
                  <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-orange-400" /> Gaps to Close</h4>
                  <div className="space-y-2">
                    {strategy.strategy.current_gaps.map((g: any, i: number) => (
                      <div key={i} className="flex items-start gap-2 bg-white/5 rounded-lg px-3 py-2">
                        <span className={`text-xs px-1.5 py-0.5 rounded mt-0.5 shrink-0 ${g.severity === 'critical' ? 'bg-red-500/20 text-red-400' : g.severity === 'high' ? 'bg-orange-500/20 text-orange-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{g.severity}</span>
                        <div>
                          <p className="text-gray-300 text-sm">{g.gap}</p>
                          <p className="text-gray-600 text-xs">{g.category}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Plan */}
              {strategy.strategy.action_plan?.length > 0 && (
                <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20">
                  <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2"><Target className="w-4 h-4 text-green-400" /> Action Plan</h4>
                  <div className="space-y-2">
                    {strategy.strategy.action_plan.map((a: any, i: number) => (
                      <div key={i} className="bg-white/5 rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded font-bold">#{a.priority}</span>
                          <span className={`text-xs px-1.5 py-0.5 rounded ${a.impact === 'high' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{a.impact} impact</span>
                          <span className="text-xs text-gray-500">{a.effort === 'quick_win' ? '⚡ Quick win' : a.effort}</span>
                          {a.auto_fixable && <span className="text-xs bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded">Auto-fixable</span>}
                        </div>
                        <p className="text-white text-sm font-medium">{a.action}</p>
                        {a.details && <p className="text-gray-400 text-xs mt-1">{a.details}</p>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Content Recommendations */}
              {strategy.strategy.content_recommendations && (
                <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20">
                  <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2"><FileText className="w-4 h-4 text-blue-400" /> Content Recommendations</h4>
                  <div className="space-y-3 bg-white/5 rounded-lg p-4">
                    {strategy.strategy.content_recommendations.suggested_title && (
                      <div><p className="text-gray-500 text-xs">Suggested Title</p><p className="text-green-400 text-sm">{strategy.strategy.content_recommendations.suggested_title}</p></div>
                    )}
                    {strategy.strategy.content_recommendations.suggested_meta_description && (
                      <div><p className="text-gray-500 text-xs">Suggested Meta</p><p className="text-green-400 text-sm">{strategy.strategy.content_recommendations.suggested_meta_description}</p></div>
                    )}
                    {strategy.strategy.content_recommendations.target_word_count && (
                      <div><p className="text-gray-500 text-xs">Target Word Count</p><p className="text-white text-sm">{strategy.strategy.content_recommendations.target_word_count} words</p></div>
                    )}
                    {strategy.strategy.content_recommendations.content_outline?.length > 0 && (
                      <div>
                        <p className="text-gray-500 text-xs mb-1">Content Outline</p>
                        {strategy.strategy.content_recommendations.content_outline.map((s: string, i: number) => (
                          <p key={i} className="text-gray-300 text-xs ml-2">• {s}</p>
                        ))}
                      </div>
                    )}
                    {strategy.strategy.content_recommendations.missing_topics?.length > 0 && (
                      <div>
                        <p className="text-gray-500 text-xs mb-1">Missing Topics</p>
                        {strategy.strategy.content_recommendations.missing_topics.map((t: string, i: number) => (
                          <p key={i} className="text-orange-400 text-xs ml-2">• {t}</p>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {strategy.generated_at && (
                <p className="text-gray-600 text-xs text-center">Strategy generated: {new Date(strategy.generated_at).toLocaleString()}</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Cannibalization Warnings */}
      {cannibalization.length > 0 && (
        <div className="bg-red-500/5 backdrop-blur-md rounded-xl p-5 border border-red-500/20">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-400" /> Keyword Cannibalization Detected
          </h3>
          <p className="text-gray-400 text-sm mb-4">These keywords have multiple pages ranking, which splits your authority and hurts rankings.</p>
          <div className="space-y-3">
            {cannibalization.slice(0, 10).map((c, i) => (
              <div key={i} className="bg-white/5 rounded-lg p-3">
                <p className="text-white text-sm font-medium mb-2">"{c.keyword}" <span className="text-red-400 text-xs">({c.page_count} pages competing)</span></p>
                <div className="space-y-1">
                  {c.pages.map((p, j) => (
                    <div key={j} className="flex items-center justify-between text-xs">
                      <span className="text-gray-400 truncate flex-1">{p.page}</span>
                      <div className="flex items-center gap-3 shrink-0 ml-2">
                        <span className="text-purple-400">Pos {p.position}</span>
                        <span className="text-blue-400">{p.clicks} clicks</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
