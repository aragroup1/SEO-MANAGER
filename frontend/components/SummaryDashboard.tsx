// frontend/components/SummaryDashboard.tsx — Unified Single-Page Summary with Sexy Charts
'use client';

import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity, TrendingUp, TrendingDown, Minus, Search, MousePointerClick,
  Eye, AlertTriangle, CheckCircle, Loader2, Zap, Bot, Globe, BarChart3,
  ChevronRight, Shield, Trophy, Target, FileText, Brain, Wand2,
  Sparkles, ArrowUp, ArrowDown, Clock, Layers, Star, MessageSquare,
  Link2, RefreshCw, ExternalLink, Lock, Unlock, Users
} from 'lucide-react';

// ─── Types ───
interface WebsiteInfo {
  id: number; domain: string; site_type: string; autonomy_mode: string; created_at: string;
}

interface AuditLatest {
  health_score: number | null; technical_score: number | null; content_score: number | null;
  performance_score: number | null; mobile_score: number | null; security_score: number | null;
  total_issues: number; critical_issues: number; errors: number; warnings: number;
  audit_date: string | null; score_change: number;
}

interface AuditHistoryPoint {
  date: string; health_score: number; technical_score: number; content_score: number;
  performance_score: number; total_issues: number;
}

interface KeywordLatest {
  total_keywords: number; total_clicks: number; total_impressions: number;
  avg_position: number; avg_ctr: number; snapshot_date: string | null;
}

interface KeywordHistoryPoint {
  date: string; total_keywords: number; total_clicks: number;
  total_impressions: number; avg_position: number;
}

interface TrackedKW {
  id: number; keyword: string; current_position: number | null;
  target_position: number; status: string; current_clicks: number; current_impressions: number;
}

interface FixSummary {
  pending: number; approved: number; applied: number; auto_approved: number; auto_applied: number;
}

interface StrategistSummary {
  has_strategy: boolean; has_weekly: boolean; has_portfolio: boolean;
  has_linking: boolean; has_decay: boolean;
  strategy_generated_at: string | null; weekly_generated_at: string | null;
}

interface GeoSummary {
  has_audit: boolean; overall_score: number | null; pages_analyzed: number | null; audit_date: string | null;
}

interface ContentItem {
  id: number; title: string; content_type: string; status: string;
}

interface FullSummary {
  website: WebsiteInfo;
  audit: { latest: AuditLatest; history: AuditHistoryPoint[] };
  keywords: { latest: KeywordLatest; history: KeywordHistoryPoint[]; tracked: TrackedKW[]; tracked_count: number };
  fixes: FixSummary;
  strategist: StrategistSummary;
  geo: GeoSummary;
  content: { recent_count: number; recent: ContentItem[] };
}

// ─── Animation Variants ───
const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.06, duration: 0.5, ease: [0.32, 0.72, 0, 1] }
  })
};

const fadeUp = { hidden: { opacity: 0, y: 16 }, visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.32, 0.72, 0, 1] } } };

// ─── Color Helpers ───
const scoreColor = (s: number | null) => !s ? 'text-[#52525b]' : s >= 70 ? 'text-[#4ade80]' : s >= 50 ? 'text-[#fbbf24]' : 'text-[#f87171]';
const scoreBg = (s: number | null) => !s ? 'bg-[#1a1a1e]' : s >= 70 ? 'bg-[#4ade80]/10' : s >= 50 ? 'bg-[#fbbf24]/10' : 'bg-[#f87171]/10';
const scoreBorder = (s: number | null) => !s ? 'border-[#52525b]/20' : s >= 70 ? 'border-[#4ade80]/20' : s >= 50 ? 'border-[#fbbf24]/20' : 'border-[#f87171]/20';
const changeIcon = (v: number) => v > 0 ? <TrendingUp className="w-3 h-3 text-[#4ade80]" /> : v < 0 ? <TrendingDown className="w-3 h-3 text-[#f87171]" /> : <Minus className="w-3 h-3 text-[#52525b]" />;
const changeColor = (v: number) => v > 0 ? 'text-[#4ade80]' : v < 0 ? 'text-[#f87171]' : 'text-[#52525b]';
const changeStr = (v: number) => v > 0 ? `+${v}` : String(v);

