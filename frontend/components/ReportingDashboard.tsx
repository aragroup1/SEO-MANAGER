// frontend/components/ReportingDashboard.tsx
'use client';

import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import {
  FileText, Download, Loader2, RefreshCw, TrendingUp,
  TrendingDown, Minus, Target, Shield, Gauge, Globe,
  Search, Sparkles, CheckCircle, XCircle, AlertTriangle,
  Clock, Star, BarChart3, Eye, MousePointerClick, Activity,
  ArrowUp, ArrowDown, ArrowRight, ChevronRight, Calendar, Zap
} from 'lucide-react';

interface ReportData {
  domain: string; site_type: string; generated_at: string; report_month: string;
  audit: any; keywords: any; tracked_keywords: any[];
  fixes: Record<string, any>; audit_history: any[];
  keyword_history: any[]; ai_summary: string;
  since_inception: any; ga4_traffic: any;
  strategy: any; hub_and_spoke: any; content_decay: any;
}

// ─── Interactive SVG Chart Component ───
function Chart({ data, xKey, yKey, color = '#a855f7', label = '', height = 140, showDots = true }: {
  data: any[]; xKey: string; yKey: string; color?: string; label?: string; height?: number; showDots?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  if (!data.length) return null;

  const vals = data.map(d => Number(d[yKey]) || 0);
  const maxV = Math.max(...vals, 1);
  const minV = Math.min(...vals, 0);
  const range = maxV - minV || 1;
  const w = 700, h = height, pad = 35;

  const points = data.map((d, i) => ({
    x: pad + (i / (data.length - 1 || 1)) * (w - pad * 2),
    y: pad + (1 - (vals[i] - minV) / range) * (h - pad * 2),
    val: vals[i],
    label: d[xKey],
  }));

  const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
  const areaD = pathD + ` L${points[points.length-1].x},${h-pad} L${points[0].x},${h-pad} Z`;

  return (
    <div className="relative">
      {label && <p className="text-xs text-gray-400 mb-1">{label}</p>}
      <svg ref={svgRef} viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: `${height}px` }}
        onMouseLeave={() => setHover(null)}>
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map(pct => {
          const y = pad + pct * (h - pad * 2);
          const val = maxV - pct * range;
          return (
            <g key={pct}>
              <line x1={pad} y1={y} x2={w-pad} y2={y} stroke="rgba(255,255,255,0.05)" />
              <text x={pad-5} y={y+3} fill="#bbb" fontSize="9" textAnchor="end">{Math.round(val)}</text>
            </g>
          );
        })}

        {/* X labels */}
        {data.length <= 15 ? data.map((d, i) => (
          <text key={i} x={points[i].x} y={h-5} fill="#bbb" fontSize="8" textAnchor="middle">
            {String(d[xKey]).slice(-5)}
          </text>
        )) : [0, Math.floor(data.length/2), data.length-1].map(i => (
          <text key={i} x={points[i].x} y={h-5} fill="#bbb" fontSize="8" textAnchor="middle">
            {String(data[i][xKey]).slice(-5)}
          </text>
        ))}

        {/* Area fill */}
        <path d={areaD} fill={`${color}15`} />

        {/* Line */}
        <path d={pathD} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />

        {/* Hover zones + dots */}
        {points.map((p, i) => (
          <g key={i} onMouseEnter={() => setHover(i)}>
            <rect x={p.x - 15} y={0} width={30} height={h} fill="transparent" />
            {showDots && (
              <circle cx={p.x} cy={p.y} r={hover === i ? 5 : 3} fill={color}
                stroke={hover === i ? 'white' : 'transparent'} strokeWidth="2" />
            )}
          </g>
        ))}

        {/* Hover tooltip */}
        {hover !== null && (
          <g>
            <line x1={points[hover].x} y1={pad} x2={points[hover].x} y2={h-pad} stroke={color} strokeWidth="1" strokeDasharray="3,3" opacity="0.5" />
            <rect x={points[hover].x - 45} y={points[hover].y - 30} width={90} height={22} rx={6}
              fill="rgba(10,10,30,0.9)" stroke={color} strokeWidth="1" />
            <text x={points[hover].x} y={points[hover].y - 15} fill="white" fontSize="11" textAnchor="middle" fontWeight="bold">
              {points[hover].val.toLocaleString()}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}

// ─── Multi-Line Health Score Trend Chart ───
interface TrendLine {
  key: string;
  label: string;
  color: string;
}

const TREND_LINES: TrendLine[] = [
  { key: 'health_score', label: 'Health', color: '#7c6cf9' },
  { key: 'technical_score', label: 'Technical', color: '#4ade80' },
  { key: 'content_score', label: 'Content', color: '#fbbf24' },
  { key: 'performance_score', label: 'Performance', color: '#f87171' },
  { key: 'mobile_score', label: 'Mobile', color: '#60a5fa' },
  { key: 'security_score', label: 'Security', color: '#06b6d4' },
];

function HealthScoreTrendChart({ data, height = 260 }: { data: any[]; height?: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const [active, setActive] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(TREND_LINES.map(l => [l.key, true]))
  );

  if (!data.length) return null;

  const activeLines = TREND_LINES.filter(l => active[l.key]);
  const allVals = data.flatMap(d => activeLines.map(l => Number(d[l.key]) || 0));
  const maxV = allVals.length ? Math.max(...allVals, 100) : 100;
  const minV = allVals.length ? Math.min(...allVals, 0) : 0;
  const range = maxV - minV || 1;
  const w = 800, h = height, padL = 50, padR = 20, padT = 20, padB = 40;

  const pointsFor = (key: string) =>
    data.map((d, i) => ({
      x: padL + (i / (data.length - 1 || 1)) * (w - padL - padR),
      y: padT + (1 - ((Number(d[key]) || 0) - minV) / range) * (h - padT - padB),
      val: Number(d[key]) || 0,
    }));

  const linePoints = activeLines.map(line => ({
    ...line,
    points: pointsFor(line.key),
    pathD: pointsFor(line.key).map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' '),
  }));

  const toggleLine = (key: string) => setActive(prev => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className="relative">
      {/* Legend */}
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <span className="text-xs text-gray-400 font-medium mr-1">Toggle:</span>
        {TREND_LINES.map(line => (
          <button
            key={line.key}
            onClick={() => toggleLine(line.key)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium transition-all border ${
              active[line.key]
                ? 'bg-white/10 text-white border-white/20'
                : 'bg-transparent text-gray-500 border-white/5 line-through opacity-50'
            }`}
          >
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: line.color }} />
            {line.label}
          </button>
        ))}
      </div>

      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: `${height}px` }} onMouseLeave={() => setHover(null)}>
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map(pct => {
          const y = padT + pct * (h - padT - padB);
          const val = maxV - pct * range;
          return (
            <g key={pct}>
              <line x1={padL} y1={y} x2={w - padR} y2={y} stroke="rgba(255,255,255,0.05)" />
              <text x={padL - 8} y={y + 3} fill="#888" fontSize="9" textAnchor="end">{Math.round(val)}</text>
            </g>
          );
        })}

        {/* X labels */}
        {data.length <= 12 ? data.map((d, i) => (
          <text key={i} x={padL + (i / (data.length - 1 || 1)) * (w - padL - padR)} y={h - 10} fill="#888" fontSize="8" textAnchor="middle">
            {String(d.audit_date || d.date).slice(5, 10)}
          </text>
        )) : [0, Math.floor(data.length / 4), Math.floor(data.length / 2), Math.floor(data.length * 3 / 4), data.length - 1].map(i => (
          <text key={i} x={padL + (i / (data.length - 1 || 1)) * (w - padL - padR)} y={h - 10} fill="#888" fontSize="8" textAnchor="middle">
            {String(data[i].audit_date || data[i].date).slice(5, 10)}
          </text>
        ))}

        {/* Lines */}
        {linePoints.map(lp => (
          <g key={lp.key}>
            <path d={lp.pathD} fill="none" stroke={lp.color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
            {lp.points.map((p, i) => (
              <circle
                key={i}
                cx={p.x} cy={p.y} r={hover === i ? 4 : 2.5}
                fill={lp.color}
                stroke={hover === i ? 'white' : 'transparent'}
                strokeWidth="1.5"
              />
            ))}
          </g>
        ))}

        {/* Hover zones */}
        {data.map((_, i) => {
          const x = padL + (i / (data.length - 1 || 1)) * (w - padL - padR);
          return (
            <rect
              key={i}
              x={x - (w - padL - padR) / (data.length - 1 || 1) / 2}
              y={padT}
              width={(w - padL - padR) / (data.length - 1 || 1)}
              height={h - padT - padB}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
            />
          );
        })}

        {/* Hover tooltip */}
        {hover !== null && (
          <g>
            <line
              x1={padL + (hover / (data.length - 1 || 1)) * (w - padL - padR)}
              y1={padT}
              x2={padL + (hover / (data.length - 1 || 1)) * (w - padL - padR)}
              y2={h - padB}
              stroke="rgba(255,255,255,0.15)"
              strokeWidth="1"
              strokeDasharray="4,4"
            />
            <g transform={`translate(${Math.min(Math.max(padL + (hover / (data.length - 1 || 1)) * (w - padL - padR) - 70, 10), w - 150)}, ${padT + 4})`}>
              <rect x={0} y={0} width={140} height={18 + activeLines.length * 16} rx={8}
                fill="rgba(10,10,25,0.95)" stroke="rgba(255,255,255,0.1)" strokeWidth="1" />
              <text x={70} y={14} fill="#ccc" fontSize="9" textAnchor="middle" fontWeight="600">
                {String(data[hover].audit_date || data[hover].date).slice(0, 10)}
              </text>
              {activeLines.map((line, li) => {
                const v = Number(data[hover][line.key]) || 0;
                return (
                  <g key={line.key} transform={`translate(0, ${18 + li * 16})`}>
                    <circle cx={12} cy={4} r={3} fill={line.color} />
                    <text x={22} y={7} fill="#ddd" fontSize="10">{line.label}</text>
                    <text x={128} y={7} fill="white" fontSize="10" textAnchor="end" fontWeight="bold">{Math.round(v)}</text>
                  </g>
                );
              })}
            </g>
          </g>
        )}
      </svg>
    </div>
  );
}

// ─── Position Chart (inverted: lower position = higher on chart) ───
function PositionChart({ data, xKey, yKey, height = 140 }: { data: any[]; xKey: string; yKey: string; height?: number; }) {
  const [hover, setHover] = useState<number | null>(null);
  if (!data.length) return null;

  const vals = data.map(d => Number(d[yKey]) || 0);
  const nonZero = vals.filter(v => v > 0);
  if (!nonZero.length) return <p className="text-gray-600 text-xs text-center py-4">No ranking data</p>;

  const maxV = Math.max(...nonZero, 1);
  const minV = Math.min(...nonZero, 1);
  const range = maxV - minV || 1;
  const w = 700, h = height, pad = 35;

  const points = data.map((d, i) => {
    const v = vals[i];
    const y = v === 0 ? h - pad : pad + ((v - minV) / range) * (h - pad * 2); // 0=bottom, lower pos=higher
    return { x: pad + (i / (data.length - 1 || 1)) * (w - pad * 2), y, val: v, label: d[xKey] };
  });

  const pathD = points.filter(p => p.val > 0).map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');

  return (
    <div className="relative">
      <p className="text-xs text-gray-400 mb-1">Avg Position (lower = better)</p>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height: `${height}px` }} onMouseLeave={() => setHover(null)}>
        {[0, 0.5, 1].map(pct => {
          const y = pad + pct * (h - pad * 2);
          const val = minV + pct * range;
          return (
            <g key={pct}>
              <line x1={pad} y1={y} x2={w-pad} y2={y} stroke="rgba(255,255,255,0.05)" />
              <text x={pad-5} y={y+3} fill="#bbb" fontSize="9" textAnchor="end">#{Math.round(val)}</text>
            </g>
          );
        })}
        <text x={w-pad+5} y={pad+4} fill="#4ade80" fontSize="9">#1</text>
        <path d={pathD} fill="none" stroke="#a855f7" strokeWidth="2" strokeLinejoin="round" />
        {points.map((p, i) => (
          <g key={i} onMouseEnter={() => setHover(i)}>
            <rect x={p.x-15} y={0} width={30} height={h} fill="transparent" />
            <circle cx={p.x} cy={p.y} r={hover === i ? 5 : 3} fill="#a855f7" stroke={hover === i ? 'white' : 'transparent'} strokeWidth="2" />
          </g>
        ))}
        {hover !== null && (
          <g>
            <rect x={points[hover].x-35} y={points[hover].y-28} width={70} height={20} rx={6} fill="rgba(10,10,30,0.9)" stroke="#a855f7" strokeWidth="1" />
            <text x={points[hover].x} y={points[hover].y-14} fill="white" fontSize="11" textAnchor="middle" fontWeight="bold">
              #{points[hover].val || 'N/R'}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}

// ─── Change Badge ───
function ChangeBadge({ value, suffix = '', invert = false }: { value: number; suffix?: string; invert?: boolean }) {
  if (!value) return null;
  const positive = invert ? value < 0 : value > 0;
  return (
    <span className={`text-xs font-medium ${positive ? 'text-green-400' : 'text-red-400'}`}>
      {value > 0 ? '+' : ''}{value}{suffix}
    </span>
  );
}

export default function ReportingDashboard({ websiteId }: { websiteId: number }) {
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [selectedMonth, setSelectedMonth] = useState('');
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);
  const [keywordTrend, setKeywordTrend] = useState<any[] | null>(null);
  const [trendLoading, setTrendLoading] = useState(false);
  const [auditHistory, setAuditHistory] = useState<any[]>([]);
  const [auditHistoryLoading, setAuditHistoryLoading] = useState(false);

  const API = process.env.NEXT_PUBLIC_API_URL || '';

  const monthOptions = (() => {
    const opts = [{ value: '', label: 'Current (Latest)' }];
    const now = new Date();
    for (let i = 0; i < 12; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      opts.push({ value: `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`, label: d.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }) });
    }
    return opts;
  })();

  useEffect(() => {
    setLoading(true); setReport(null);
    const monthParam = selectedMonth ? `?month=${selectedMonth}` : '';
    fetch(`${API}/api/reports/${websiteId}${monthParam}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d && !d.error) setReport(d); })
      .catch(() => {}).finally(() => setLoading(false));
  }, [websiteId, selectedMonth, API]);

  useEffect(() => {
    setAuditHistoryLoading(true);
    fetch(`${API}/api/audit/${websiteId}/history?limit=90`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (Array.isArray(d)) {
          // API returns newest first; reverse for chronological order
          setAuditHistory(d.reverse());
        } else {
          setAuditHistory([]);
        }
      })
      .catch(() => setAuditHistory([]))
      .finally(() => setAuditHistoryLoading(false));
  }, [websiteId, API]);

  const downloadPdf = async () => {
    setDownloading(true);
    try {
      const mp = selectedMonth ? `?month=${selectedMonth}` : '';
      const r = await fetch(`${API}/api/reports/${websiteId}/pdf${mp}`);
      if (r.ok) {
        const blob = await r.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url;
        a.download = `seo-report-${report?.domain || 'site'}-${selectedMonth || 'latest'}.pdf`;
        a.click(); window.URL.revokeObjectURL(url);
      } else {
        const txt = await r.text().catch(() => '');
        alert(`PDF export failed (${r.status}). ${txt.slice(0, 300)}`);
      }
    } catch (err: any) {
      alert(`PDF export error: ${err?.message || err}`);
    } finally { setDownloading(false); }
  };

  const fetchKeywordTrend = async (keyword: string) => {
    if (selectedKeyword === keyword) { setSelectedKeyword(null); setKeywordTrend(null); return; }
    setSelectedKeyword(keyword);
    setTrendLoading(true); setKeywordTrend(null);
    try {
      const r = await fetch(`${API}/api/keywords/${websiteId}/keyword-history?keyword=${encodeURIComponent(keyword)}&days=90`);
      if (r.ok) { const d = await r.json(); setKeywordTrend(d.history || d.data || []); }
    } catch {} finally { setTrendLoading(false); }
  };

  const sc = (s: number) => s >= 70 ? 'text-green-400' : s >= 40 ? 'text-yellow-400' : 'text-red-400';

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 text-purple-400 animate-spin" /></div>;
  if (!report) return (
    <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
      <FileText className="w-12 h-12 text-purple-400 mx-auto mb-4" />
      <h3 className="text-xl font-bold text-white mb-2">No Report Data</h3>
      <p className="text-gray-400">Run an audit and sync keywords to generate a report.</p>
    </div>
  );

  const { audit, keywords: kw, fixes, tracked_keywords: tracked, since_inception: inception } = report;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <FileText className="w-6 h-6 text-purple-400" /> SEO Report
          </h2>
          <p className="text-gray-400 mt-1 text-sm">{report.domain} &middot; {report.generated_at?.slice(0,10)}</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)}
            className="bg-white/10 text-white border border-white/20 rounded-lg px-3 py-2.5 text-sm">
            {monthOptions.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
          <button onClick={downloadPdf} disabled={downloading}
            className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-5 py-2.5 rounded-lg font-medium hover:shadow-lg transition-all flex items-center gap-2 disabled:opacity-50">
            {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            PDF
          </button>
        </div>
      </div>

      {/* Health Score Trend Chart */}
      {(auditHistory.length > 1 || auditHistoryLoading) && (
        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-white font-semibold flex items-center gap-2 text-sm">
              <Activity className="w-4 h-4 text-purple-400" /> Health Score Trend (Last 90 Days)
            </h3>
            {auditHistoryLoading && <Loader2 className="w-4 h-4 text-purple-400 animate-spin" />}
          </div>
          {auditHistory.length > 1 ? (
            <HealthScoreTrendChart data={auditHistory} height={260} />
          ) : (
            <p className="text-gray-500 text-xs text-center py-8">Not enough history to show trend</p>
          )}
        </div>
      )}

      {/* Health Score Card */}
      {audit && (
        <div className="bg-gradient-to-r from-purple-500/15 to-pink-500/15 rounded-2xl p-6 border border-white/20">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="text-center">
              <div className="relative inline-flex items-center justify-center">
                <svg className="w-28 h-28 transform -rotate-90">
                  <circle cx="56" cy="56" r="48" stroke="rgba(255,255,255,0.1)" strokeWidth="10" fill="none" />
                  <circle cx="56" cy="56" r="48" stroke="url(#rg)" strokeWidth="10" fill="none"
                    strokeDasharray={`${(audit.health_score/100)*301.6} 301.6`} strokeLinecap="round" />
                  <defs><linearGradient id="rg"><stop offset="0%" stopColor="#a855f7" /><stop offset="100%" stopColor="#ec4899" /></linearGradient></defs>
                </svg>
                <div className="absolute">
                  <p className={`text-3xl font-bold ${sc(audit.health_score)}`}>{Math.round(audit.health_score)}</p>
                  <p className="text-[10px] text-gray-400">Health</p>
                </div>
              </div>
              <div className="mt-2"><ChangeBadge value={audit.score_change} suffix=" pts" /></div>
            </div>
            <div className="col-span-2 grid grid-cols-5 gap-2">
              {[
                { l: 'Technical', s: audit.technical_score, i: Globe },
                { l: 'Content', s: audit.content_score, i: FileText },
                { l: 'Performance', s: audit.performance_score, i: Gauge },
                { l: 'Mobile', s: audit.mobile_score, i: Activity },
                { l: 'Security', s: audit.security_score, i: Shield },
              ].map(c => (
                <div key={c.l} className="text-center">
                  <c.i className="w-4 h-4 text-gray-400 mx-auto mb-1" />
                  <p className={`text-lg font-bold ${sc(c.s)}`}>{Math.round(c.s)}</p>
                  <p className="text-[10px] text-gray-500">{c.l}</p>
                </div>
              ))}
            </div>
            <div className="space-y-1.5 text-sm">
              <div className="flex justify-between"><span className="text-gray-400">Issues</span><span className="text-white font-bold">{audit.total_issues} <ChangeBadge value={audit.issues_change} invert /></span></div>
              <div className="flex justify-between"><span className="text-gray-400">Critical</span><span className="text-red-400 font-bold">{audit.critical_issues}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Errors</span><span className="text-orange-400">{audit.errors}</span></div>
              <div className="flex justify-between"><span className="text-gray-400">Pages</span><span className="text-gray-300">{audit.pages_crawled}</span></div>
            </div>
          </div>
        </div>
      )}

      {/* ═══ CHARTS ═══ */}
      {report.keyword_history?.length > 1 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white/5 rounded-xl p-4 border border-white/10">
            <Chart data={report.keyword_history} xKey="date" yKey="clicks" color="#3b82f6" label="Organic Clicks Over Time" />
          </div>
          <div className="bg-white/5 rounded-xl p-4 border border-white/10">
            <Chart data={report.keyword_history} xKey="date" yKey="impressions" color="#8b5cf6" label="Impressions Over Time" />
          </div>
          <div className="bg-white/5 rounded-xl p-4 border border-white/10">
            <Chart data={report.keyword_history} xKey="date" yKey="total" color="#06b6d4" label="Keywords Ranking" />
          </div>
          <div className="bg-white/5 rounded-xl p-4 border border-white/10">
            <PositionChart data={report.keyword_history} xKey="date" yKey="avg_position" />
          </div>
        </div>
      )}

      {/* Health Score Trend */}
      {report.audit_history?.length > 1 && (
        <div className="bg-white/5 rounded-xl p-4 border border-white/10">
          <Chart data={report.audit_history} xKey="date" yKey="score" color="#ec4899" label="Health Score Trend" height={120} />
        </div>
      )}

      {/* ═══ SINCE INCEPTION ═══ */}
      {inception && (
        <div className="bg-gradient-to-r from-cyan-500/10 to-blue-500/10 rounded-xl p-5 border border-cyan-500/20">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><TrendingUp className="w-5 h-5 text-cyan-400" /> Since Tracking Began ({inception.tracking_started})</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {[
              { l: 'Keywords', v: `${inception.initial_keywords} → ${kw?.total || 0}`, c: inception.keywords_growth },
              { l: 'Clicks', v: `${inception.initial_clicks} → ${kw?.total_clicks || 0}`, c: inception.clicks_growth },
              { l: 'Impressions', v: `${inception.initial_impressions?.toLocaleString()} → ${kw?.total_impressions?.toLocaleString() || 0}`, c: inception.impressions_growth },
              { l: 'Avg Position', v: `${inception.initial_avg_position} → ${kw?.avg_position || 0}`, c: inception.position_change },
              { l: 'Fixes Applied', v: String(inception.total_fixes_applied), c: 0 },
            ].map(m => (
              <div key={m.l} className="bg-white/5 rounded-lg p-3 text-center">
                <p className="text-gray-400 text-[10px] mb-1">{m.l}</p>
                <p className="text-white text-xs font-medium">{m.v}</p>
                {m.c !== 0 && <ChangeBadge value={m.c} />}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Keywords Summary */}
      {kw && (
        <div className="bg-white/5 rounded-xl p-5 border border-white/10">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Search className="w-5 h-5 text-purple-400" /> Organic Search</h3>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-4">
            {[
              { l: 'Keywords', v: kw.total, c: kw.keywords_change },
              { l: 'Clicks', v: kw.total_clicks, c: kw.clicks_change },
              { l: 'Impressions', v: kw.total_impressions, c: kw.impressions_change },
              { l: 'Top 3', v: kw.top3 },
              { l: 'Top 10', v: kw.top10 },
              { l: 'Top 20', v: kw.top20 },
            ].map(m => (
              <div key={m.l} className="text-center bg-white/5 rounded-lg p-3">
                <p className="text-lg font-bold text-white">{typeof m.v === 'number' ? m.v.toLocaleString() : m.v}</p>
                <p className="text-[10px] text-gray-500">{m.l}</p>
                {'c' in m && m.c ? <ChangeBadge value={m.c as number} /> : null}
              </div>
            ))}
          </div>

          {/* Top keywords table — click to see trend */}
          {kw.top_keywords?.length > 0 && (
            <div className="bg-white/5 rounded-lg overflow-hidden">
              <div className="grid grid-cols-12 px-3 py-2 text-xs text-gray-500 border-b border-white/10">
                <div className="col-span-4">Keyword</div><div className="col-span-2 text-right">Position</div>
                <div className="col-span-2 text-right">Change</div>
                <div className="col-span-2 text-right">Clicks</div><div className="col-span-2 text-right">Impressions</div>
              </div>
              {kw.top_keywords.slice(0, 20).map((k: any, i: number) => {
                const change = k.position_change || k.change || 0;
                const isSelected = selectedKeyword === k.query;
                return (
                  <div key={i}>
                    <div onClick={() => fetchKeywordTrend(k.query)}
                      className={`grid grid-cols-12 px-3 py-2 text-sm border-b border-white/5 cursor-pointer hover:bg-white/5 transition-all ${isSelected ? 'bg-purple-500/10 border-l-2 border-l-purple-500' : ''}`}>
                      <div className="col-span-4 text-white truncate flex items-center gap-1">
                        <ChevronRight className={`w-3 h-3 text-gray-500 transition-transform shrink-0 ${isSelected ? 'rotate-90' : ''}`} />
                        {k.query}
                      </div>
                      <div className={`col-span-2 text-right font-bold ${k.position <= 3 ? 'text-green-400' : k.position <= 10 ? 'text-yellow-400' : k.position <= 20 ? 'text-orange-400' : 'text-red-400'}`}>
                        #{k.position}
                      </div>
                      <div className="col-span-2 text-right">
                        {change !== 0 ? (
                          <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${change > 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {change > 0 ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
                            {Math.abs(change)}
                          </span>
                        ) : <span className="text-gray-600 text-xs">—</span>}
                      </div>
                      <div className="col-span-2 text-right text-blue-400">{k.clicks}</div>
                      <div className="col-span-2 text-right text-gray-400">{k.impressions?.toLocaleString()}</div>
                    </div>
                    {/* Expanded trend chart */}
                    {isSelected && (
                      <div className="px-4 py-3 bg-purple-500/5 border-b border-white/10">
                        {trendLoading ? (
                          <div className="flex items-center justify-center py-4">
                            <Loader2 className="w-4 h-4 text-purple-400 animate-spin mr-2" />
                            <span className="text-gray-400 text-xs">Loading trend...</span>
                          </div>
                        ) : keywordTrend && keywordTrend.length > 1 ? (
                          <div className="space-y-2">
                            <p className="text-purple-400 text-xs font-medium">Position trend for "{k.query}" (last 90 days)</p>
                            <PositionChart data={keywordTrend} xKey="date" yKey="position" height={120} />
                            <div className="grid grid-cols-3 gap-2 mt-2">
                              {[
                                { l: 'Best Position', v: Math.min(...keywordTrend.filter((t: any) => t.position > 0).map((t: any) => t.position)), c: 'text-green-400' },
                                { l: 'Avg Clicks/Day', v: (keywordTrend.reduce((s: number, t: any) => s + (t.clicks || 0), 0) / keywordTrend.length).toFixed(1), c: 'text-blue-400' },
                                { l: 'Total Impressions', v: keywordTrend.reduce((s: number, t: any) => s + (t.impressions || 0), 0).toLocaleString(), c: 'text-gray-300' },
                              ].map(m => (
                                <div key={m.l} className="text-center bg-white/5 rounded p-2">
                                  <p className={`text-sm font-bold ${m.c}`}>{m.v}</p>
                                  <p className="text-[10px] text-gray-500">{m.l}</p>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <p className="text-gray-500 text-xs text-center py-2">No trend data available for this keyword</p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Ranking Changes */}
      {kw?.ranking_changes && (kw.ranking_changes.improved?.length > 0 || kw.ranking_changes.declined?.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {kw.ranking_changes.improved?.length > 0 && (
            <div className="bg-green-500/5 rounded-xl p-5 border border-green-500/20">
              <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><TrendingUp className="w-5 h-5 text-green-400" /> Improved ({kw.ranking_changes.total_improved})</h3>
              {kw.ranking_changes.improved.map((c: any, i: number) => (
                <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2 mb-1.5">
                  <span className="text-white text-sm truncate flex-1">{c.query}</span>
                  <div className="flex items-center gap-2 shrink-0 ml-2">
                    <span className="text-gray-500 text-xs line-through">#{c.previous}</span>
                    <ArrowRight className="w-3 h-3 text-green-400" />
                    <span className="text-green-400 font-bold">#{c.current}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          {kw.ranking_changes.declined?.length > 0 && (
            <div className="bg-red-500/5 rounded-xl p-5 border border-red-500/20">
              <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><TrendingDown className="w-5 h-5 text-red-400" /> Declined ({kw.ranking_changes.total_declined})</h3>
              {kw.ranking_changes.declined.map((c: any, i: number) => (
                <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2 mb-1.5">
                  <span className="text-white text-sm truncate flex-1">{c.query}</span>
                  <div className="flex items-center gap-2 shrink-0 ml-2">
                    <span className="text-gray-500 text-xs line-through">#{c.previous}</span>
                    <ArrowRight className="w-3 h-3 text-red-400" />
                    <span className="text-red-400 font-bold">#{c.current}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tracked Keywords */}
      {tracked?.length > 0 && (
        <div className="bg-white/5 rounded-xl p-5 border border-white/10">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Star className="w-5 h-5 text-yellow-400" /> Priority Keywords</h3>
          {tracked.map((tk: any, i: number) => (
            <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2 mb-1.5">
              <div className="flex items-center gap-2 min-w-0">
                <Star className="w-3.5 h-3.5 text-yellow-400 fill-yellow-400 shrink-0" />
                <span className="text-white text-sm truncate">{tk.keyword}</span>
              </div>
              <div className="flex items-center gap-4 shrink-0">
                <span className={`text-sm font-bold ${tk.position ? sc(100-tk.position*5) : 'text-gray-500'}`}>{tk.position ? `#${tk.position}` : 'N/R'}</span>
                <span className="text-blue-400 text-xs">{tk.clicks} clicks</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Work Done */}
      {fixes && (fixes.applied > 0 || fixes.pending > 0) && (
        <div className="bg-white/5 rounded-xl p-5 border border-white/10">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Sparkles className="w-5 h-5 text-purple-400" /> Technical Work</h3>
          <div className="grid grid-cols-5 gap-3 mb-3">
            {[
              { l: 'Applied', v: fixes.applied, c: 'text-green-400' },
              { l: 'This Period', v: fixes.applied_this_month, c: 'text-green-400' },
              { l: 'Pending', v: fixes.pending, c: 'text-yellow-400' },
              { l: 'Failed', v: fixes.failed, c: 'text-red-400' },
              { l: 'Generated', v: fixes.generated_this_month, c: 'text-purple-400' },
            ].map(f => (
              <div key={f.l} className="text-center bg-white/5 rounded-lg p-2">
                <p className={`text-lg font-bold ${f.c}`}>{f.v || 0}</p>
                <p className="text-[10px] text-gray-500">{f.l}</p>
              </div>
            ))}
          </div>
          {fixes.by_type && Object.keys(fixes.by_type).length > 0 && (
            <div className="space-y-1">
              <p className="text-gray-500 text-xs mb-1">Applied by type:</p>
              {Object.entries(fixes.by_type).map(([type, count]: [string, any]) => {
                const labels: Record<string, string> = { alt_text: 'Alt Text Added', meta_title: 'Meta Titles Optimized', meta_description: 'Meta Descriptions', thin_content: 'Content Expanded', structured_data: 'Schema Added' };
                return (
                  <div key={type} className="flex items-center justify-between bg-white/5 rounded px-3 py-1.5">
                    <span className="text-gray-300 text-xs">{labels[type] || type}</span>
                    <span className="text-green-400 text-xs font-bold">{count} fixes</span>
                  </div>
                );
              })}
            </div>
          )}
          {fixes.by_resource && Object.keys(fixes.by_resource).length > 0 && (
            <div className="mt-2 flex gap-2 flex-wrap">
              {Object.entries(fixes.by_resource).map(([type, count]: [string, any]) => (
                <span key={type} className="text-xs bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded-full">{count} {type}s fixed</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* AI Strategy */}
      {report.strategy && (
        <div className="bg-gradient-to-r from-indigo-500/10 to-purple-500/10 rounded-xl p-5 border border-indigo-500/20 space-y-4">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <Target className="w-5 h-5 text-indigo-400" /> AI Master Strategy
            {report.strategy.generated_at && (
              <span className="text-[10px] text-gray-500 font-normal ml-2">
                generated {String(report.strategy.generated_at).slice(0, 10)}
              </span>
            )}
          </h3>

          {report.strategy.executive_summary && (
            <p className="text-gray-200 text-sm leading-relaxed bg-white/5 rounded-lg p-3 border border-white/5">
              {report.strategy.executive_summary}
            </p>
          )}

          {(report.strategy.current_state?.strengths?.length ||
            report.strategy.current_state?.weaknesses?.length ||
            report.strategy.current_state?.opportunities?.length ||
            report.strategy.current_state?.threats?.length) ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                { l: 'Strengths', k: 'strengths', c: 'text-green-400', b: 'border-green-500/20' },
                { l: 'Weaknesses', k: 'weaknesses', c: 'text-red-400', b: 'border-red-500/20' },
                { l: 'Opportunities', k: 'opportunities', c: 'text-cyan-400', b: 'border-cyan-500/20' },
                { l: 'Threats', k: 'threats', c: 'text-orange-400', b: 'border-orange-500/20' },
              ].map(s => {
                const items: string[] = report.strategy.current_state?.[s.k] || [];
                if (!items.length) return null;
                return (
                  <div key={s.k} className={`bg-white/5 rounded-lg p-3 border ${s.b}`}>
                    <p className={`text-xs font-semibold mb-2 ${s.c}`}>{s.l}</p>
                    <ul className="space-y-1">
                      {items.map((it: string, i: number) => (
                        <li key={i} className="text-gray-300 text-xs flex gap-2"><span className={s.c}>•</span>{it}</li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          ) : null}

          {report.strategy.weekly_focus?.this_week?.length > 0 && (
            <div className="bg-white/5 rounded-lg p-3 border border-white/10">
              <p className="text-xs font-semibold mb-2 text-purple-400 flex items-center gap-1">
                <Zap className="w-3 h-3" /> This Week's Focus
              </p>
              <ul className="space-y-1">
                {report.strategy.weekly_focus.this_week.map((a: string, i: number) => (
                  <li key={i} className="text-gray-300 text-xs flex gap-2">
                    <span className="text-purple-400 font-bold">{i + 1}.</span>{a}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {report.strategy.weekly_focus?.quick_wins?.length > 0 && (
            <div className="bg-green-500/5 rounded-lg p-3 border border-green-500/20">
              <p className="text-xs font-semibold mb-2 text-green-400">Quick Wins (&lt;1 hour)</p>
              <ul className="space-y-1">
                {report.strategy.weekly_focus.quick_wins.map((a: string, i: number) => (
                  <li key={i} className="text-gray-300 text-xs flex gap-2"><CheckCircle className="w-3 h-3 text-green-400 shrink-0 mt-0.5" />{a}</li>
                ))}
              </ul>
            </div>
          )}

          {report.strategy.strategic_goals?.length > 0 && (
            <div>
              <p className="text-xs font-semibold mb-2 text-gray-400">Strategic Goals</p>
              <div className="space-y-1.5">
                {report.strategy.strategic_goals.map((g: any, i: number) => (
                  <div key={i} className="bg-white/5 rounded-lg p-2.5 border border-white/10">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-white text-xs font-medium">{g.goal}</span>
                      <span className="text-[10px] text-gray-500 shrink-0">{g.timeframe}</span>
                    </div>
                    {g.target && <p className="text-gray-400 text-[11px] mt-0.5">Target: {g.target}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {report.strategy.technical_priorities?.length > 0 && (
            <div>
              <p className="text-xs font-semibold mb-2 text-gray-400">Technical Priorities</p>
              <div className="space-y-1">
                {report.strategy.technical_priorities.map((t: any, i: number) => (
                  <div key={i} className="flex items-center justify-between bg-white/5 rounded px-3 py-1.5 text-xs">
                    <span className="text-gray-200 truncate">{t.action}</span>
                    <div className="flex gap-1.5 shrink-0 ml-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] ${t.impact === 'high' ? 'bg-red-500/20 text-red-300' : t.impact === 'medium' ? 'bg-yellow-500/20 text-yellow-300' : 'bg-gray-500/20 text-gray-300'}`}>{t.impact}</span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-white/5 text-gray-400">{t.effort}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {(report.strategy.keyword_portfolio?.primary_keywords?.length ||
            report.strategy.content_strategy?.content_gaps?.length) ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {report.strategy.keyword_portfolio?.primary_keywords?.length > 0 && (
                <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                  <p className="text-xs font-semibold mb-2 text-purple-400">Primary Keywords</p>
                  <ul className="space-y-1">
                    {report.strategy.keyword_portfolio.primary_keywords.slice(0, 5).map((k: string, i: number) => (
                      <li key={i} className="text-gray-300 text-xs">• {k}</li>
                    ))}
                  </ul>
                </div>
              )}
              {report.strategy.content_strategy?.content_gaps?.length > 0 && (
                <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                  <p className="text-xs font-semibold mb-2 text-cyan-400">Content Gaps</p>
                  <ul className="space-y-1">
                    {report.strategy.content_strategy.content_gaps.slice(0, 5).map((k: string, i: number) => (
                      <li key={i} className="text-gray-300 text-xs">• {k}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* Hub & Spoke */}
      {report.hub_and_spoke && (
        <div className="bg-white/5 rounded-xl p-5 border border-white/10 space-y-3">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <Globe className="w-5 h-5 text-pink-400" /> Hub &amp; Spoke Internal Linking
            {report.hub_and_spoke.analyzed_at && (
              <span className="text-[10px] text-gray-500 font-normal ml-2">
                analyzed {String(report.hub_and_spoke.analyzed_at).slice(0, 10)}
              </span>
            )}
          </h3>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { l: 'Pages', v: report.hub_and_spoke.total_pages },
              { l: 'Internal Links', v: report.hub_and_spoke.total_internal_links },
              { l: 'Avg Links/Page', v: report.hub_and_spoke.avg_links_per_page },
              { l: 'Orphans', v: report.hub_and_spoke.orphans?.length || 0 },
            ].map(m => (
              <div key={m.l} className="text-center bg-white/5 rounded-lg p-3">
                <p className="text-lg font-bold text-white">{typeof m.v === 'number' ? m.v.toLocaleString() : m.v}</p>
                <p className="text-[10px] text-gray-500">{m.l}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {report.hub_and_spoke.hubs?.length > 0 && (
              <div className="bg-white/5 rounded-lg p-3 border border-white/10">
                <p className="text-xs font-semibold mb-2 text-purple-400">Top Hub Pages</p>
                <div className="space-y-1">
                  {report.hub_and_spoke.hubs.slice(0, 6).map((h: any, i: number) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="text-gray-300 truncate">{h.url}</span>
                      <span className="text-purple-400 font-bold shrink-0 ml-2">{h.inbound}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {report.hub_and_spoke.orphans?.length > 0 && (
              <div className="bg-orange-500/5 rounded-lg p-3 border border-orange-500/20">
                <p className="text-xs font-semibold mb-2 text-orange-400">Orphan Pages (need links)</p>
                <div className="space-y-1">
                  {report.hub_and_spoke.orphans.slice(0, 6).map((o: any, i: number) => (
                    <div key={i} className="text-gray-300 text-xs truncate">{o.url}</div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {report.hub_and_spoke.suggestions?.length > 0 && (
            <div>
              <p className="text-xs font-semibold mb-2 text-gray-400">Top Link Suggestions</p>
              <div className="space-y-1">
                {report.hub_and_spoke.suggestions.slice(0, 8).map((s: any, i: number) => (
                  <div key={i} className="bg-white/5 rounded-lg p-2 text-xs border border-white/5">
                    <div className="flex items-center gap-2 text-gray-200">
                      <span className="truncate">{s.from}</span>
                      <ArrowRight className="w-3 h-3 text-pink-400 shrink-0" />
                      <span className="truncate">{s.to}</span>
                    </div>
                    {(s.anchor || s.reason) && (
                      <p className="text-gray-500 text-[11px] mt-1">
                        {s.anchor && <span className="text-pink-400">"{s.anchor}"</span>}
                        {s.anchor && s.reason && ' — '}
                        {s.reason}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Content Decay */}
      {report.content_decay && (report.content_decay.high_risk_count > 0 || report.content_decay.medium_risk_count > 0) && (
        <div className="bg-white/5 rounded-xl p-5 border border-white/10">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
            <Clock className="w-5 h-5 text-orange-400" /> Content Decay
          </h3>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div className="text-center bg-white/5 rounded-lg p-3">
              <p className="text-lg font-bold text-white">{report.content_decay.total_pages_analyzed}</p>
              <p className="text-[10px] text-gray-500">Analyzed</p>
            </div>
            <div className="text-center bg-red-500/5 rounded-lg p-3 border border-red-500/20">
              <p className="text-lg font-bold text-red-400">{report.content_decay.high_risk_count}</p>
              <p className="text-[10px] text-gray-500">High Risk</p>
            </div>
            <div className="text-center bg-yellow-500/5 rounded-lg p-3 border border-yellow-500/20">
              <p className="text-lg font-bold text-yellow-400">{report.content_decay.medium_risk_count}</p>
              <p className="text-[10px] text-gray-500">Medium Risk</p>
            </div>
          </div>
          {report.content_decay.high_risk?.length > 0 && (
            <div className="space-y-1">
              {report.content_decay.high_risk.slice(0, 6).map((p: any, i: number) => (
                <div key={i} className="bg-white/5 rounded px-3 py-1.5 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-gray-200 truncate">{p.url}</span>
                    <span className="text-orange-400 text-[10px] shrink-0">{p.days}d old</span>
                  </div>
                  {p.rec && <p className="text-gray-500 text-[11px] mt-0.5">{p.rec}</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* AI Summary */}
      {report.ai_summary && (
        <div className="bg-gradient-to-r from-purple-500/10 to-cyan-500/10 rounded-xl p-5 border border-purple-500/20">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Activity className="w-5 h-5 text-cyan-400" /> AI Analysis</h3>
          <div className="text-gray-300 text-sm leading-relaxed whitespace-pre-line">{report.ai_summary}</div>
        </div>
      )}

      {/* GA4 Traffic */}
      {report.ga4_traffic && !report.ga4_traffic.error && (
        <div className="bg-white/5 rounded-xl p-5 border border-white/10">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><BarChart3 className="w-5 h-5 text-blue-400" /> Google Analytics Traffic</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            {[
              { l: 'Sessions', v: report.ga4_traffic.current?.sessions, c: report.ga4_traffic.changes?.sessions },
              { l: 'Users', v: report.ga4_traffic.current?.users, c: report.ga4_traffic.changes?.users },
              { l: 'Pageviews', v: report.ga4_traffic.current?.pageviews, c: report.ga4_traffic.changes?.pageviews },
              { l: 'Organic', v: report.ga4_traffic.current?.organic_sessions },
            ].map(m => (
              <div key={m.l} className="text-center bg-white/5 rounded-lg p-3">
                <p className="text-lg font-bold text-white">{(m.v || 0).toLocaleString()}</p>
                <p className="text-[10px] text-gray-500">{m.l}</p>
                {m.c ? <ChangeBadge value={m.c} /> : null}
              </div>
            ))}
          </div>
          {report.ga4_traffic.daily_trend?.length > 1 && (
            <Chart data={report.ga4_traffic.daily_trend} xKey="date" yKey="sessions" color="#3b82f6" label="Daily Sessions" height={120} />
          )}
        </div>
      )}
    </div>
  );
}
