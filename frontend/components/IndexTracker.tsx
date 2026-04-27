// frontend/components/IndexTracker.tsx — Page Index Status Tracker
'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, RefreshCw, Loader2, CheckCircle, XCircle,
  AlertTriangle, Globe, BarChart3, ExternalLink, Filter,
  ChevronDown, ChevronUp, Clock, TrendingUp, TrendingDown
} from 'lucide-react';

// ─── Types ───
interface IndexItem {
  id: number;
  url: string;
  is_indexed: boolean;
  coverage_state: string;
  last_checked: string | null;
  first_seen: string | null;
  check_method: string;
}

interface IndexSummary {
  total_urls: number;
  indexed: number;
  not_indexed: number;
  index_rate: number;
  checked_last_24h: number;
  gsc_inspected: number;
  search_fallback: number;
}

interface TrendPoint {
  date: string;
  indexed: number;
  not_indexed: number;
  total: number;
}

interface IndexTrends {
  days: number;
  trends: TrendPoint[];
}

// ─── Animation Variants ───
const cardVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.05, duration: 0.4, ease: [0.32, 0.72, 0, 1] }
  })
};

const fadeUp = { hidden: { opacity: 0, y: 12 }, visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.32, 0.72, 0, 1] } } };

// ─── Circular Progress Gauge ───
function CircularGauge({ percentage, size = 100, strokeWidth = 8, label }: { percentage: number; size?: number; strokeWidth?: number; label?: string }) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;
  const color = percentage >= 80 ? '#4ade80' : percentage >= 50 ? '#fbbf24' : '#f87171';

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="#1a1a1e" strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: 'stroke-dashoffset 1s ease-out', transform: 'rotate(-90deg)', transformOrigin: '50% 50%' }}
        />
        <text x={size / 2} y={size / 2 + 5} textAnchor="middle" fill="#f5f5f7" fontSize="18" fontWeight="bold">
          {Math.round(percentage)}%
        </text>
      </svg>
      {label && <span className="text-[10px] text-[#52525b] mt-1">{label}</span>}
    </div>
  );
}

// ─── Trend Line Chart (SVG) ───
function TrendChart({ data }: { data: TrendPoint[] }) {
  if (!data.length) {
    return <div className="h-[160px] flex items-center justify-center"><p className="text-[#52525b] text-xs">No trend data</p></div>;
  }

  const w = 600, h = 160, pad = { top: 10, right: 10, bottom: 24, left: 36 };
  const chartW = w - pad.left - pad.right;
  const chartH = h - pad.top - pad.bottom;

  const maxVal = Math.max(...data.map(d => d.total), 1);

  const xFor = (i: number) => pad.left + (i / (data.length - 1 || 1)) * chartW;
  const yFor = (val: number) => pad.top + (1 - val / maxVal) * chartH;

  const indexedPoints = data.map((d, i) => `${xFor(i)},${yFor(d.indexed)}`).join(' ');
  const totalPoints = data.map((d, i) => `${xFor(i)},${yFor(d.total)}`).join(' ');

  // X-axis labels (show ~5 labels)
  const labelStep = Math.max(1, Math.floor(data.length / 5));

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: h }}>
      {/* Grid lines */}
      {[0, 0.25, 0.5, 0.75, 1].map(pct => {
        const y = pad.top + (1 - pct) * chartH;
        return (
          <g key={pct}>
            <line x1={pad.left} y1={y} x2={w - pad.right} y2={y} stroke="#ffffff08" strokeWidth="1" />
            <text x={pad.left - 6} y={y + 3} textAnchor="end" fill="#52525b" fontSize="9">{Math.round(maxVal * pct)}</text>
          </g>
        );
      })}

      {/* Total area (subtle) */}
      <polygon
        points={`${indexedPoints} ${xFor(data.length - 1)},${yFor(0)} ${xFor(0)},${yFor(0)}`}
        fill="#f8717110"
      />

      {/* Indexed line */}
      <polyline fill="none" stroke="#4ade80" strokeWidth="2.5" points={indexedPoints} strokeLinecap="round" strokeLinejoin="round" />
      {/* Total line */}
      <polyline fill="none" stroke="#f87171" strokeWidth="2" strokeDasharray="4 3" points={totalPoints} strokeLinecap="round" strokeLinejoin="round" />

      {/* Dots for indexed */}
      {data.map((d, i) => (
        <circle key={`idx-${i}`} cx={xFor(i)} cy={yFor(d.indexed)} r="3" fill="#4ade80" />
      ))}

      {/* X-axis labels */}
      {data.map((d, i) => (
        i % labelStep === 0 ? (
          <text key={`lbl-${i}`} x={xFor(i)} y={h - 6} textAnchor="middle" fill="#52525b" fontSize="9">
            {d.date.slice(5)}
          </text>
        ) : null
      ))}

      {/* Legend */}
      <g transform={`translate(${w - 140}, 12)`}>
        <circle cx="0" cy="0" r="3" fill="#4ade80" />
        <text x="8" y="3" fill="#a1a1aa" fontSize="9">Indexed</text>
        <circle cx="70" cy="0" r="3" fill="#f87171" />
        <text x="78" y="3" fill="#a1a1aa" fontSize="9">Total</text>
      </g>
    </svg>
  );
}

