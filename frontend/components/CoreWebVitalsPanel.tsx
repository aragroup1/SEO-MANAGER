// frontend/components/CoreWebVitalsPanel.tsx — Core Web Vitals Monitoring Dashboard
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Gauge, Activity, Clock, Zap, Monitor, Smartphone, RefreshCw, AlertTriangle, CheckCircle, Loader2 } from 'lucide-react';

interface CWVData {
  lcp: number | null; lcp_status: string;
  inp: number | null; inp_status: string;
  cls: number | null; cls_status: string;
  fcp: number | null; fcp_status: string;
  ttfb: number | null; ttfb_status: string;
  checked_at: string | null;
}

interface CWVHistoryPoint {
  date: string; lcp: number | null; inp: number | null; cls: number | null;
  fcp: number | null; ttfb: number | null;
}

interface Props { websiteId: number; }

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

const statusColor = (s: string) => {
  if (s === 'good') return 'text-[#4ade80]';
  if (s === 'needs_improvement') return 'text-[#fbbf24]';
  if (s === 'poor') return 'text-[#f87171]';
  return 'text-[#52525b]';
};
const statusBg = (s: string) => {
  if (s === 'good') return 'bg-[#4ade80]/10 border-[#4ade80]/20';
  if (s === 'needs_improvement') return 'bg-[#fbbf24]/10 border-[#fbbf24]/20';
  if (s === 'poor') return 'bg-[#f87171]/10 border-[#f87171]/20';
  return 'bg-[#1a1a1e] border-white/[0.06]';
};
const statusLabel = (s: string) => {
  if (s === 'good') return 'Good';
  if (s === 'needs_improvement') return 'Needs Improvement';
  if (s === 'poor') return 'Poor';
  return 'No Data';
};

function MetricCard({ label, value, status, unit, icon: Icon, threshold }: {
  label: string; value: number | null; status: string; unit: string;
  icon: any; threshold: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-2xl border p-5 ${statusBg(status)}`}
    >
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${status === 'good' ? 'bg-[#4ade80]/20' : status === 'needs_improvement' ? 'bg-[#fbbf24]/20' : 'bg-[#f87171]/20'}`}>
          <Icon className={`w-4 h-4 ${statusColor(status)}`} />
        </div>
        <div>
          <p className="text-[#f5f5f7] text-sm font-medium">{label}</p>
          <p className={`text-xs ${statusColor(status)}`}>{statusLabel(status)}</p>
        </div>
      </div>
      <p className={`text-3xl font-bold ${statusColor(status)}`}>
        {value !== null ? value : '—'}
        <span className="text-sm font-normal text-[#52525b] ml-1">{unit}</span>
      </p>
      <p className="text-[#52525b] text-xs mt-1">{threshold}</p>
    </motion.div>
  );
}