// ─── Mini Sparkline Chart (SVG) ───
function Sparkline({ data, metric, color = '#7c6cf9', height = 60, fill = false }: {
  data: { date: string; value: number }[]; metric: string; color?: string; height?: number; fill?: boolean;
}) {
  if (!data.length) return <div className="h-[60px] flex items-center justify-center"><span className="text-[#52525b] text-[10px]">No data</span></div>;

  const values = data.map(d => d.value);
  const maxVal = Math.max(...values, 1);
  const minVal = Math.min(...values, 0);
  const range = maxVal - minVal || 1;
  const w = 300, h = height, pad = 10;

  const points = data.map((d, i) => {
    const x = pad + (i / (data.length - 1 || 1)) * (w - pad * 2);
    const y = pad + (1 - (d.value - minVal) / range) * (h - pad * 2);
    return `${x},${y}`;
  }).join(' ');

  const fillPath = fill ? `${points} ${pad + w - pad * 2},${h} ${pad},${h}` : '';

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" preserveAspectRatio="none" style={{ height }}>
      {fill && <polygon points={fillPath} fill={`${color}15`} />}
      <polyline fill="none" stroke={color} strokeWidth="2" points={points} strokeLinecap="round" strokeLinejoin="round" />
      {/* Dots at each point */}
      {data.map((d, i) => {
        const x = pad + (i / (data.length - 1 || 1)) * (w - pad * 2);
        const y = pad + (1 - (d.value - minVal) / range) * (h - pad * 2);
        return <circle key={i} cx={x} cy={y} r="2.5" fill={color} />;
      })}
    </svg>
  );
}

// ─── Score Gauge (SVG Arc) ───
function ScoreGauge({ score, size = 80, strokeWidth = 8, label }: { score: number | null; size?: number; strokeWidth?: number; label?: string }) {
  if (score === null) {
    return (
      <div className="flex flex-col items-center">
        <div className="text-[#52525b] text-2xl font-bold">--</div>
        {label && <span className="text-[#52525b] text-[10px] mt-1">{label}</span>}
      </div>
    );
  }
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const arc = circumference * 0.75;
  const offset = arc - (score / 100) * arc;
  const color = score >= 70 ? '#4ade80' : score >= 50 ? '#fbbf24' : '#f87171';

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke="#1a1a1e" strokeWidth={strokeWidth} strokeDasharray={`${arc} ${circumference}`} strokeLinecap="round" transform={`rotate(135 ${size/2} ${size/2})`} />
        <circle cx={size/2} cy={size/2} r={radius} fill="none" stroke={color} strokeWidth={strokeWidth} strokeDasharray={`${arc} ${circumference}`} strokeDashoffset={offset} strokeLinecap="round" transform={`rotate(135 ${size/2} ${size/2})`} style={{ transition: 'stroke-dashoffset 1s ease-out' }} />
        <text x={size/2} y={size/2 + 4} textAnchor="middle" fill="#f5f5f7" fontSize="16" fontWeight="bold">{Math.round(score)}</text>
      </svg>
      {label && <span className="text-[#52525b] text-[10px] mt-1">{label}</span>}
    </div>
  );
}

// ─── Bar Distribution Chart ───
function BarDistribution({ data, colors }: { data: { label: string; value: number; color: string }[]; colors?: string[] }) {
  const maxVal = Math.max(...data.map(d => d.value), 1);
  return (
    <div className="space-y-2">
      {data.map((d, i) => (
        <div key={d.label} className="flex items-center gap-2">
          <span className="text-[10px] text-[#52525b] w-12 text-right shrink-0">{d.label}</span>
          <div className="flex-1 h-2 bg-white/[0.04] rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${(d.value / maxVal) * 100}%` }}
              transition={{ duration: 0.8, delay: i * 0.05, ease: [0.32, 0.72, 0, 1] }}
              className="h-full rounded-full"
              style={{ backgroundColor: d.color }}
            />
          </div>
          <span className="text-[10px] text-[#a1a1aa] w-6 text-right shrink-0">{d.value}</span>
        </div>
      ))}
    </div>
  );
}