// ─── Main Component ───
export default function IndexTracker({ websiteId }: { websiteId: number }) {
  const [items, setItems] = useState<IndexItem[]>([]);
  const [summary, setSummary] = useState<IndexSummary | null>(null);
  const [trends, setTrends] = useState<IndexTrends | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [filterIndexed, setFilterIndexed] = useState<boolean | null>(null);
  const [sortDesc, setSortDesc] = useState(true);
  const [page, setPage] = useState(0);
  const pageSize = 50;

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [summaryRes, trendsRes] = await Promise.all([
        fetch(`${API_URL}/api/index/${websiteId}/summary`),
        fetch(`${API_URL}/api/index/${websiteId}/trends?days=30`),
      ]);

      if (summaryRes.ok) {
        const s = await summaryRes.json();
        if (!s.error) setSummary(s);
      }
      if (trendsRes.ok) {
        const t = await trendsRes.json();
        if (!t.error) setTrends(t);
      }

      // Fetch items with current filter
      const url = new URL(`${API_URL}/api/index/${websiteId}`);
      url.searchParams.set('limit', '500');
      if (filterIndexed !== null) {
        url.searchParams.set('indexed', String(filterIndexed));
      }
      const itemsRes = await fetch(url.toString());
      if (itemsRes.ok) {
        const d = await itemsRes.json();
        if (!d.error) setItems(d.items || []);
      }
    } catch (e) {
      setError('Failed to load index data');
    } finally {
      setLoading(false);
    }
  }, [websiteId, API_URL, filterIndexed]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const r = await fetch(`${API_URL}/api/index/${websiteId}/sync`, { method: 'POST' });
      if (r.ok) {
        // Poll for updates
        let attempts = 0;
        const poll = setInterval(async () => {
          attempts++;
          await fetchData();
          if (attempts >= 6) {
            clearInterval(poll);
            setSyncing(false);
          }
        }, 3000);
      } else {
        setSyncing(false);
        setError('Sync failed');
      }
    } catch {
      setSyncing(false);
      setError('Sync failed');
    }
  };

  // Filtered & sorted items
  const displayedItems = useMemo(() => {
    let list = [...items];
    if (sortDesc) {
      list.sort((a, b) => new Date(b.last_checked || 0).getTime() - new Date(a.last_checked || 0).getTime());
    } else {
      list.sort((a, b) => new Date(a.last_checked || 0).getTime() - new Date(b.last_checked || 0).getTime());
    }
    return list;
  }, [items, sortDesc]);

  const paginatedItems = displayedItems.slice(page * pageSize, (page + 1) * pageSize);
  const totalPages = Math.ceil(displayedItems.length / pageSize);

  // ─── Loading State ───
  if (loading && !items.length && !summary) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center">
          <div className="w-10 h-10 rounded-2xl bg-[#0f0f12] border border-white/[0.06] flex items-center justify-center mx-auto mb-4">
            <Loader2 className="w-5 h-5 text-[#7c6cf9] animate-spin" />
          </div>
          <p className="text-[#52525b] text-sm">Loading index status...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ─── Header ─── */}
      <motion.div variants={fadeUp} initial="hidden" animate="visible" className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#7c6cf9]/10 border border-[#7c6cf9]/20 flex items-center justify-center">
              <Search className="w-5 h-5 text-[#7c6cf9]" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-[#f5f5f7] tracking-tight">Index Status Tracker</h2>
              <p className="text-[#52525b] text-xs">Monitor which pages are indexed in Google</p>
            </div>
          </div>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="btn-premium disabled:opacity-50"
        >
          {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {syncing ? 'Syncing...' : 'Sync Index Status'}
        </button>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial="hidden" animate="visible" className="bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
          <p className="text-red-400 text-sm flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> {error}</p>
        </motion.div>
      )}

      {/* ─── Summary Cards ─── */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {[
            { label: 'Total URLs', value: summary.total_urls, icon: Globe, color: 'text-[#7c6cf9]', bg: 'bg-[#7c6cf9]/10', border: 'border-[#7c6cf9]/20' },
            { label: 'Indexed', value: summary.indexed, icon: CheckCircle, color: 'text-[#4ade80]', bg: 'bg-[#4ade80]/10', border: 'border-[#4ade80]/20' },
            { label: 'Not Indexed', value: summary.not_indexed, icon: XCircle, color: 'text-[#f87171]', bg: 'bg-[#f87171]/10', border: 'border-[#f87171]/20' },
            { label: 'Checked 24h', value: summary.checked_last_24h, icon: Clock, color: 'text-[#60a5fa]', bg: 'bg-[#60a5fa]/10', border: 'border-[#60a5fa]/20' },
          ].map((s, i) => (
            <motion.div key={s.label} custom={i} variants={cardVariants} initial="hidden" animate="visible"
              className={`${s.bg} border ${s.border} rounded-xl p-4`}>
              <div className="flex items-center gap-2 mb-2">
                <s.icon className={`w-4 h-4 ${s.color}`} />
                <span className="text-[#52525b] text-[10px] uppercase tracking-wider font-medium">{s.label}</span>
              </div>
              <p className={`text-2xl font-bold tracking-tight ${s.color}`}>{s.value.toLocaleString()}</p>
            </motion.div>
          ))}
          {/* Index Rate Gauge */}
          <motion.div custom={4} variants={cardVariants} initial="hidden" animate="visible"
            className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4 flex items-center justify-center">
            <CircularGauge percentage={summary.index_rate} size={80} strokeWidth={7} label="Index Rate" />
          </motion.div>
        </div>
      )}

      {/* ─── Trend Chart ─── */}
      <motion.div custom={5} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-[#4ade80]" />
            <h3 className="text-[#f5f5f7] font-semibold text-sm">Index Trends (Last 30 Days)</h3>
          </div>
          {trends && trends.trends.length > 0 && (
            <span className="text-[10px] text-[#52525b]">
              Latest: {trends.trends[trends.trends.length - 1]?.indexed || 0} indexed / {trends.trends[trends.trends.length - 1]?.total || 0} total
            </span>
          )}
        </div>
        <TrendChart data={trends?.trends || []} />
      </motion.div>

      {/* ─── URLs Table ─── */}
      <motion.div custom={6} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-[#7c6cf9]" />
            <h3 className="text-[#f5f5f7] font-semibold text-sm">URL Index Status</h3>
            <span className="text-[10px] text-[#52525b] ml-2">{displayedItems.length} URLs</span>
          </div>
          <div className="flex items-center gap-2">
            {/* Filter buttons */}
            <div className="flex items-center bg-white/[0.03] rounded-lg border border-white/[0.06] overflow-hidden">
              <button
                onClick={() => { setFilterIndexed(null); setPage(0); }}
                className={`px-3 py-1.5 text-[11px] font-medium transition-all ${filterIndexed === null ? 'bg-[#7c6cf9]/20 text-[#7c6cf9]' : 'text-[#52525b] hover:text-[#a1a1aa]'}`}
              >
                All
              </button>
              <button
                onClick={() => { setFilterIndexed(true); setPage(0); }}
                className={`px-3 py-1.5 text-[11px] font-medium transition-all ${filterIndexed === true ? 'bg-[#4ade80]/20 text-[#4ade80]' : 'text-[#52525b] hover:text-[#a1a1aa]'}`}
              >
                Indexed
              </button>
              <button
                onClick={() => { setFilterIndexed(false); setPage(0); }}
                className={`px-3 py-1.5 text-[11px] font-medium transition-all ${filterIndexed === false ? 'bg-[#f87171]/20 text-[#f87171]' : 'text-[#52525b] hover:text-[#a1a1aa]'}`}
              >
                Not Indexed
              </button>
            </div>
            <button
              onClick={() => setSortDesc(!sortDesc)}
              className="flex items-center gap-1 px-2 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-[11px] text-[#52525b] hover:text-[#a1a1aa] transition-all"
            >
              <Clock className="w-3 h-3" />
              {sortDesc ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/[0.06]">
                <th className="text-left text-[10px] text-[#52525b] uppercase tracking-wider font-medium py-2 px-3">URL</th>
                <th className="text-left text-[10px] text-[#52525b] uppercase tracking-wider font-medium py-2 px-3 w-28">Status</th>
                <th className="text-left text-[10px] text-[#52525b] uppercase tracking-wider font-medium py-2 px-3 w-36">Last Checked</th>
                <th className="text-left text-[10px] text-[#52525b] uppercase tracking-wider font-medium py-2 px-3 w-32">Method</th>
                <th className="text-right text-[10px] text-[#52525b] uppercase tracking-wider font-medium py-2 px-3 w-10"></th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence>
                {paginatedItems.map((item, i) => (
                  <motion.tr
                    key={item.id}
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.015, duration: 0.2 }}
                    className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="py-2.5 px-3">
                      <p className="text-xs text-[#a1a1aa] truncate max-w-[280px] md:max-w-[400px]" title={item.url}>
                        {item.url}
                      </p>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ${
                        item.is_indexed
                          ? 'bg-[#4ade80]/10 text-[#4ade80] border border-[#4ade80]/20'
                          : 'bg-[#f87171]/10 text-[#f87171] border border-[#f87171]/20'
                      }`}>
                        {item.is_indexed ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                        {item.is_indexed ? 'Indexed' : 'Not Indexed'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="text-[11px] text-[#52525b]">
                        {item.last_checked ? new Date(item.last_checked).toLocaleDateString() : '—'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                        item.check_method === 'gsc_url_inspection'
                          ? 'bg-[#7c6cf9]/10 text-[#7c6cf9]'
                          : 'bg-[#fbbf24]/10 text-[#fbbf24]'
                      }`}>
                        {item.check_method === 'gsc_url_inspection' ? 'GSC API' : 'Search'}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#52525b] hover:text-[#7c6cf9] transition-colors"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>

        {/* Empty state */}
        {paginatedItems.length === 0 && (
          <div className="text-center py-12">
            <Search className="w-8 h-8 text-[#52525b] mx-auto mb-3" />
            <p className="text-[#52525b] text-sm">No URLs found</p>
            <p className="text-[#52525b] text-xs mt-1">Click "Sync Index Status" to start tracking</p>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/[0.06]">
            <span className="text-[10px] text-[#52525b]">
              Page {page + 1} of {totalPages}
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-[11px] text-[#a1a1aa] hover:text-[#f5f5f7] disabled:opacity-30 transition-all"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-[11px] text-[#a1a1aa] hover:text-[#f5f5f7] disabled:opacity-30 transition-all"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