function TrendChart({ data, metric, color }: { data: CWVHistoryPoint[]; metric: keyof CWVHistoryPoint; color: string }) {
  if (!data.length) return <div className="h-[120px] flex items-center justify-center"><span className="text-[#52525b] text-xs">No history data</span></div>;
  const values = data.map(d => d[metric] as number).filter(v => v !== null);
  if (!values.length) return <div className="h-[120px] flex items-center justify-center"><span className="text-[#52525b] text-xs">No data points</span></div>;

  const maxVal = Math.max(...values, 0.001);
  const minVal = Math.min(...values, 0);
  const range = maxVal - minVal || 1;
  const width = 600;
  const height = 120;
  const padding = 10;

  const points = values.map((v, i) => {
    const x = padding + (i / (values.length - 1 || 1)) * (width - padding * 2);
    const y = height - padding - ((v - minVal) / range) * (height - padding * 2);
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-[120px]">
      <polyline fill="none" stroke={color} strokeWidth="2" points={points} />
      {values.map((v, i) => {
        const x = padding + (i / (values.length - 1 || 1)) * (width - padding * 2);
        const y = height - padding - ((v - minVal) / range) * (height - padding * 2);
        return <circle key={i} cx={x} cy={y} r="3" fill={color} />;
      })}
    </svg>
  );
}

export default function CoreWebVitalsPanel({ websiteId }: Props) {
  const [activeDevice, setActiveDevice] = useState<'mobile' | 'desktop'>('mobile');
  const [latest, setLatest] = useState<CWVData | null>(null);
  const [history, setHistory] = useState<CWVHistoryPoint[]>([]);
  const [trends, setTrends] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [latestRes, historyRes, trendsRes] = await Promise.all([
        fetch(`${API_URL}/api/cwv/${websiteId}/latest`),
        fetch(`${API_URL}/api/cwv/${websiteId}/history?days=30&device=${activeDevice}`),
        fetch(`${API_URL}/api/cwv/${websiteId}/trends`),
      ]);
      if (latestRes.ok) setLatest((await latestRes.json())[activeDevice]);
      if (historyRes.ok) setHistory((await historyRes.json()).history);
      if (trendsRes.ok) setTrends(await trendsRes.json());
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const runCheck = async () => {
    setChecking(true);
    try {
      await fetch(`${API_URL}/api/cwv/${websiteId}/check`, { method: 'POST' });
      await fetchData();
    } catch (e) { console.error(e); }
    setChecking(false);
  };

  useEffect(() => { fetchData(); }, [websiteId, activeDevice]);

  const data = latest;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-[#f5f5f7]">Core Web Vitals</h2>
          <p className="text-[#52525b] text-sm mt-1">Google's page experience metrics — monitored continuously</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex bg-[#0f0f12] rounded-xl border border-white/[0.06] p-1">
            <button onClick={() => setActiveDevice('mobile')} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${activeDevice === 'mobile' ? 'bg-[#7c6cf9]/20 text-[#7c6cf9]' : 'text-[#52525b]'}`}>
              <Smartphone className="w-3.5 h-3.5" /> Mobile
            </button>
            <button onClick={() => setActiveDevice('desktop')} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${activeDevice === 'desktop' ? 'bg-[#7c6cf9]/20 text-[#7c6cf9]' : 'text-[#52525b]'}`}>
              <Monitor className="w-3.5 h-3.5" /> Desktop
            </button>
          </div>
          <button onClick={runCheck} disabled={checking} className="px-4 py-2 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors flex items-center gap-2 disabled:opacity-50">
            {checking ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            {checking ? 'Checking...' : 'Run Check'}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-[#7c6cf9] animate-spin" />
        </div>
      ) : !data ? (
        <div className="text-center py-16">
          <Gauge className="w-12 h-12 text-[#52525b] mx-auto mb-4" />
          <p className="text-[#f5f5f7] font-medium">No CWV data yet</p>
          <p className="text-[#52525b] text-sm mt-1">Run a check to get your Core Web Vitals scores</p>
          <button onClick={runCheck} className="mt-4 px-5 py-2 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors">
            Run First Check
          </button>
        </div>
      ) : (
        <>
          {/* Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
            <MetricCard label="LCP" value={data.lcp} status={data.lcp_status} unit="s" icon={Clock} threshold="< 2.5s good" />
            <MetricCard label="INP" value={data.inp} status={data.inp_status} unit="s" icon={Zap} threshold="< 200ms good" />
            <MetricCard label="CLS" value={data.cls} status={data.cls_status} unit="" icon={Activity} threshold="< 0.1 good" />
            <MetricCard label="FCP" value={data.fcp} status={data.fcp_status} unit="s" icon={Gauge} threshold="< 1.8s good" />
            <MetricCard label="TTFB" value={data.ttfb} status={data.ttfb_status} unit="s" icon={Clock} threshold="< 0.8s good" />
          </div>

          {/* Trend Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {[
              { label: 'LCP Trend', metric: 'lcp' as const, color: '#7c6cf9' },
              { label: 'CLS Trend', metric: 'cls' as const, color: '#4ade80' },
            ].map(chart => (
              <div key={chart.label} className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-5">
                <h3 className="text-[#f5f5f7] text-sm font-medium mb-3">{chart.label}</h3>
                <TrendChart data={history} metric={chart.metric} color={chart.color} />
              </div>
            ))}
          </div>

          {/* 7d / 30d Summary */}
          {trends && (
            <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-5">
              <h3 className="text-[#f5f5f7] text-sm font-medium mb-4">Trend Summary ({activeDevice})</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {['7d', '30d'].map(period => (
                  <div key={period} className="space-y-2">
                    <p className="text-[#52525b] text-xs uppercase tracking-wider">{period} Average</p>
                    {trends[activeDevice]?.[period] && (
                      <div className="space-y-1">
                        <p className="text-[#f5f5f7] text-sm">LCP: <span className="text-[#7c6cf9]">{trends[activeDevice][period].lcp ?? '—'}s</span></p>
                        <p className="text-[#f5f5f7] text-sm">CLS: <span className="text-[#4ade80]">{trends[activeDevice][period].cls ?? '—'}</span></p>
                        <p className="text-[#f5f5f7] text-sm">INP: <span className="text-[#fbbf24]">{trends[activeDevice][period].inp ? (trends[activeDevice][period].inp * 1000).toFixed(0) + 'ms' : '—'}</span></p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
