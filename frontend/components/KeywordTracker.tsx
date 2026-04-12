// frontend/components/KeywordTracker.tsx
'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, RefreshCw, ArrowUp, ArrowDown, ArrowUpDown, Eye,
  MousePointerClick, Target, Loader2, ExternalLink,
  BarChart3, Hash, AlertTriangle, Star, Trash2, Trophy,
  ChevronDown, ChevronUp, X, Globe
} from 'lucide-react';

interface Keyword {
  query: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
  page?: string;
  country?: string;
  countries?: { country: string; clicks: number; impressions: number; position: number }[];
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

interface HistoryPoint {
  date: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
}

type SortField = 'clicks' | 'impressions' | 'ctr' | 'position' | 'query';
type SortDir = 'asc' | 'desc';

const COUNTRY_FLAGS: Record<string, string> = {
  'US': '🇺🇸', 'GB': '🇬🇧', 'CA': '🇨🇦', 'AU': '🇦🇺', 'DE': '🇩🇪', 'FR': '🇫🇷',
  'IN': '🇮🇳', 'BR': '🇧🇷', 'JP': '🇯🇵', 'IT': '🇮🇹', 'ES': '🇪🇸', 'NL': '🇳🇱',
  'MX': '🇲🇽', 'PK': '🇵🇰', 'NG': '🇳🇬', 'PH': '🇵🇭', 'ZA': '🇿🇦', 'KE': '🇰🇪',
  'SE': '🇸🇪', 'NO': '🇳🇴', 'DK': '🇩🇰', 'FI': '🇫🇮', 'PL': '🇵🇱', 'IE': '🇮🇪',
  'NZ': '🇳🇿', 'SG': '🇸🇬', 'AE': '🇦🇪', 'SA': '🇸🇦', 'KR': '🇰🇷', 'TR': '🇹🇷',
  'RU': '🇷🇺', 'CN': '🇨🇳', 'ID': '🇮🇩', 'TH': '🇹🇭', 'MY': '🇲🇾', 'VN': '🇻🇳',
  'PT': '🇵🇹', 'BE': '🇧🇪', 'CH': '🇨🇭', 'AT': '🇦🇹', 'CZ': '🇨🇿', 'RO': '🇷🇴',
  'HU': '🇭🇺', 'GR': '🇬🇷', 'IL': '🇮🇱', 'CL': '🇨🇱', 'CO': '🇨🇴', 'AR': '🇦🇷',
  'EG': '🇪🇬', 'BD': '🇧🇩', 'UA': '🇺🇦', 'GH': '🇬🇭', 'TZ': '🇹🇿', 'UG': '🇺🇬',
};

function getFlag(code: string) { return COUNTRY_FLAGS[code] || '🌍'; }

export default function KeywordTracker({ websiteId }: { websiteId: number }) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [trackedKeywords, setTrackedKeywords] = useState<TrackedKW[]>([]);
  const [snapshotHistory, setSnapshotHistory] = useState<{date: string; keywords: number; clicks: number; impressions: number; position: number}[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortField, setSortField] = useState<SortField>('clicks');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [positionFilter, setPositionFilter] = useState('all');
  const [showTracked, setShowTracked] = useState(true);
  const [trackingInProgress, setTrackingInProgress] = useState<string | null>(null);
  const [subTab, setSubTab] = useState<'rankings' | 'research'>('rankings');
  const [dateRange, setDateRange] = useState(3); // 3=latest, 7=week, 28=month, 90=quarter

