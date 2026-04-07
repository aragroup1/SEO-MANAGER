// frontend/components/KeywordTracker.tsx
'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, TrendingUp, TrendingDown, Minus, RefreshCw,
  ArrowUp, ArrowDown, ArrowUpDown, Eye, MousePointerClick,
  Target, Loader2, Filter, Download, ExternalLink,
  BarChart3, Hash, ChevronRight, AlertTriangle
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

type SortField = 'clicks' | 'impressions' | 'ctr' | 'position' | 'query';
type SortDir = 'asc' | 'desc';

export default function KeywordTracker({ websiteId }: { websiteId: number }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('clicks');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [positionFilter, setPositionFilter] = useState('all');
  const [expandedKeyword, setExpandedKeyword] = useState<string | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchKeywords = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/keywords/${websiteId}`);
      if (response.ok) {
        const data = await response.json();
        if (data.snapshot) {
          setSnapshot(data.snapshot);
          setError('');
        } else {
          setSnapshot(null);
          setError('');
        }
      }
    } catch (err) {
      console.error('Error fetching keywords:', err);
    } finally {
      setLoading(false);
    }
  }, [API_URL, websiteId]);

  useEffect(() => {
    setLoading(true);
    fetchKeywords();
  }, [websiteId, fetchKeywords]);

  // Poll while syncing
  useEffect(() => {
    if (!syncing) return;
    const interval = setInterval(() => {
      fetchKeywords();
    }, 5000);
    // Stop after 60s
    const timeout = setTimeout(() => {
      setSyncing(false);
    }, 60000);
    return () => { clearInterval(interval); clearTimeout(timeout); };
  }, [syncing, fetchKeywords]);

  // Detect when new data arrives during sync
  useEffect(() => {
    if (syncing && snapshot) {
      setSyncing(false);
    }
  }, [snapshot]);

  const syncKeywords = async () => {
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

  // Filter and sort keywords
  const filteredKeywords = useMemo(() => {
    if (!snapshot?.keywords) return [];

    let filtered = [...snapshot.keywords];

    // Search filter
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(k =>
        k.query.toLowerCase().includes(q) ||
        (k.page && k.page.toLowerCase().includes(q))
      );
    }

    // Position filter
    if (positionFilter !== 'all') {
      switch (positionFilter) {
        case 'top3':
          filtered = filtered.filter(k => k.position <= 3);
          break;
        case 'top10':
          filtered = filtered.filter(k => k.position <= 10);
          break;
        case 'top20':
          filtered = filtered.filter(k => k.position <= 20);
          break;
        case 'striking':
          filtered = filtered.filter(k => k.position > 10 && k.position <= 20);
          break;
        case 'opportunity':
          filtered = filtered.filter(k => k.position > 20 && k.impressions > 10);
          break;
      }
    }

    // Sort
    filtered.sort((a, b) => {
      let valA: number | string = a[sortField];
      let valB: number | string = b[sortField];
      if (sortField === 'query') {
        return sortDir === 'asc'
          ? String(valA).localeCompare(String(valB))
          : String(valB).localeCompare(String(valA));
      }
      return sortDir === 'asc'
        ? (valA as number) - (valB as number)
        : (valB as number) - (valA as number);
    });

    return filtered;
  }, [snapshot, searchQuery, sortField, sortDir, positionFilter]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir(field === 'position' ? 'asc' : 'desc');
    }
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
    return sortDir === 'asc'
      ? <ArrowUp className="w-3 h-3 text-purple-400" />
      : <ArrowDown className="w-3 h-3 text-purple-400" />;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
      </div>
    );
  }

  // No data yet
  if (!snapshot) {
    return (
      <div className="space-y-6">
        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
          <div className="w-20 h-20 bg-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            {syncing ? (
              <Loader2 className="w-10 h-10 text-purple-400 animate-spin" />
            ) : (
              <Search className="w-10 h-10 text-purple-400" />
            )}
          </div>

          {syncing ? (
            <>
              <h2 className="text-2xl font-bold text-white mb-3">Syncing Keywords...</h2>
              <p className="text-purple-300 mb-2">Pulling data from Google Search Console. This usually takes 10-30 seconds.</p>
            </>
          ) : (
            <>
              <h2 className="text-2xl font-bold text-white mb-3">No Keyword Data Yet</h2>
              <p className="text-purple-300 mb-6">
                Connect Google Search Console and sync to see your real keyword rankings, clicks, and impressions.
              </p>
              {error && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-4 max-w-md mx-auto">
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              )}
              <button onClick={syncKeywords}
                className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg hover:shadow-purple-500/25 transition-all text-lg">
                Sync from Search Console
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  // Position distribution for the summary
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
          <p className="text-purple-300 mt-1">
            {snapshot.gsc_property && <span className="text-gray-500 text-sm mr-2">{snapshot.gsc_property}</span>}
            Data from {snapshot.date_from} to {snapshot.date_to}
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
          <p className="text-red-400 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> {error}
          </p>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20 text-center">
          <MousePointerClick className="w-5 h-5 text-blue-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{snapshot.total_clicks.toLocaleString()}</p>
          <p className="text-xs text-gray-400 mt-1">Total Clicks</p>
        </div>
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20 text-center">
          <Eye className="w-5 h-5 text-purple-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{snapshot.total_impressions.toLocaleString()}</p>
          <p className="text-xs text-gray-400 mt-1">Impressions</p>
        </div>
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20 text-center">
          <Target className="w-5 h-5 text-green-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{snapshot.avg_position}</p>
          <p className="text-xs text-gray-400 mt-1">Avg Position</p>
        </div>
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20 text-center">
          <BarChart3 className="w-5 h-5 text-yellow-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{snapshot.avg_ctr}%</p>
          <p className="text-xs text-gray-400 mt-1">Avg CTR</p>
        </div>
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20 text-center">
          <Hash className="w-5 h-5 text-pink-400 mx-auto mb-2" />
          <p className="text-2xl font-bold text-white">{snapshot.total_keywords.toLocaleString()}</p>
          <p className="text-xs text-gray-400 mt-1">Keywords</p>
        </div>
      </div>

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
            const pct = snapshot.total_keywords > 0
              ? (bucket.count / snapshot.total_keywords * 100)
              : 0;
            return (
              <div key={bucket.label} className="flex-1 text-center">
                <div className="h-16 bg-white/5 rounded-lg overflow-hidden flex flex-col justify-end mb-1">
                  <div className={`${bucket.color} rounded-t-sm transition-all`}
                    style={{ height: `${Math.max(pct, 2)}%` }} />
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
            <input
              type="text"
              placeholder="Search keywords or URLs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/10 border border-white/20 rounded-lg pl-10 pr-4 py-2 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-purple-500"
            />
          </div>
          <select value={positionFilter} onChange={(e) => setPositionFilter(e.target.value)}
            className="bg-white/10 text-white border border-white/20 rounded-lg px-3 py-2 text-sm">
            <option value="all">All Positions</option>
            <option value="top3">Top 3</option>
            <option value="top10">Top 10</option>
            <option value="top20">Top 20</option>
            <option value="striking">Striking Distance (11-20)</option>
            <option value="opportunity">Opportunities (20+ with impressions)</option>
          </select>
          <div className="text-gray-400 text-sm">
            {filteredKeywords.length} of {snapshot.keywords.length} keywords
          </div>
        </div>
      </div>

      {/* Keyword Table */}
      <div className="bg-white/10 backdrop-blur-md rounded-xl border border-white/20 overflow-hidden">
        {/* Table Header */}
        <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-white/10 text-xs font-medium text-gray-400">
          <div className="col-span-5 flex items-center gap-1 cursor-pointer hover:text-white transition-colors"
            onClick={() => handleSort('query')}>
            Keyword <SortIcon field="query" />
          </div>
          <div className="col-span-2 flex items-center gap-1 cursor-pointer hover:text-white transition-colors text-right justify-end"
            onClick={() => handleSort('clicks')}>
            Clicks <SortIcon field="clicks" />
          </div>
          <div className="col-span-2 flex items-center gap-1 cursor-pointer hover:text-white transition-colors text-right justify-end"
            onClick={() => handleSort('impressions')}>
            Impr. <SortIcon field="impressions" />
          </div>
          <div className="col-span-1 flex items-center gap-1 cursor-pointer hover:text-white transition-colors text-right justify-end"
            onClick={() => handleSort('ctr')}>
            CTR <SortIcon field="ctr" />
          </div>
          <div className="col-span-2 flex items-center gap-1 cursor-pointer hover:text-white transition-colors text-right justify-end"
            onClick={() => handleSort('position')}>
            Position <SortIcon field="position" />
          </div>
        </div>

        {/* Table Body */}
        <div className="max-h-[600px] overflow-y-auto">
          {filteredKeywords.slice(0, 200).map((kw, idx) => (
            <div key={kw.query + idx}>
              <div
                className="grid grid-cols-12 gap-2 px-4 py-2.5 border-b border-white/5 hover:bg-white/5 transition-all cursor-pointer items-center"
                onClick={() => setExpandedKeyword(expandedKeyword === kw.query ? null : kw.query)}
              >
                <div className="col-span-5 min-w-0">
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
                  <span className={`text-sm font-bold ${getPositionColor(kw.position)}`}>
                    {kw.position}
                  </span>
                  <div className={`px-1.5 py-0.5 rounded text-xs border ${getPositionBg(kw.position)} ${getPositionColor(kw.position)}`}>
                    {kw.position <= 3 ? '🏆' : kw.position <= 10 ? 'P1' : kw.position <= 20 ? 'P2' : kw.position <= 50 ? 'P3+' : '50+'}
                  </div>
                </div>
              </div>

              {/* Expanded row */}
              <AnimatePresence>
                {expandedKeyword === kw.query && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="border-b border-white/10 bg-white/5 overflow-hidden"
                  >
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
                      <div className="flex items-center gap-6 text-xs">
                        <span className="text-gray-500">
                          Click-through rate: <span className="text-white">{kw.ctr}%</span>
                          {kw.ctr < 2 && kw.position <= 10 && (
                            <span className="text-yellow-400 ml-2">Low CTR for this position — improve title/description</span>
                          )}
                        </span>
                        {kw.position > 10 && kw.position <= 20 && (
                          <span className="text-yellow-400">Striking distance — optimize to reach page 1</span>
                        )}
                        {kw.position > 20 && kw.impressions > 50 && (
                          <span className="text-orange-400">High impressions but low ranking — opportunity keyword</span>
                        )}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}

          {filteredKeywords.length === 0 && (
            <div className="text-center py-12">
              <Search className="w-8 h-8 text-gray-600 mx-auto mb-2" />
              <p className="text-gray-400 text-sm">No keywords match your filters</p>
            </div>
          )}

          {filteredKeywords.length > 200 && (
            <div className="text-center py-3 border-t border-white/10">
              <p className="text-gray-500 text-xs">
                Showing top 200 of {filteredKeywords.length} keywords. Use search to find specific terms.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