// ─── Main Component ───
export default function SummaryDashboard({ websiteId, onNavigate }: { websiteId: number; onNavigate?: (tab: string) => void }) {
  const [data, setData] = useState<FullSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchSummary = async () => {
    try {
      const r = await fetch(`${API_URL}/api/websites/${websiteId}/full-summary`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setData(d);
      setError('');
    } catch (e) {
      setError('Failed to load summary');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    setData(null);
    fetchSummary();
  }, [websiteId, API_URL]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchSummary();
  };

  // ─── Derived Data ───
  const healthHistory = useMemo(() => {
    if (!data?.audit?.history?.length) return [];
    return data.audit.history.map(h => ({ date: h.date.slice(5, 10), value: h.health_score }));
  }, [data?.audit?.history]);

  const issueHistory = useMemo(() => {
    if (!data?.audit?.history?.length) return [];
    return data.audit.history.map(h => ({ date: h.date.slice(5, 10), value: h.total_issues }));
  }, [data?.audit?.history]);

  const keywordHistory = useMemo(() => {
    if (!data?.keywords?.history?.length) return [];
    return data.keywords.history.map(h => ({ date: h.date.slice(5, 10), value: h.total_keywords }));
  }, [data?.keywords?.history]);

  const clicksHistory = useMemo(() => {
    if (!data?.keywords?.history?.length) return [];
    return data.keywords.history.map(h => ({ date: h.date.slice(5, 10), value: h.total_clicks }));
  }, [data?.keywords?.history]);

  const positionHistory = useMemo(() => {
    if (!data?.keywords?.history?.length) return [];
    return data.keywords.history.map(h => ({ date: h.date.slice(5, 10), value: h.avg_position }));
  }, [data?.keywords?.history]);

  // ─── Loading State ───
  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center">
          <div className="w-10 h-10 rounded-2xl bg-[#0f0f12] border border-white/[0.06] flex items-center justify-center mx-auto mb-4">
            <Loader2 className="w-5 h-5 text-[#7c6cf9] animate-spin" />
          </div>
          <p className="text-[#52525b] text-sm">Loading summary...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="card-liquid p-8 text-center">
          <AlertTriangle className="w-10 h-10 text-[#f87171] mx-auto mb-3" />
          <p className="text-[#f5f5f7] font-medium">{error || 'No data available'}</p>
          <button onClick={handleRefresh} className="btn-premium mt-4">
            <RefreshCw className="w-4 h-4" /> Retry
          </button>
        </div>
      </div>
    );
  }

  const { website, audit, keywords, fixes, strategist, geo, content } = data;
  const latest = audit.latest;

  // Issue breakdown
  const issueBreakdown = [
    { label: 'Critical', value: latest.critical_issues, color: '#f87171' },
    { label: 'Errors', value: latest.errors, color: '#fbbf24' },
    { label: 'Warnings', value: latest.warnings, color: '#60a5fa' },
  ].filter(i => i.value > 0);

  // Sub-score gauges
  const subScores = [
    { label: 'Technical', score: latest.technical_score },
    { label: 'Content', score: latest.content_score },
    { label: 'Performance', score: latest.performance_score },
    { label: 'Mobile', score: latest.mobile_score },
    { label: 'Security', score: latest.security_score },
  ].filter(s => s.score !== null);

  return (
    <div className="space-y-6">
      {/* ─── Header ─── */}
      <motion.div variants={fadeUp} initial="hidden" animate="visible" className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-[#f5f5f7] tracking-tight">{website.domain}</h2>
            <span className="eyebrow bg-white/[0.04] text-[#52525b] border border-white/[0.06]">{website.site_type}</span>
            {website.autonomy_mode !== 'manual' && (
              <span className={`eyebrow border ${website.autonomy_mode === 'ultra' ? 'bg-[#4ade80]/10 text-[#4ade80] border-[#4ade80]/20' : 'bg-[#7c6cf9]/10 text-[#7c6cf9] border-[#7c6cf9]/20'}`}>
                {website.autonomy_mode === 'ultra' ? 'Ultra Mode' : 'Smart Mode'}
              </span>
            )}
          </div>
          <p className="text-[#52525b] text-sm mt-1">
            {latest.audit_date ? `Last audit: ${new Date(latest.audit_date).toLocaleDateString()}` : 'No audit yet'}
            {keywords.latest.snapshot_date && ` · Keywords: ${new Date(keywords.latest.snapshot_date).toLocaleDateString()}`}
          </p>
        </div>
        <button onClick={handleRefresh} disabled={refreshing} className="btn-premium disabled:opacity-50">
          {refreshing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </motion.div>

      {/* ─── Top Stats Row ─── */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {[
          { icon: Activity, label: 'Health Score', value: latest.health_score !== null ? `${Math.round(latest.health_score)}` : '--', color: latest.health_score ? (latest.health_score >= 70 ? 'text-[#4ade80]' : latest.health_score >= 50 ? 'text-[#fbbf24]' : 'text-[#f87171]') : 'text-[#52525b]', change: latest.score_change },
          { icon: Search, label: 'Keywords', value: keywords.latest.total_keywords.toLocaleString(), color: 'text-[#7c6cf9]' },
          { icon: MousePointerClick, label: 'Clicks', value: keywords.latest.total_clicks.toLocaleString(), color: 'text-[#60a5fa]' },
          { icon: Eye, label: 'Impressions', value: keywords.latest.total_impressions.toLocaleString(), color: 'text-[#a78bfa]' },
          { icon: AlertTriangle, label: 'Issues', value: String(latest.total_issues), color: latest.total_issues > 0 ? 'text-[#fbbf24]' : 'text-[#4ade80]' },
          { icon: Target, label: 'Avg Position', value: keywords.latest.avg_position ? `#${keywords.latest.avg_position.toFixed(1)}` : '--', color: 'text-[#4ade80]' },
        ].map((s, i) => (
          <motion.div key={s.label} custom={i} variants={cardVariants} initial="hidden" animate="visible"
            className="card-liquid p-4">
            <div className="flex items-center gap-2 mb-2">
              <s.icon className={`w-4 h-4 ${s.color}`} />
              <span className="text-[#52525b] text-[10px] uppercase tracking-wider font-medium">{s.label}</span>
            </div>
            <p className={`text-2xl font-bold tracking-tight ${s.color}`}>{s.value}</p>
            {s.change !== undefined && s.change !== 0 && (
              <div className={`flex items-center gap-1 mt-1 text-[10px] ${changeColor(s.change)}`}>
                {changeIcon(s.change)}
                <span>{changeStr(s.change)} pts</span>
              </div>
            )}
          </motion.div>
        ))}
      </div>

      {/* ─── Main Grid: Charts + Details ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Health & Issues */}
        <div className="lg:col-span-2 space-y-6">
          {/* Health Score Trend */}
          <motion.div custom={0} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-[#4ade80]" />
                <h3 className="text-[#f5f5f7] font-semibold text-sm">Health Score Trend</h3>
              </div>
              {latest.score_change !== 0 && (
                <span className={`text-[10px] px-2 py-0.5 rounded-full border ${latest.score_change > 0 ? 'bg-[#4ade80]/10 text-[#4ade80] border-[#4ade80]/20' : 'bg-[#f87171]/10 text-[#f87171] border-[#f87171]/20'}`}>
                  {latest.score_change > 0 ? '+' : ''}{latest.score_change} pts
                </span>
              )}
            </div>
            {healthHistory.length > 1 ? (
              <Sparkline data={healthHistory} metric="health" color="#4ade80" height={80} fill />
            ) : (
              <div className="h-[80px] flex items-center justify-center">
                <p className="text-[#52525b] text-xs">Run at least 2 audits to see trends</p>
              </div>
            )}
          </motion.div>

          {/* Keyword Trends */}
          <motion.div custom={1} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-[#7c6cf9]" />
                <h3 className="text-[#f5f5f7] font-semibold text-sm">Keyword Performance</h3>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-[10px] text-[#52525b] uppercase tracking-wider mb-2">Keywords Ranking</p>
                {keywordHistory.length > 1 ? (
                  <Sparkline data={keywordHistory} metric="keywords" color="#7c6cf9" height={60} fill />
                ) : <p className="text-[#52525b] text-xs">No history</p>}
              </div>
              <div>
                <p className="text-[10px] text-[#52525b] uppercase tracking-wider mb-2">Total Clicks</p>
                {clicksHistory.length > 1 ? (
                  <Sparkline data={clicksHistory} metric="clicks" color="#60a5fa" height={60} fill />
                ) : <p className="text-[#52525b] text-xs">No history</p>}
              </div>
            </div>
            <div className="mt-4">
              <p className="text-[10px] text-[#52525b] uppercase tracking-wider mb-2">Avg Position (↑ = better)</p>
              {positionHistory.length > 1 ? (
                <Sparkline data={positionHistory} metric="position" color="#fbbf24" height={50} />
              ) : <p className="text-[#52525b] text-xs">No history</p>}
            </div>
          </motion.div>

          {/* Issues Breakdown + Issue Trend */}
          <motion.div custom={2} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[#fbbf24]" />
                <h3 className="text-[#f5f5f7] font-semibold text-sm">Issues Breakdown</h3>
              </div>
              <button onClick={() => onNavigate?.('issues')} className="text-[10px] text-[#7c6cf9] hover:text-[#f5f5f7] transition-colors flex items-center gap-1">
                View All <ChevronRight className="w-3 h-3" />
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <BarDistribution data={issueBreakdown.length ? issueBreakdown : [{ label: 'None', value: 0, color: '#4ade80' }]} />
              <div>
                <p className="text-[10px] text-[#52525b] uppercase tracking-wider mb-2">Issue Trend</p>
                {issueHistory.length > 1 ? (
                  <Sparkline data={issueHistory} metric="issues" color="#f87171" height={60} />
                ) : <p className="text-[#52525b] text-xs">No history</p>}
              </div>
            </div>
          </motion.div>

          {/* Fixes & Automation */}
          <motion.div custom={3} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Wand2 className="w-4 h-4 text-[#7c6cf9]" />
                <h3 className="text-[#f5f5f7] font-semibold text-sm">Fixes & Automation</h3>
              </div>
              <button onClick={() => onNavigate?.('issues')} className="text-[10px] text-[#7c6cf9] hover:text-[#f5f5f7] transition-colors flex items-center gap-1">
                Queue <ChevronRight className="w-3 h-3" />
              </button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {[
                { label: 'Pending', value: fixes.pending, color: 'text-[#fbbf24]', bg: 'bg-[#fbbf24]/10', border: 'border-[#fbbf24]/20' },
                { label: 'Approved', value: fixes.approved, color: 'text-[#60a5fa]', bg: 'bg-[#60a5fa]/10', border: 'border-[#60a5fa]/20' },
                { label: 'Applied', value: fixes.applied, color: 'text-[#4ade80]', bg: 'bg-[#4ade80]/10', border: 'border-[#4ade80]/20' },
                { label: 'Auto-Approved', value: fixes.auto_approved, color: 'text-[#a78bfa]', bg: 'bg-[#a78bfa]/10', border: 'border-[#a78bfa]/20' },
                { label: 'Auto-Applied', value: fixes.auto_applied, color: 'text-[#06b6d4]', bg: 'bg-[#06b6d4]/10', border: 'border-[#06b6d4]/20' },
              ].map(f => (
                <div key={f.label} className={`${f.bg} border ${f.border} rounded-xl p-3 text-center`}>
                  <p className={`text-xl font-bold ${f.color}`}>{f.value}</p>
                  <p className="text-[10px] text-[#52525b] mt-0.5">{f.label}</p>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Right Column: Status Cards */}
        <div className="space-y-6">
          {/* Health Score Gauge */}
          <motion.div custom={4} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
            <h3 className="text-[#f5f5f7] font-semibold text-sm mb-4">Overall Health</h3>
            <div className="flex justify-center">
              <ScoreGauge score={latest.health_score} size={120} strokeWidth={10} />
            </div>
            {subScores.length > 0 && (
              <div className="grid grid-cols-3 gap-3 mt-4">
                {subScores.map(s => (
                  <ScoreGauge key={s.label} score={s.score} size={60} strokeWidth={5} label={s.label} />
                ))}
              </div>
            )}
          </motion.div>

          {/* Road to #1 Progress */}
          <motion.div custom={5} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Trophy className="w-4 h-4 text-[#fbbf24]" />
                <h3 className="text-[#f5f5f7] font-semibold text-sm">Road to #1</h3>
              </div>
              <span className="text-[10px] text-[#52525b]">{keywords.tracked_count} tracked</span>
            </div>
            {keywords.tracked.length > 0 ? (
              <div className="space-y-3">
                {keywords.tracked.slice(0, 5).map((tk, i) => {
                  const progress = tk.current_position ? Math.max(0, 100 - (tk.current_position - 1) * 2) : 0;
                  return (
                    <div key={tk.id}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-[#a1a1aa] truncate flex-1">{tk.keyword}</span>
                        <span className={`text-xs font-bold ml-2 ${tk.current_position && tk.current_position <= 10 ? 'text-[#4ade80]' : 'text-[#fbbf24]'}`}>
                          {tk.current_position ? `#${Math.round(tk.current_position)}` : 'N/R'}
                        </span>
                      </div>
                      <div className="h-1.5 bg-white/[0.04] rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${progress}%` }}
                          transition={{ duration: 0.8, delay: i * 0.1 }}
                          className={`h-full rounded-full ${progress >= 80 ? 'bg-[#4ade80]' : progress >= 50 ? 'bg-[#fbbf24]' : 'bg-[#f87171]'}`}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-center py-4">
                <p className="text-[#52525b] text-xs">No tracked keywords yet</p>
                <button onClick={() => onNavigate?.('keywords')} className="text-[10px] text-[#7c6cf9] mt-2 hover:underline">
                  Go to Keywords to track
                </button>
              </div>
            )}
            <button onClick={() => onNavigate?.('road-to-one')} className="w-full mt-4 text-[10px] text-[#7c6cf9] hover:text-[#f5f5f7] transition-colors flex items-center justify-center gap-1 py-2 rounded-lg hover:bg-white/[0.03]">
              View Road to #1 <ChevronRight className="w-3 h-3" />
            </button>
          </motion.div>

          {/* GEO Score */}
          <motion.div custom={6} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Brain className="w-4 h-4 text-[#a78bfa]" />
                <h3 className="text-[#f5f5f7] font-semibold text-sm">AI Search (GEO)</h3>
              </div>
            </div>
            {geo.has_audit ? (
              <div className="text-center">
                <ScoreGauge score={geo.overall_score} size={100} strokeWidth={8} />
                <p className="text-[10px] text-[#52525b] mt-2">{geo.pages_analyzed} pages analyzed</p>
                {geo.audit_date && <p className="text-[10px] text-[#52525b]">{new Date(geo.audit_date).toLocaleDateString()}</p>}
              </div>
            ) : (
              <div className="text-center py-4">
                <p className="text-[#52525b] text-xs">No GEO audit yet</p>
              </div>
            )}
            <button onClick={() => onNavigate?.('ai-search')} className="w-full mt-3 text-[10px] text-[#7c6cf9] hover:text-[#f5f5f7] transition-colors flex items-center justify-center gap-1 py-2 rounded-lg hover:bg-white/[0.03]">
              Run GEO Audit <ChevronRight className="w-3 h-3" />
            </button>
          </motion.div>

          {/* AI Strategist Status */}
          <motion.div custom={7} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-[#7c6cf9]" />
                <h3 className="text-[#f5f5f7] font-semibold text-sm">AI Strategist</h3>
              </div>
            </div>
            <div className="space-y-2">
              {[
                { label: 'Master Strategy', has: strategist.has_strategy, date: strategist.strategy_generated_at },
                { label: 'Weekly Plan', has: strategist.has_weekly, date: strategist.weekly_generated_at },
                { label: 'Portfolio', has: strategist.has_portfolio },
                { label: 'Linking Analysis', has: strategist.has_linking },
                { label: 'Decay Detection', has: strategist.has_decay },
              ].map(item => (
                <div key={item.label} className="flex items-center justify-between py-1.5">
                  <span className="text-xs text-[#a1a1aa]">{item.label}</span>
                  <div className="flex items-center gap-2">
                    {item.date && <span className="text-[10px] text-[#52525b]">{new Date(item.date).toLocaleDateString()}</span>}
                    {item.has ? (
                      <CheckCircle className="w-3.5 h-3.5 text-[#4ade80]" />
                    ) : (
                      <Clock className="w-3.5 h-3.5 text-[#52525b]" />
                    )}
                  </div>
                </div>
              ))}
            </div>
            <button onClick={() => onNavigate?.('strategist')} className="w-full mt-3 text-[10px] text-[#7c6cf9] hover:text-[#f5f5f7] transition-colors flex items-center justify-center gap-1 py-2 rounded-lg hover:bg-white/[0.03]">
              Open Strategist <ChevronRight className="w-3 h-3" />
            </button>
          </motion.div>

          {/* Recent Content */}
          <motion.div custom={8} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-[#60a5fa]" />
                <h3 className="text-[#f5f5f7] font-semibold text-sm">Recent Content</h3>
              </div>
              <span className="text-[10px] text-[#52525b]">{content.recent_count} items</span>
            </div>
            {content.recent.length > 0 ? (
              <div className="space-y-2">
                {content.recent.map(c => (
                  <div key={c.id} className="flex items-center justify-between py-1.5 border-b border-white/[0.04] last:border-0">
                    <div className="min-w-0">
                      <p className="text-xs text-[#a1a1aa] truncate">{c.title}</p>
                      <p className="text-[10px] text-[#52525b]">{c.content_type}</p>
                    </div>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${c.status === 'Published' ? 'bg-[#4ade80]/10 text-[#4ade80]' : 'bg-[#fbbf24]/10 text-[#fbbf24]'}`}>
                      {c.status}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[#52525b] text-xs text-center py-2">No content yet</p>
            )}
            <button onClick={() => onNavigate?.('content')} className="w-full mt-3 text-[10px] text-[#7c6cf9] hover:text-[#f5f5f7] transition-colors flex items-center justify-center gap-1 py-2 rounded-lg hover:bg-white/[0.03]">
              Content Writer <ChevronRight className="w-3 h-3" />
            </button>
          </motion.div>

          {/* Quick Actions */}
          <motion.div custom={9} variants={cardVariants} initial="hidden" animate="visible" className="card-liquid p-5">
            <h3 className="text-[#f5f5f7] font-semibold text-sm mb-4">Quick Actions</h3>
            <div className="space-y-2">
              {[
                { label: 'Run Site Audit', tab: 'audit', icon: Activity },
                { label: 'Sync Keywords', tab: 'keywords', icon: Search },
                { label: 'Check Competitors', tab: 'competitors', icon: Users },
                { label: 'View Reports', tab: 'reports', icon: BarChart3 },
              ].map(action => (
                <button
                  key={action.tab}
                  onClick={() => onNavigate?.(action.tab)}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-[#a1a1aa] hover:bg-white/[0.03] hover:text-[#f5f5f7] transition-all"
                >
                  <action.icon className="w-3.5 h-3.5" />
                  <span className="flex-1 text-left">{action.label}</span>
                  <ChevronRight className="w-3 h-3 text-[#52525b]" />
                </button>
              ))}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