  // Detail panel
  const [selectedKeyword, setSelectedKeyword] = useState<Keyword | null>(null);
  const [keywordHistory, setKeywordHistory] = useState<HistoryPoint[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Keyword research
  const [researchSeed, setResearchSeed] = useState('');
  const [researchCountry, setResearchCountry] = useState('GB');
  const [researchNiche, setResearchNiche] = useState('');
  const [researchResults, setResearchResults] = useState<any[]>([]);
  const [researching, setResearching] = useState(false);

  // Search volume data from DataForSEO
  const [searchVolumes, setSearchVolumes] = useState<Record<string, { search_volume: number; competition: number; cpc: number }>>({});
  const [volumeSource, setVolumeSource] = useState<string>('');
  const [loadingVolumes, setLoadingVolumes] = useState(false);

  const snapshotIdAtSync = useRef<number | null>(null);
  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  // ─── Data fetching (direct, no stale closures) ───
  useEffect(() => {
    setSnapshot(null);
    setTrackedKeywords([]);
    setSnapshotHistory([]);
    setLoading(true);
    setSyncing(false);
    setError('');
    setSearchQuery('');
    setSelectedKeyword(null);
    setKeywordHistory([]);
    setResearchResults([]);
    setSubTab('rankings');
    snapshotIdAtSync.current = null;

    fetch(`${API_URL}/api/keywords/${websiteId}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.snapshot) { setSnapshot(data.snapshot); }
        else { setSnapshot(null); }
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    fetch(`${API_URL}/api/keywords/${websiteId}/tracked`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.tracked) setTrackedKeywords(data.tracked); })
      .catch(() => {});

    // Fetch snapshot history for trend chart
    fetch(`${API_URL}/api/keywords/${websiteId}/history?limit=20`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.snapshots) {
          const history = data.snapshots.reverse().map((s: any) => ({
            date: s.date_to,
            keywords: s.total_keywords,
            clicks: s.total_clicks,
            impressions: s.total_impressions,
            position: s.avg_position,
          }));
          setSnapshotHistory(history);
        }
      })
      .catch(() => {});
  }, [websiteId, API_URL]);

  // Fetch search volumes from DataForSEO when snapshot loads
  useEffect(() => {
    if (!snapshot?.keywords?.length) return;
    setLoadingVolumes(true);
    const topKeywords = snapshot.keywords.slice(0, 100).map(k => k.query);
    fetch(`${API_URL}/api/keywords/${websiteId}/search-volumes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keywords: topKeywords, country: 'GB' })
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.volumes) {
          setSearchVolumes(data.volumes);
          setVolumeSource(data.source || '');
        }
      })
      .catch(() => {})
      .finally(() => setLoadingVolumes(false));
  }, [snapshot?.id, API_URL, websiteId]);

  // Poll while syncing
  useEffect(() => {
    if (!syncing) return;
    const interval = setInterval(() => {
      fetch(`${API_URL}/api/keywords/${websiteId}`)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data?.snapshot) {
            setSnapshot(data.snapshot);
            if (snapshotIdAtSync.current !== null && data.snapshot.id !== snapshotIdAtSync.current) {
              setSyncing(false);
              // Also refresh tracked
              fetch(`${API_URL}/api/keywords/${websiteId}/tracked`)
                .then(r => r.ok ? r.json() : null)
                .then(d => { if (d?.tracked) setTrackedKeywords(d.tracked); });
            }
          }
        });
    }, 5000);
    const timeout = setTimeout(() => setSyncing(false), 90000);
    return () => { clearInterval(interval); clearTimeout(timeout); };
  }, [syncing, websiteId, API_URL]);

  const syncKeywords = async (days?: number) => {
    const syncDays = days ?? dateRange;
    snapshotIdAtSync.current = snapshot?.id ?? null;
    setSyncing(true);
    setError('');
    try {
      const r = await fetch(`${API_URL}/api/keywords/${websiteId}/sync?days=${syncDays}`, { method: 'POST' });
      if (!r.ok) { const d = await r.json(); setError(d.detail || 'Sync failed'); setSyncing(false); }
    } catch { setError('Connection error'); setSyncing(false); }
  };

  // ─── Keyword detail + history ───
  const openKeywordDetail = async (kw: Keyword) => {
    setSelectedKeyword(kw);
    setLoadingHistory(true);
    setKeywordHistory([]);
    try {
      const r = await fetch(`${API_URL}/api/keywords/${websiteId}/keyword-history?keyword=${encodeURIComponent(kw.query)}&days=90`);
      if (r.ok) {
        const data = await r.json();
        setKeywordHistory(data.history || []);
      }
    } catch (err) {
      console.error('Error fetching keyword history:', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  // ─── Track/untrack ───
  const trackKeyword = async (kw: Keyword) => {
    setTrackingInProgress(kw.query);
    try {
      const r = await fetch(`${API_URL}/api/keywords/${websiteId}/track`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: kw.query, position: kw.position, clicks: kw.clicks, impressions: kw.impressions, ctr: kw.ctr, page: kw.page || '' })
      });
      if (r.ok) {
        const tr = await fetch(`${API_URL}/api/keywords/${websiteId}/tracked`);
        if (tr.ok) { const d = await tr.json(); setTrackedKeywords(d.tracked || []); }
      }
    } catch {} finally { setTrackingInProgress(null); }
  };

  const untrackKeyword = async (id: number) => {
    try {
      await fetch(`${API_URL}/api/keywords/${websiteId}/track/${id}`, { method: 'DELETE' });
      setTrackedKeywords(prev => prev.filter(t => t.id !== id));
    } catch {}
  };

  const isTracked = (q: string) => trackedKeywords.some(t => t.keyword === q.toLowerCase());

  // Reset keyword data (clear wrong property)
  const resetKeywordData = async () => {
    if (!confirm('Clear all keyword data and reset GSC property for this website?')) return;
    try {
      await fetch(`${API_URL}/api/keywords/${websiteId}/reset`, { method: 'POST' });
      setSnapshot(null);
      setTrackedKeywords([]);
      setError('');
    } catch {}
  };

  // Keyword research
  const runResearch = async () => {
    if (!researchSeed.trim()) return;
    setResearching(true);
    setResearchResults([]);
    try {
      const r = await fetch(`${API_URL}/api/keywords/${websiteId}/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seed_keyword: researchSeed, country: researchCountry, niche: researchNiche })
      });
      if (r.ok) {
        const data = await r.json();
        setResearchResults(data.keywords || []);
      }
    } catch (err) {
      console.error('Research error:', err);
    } finally {
      setResearching(false);
    }
  };

  // Road to #1 strategy
  const [generatingStrategy, setGeneratingStrategy] = useState<number | null>(null);
  const [strategyData, setStrategyData] = useState<any>(null);
  const [showStrategyPanel, setShowStrategyPanel] = useState(false);

  const generateStrategy = async (keywordId: number) => {
    setGeneratingStrategy(keywordId);
    try {
      // Trigger generation
      await fetch(`${API_URL}/api/keywords/${websiteId}/track/${keywordId}/strategy`, { method: 'POST' });
      // Poll for result
      const poll = setInterval(async () => {
        const r = await fetch(`${API_URL}/api/keywords/${websiteId}/track/${keywordId}/strategy`);
        if (r.ok) {
          const data = await r.json();
          if (data.strategy) {
            clearInterval(poll);
            setGeneratingStrategy(null);
            setStrategyData(data);
            setShowStrategyPanel(true);
          }
        }
      }, 5000);
      // Timeout after 90s
      setTimeout(() => { clearInterval(poll); setGeneratingStrategy(null); }, 90000);
    } catch (err) {
      console.error('Strategy error:', err);
      setGeneratingStrategy(null);
    }
  };

  // ─── Filter + sort ───
  const filteredKeywords = useMemo(() => {
    if (!snapshot?.keywords) return [];
    let f = [...snapshot.keywords];
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      f = f.filter(k => k.query.toLowerCase().includes(q) || (k.page && k.page.toLowerCase().includes(q)));
    }
    if (positionFilter !== 'all') {
      switch (positionFilter) {
        case 'top3': f = f.filter(k => k.position <= 3); break;
        case 'top10': f = f.filter(k => k.position <= 10); break;
        case 'top20': f = f.filter(k => k.position <= 20); break;
        case 'striking': f = f.filter(k => k.position > 10 && k.position <= 20); break;
        case 'opportunity': f = f.filter(k => k.position > 20 && k.impressions > 10); break;
      }
    }
    f.sort((a, b) => {
      if (sortField === 'query') return sortDir === 'asc' ? a.query.localeCompare(b.query) : b.query.localeCompare(a.query);
      return sortDir === 'asc' ? (a[sortField] as number) - (b[sortField] as number) : (b[sortField] as number) - (a[sortField] as number);
    });
    return f;
  }, [snapshot, searchQuery, sortField, sortDir, positionFilter]);

  const handleSort = (field: SortField) => {
    if (sortField === field) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortField(field); setSortDir(field === 'position' ? 'asc' : 'desc'); }
  };

  const posColor = (p: number) => p <= 3 ? 'text-green-400' : p <= 10 ? 'text-emerald-400' : p <= 20 ? 'text-yellow-400' : p <= 50 ? 'text-orange-400' : 'text-red-400';
  const posBg = (p: number) => p <= 3 ? 'bg-green-500/10 border-green-500/20' : p <= 10 ? 'bg-emerald-500/10 border-emerald-500/20' : p <= 20 ? 'bg-yellow-500/10 border-yellow-500/20' : p <= 50 ? 'bg-orange-500/10 border-orange-500/20' : 'bg-red-500/10 border-red-500/20';
  const SortIcon = ({ field }: { field: SortField }) => sortField !== field ? <ArrowUpDown className="w-3 h-3 text-gray-600" /> : sortDir === 'asc' ? <ArrowUp className="w-3 h-3 text-purple-400" /> : <ArrowDown className="w-3 h-3 text-purple-400" />;

  // ─── Simple SVG chart for keyword history ───
  const HistoryChart = ({ data, metric, invertY = false }: { data: HistoryPoint[]; metric: 'position' | 'clicks' | 'impressions'; invertY?: boolean }) => {
    if (!data.length) return null;
    const isPosition = metric === 'position';
    const shouldInvert = isPosition || invertY;

    // For position: filter out 0s (not ranking) for scale calculation, treat 0 as worst
    let values = data.map(d => d[metric] as number);
    const nonZeroValues = isPosition ? values.filter(v => v > 0) : values;

    if (nonZeroValues.length === 0 && isPosition) {
      // All zeros — not ranking at all
      return (
        <svg viewBox="0 0 600 120" className="w-full h-28" preserveAspectRatio="none">
          <text x="300" y="60" fill="#666" fontSize="12" textAnchor="middle">Not ranking yet</text>
        </svg>
      );
    }

    const maxVal = Math.max(...nonZeroValues, 1);
    const minVal = isPosition ? Math.min(...nonZeroValues, 1) : Math.min(...values, 0);
    const range = maxVal - minVal || 1;
    const w = 600, h = 120, pad = 30;

    const points = data.map((d, i) => {
      const x = pad + (i / (data.length - 1 || 1)) * (w - pad * 2);
      const val = d[metric] as number;

      let y: number;
      if (isPosition && val === 0) {
        // Not ranking = bottom of chart
        y = h - pad;
      } else if (shouldInvert) {
        // Position: 1 at top, higher numbers toward bottom
        y = pad + ((val - minVal) / range) * (h - pad * 2);
      } else {
        y = pad + (1 - (val - minVal) / range) * (h - pad * 2);
      }
      return `${x},${y}`;
    }).join(' ');

    const color = metric === 'position' ? '#a855f7' : metric === 'clicks' ? '#3b82f6' : '#8b5cf6';
    const topLabel = shouldInvert ? (isPosition ? '#' + minVal : minVal) : maxVal;
    const bottomLabel = shouldInvert ? (isPosition ? maxVal > 0 ? '#' + maxVal : 'N/R' : maxVal) : minVal;

    return (
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-28" preserveAspectRatio="none">
        <polyline fill="none" stroke={color} strokeWidth="2" points={points} />
        <text x={pad} y={h - 5} fill="#666" fontSize="10">{data[0].date.slice(5)}</text>
        <text x={w - pad} y={h - 5} fill="#666" fontSize="10" textAnchor="end">{data[data.length - 1].date.slice(5)}</text>
        <text x={pad - 5} y={pad + 4} fill="#888" fontSize="10" textAnchor="end">{topLabel}</text>
        <text x={pad - 5} y={h - pad + 4} fill="#888" fontSize="10" textAnchor="end">{bottomLabel}</text>
        {shouldInvert && <text x={w - 5} y={pad + 4} fill="#4ade80" fontSize="9" textAnchor="end">#1 ↑</text>}
      </svg>
    );
  };

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 text-purple-400 animate-spin" /></div>;

  // No data
  if (!snapshot) return (
    <div className="space-y-6">
      {syncing ? (
        <div className="bg-purple-500/10 border border-purple-500/30 rounded-xl p-8 text-center">
          <Loader2 className="w-10 h-10 text-purple-400 animate-spin mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-white mb-2">Syncing Keywords...</h3>
          <p className="text-purple-300 text-sm">Pulling data from Google Search Console...</p>
        </div>
      ) : (
        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
          <div className="w-20 h-20 bg-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <Search className="w-10 h-10 text-purple-400" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">No Keyword Data Yet</h2>
          <p className="text-purple-300 mb-6">Connect Google Search Console and sync to see your rankings.</p>
          {error && <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-4 max-w-lg mx-auto"><p className="text-red-400 text-sm">{error}</p></div>}
          <button onClick={() => syncKeywords()} className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-6 py-3 rounded-lg font-medium hover:shadow-lg transition-all">
            Sync from Search Console
          </button>
        </div>
      )}
    </div>
  );

  const buckets = {
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
            <Search className="w-6 h-6 text-purple-400" /> Keyword Rankings
          </h2>
          <p className="text-purple-300 mt-1 text-sm">
            {snapshot.gsc_property && <span className="text-gray-500 mr-2">{snapshot.gsc_property}</span>}
            {snapshot.date_from} to {snapshot.date_to}
            {(snapshot as any).changes && (
              <span className="text-gray-600 ml-2">· vs {(snapshot as any).changes.prev_date_from} to {(snapshot as any).changes.prev_date_to}</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select value={dateRange} onChange={e => { setDateRange(Number(e.target.value)); syncKeywords(Number(e.target.value)); }}
            className="bg-white/10 text-white border border-white/20 rounded-lg px-3 py-2 text-sm">
            <option value={3}>Latest (3 days)</option>
            <option value={7}>Last 7 days</option>
            <option value={28}>Last 28 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button onClick={resetKeywordData}
            className="bg-white/10 text-gray-300 px-3 py-2 rounded-lg text-sm hover:bg-white/20 transition-all flex items-center gap-1.5"
            title="Reset GSC property and clear data">
            <Trash2 className="w-3.5 h-3.5" /> Reset
          </button>
          <button onClick={() => syncKeywords()} disabled={syncing}
            className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-4 py-2 rounded-lg font-medium hover:shadow-lg transition-all flex items-center gap-2 disabled:opacity-50">
            {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            {syncing ? 'Syncing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {error && <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3"><p className="text-red-400 text-sm flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> {error}</p></div>}

      {/* Sub-tabs */}
      <div className="flex gap-2">
        <button onClick={() => setSubTab('rankings')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${subTab === 'rankings' ? 'bg-purple-500/30 text-white border border-purple-500/50' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
          Rankings
        </button>
        <button onClick={() => setSubTab('research')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${subTab === 'research' ? 'bg-purple-500/30 text-white border border-purple-500/50' : 'bg-white/5 text-gray-400 hover:bg-white/10'}`}>
          Keyword Research
        </button>
      </div>

      {subTab === 'research' && (
        <div className="space-y-4">
          {/* Research Input */}
          <div className="bg-white/10 backdrop-blur-md rounded-xl p-5 border border-white/20">
            <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Search className="w-5 h-5 text-purple-400" /> Keyword Research</h3>
            <p className="text-gray-400 text-sm mb-4">Enter a seed keyword to discover related terms with search volume and difficulty estimates.</p>
            <div className="flex gap-3 flex-wrap">
              <input type="text" placeholder="e.g. canvas wall art, barcode generator..." value={researchSeed} onChange={e => setResearchSeed(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && runResearch()}
                className="flex-1 min-w-[250px] bg-white/10 border border-white/20 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500" />
              <select value={researchCountry} onChange={e => setResearchCountry(e.target.value)}
                className="bg-white/10 text-white border border-white/20 rounded-lg px-3 py-2.5 text-sm">
                <option value="GLOBAL">🌍 Worldwide</option>
                <option value="GB">🇬🇧 UK</option><option value="US">🇺🇸 US</option><option value="CA">🇨🇦 CA</option>
                <option value="AU">🇦🇺 AU</option><option value="DE">🇩🇪 DE</option><option value="FR">🇫🇷 FR</option>
                <option value="IN">🇮🇳 IN</option><option value="BR">🇧🇷 BR</option><option value="JP">🇯🇵 JP</option>
              </select>
              <input type="text" placeholder="Niche (optional)" value={researchNiche} onChange={e => setResearchNiche(e.target.value)}
                className="w-40 bg-white/10 border border-white/20 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-purple-500" />
              <button onClick={runResearch} disabled={researching || !researchSeed.trim()}
                className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-5 py-2.5 rounded-lg font-medium hover:shadow-lg transition-all disabled:opacity-50 flex items-center gap-2">
                {researching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                {researching ? 'Researching...' : 'Research'}
              </button>
            </div>
          </div>

          {/* Research Results */}
          {researchResults.length > 0 && (
            <div className="bg-white/10 backdrop-blur-md rounded-xl border border-white/20 overflow-hidden">
              <div className="grid grid-cols-12 gap-2 px-4 py-3 border-b border-white/10 text-xs font-medium text-gray-400">
                <div className="col-span-1"></div>
                <div className="col-span-4">Keyword</div>
                <div className="col-span-2 text-right">Volume</div>
                <div className="col-span-2 text-center">Difficulty</div>
                <div className="col-span-1 text-right">CPC</div>
                <div className="col-span-2 text-center">Score</div>
              </div>
              <div className="max-h-[500px] overflow-y-auto">
                {researchResults.map((kw: any, idx: number) => (
                  <div key={kw.keyword + idx} className="grid grid-cols-12 gap-2 px-4 py-2.5 border-b border-white/5 hover:bg-white/5 items-center">
                    <div className="col-span-1">
                      <button onClick={() => trackKeyword({ query: kw.keyword, clicks: 0, impressions: 0, ctr: 0, position: 0 })}
                        disabled={isTracked(kw.keyword)}
                        className={`p-1 rounded transition-all ${isTracked(kw.keyword) ? 'text-yellow-400' : 'text-gray-600 hover:text-yellow-400'}`}>
                        <Star className={`w-4 h-4 ${isTracked(kw.keyword) ? 'fill-yellow-400' : ''}`} />
                      </button>
                    </div>
                    <div className="col-span-4 min-w-0">
                      <p className="text-white text-sm truncate">{kw.keyword}</p>
                      <p className="text-gray-600 text-xs">{kw.intent} · {kw.category}</p>
                    </div>
                    <div className="col-span-2 text-right">
                      <span className="text-blue-400 text-sm font-medium">{(kw.search_volume || 0).toLocaleString()}</span>
                      <p className="text-gray-600 text-[10px]">/month</p>
                    </div>
                    <div className="col-span-2 text-center">
                      <div className="inline-flex items-center gap-1.5">
                        <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${(kw.difficulty || 0) <= 30 ? 'bg-green-500' : (kw.difficulty || 0) <= 60 ? 'bg-yellow-500' : 'bg-red-500'}`}
                            style={{ width: `${kw.difficulty || 0}%` }} />
                        </div>
                        <span className="text-xs text-gray-400">{kw.difficulty || 0}</span>
                      </div>
                      <p className="text-gray-600 text-[10px]">{kw.difficulty_label}</p>
                    </div>
                    <div className="col-span-1 text-right">
                      <span className="text-green-400 text-sm">${(kw.cpc || 0).toFixed(2)}</span>
                    </div>
                    <div className="col-span-2 text-center">
                      <div className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${
                        (kw.opportunity_score || 0) >= 70 ? 'bg-green-500/20 text-green-400' :
                        (kw.opportunity_score || 0) >= 40 ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-red-500/20 text-red-400'
                      }`}>
                        {kw.opportunity_score || 0}/100
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {subTab === 'rankings' && (<>

      {/* Keyword Ranking Trend — at top */}
      {snapshotHistory.length > 1 && (
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20">
          <h3 className="text-white font-medium mb-3 text-sm">Keyword Ranking Trend</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white/5 rounded-lg p-3">
              <p className="text-xs text-gray-400 mb-2">Total Keywords Ranking</p>
              <HistoryChart data={snapshotHistory.map(s => ({ date: s.date, clicks: s.keywords, impressions: 0, ctr: 0, position: 0 }))} metric="clicks" />
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <p className="text-xs text-gray-400 mb-2">Total Clicks</p>
              <HistoryChart data={snapshotHistory.map(s => ({ date: s.date, clicks: s.clicks, impressions: 0, ctr: 0, position: 0 }))} metric="clicks" />
            </div>
            <div className="bg-white/5 rounded-lg p-3">
              <p className="text-xs text-gray-400 mb-2">Avg Position (↑ = better)</p>
              <HistoryChart data={snapshotHistory.map(s => ({ date: s.date, clicks: 0, impressions: 0, ctr: 0, position: s.position }))} metric="position" />
            </div>
          </div>
        </div>
      )}

      {/* Summary */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { icon: MousePointerClick, color: 'text-blue-400', value: snapshot.total_clicks.toLocaleString(), label: 'Total Clicks', change: (snapshot as any).changes?.clicks_change },
          { icon: Eye, color: 'text-purple-400', value: snapshot.total_impressions.toLocaleString(), label: 'Impressions', change: (snapshot as any).changes?.impressions_change },
          { icon: Target, color: 'text-green-400', value: String(snapshot.avg_position), label: 'Avg Position', change: (snapshot as any).changes?.position_change, invertPositive: false },
          { icon: BarChart3, color: 'text-yellow-400', value: snapshot.avg_ctr + '%', label: 'Avg CTR' },
          { icon: Hash, color: 'text-pink-400', value: snapshot.total_keywords.toLocaleString(), label: 'Keywords', change: (snapshot as any).changes?.keywords_change },
        ].map(c => (
          <div key={c.label} className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20 text-center">
            <c.icon className={`w-5 h-5 ${c.color} mx-auto mb-2`} />
            <p className="text-2xl font-bold text-white">{c.value}</p>
            <p className="text-xs text-gray-400 mt-1">{c.label}</p>
            {c.change !== undefined && c.change !== null && c.change !== 0 && (
              <p className={`text-xs mt-1 ${c.label === 'Avg Position' ? (c.change > 0 ? 'text-green-400' : 'text-red-400') : (c.change > 0 ? 'text-green-400' : 'text-red-400')}`}>
                {c.change > 0 ? '↑' : '↓'} {c.label === 'Avg Position' ? (c.change > 0 ? '+' : '') + c.change + ' pos' : (c.change > 0 ? '+' : '') + c.change.toLocaleString()}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Tracked Keywords */}
      {trackedKeywords.length > 0 && (
        <div className="bg-gradient-to-r from-yellow-500/10 to-orange-500/10 backdrop-blur-md rounded-xl border border-yellow-500/20 overflow-hidden">
          <button onClick={() => setShowTracked(!showTracked)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-white/5 transition-all">
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
                    <div key={tk.id} className="bg-white/5 rounded-lg border border-white/10">
                      <div className="flex items-center gap-3 p-3 cursor-pointer hover:bg-white/10 transition-all"
                        onClick={() => { const kw = snapshot.keywords.find(k => k.query.toLowerCase() === tk.keyword); if (kw) openKeywordDetail(kw); }}>
                        <Star className="w-4 h-4 text-yellow-400 fill-yellow-400 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-white text-sm font-medium">{tk.keyword}</p>
                          {tk.ranking_url && <p className="text-gray-500 text-xs truncate">{tk.ranking_url}</p>}
                        </div>
                        <div className="flex items-center gap-4 shrink-0">
                          <div className="text-center"><p className={`text-lg font-bold ${tk.current_position ? posColor(tk.current_position) : 'text-gray-500'}`}>{tk.current_position ?? '—'}</p><p className="text-[10px] text-gray-500">Pos</p></div>
                          <div className="text-center"><p className="text-sm font-medium text-blue-400">{tk.current_clicks}</p><p className="text-[10px] text-gray-500">Clicks</p></div>
                          <div className="text-center"><p className="text-sm font-medium text-purple-300">{tk.current_impressions}</p><p className="text-[10px] text-gray-500">Impr</p></div>
                          <button onClick={e => { e.stopPropagation(); generateStrategy(tk.id); }}
                            className="bg-gradient-to-r from-yellow-500/20 to-orange-500/20 text-yellow-400 px-2.5 py-1 rounded-lg text-xs font-medium hover:from-yellow-500/30 hover:to-orange-500/30 transition-all flex items-center gap-1 border border-yellow-500/30">
                            <Target className="w-3 h-3" /> Strategy
                          </button>
                          <button onClick={e => { e.stopPropagation(); untrackKeyword(tk.id); }} className="text-gray-600 hover:text-red-400 transition-colors p-1"><Trash2 className="w-3.5 h-3.5" /></button>
                        </div>
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
            { label: 'Top 3', count: buckets.top3, color: 'bg-green-500' },
            { label: '4-10', count: buckets.top10, color: 'bg-emerald-500' },
            { label: '11-20', count: buckets.top20, color: 'bg-yellow-500' },
            { label: '21-50', count: buckets.top50, color: 'bg-orange-500' },
            { label: '50+', count: buckets.beyond, color: 'bg-red-500' },
          ].map(b => {
            const pct = snapshot.total_keywords > 0 ? (b.count / snapshot.total_keywords * 100) : 0;
            return (
              <div key={b.label} className="flex-1 text-center">
                <div className="h-16 bg-white/5 rounded-lg overflow-hidden flex flex-col justify-end mb-1">
                  <div className={`${b.color} rounded-t-sm`} style={{ height: `${Math.max(pct, 2)}%` }} />
                </div>
                <p className="text-white text-xs font-bold">{b.count}</p><p className="text-gray-500 text-xs">{b.label}</p>
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
            <input type="text" placeholder="Search keywords or URLs..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-white/10 border border-white/20 rounded-lg pl-10 pr-4 py-2 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-purple-500" />
          </div>
          <select value={positionFilter} onChange={e => setPositionFilter(e.target.value)} className="bg-white/10 text-white border border-white/20 rounded-lg px-3 py-2 text-sm">
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
        {/* DataForSEO status */}
        {volumeSource && (
          <div className="px-4 py-1.5 border-b border-white/5 flex items-center gap-2">
            {volumeSource === 'dataforseo' ? (
              <span className="text-green-400 text-[10px] flex items-center gap-1">● Search volumes from DataForSEO ({Object.keys(searchVolumes).length} keywords)</span>
            ) : volumeSource === 'not_configured' ? (
              <span className="text-yellow-400 text-[10px]">⚠ Add DATAFORSEO_LOGIN + DATAFORSEO_PASSWORD env vars for search volume data</span>
            ) : volumeSource === 'error' ? (
              <span className="text-red-400 text-[10px]">⚠ DataForSEO error — check credentials</span>
            ) : null}
            {loadingVolumes && <Loader2 className="w-3 h-3 text-purple-400 animate-spin" />}
          </div>
        )}

        <div className="grid grid-cols-14 gap-1 px-4 py-3 border-b border-white/10 text-xs font-medium text-gray-400" style={{ gridTemplateColumns: '2.5rem 1fr 4.5rem 3.5rem 3.5rem 3rem 2.5rem 4.5rem 3rem' }}>
          <div></div>
          <div className="flex items-center gap-1 cursor-pointer hover:text-white" onClick={() => handleSort('query')}>Keyword <SortIcon field="query" /></div>
          <div className="text-center">Country</div>
          <div className="text-right text-purple-300">Vol</div>
          <div className="flex items-center gap-1 cursor-pointer hover:text-white justify-end" onClick={() => handleSort('clicks')}>Clicks <SortIcon field="clicks" /></div>
          <div className="flex items-center gap-1 cursor-pointer hover:text-white justify-end" onClick={() => handleSort('impressions')}>Impr <SortIcon field="impressions" /></div>
          <div className="flex items-center gap-1 cursor-pointer hover:text-white justify-end" onClick={() => handleSort('ctr')}>CTR <SortIcon field="ctr" /></div>
          <div className="flex items-center gap-1 cursor-pointer hover:text-white justify-end" onClick={() => handleSort('position')}>Position <SortIcon field="position" /></div>
          <div className="text-center">Change</div>
        </div>

        <div className="max-h-[600px] overflow-y-auto">
          {filteredKeywords.slice(0, 200).map((kw, idx) => {
            const tracked = isTracked(kw.query);
            const vol = searchVolumes[kw.query.toLowerCase()];
            const posChange = (kw as any).position_change;
            return (
              <div key={kw.query + idx} className="grid gap-1 px-4 py-2.5 border-b border-white/5 hover:bg-white/5 transition-all items-center cursor-pointer"
                style={{ gridTemplateColumns: '2.5rem 1fr 4.5rem 3.5rem 3.5rem 3rem 2.5rem 4.5rem 3rem' }}
                onClick={() => openKeywordDetail(kw)}>
                <div>
                  <button onClick={e => { e.stopPropagation(); if (!tracked) trackKeyword(kw); }}
                    disabled={trackingInProgress === kw.query}
                    className={`p-1 rounded transition-all ${tracked ? 'text-yellow-400' : 'text-gray-600 hover:text-yellow-400'}`}
                    title={tracked ? 'Tracked' : 'Track for Road to #1'}>
                    {trackingInProgress === kw.query ? <Loader2 className="w-4 h-4 animate-spin" /> : <Star className={`w-4 h-4 ${tracked ? 'fill-yellow-400' : ''}`} />}
                  </button>
                </div>
                <div className="min-w-0"><p className="text-white text-sm truncate">{kw.query}</p></div>
                <div className="text-center">
                  {kw.country ? (
                    <span className="text-sm" title={kw.country}>{getFlag(kw.country)} <span className="text-gray-400 text-xs">{kw.country}</span></span>
                  ) : <span className="text-gray-600 text-xs">—</span>}
                </div>
                <div className="text-right">
                  {vol ? (
                    <span className="text-purple-300 text-xs font-medium">{vol.search_volume.toLocaleString()}</span>
                  ) : (
                    <span className="text-gray-700 text-xs">—</span>
                  )}
                </div>
                <div className="text-right"><span className="text-blue-400 text-sm font-medium">{kw.clicks.toLocaleString()}</span></div>
                <div className="text-right"><span className="text-purple-300 text-xs">{kw.impressions.toLocaleString()}</span></div>
                <div className="text-right"><span className="text-gray-400 text-xs">{kw.ctr}%</span></div>
                <div className="text-right flex items-center justify-end gap-1.5">
                  <span className={`text-sm font-bold ${posColor(kw.position)}`}>{kw.position}</span>
                  <div className={`px-1 py-0.5 rounded text-[10px] border ${posBg(kw.position)} ${posColor(kw.position)}`}>
                    {kw.position <= 3 ? '🏆' : kw.position <= 10 ? 'P1' : kw.position <= 20 ? 'P2' : kw.position <= 50 ? 'P3+' : '50+'}
                  </div>
                </div>
                <div className="text-center">
                  {posChange !== null && posChange !== undefined && posChange !== 0 ? (
                    <span className={`text-xs font-bold ${posChange > 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {posChange > 0 ? '▲' : '▼'}{Math.abs(posChange)}
                    </span>
                  ) : (
                    <span className="text-gray-700 text-xs">—</span>
                  )}
                </div>
              </div>
            );
          })}
          {filteredKeywords.length === 0 && <div className="text-center py-12"><Search className="w-8 h-8 text-gray-600 mx-auto mb-2" /><p className="text-gray-400 text-sm">No keywords match</p></div>}
          {filteredKeywords.length > 200 && <div className="text-center py-3 border-t border-white/10"><p className="text-gray-500 text-xs">Showing top 200 of {filteredKeywords.length}</p></div>}
        </div>
      </div>

      </>)}

      {/* Keyword Detail Panel (slide-over) */}
      <AnimatePresence>
        {selectedKeyword && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex justify-end" onClick={() => setSelectedKeyword(null)}>
            <motion.div initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="w-full max-w-lg bg-gray-900 border-l border-white/10 h-full overflow-y-auto" onClick={e => e.stopPropagation()}>
              <div className="p-6 space-y-6">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-xl font-bold text-white break-words">{selectedKeyword.query}</h3>
                    {selectedKeyword.page && (
                      <a href={selectedKeyword.page} target="_blank" rel="noopener noreferrer"
                        className="text-purple-400 text-sm hover:text-purple-300 flex items-center gap-1 mt-1">
                        {selectedKeyword.page} <ExternalLink className="w-3 h-3 shrink-0" />
                      </a>
                    )}
                  </div>
                  <button onClick={() => setSelectedKeyword(null)} className="text-gray-400 hover:text-white p-1"><X className="w-5 h-5" /></button>
                </div>

                {/* Current stats */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-white/5 rounded-lg p-3 text-center">
                    <p className={`text-3xl font-bold ${posColor(selectedKeyword.position)}`}>{selectedKeyword.position}</p>
                    <p className="text-xs text-gray-400 mt-1">Position</p>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3 text-center">
                    <p className="text-3xl font-bold text-blue-400">{selectedKeyword.clicks}</p>
                    <p className="text-xs text-gray-400 mt-1">Clicks</p>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-purple-300">{selectedKeyword.impressions.toLocaleString()}</p>
                    <p className="text-xs text-gray-400 mt-1">Impressions</p>
                  </div>
                  <div className="bg-white/5 rounded-lg p-3 text-center">
                    <p className="text-2xl font-bold text-yellow-400">{selectedKeyword.ctr}%</p>
                    <p className="text-xs text-gray-400 mt-1">CTR</p>
                  </div>
                </div>

                {/* Search Volume from DataForSEO */}
                {(() => {
                  const sv = searchVolumes[selectedKeyword.query.toLowerCase()];
                  if (!sv) return null;
                  return (
                    <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-3">
                      <p className="text-purple-400 text-xs font-medium mb-2">Search Volume Data (DataForSEO)</p>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="text-center">
                          <p className="text-xl font-bold text-white">{sv.search_volume.toLocaleString()}</p>
                          <p className="text-[10px] text-gray-400">Monthly Volume</p>
                        </div>
                        <div className="text-center">
                          <p className="text-xl font-bold text-orange-400">{sv.competition}</p>
                          <p className="text-[10px] text-gray-400">Competition</p>
                        </div>
                        <div className="text-center">
                          <p className="text-xl font-bold text-green-400">${sv.cpc}</p>
                          <p className="text-[10px] text-gray-400">CPC</p>
                        </div>
                      </div>
                    </div>
                  );
                })()}

                {/* Countries */}
                {selectedKeyword.countries && selectedKeyword.countries.length > 0 && (
                  <div>
                    <h4 className="text-white font-medium text-sm mb-2 flex items-center gap-2"><Globe className="w-4 h-4 text-purple-400" /> Ranking by Country</h4>
                    <div className="space-y-1.5">
                      {selectedKeyword.countries.map(c => (
                        <div key={c.country} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2">
                          <span className="text-white text-sm">{getFlag(c.country)} {c.country}</span>
                          <div className="flex items-center gap-4 text-xs">
                            <span className={posColor(c.position)}>Pos {c.position}</span>
                            <span className="text-blue-400">{c.clicks} clicks</span>
                            <span className="text-gray-400">{c.impressions} impr</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Track button */}
                {!isTracked(selectedKeyword.query) && (
                  <button onClick={() => trackKeyword(selectedKeyword)}
                    className="w-full bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-yellow-500/30 transition-all flex items-center justify-center gap-2">
                    <Star className="w-4 h-4" /> Track for Road to #1
                  </button>
                )}

                {/* Historical Charts */}
                <div>
                  <h4 className="text-white font-medium text-sm mb-3">90-Day History</h4>
                  {loadingHistory ? (
                    <div className="flex items-center justify-center py-8"><Loader2 className="w-6 h-6 text-purple-400 animate-spin" /></div>
                  ) : keywordHistory.length === 0 ? (
                    <p className="text-gray-500 text-sm text-center py-4">No historical data available for this keyword</p>
                  ) : (
                    <div className="space-y-4">
                      <div className="bg-white/5 rounded-lg p-3">
                        <p className="text-xs text-gray-400 mb-2">Position (lower is better)</p>
                        <HistoryChart data={keywordHistory} metric="position" />
                      </div>
                      <div className="bg-white/5 rounded-lg p-3">
                        <p className="text-xs text-gray-400 mb-2">Clicks</p>
                        <HistoryChart data={keywordHistory} metric="clicks" />
                      </div>
                      <div className="bg-white/5 rounded-lg p-3">
                        <p className="text-xs text-gray-400 mb-2">Impressions</p>
                        <HistoryChart data={keywordHistory} metric="impressions" />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Strategy Panel */}
      <AnimatePresence>
        {showStrategyPanel && strategyData?.strategy && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex justify-end" onClick={() => setShowStrategyPanel(false)}>
            <motion.div initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }} transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="w-full max-w-2xl bg-gray-900 border-l border-white/10 h-full overflow-y-auto" onClick={e => e.stopPropagation()}>
              <div className="p-6 space-y-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-xl font-bold text-white flex items-center gap-2">
                      <Trophy className="w-5 h-5 text-yellow-400" /> Road to #1
                    </h3>
                    <p className="text-purple-300 text-sm mt-1">Strategy for: <span className="text-white font-medium">{strategyData.keyword}</span></p>
                    <p className="text-gray-500 text-xs mt-1">Current position: {strategyData.current_position ?? 'Not ranking'}</p>
                  </div>
                  <button onClick={() => setShowStrategyPanel(false)} className="text-gray-400 hover:text-white p-1"><X className="w-5 h-5" /></button>
                </div>

                {/* Summary */}
                <div className="bg-purple-500/10 border border-purple-500/20 rounded-lg p-4">
                  <p className="text-white text-sm">{strategyData.strategy.summary}</p>
                  {strategyData.strategy.estimated_timeline && (
                    <p className="text-purple-400 text-xs mt-2">Estimated timeline: {strategyData.strategy.estimated_timeline}</p>
                  )}
                  {strategyData.strategy.confidence_score && (
                    <p className="text-gray-400 text-xs mt-1">Confidence: {strategyData.strategy.confidence_score}%</p>
                  )}
                </div>

                {/* Gaps */}
                {strategyData.strategy.current_gaps?.length > 0 && (
                  <div>
                    <h4 className="text-white font-medium text-sm mb-2">Current Gaps</h4>
                    <div className="space-y-1.5">
                      {strategyData.strategy.current_gaps.map((gap: any, i: number) => (
                        <div key={i} className="flex items-start gap-2 bg-white/5 rounded-lg px-3 py-2">
                          <span className={`text-xs px-1.5 py-0.5 rounded mt-0.5 ${gap.severity === 'critical' ? 'bg-red-500/20 text-red-400' : gap.severity === 'high' ? 'bg-orange-500/20 text-orange-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{gap.severity}</span>
                          <p className="text-gray-300 text-sm">{gap.gap}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Action Plan */}
                {strategyData.strategy.action_plan?.length > 0 && (
                  <div>
                    <h4 className="text-white font-medium text-sm mb-2">Action Plan</h4>
                    <div className="space-y-2">
                      {strategyData.strategy.action_plan.map((action: any, i: number) => (
                        <div key={i} className="bg-white/5 rounded-lg p-3 border border-white/10">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs bg-purple-500/20 text-purple-400 px-1.5 py-0.5 rounded">#{action.priority}</span>
                            <span className={`text-xs px-1.5 py-0.5 rounded ${action.impact === 'high' ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}>{action.impact} impact</span>
                            <span className="text-xs text-gray-500">{action.effort}</span>
                            {action.auto_fixable && <span className="text-xs bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded">Auto-fixable</span>}
                          </div>
                          <p className="text-white text-sm font-medium">{action.action}</p>
                          {action.details && <p className="text-gray-400 text-xs mt-1">{action.details}</p>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Content Recommendations */}
                {strategyData.strategy.content_recommendations && (
                  <div>
                    <h4 className="text-white font-medium text-sm mb-2">Content Recommendations</h4>
                    <div className="bg-white/5 rounded-lg p-4 space-y-3">
                      {strategyData.strategy.content_recommendations.suggested_title && (
                        <div><p className="text-gray-500 text-xs">Suggested Title</p><p className="text-green-400 text-sm">{strategyData.strategy.content_recommendations.suggested_title}</p></div>
                      )}
                      {strategyData.strategy.content_recommendations.suggested_meta_description && (
                        <div><p className="text-gray-500 text-xs">Suggested Meta Description</p><p className="text-green-400 text-sm">{strategyData.strategy.content_recommendations.suggested_meta_description}</p></div>
                      )}
                      {strategyData.strategy.content_recommendations.suggested_h1 && (
                        <div><p className="text-gray-500 text-xs">Suggested H1</p><p className="text-green-400 text-sm">{strategyData.strategy.content_recommendations.suggested_h1}</p></div>
                      )}
                      {strategyData.strategy.content_recommendations.target_word_count && (
                        <div><p className="text-gray-500 text-xs">Target Word Count</p><p className="text-white text-sm">{strategyData.strategy.content_recommendations.target_word_count} words</p></div>
                      )}
                      {strategyData.strategy.content_recommendations.content_outline?.length > 0 && (
                        <div>
                          <p className="text-gray-500 text-xs mb-1">Content Outline</p>
                          {strategyData.strategy.content_recommendations.content_outline.map((section: string, i: number) => (
                            <p key={i} className="text-gray-300 text-xs ml-2">• {section}</p>
                          ))}
                        </div>
                      )}
                      {strategyData.strategy.content_recommendations.missing_topics?.length > 0 && (
                        <div>
                          <p className="text-gray-500 text-xs mb-1">Missing Topics (competitors cover these)</p>
                          {strategyData.strategy.content_recommendations.missing_topics.map((topic: string, i: number) => (
                            <p key={i} className="text-orange-400 text-xs ml-2">• {topic}</p>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Competitors */}
                {strategyData.competitors?.length > 0 && (
                  <div>
                    <h4 className="text-white font-medium text-sm mb-2">Competitor Analysis</h4>
                    <div className="space-y-2">
                      {strategyData.competitors.map((comp: any, i: number) => (
                        <div key={i} className="bg-white/5 rounded-lg p-3 flex items-center justify-between">
                          <div className="min-w-0 flex-1">
                            <p className="text-white text-sm font-medium truncate">{comp.title || comp.url}</p>
                            <p className="text-gray-500 text-xs truncate">{comp.url}</p>
                          </div>
                          <div className="flex items-center gap-3 shrink-0 ml-3">
                            <span className="text-xs text-gray-400">{comp.word_count} words</span>
                            <span className="text-xs text-purple-400">Pos ~{comp.position}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {strategyData.generated_at && (
                  <p className="text-gray-600 text-xs text-center">Generated: {new Date(strategyData.generated_at).toLocaleString()}</p>
                )}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Generating Strategy Overlay */}
      {generatingStrategy && (
        <div className="fixed bottom-6 right-6 z-40 bg-gray-900 border border-yellow-500/30 rounded-xl p-4 shadow-2xl flex items-center gap-3">
          <Loader2 className="w-5 h-5 text-yellow-400 animate-spin" />
          <div>
            <p className="text-white text-sm font-medium">Generating Strategy...</p>
            <p className="text-gray-400 text-xs">Analyzing competitors (30-60 seconds)</p>
          </div>
        </div>
      )}
    </div>
  );
}
