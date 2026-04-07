// frontend/components/KeywordTracker.tsx
'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, RefreshCw, ArrowUp, ArrowDown, ArrowUpDown, Eye,
  MousePointerClick, Target, Loader2, ExternalLink,
  BarChart3, Hash, AlertTriangle, Star, Trash2, Trophy,
  TrendingUp, ChevronDown, ChevronUp
} from 'lucide-react';

interface Keyword {
  query: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
  page?: string;
}

interface Snapshot {
  id: number;
  date_from: string;
  date_to: string;
  snapshot_date: string;
  total_keywords: number;
  total_clicks: number;
  total_impressions: number;
  avg_position: number;
  avg_ctr: number;
  gsc_property?: string;
  keywords: Keyword[];
}

interface TrackedKW {
  id: number;
  keyword: string;
  current_position: number | null;
  current_clicks: number;
  current_impressions: number;
  current_ctr: number;
  ranking_url: string | null;
  target_position: number;
  status: string;
}

type SortField = 'clicks' | 'impressions' | 'ctr' | 'position' | 'query';
type SortDir = 'asc' | 'desc';

export default function KeywordTracker({ websiteId }: { websiteId: number }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [trackedKeywords, setTrackedKeywords] = useState<TrackedKW[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('clicks');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [positionFilter, setPositionFilter] = useState('all');
  const [expandedKeyword, setExpandedKeyword] = useState<string | null>(null);
  const [showTracked, setShowTracked] = useState(true);
  const [trackingInProgress, setTrackingInProgress] = useState<string | null>(null);

  const snapshotIdAtSync = useRef<number | null>(null);
  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchKeywords = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/keywords/${websiteId}`);
      if (response.ok) {
        const data = await response.json();
        if (data.snapshot) {
          setSnapshot(data.snapshot);
          setError('');
          if (syncing && snapshotIdAtSync.current !== null && data.snapshot.id !== snapshotIdAtSync.current) {
            setSyncing(false);
          }
        } else {
          setSnapshot(null);
        }
      }
    } catch (err) {
      console.error('Error fetching keywords:', err);
    } finally {
      setLoading(false);
    }
  }, [API_URL, websiteId, syncing]);

  const fetchTracked = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/keywords/${websiteId}/tracked`);
      if (response.ok) {
        const data = await response.json();
        setTrackedKeywords(data.tracked || []);
      }
    } catch (err) {
      console.error('Error fetching tracked:', err);
    }
  }, [API_URL, websiteId]);

  // Reset on website change - fetch directly to avoid stale closures
  useEffect(() => {
    setSnapshot(null);
    setTrackedKeywords([]);
    setLoading(true);
    setSyncing(false);
    setError('');
    setSearchQuery('');
    setExpandedKeyword(null);
    snapshotIdAtSync.current = null;

    // Fetch keywords directly (not via callback) to ensure correct websiteId
    fetch(`${API_URL}/api/keywords/${websiteId}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.snapshot) { setSnapshot(data.snapshot); setError(''); }
        else { setSnapshot(null); }
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    // Fetch tracked keywords
    fetch(`${API_URL}/api/keywords/${websiteId}/tracked`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.tracked) setTrackedKeywords(data.tracked); })
      .catch(() => {});
  }, [websiteId, API_URL]);

  // Poll while syncing
  useEffect(() => {
    if (!syncing) return;
    const interval = setInterval(() => { fetchKeywords(); fetchTracked(); }, 5000);
    const timeout = setTimeout(() => setSyncing(false), 90000);
    return () => { clearInterval(interval); clearTimeout(timeout); };
  }, [syncing, fetchKeywords, fetchTracked]);

  const syncKeywords = async () => {
    snapshotIdAtSync.current = snapshot?.id ?? null;
    setSyncing(true);
    setError('');
    try {
      const response = await fetch(`${API_URL}/api/keywords/${websiteId}/sync`, { method: 'POST' });
      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || 'Sync failed');
        setSyncing(false);
      }
    } catch (err) {
      setError('Connection error');
      setSyncing(false);
    }
  };

  const trackKeyword = async (kw: Keyword) => {
    setTrackingInProgress(kw.query);
    try {
      const response = await fetch(`${API_URL}/api/keywords/${websiteId}/track`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keyword: kw.query,
          position: kw.position,
          clicks: kw.clicks,
          impressions: kw.impressions,
          ctr: kw.ctr,
          page: kw.page || '',
        })
      });
      if (response.ok) {
        await fetchTracked();
      }
    } catch (err) {
      console.error('Error tracking keyword:', err);
    } finally {
      setTrackingInProgress(null);
    }
  };

  const untrackKeyword = async (id: number) => {
    try {
      await fetch(`${API_URL}/api/keywords/${websiteId}/track/${id}`, { method: 'DELETE' });
      await fetchTracked();
    } catch (err) {
      console.error('Error untracking:', err);
    }
  };

  const isTracked = (query: string) => trackedKeywords.some(tk => tk.keyword === query.toLowerCase());

  // Filter and sort
  const filteredKeywords = useMemo(() => {
    if (!snapshot?.keywords) return [];
    let filtered = [...snapshot.keywords];

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(k => k.query.toLowerCase().includes(q) || (k.page && k.page.toLowerCase().includes(q)));
    }

    if (positionFilter !== 'all') {
      switch (positionFilter) {
        case 'top3': filtered = filtered.filter(k => k.position <= 3); break;
        case 'top10': filtered = filtered.filter(k => k.position <= 10); break;
        case 'top20': filtered = filtered.filter(k => k.position <= 20); break;
        case 'striking': filtered = filtered.filter(k => k.position > 10 && k.position <= 20); break;
        case 'opportunity': filtered = filtered.filter(k => k.position > 20 && k.impressions > 10); break;
      }
    }

    filtered.sort((a, b) => {
      if (sortField === 'query') return sortDir === 'asc' ? a.query.localeCompare(b.query) : b.query.localeCompare(a.query);
      return sortDir === 'asc' ? (a[sortField] as number) - (b[sortField] as number) : (b[sortField] as number) - (a[sortField] as number);
    });

    return filtered;
  }, [snapshot, searchQuery, sortField, sortDir, positionFilter]);

  const handleSort = (field: SortField) => {
    if (sortField === field) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir(field === 'position' ? 'asc' : 'desc'); }
  };

  const getPositionColor = (pos: number) => {
    if (pos <= 3) return 'text-green-400';
    if (pos <= 10) return 'text-emerald-400';
    if (pos <= 20) return 'text-yellow-400';
    if (pos <= 50) return 'text-orange-400';
    return 'text-red-400';
  };

  const getPositionBg = (pos: number) => {
    if (pos <= 3) return 'bg-green-500/10 border-green-500/20';
    if (pos <= 10) return 'bg-emerald-500/10 border-emerald-500/20';
    if (pos <= 20) return 'bg-yellow-500/10 border-yellow-500/20';
    if (pos <= 50) return 'bg-orange-500/10 border-orange-500/20';
    return 'bg-red-500/10 border-red-500/20';
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown className="w-3 h-3 text-gray-600" />;
    return sortDir === 'asc' ? <ArrowUp className="w-3 h-3 text-purple-400" /> : <ArrowDown className="w-3 h-3 text-purple-400" />;
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 text-purple-400 animate-spin" /></div>;
  }

  // No data
  if (!snapshot) {
    return (
      <div className="space-y-6">
        {syncing ? (
          <div className="bg-purple-500/10 border border-purple-500/30 rounded-xl p-8 text-center">
            <Loader2 className="w-10 h-10 text-purple-400 animate-spin mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-white mb-2">Syncing Keywords...</h3>
            <p className="text-purple-300 text-sm">Pulling data from Google Search Console. This may take 10-30 seconds.</p>
          </div>
        ) : (
          <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
            <div className="w-20 h-20 bg-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
              <Search className="w-10 h-10 text-purple-400" />
            </div>
            <h2 className="text-2xl font-bold text-white mb-3">No Keyword Data Yet</h2>
            <p className="text-purple-300 mb-6">
              Connect Google Search Console and sync to see your real keyword rankings.
            </p>
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-4 max-w-lg mx-auto">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}
            <button onClick={syncKeywords}
              className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-6 py-3 rounded-lg font-medium hover:shadow-lg transition-all">
              Sync from Search Console
            </button>
          </div>
        )}
      </div>
    );
  }

  const positionBuckets = {
    top3: snapshot.keywords.filter(k => k.position <= 3).length,
    top10: snapshot.keywords.filter(k => k.position > 3 && k.position <= 10).length,
    top20: snapshot.keywords.filter(k => k.position > 10 && k.position <= 20).length,
    top50: snapshot.keywords.filter(k => k.position > 20 && k.position <= 50).length,
    beyond: snapshot.keywords.filter(k => k.position > 50).length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <Search className="w-6 h-6 text-purple-400" />
            Keyword Rankings
          </h2>
          <p className="text-purple-300 mt-1 text-sm">
            {snapshot.gsc_property && <span className="text-gray-500 mr-2">{snapshot.gsc_property}</span>}
            {snapshot.date_from} to {snapshot.date_to}
          </p>
        </div>
        <button onClick={syncKeywords} disabled={syncing}
          className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-4 py-2 rounded-lg font-medium hover:shadow-lg transition-all flex items-center gap-2 disabled:opacity-50">
          {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {syncing ? 'Syncing...' : 'Refresh Data'}
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
          <p className="text-red-400 text-sm flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> {error}</p>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { icon: MousePointerClick, color: 'text-blue-400', value: snapshot.total_clicks.toLocaleString(), label: 'Total Clicks' },
          { icon: Eye, color: 'text-purple-400', value: snapshot.total_impressions.toLocaleString(), label: 'Impressions' },
          { icon: Target, color: 'text-green-400', value: String(snapshot.avg_position), label: 'Avg Position' },
          { icon: BarChart3, color: 'text-yellow-400', value: snapshot.avg_ctr + '%', label: 'Avg CTR' },
          { icon: Hash, color: 'text-pink-400', value: snapshot.total_keywords.toLocaleString(), label: 'Keywords' },
        ].map(card => (
          <div key={card.label} className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20 text-center">
            <card.icon className={`w-5 h-5 ${card.color} mx-auto mb-2`} />
            <p className="text-2xl font-bold text-white">{card.value}</p>
            <p className="text-xs text-gray-400 mt-1">{card.label}</p>
          </div>
        ))}
      </div>

      {/* Tracked Keywords (Road to #1) */}
      {trackedKeywords.length > 0 && (
        <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 backdrop-blur-md rounded-xl border border-yellow-500/20 overflow-hidden">
          <button onClick={() => setShowTracked(!showTracked)}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-all">
            <div className="flex items-center gap-2">
              <Trophy className="w-5 h-5 text-yellow-400" />
              <h3 className="text-white font-semibold text-sm">Road to #1 — Tracked Keywords</h3>
              <span className="text-xs text-yellow-400 bg-yellow-500/20 px-2 py-0.5 rounded-full">{trackedKeywords.length}</span>
            </div>
            {showTracked ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
          </button>

          <AnimatePresence>
            {showTracked && (
              <motion.div initial={{ height: 0 }} animate={{ height: 'auto' }} exit={{ height: 0 }} className="overflow-hidden">
                <div className="px-4 pb-4 space-y-2">
                  {trackedKeywords.map(tk => (
                    <div key={tk.id} className="flex items-center gap-3 bg-white/5 rounded-lg p-3 border border-white/10">
                      <Star className="w-4 h-4 text-yellow-400 fill-yellow-400 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-white text-sm font-medium">{tk.keyword}</p>
                        {tk.ranking_url && (
                          <p className="text-gray-500 text-xs truncate">{tk.ranking_url}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-4 shrink-0">
                        <div className="text-center">
                          <p className={`text-lg font-bold ${tk.current_position ? getPositionColor(tk.current_position) : 'text-gray-500'}`}>
                            {tk.current_position ? tk.current_position : '—'}
                          </p>
                          <p className="text-[10px] text-gray-500">Position</p>
                        </div>
                        <div className="text-center">
                          <p className="text-sm font-medium text-blue-400">{tk.current_clicks}</p>
                          <p className="text-[10px] text-gray-500">Clicks</p>
                        </div>
                        <div className="text-center">
                          <p className="text-sm font-medium text-purple-300">{tk.current_impressions}</p>
                          <p className="text-[10px] text-gray-500">Impr.</p>
                        </div>
                        <button onClick={() => untrackKeyword(tk.id)}
                          className="text-gray-600 hover:text-red-400 transition-colors p-1" title="Remove from tracking">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Position Distribution */}
      <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20">
        <h3 className="text-white font-medium mb-3 text-sm">Position Distribution</h3>
        <div className="flex gap-2">
          {[
            { label: 'Top 3', count: positionBuckets.top3, color: 'bg-green-500' },
            { label: '4-10', count: positionBuckets.top10, color: 'bg-emerald-500' },
            { label: '11-20', count: positionBuckets.top20, color: 'bg-yellow-500' },
            { label: '21-50', count: positionBuckets.top50, color: 'bg-orange-500' },
            { label: '50+', count: positionBuckets.beyond, color: 'bg-red-500' },
          ].map(bucket => {
            const pct = snapshot.total_keywords > 0 ? (bucket.count / snapshot.total_keywords * 100) : 0;
            return (
              <div key={bucket.label} className="flex-1 text-center">
                <div className="h-16 bg-white/5 rounded-lg overflow-hidden flex flex-col justify-end mb-1">
                  <div className={`${bucket.color} rounded-t-sm transition-all`} style={{ height: `${Math.max(pct, 2)}%` }} />
                </div>
                <p className="text-white text-xs font-bold">{bucket.count}</p>
                <p className="text-gray-500 text-xs">{bucket.label}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex-1 min-w-[200px] relative">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input type="text" placeholder="Search keywords or URLs..."
              value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-white/10 border border-white/20 rounded-lg pl-10 pr-4 py-2 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-purple-500" />
          </div>
          <select value={positionFilter} onChange={e => setPositionFilter(e.target.value)}
            className="bg-white/10 text-white border border-white/20 rounded-lg px-3 py-2 text-sm">
            <option value="all">All Positions</option>
            <option value="top3">Top 3</option>
            <option value="top10">Top 10</option>
            <option value="top20">Top 20</option>
            <option value="striking">Striking Distance (11-20)</option>
            <option value="opportunity">Opportunities (20+)</option>
          </select>
          <div className="text-gray-400 text-sm">{filteredKeywords.length} of {snapshot.keywords.length}</div>
        </div>
      </div>

      {/* Keyword Table */}
      <div className="bg-white/10 backdrop-blur-md rounded-xl border border-white/20 overflow-hidden">
        {/* Header */}
        <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-white/10 text-xs font-medium text-gray-400">
          <div className="col-span-1"></div>
          <div className="col-span-4 flex items-center gap-1 cursor-pointer hover:text-white" onClick={() => handleSort('query')}>
            Keyword <SortIcon field="query" />
          </div>
          <div className="col-span-2 flex items-center gap-1 cursor-pointer hover:text-white justify-end" onClick={() => handleSort('clicks')}>
            Clicks <SortIcon field="clicks" />
          </div>
          <div className="col-span-2 flex items-center gap-1 cursor-pointer hover:text-white justify-end" onClick={() => handleSort('impressions')}>
            Impr. <SortIcon field="impressions" />
          </div>
          <div className="col-span-1 flex items-center gap-1 cursor-pointer hover:text-white justify-end" onClick={() => handleSort('ctr')}>
            CTR <SortIcon field="ctr" />
          </div>
          <div className="col-span-2 flex items-center gap-1 cursor-pointer hover:text-white justify-end" onClick={() => handleSort('position')}>
            Position <SortIcon field="position" />
          </div>
        </div>

        {/* Rows */}
        <div className="max-h-[600px] overflow-y-auto">
          {filteredKeywords.slice(0, 200).map((kw, idx) => {
            const tracked = isTracked(kw.query);
            return (
              <div key={kw.query + idx}>
                <div className="grid grid-cols-12 gap-2 px-4 py-2.5 border-b border-white/5 hover:bg-white/5 transition-all items-center">
                  {/* Track button */}
                  <div className="col-span-1">
                    <button
                      onClick={(e) => { e.stopPropagation(); if (!tracked) trackKeyword(kw); }}
                      disabled={trackingInProgress === kw.query}
                      className={`p-1 rounded transition-all ${
                        tracked
                          ? 'text-yellow-400 cursor-default'
                          : 'text-gray-600 hover:text-yellow-400'
                      }`}
                      title={tracked ? 'Already tracked' : 'Track for Road to #1'}
                    >
                      {trackingInProgress === kw.query
                        ? <Loader2 className="w-4 h-4 animate-spin" />
                        : <Star className={`w-4 h-4 ${tracked ? 'fill-yellow-400' : ''}`} />
                      }
                    </button>
                  </div>

                  {/* Keyword */}
                  <div className="col-span-4 min-w-0 cursor-pointer" onClick={() => setExpandedKeyword(expandedKeyword === kw.query ? null : kw.query)}>
                    <p className="text-white text-sm truncate">{kw.query}</p>
                  </div>

                  <div className="col-span-2 text-right">
                    <span className="text-blue-400 text-sm font-medium">{kw.clicks.toLocaleString()}</span>
                  </div>
                  <div className="col-span-2 text-right">
                    <span className="text-purple-300 text-sm">{kw.impressions.toLocaleString()}</span>
                  </div>
                  <div className="col-span-1 text-right">
                    <span className="text-gray-400 text-sm">{kw.ctr}%</span>
                  </div>
                  <div className="col-span-2 text-right flex items-center justify-end gap-2">
                    <span className={`text-sm font-bold ${getPositionColor(kw.position)}`}>{kw.position}</span>
                    <div className={`px-1.5 py-0.5 rounded text-xs border ${getPositionBg(kw.position)} ${getPositionColor(kw.position)}`}>
                      {kw.position <= 3 ? '🏆' : kw.position <= 10 ? 'P1' : kw.position <= 20 ? 'P2' : kw.position <= 50 ? 'P3+' : '50+'}
                    </div>
                  </div>
                </div>

                {/* Expanded */}
                <AnimatePresence>
                  {expandedKeyword === kw.query && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                      className="border-b border-white/10 bg-white/5 overflow-hidden">
                      <div className="px-4 py-3 space-y-2">
                        {kw.page && (
                          <div className="flex items-center gap-2">
                            <span className="text-gray-500 text-xs">Ranking URL:</span>
                            <a href={kw.page} target="_blank" rel="noopener noreferrer"
                              className="text-purple-400 text-xs hover:text-purple-300 truncate flex items-center gap-1">
                              {kw.page} <ExternalLink className="w-3 h-3 shrink-0" />
                            </a>
                          </div>
                        )}
                        <div className="flex items-center gap-4 text-xs flex-wrap">
                          {kw.ctr < 2 && kw.position <= 10 && (
                            <span className="text-yellow-400">Low CTR — improve title & description</span>
                          )}
                          {kw.position > 10 && kw.position <= 20 && (
                            <span className="text-yellow-400">Striking distance — optimize to reach page 1</span>
                          )}
                          {kw.position > 20 && kw.impressions > 50 && (
                            <span className="text-orange-400">High impressions, low ranking — opportunity keyword</span>
                          )}
                          {!tracked && (
                            <button onClick={() => trackKeyword(kw)}
                              className="flex items-center gap-1 text-yellow-400 hover:text-yellow-300 bg-yellow-500/10 px-2 py-0.5 rounded transition-all">
                              <Star className="w-3 h-3" /> Track for Road to #1
                            </button>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            );
          })}

          {filteredKeywords.length === 0 && (
            <div className="text-center py-12">
              <Search className="w-8 h-8 text-gray-600 mx-auto mb-2" />
              <p className="text-gray-400 text-sm">No keywords match your filters</p>
            </div>
          )}

          {filteredKeywords.length > 200 && (
            <div className="text-center py-3 border-t border-white/10">
              <p className="text-gray-500 text-xs">Showing top 200 of {filteredKeywords.length}. Use search to narrow down.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
