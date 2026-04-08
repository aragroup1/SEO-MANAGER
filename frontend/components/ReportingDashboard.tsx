// frontend/components/ReportingDashboard.tsx
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  FileText, Download, Loader2, RefreshCw, TrendingUp,
  TrendingDown, Minus, Target, Shield, Gauge, Globe,
  Search, Sparkles, CheckCircle, XCircle, AlertTriangle,
  Clock, Star, BarChart3, Eye, MousePointerClick, Activity
} from 'lucide-react';

interface ReportData {
  domain: string;
  site_type: string;
  generated_at: string;
  audit: any;
  keywords: any;
  tracked_keywords: any[];
  fixes: Record<string, number>;
  audit_history: { date: string; score: number }[];
}

export default function ReportingDashboard({ websiteId }: { websiteId: number }) {
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [selectedMonth, setSelectedMonth] = useState('');

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  // Generate month options (last 12 months)
  const monthOptions = (() => {
    const opts = [{ value: '', label: 'Current (Latest Data)' }];
    const now = new Date();
    for (let i = 0; i < 12; i++) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const val = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      const label = d.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });
      opts.push({ value: val, label });
    }
    return opts;
  })();

  useEffect(() => {
    setLoading(true);
    setReport(null);
    fetch(`${API_URL}/api/reports/${websiteId}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data && !data.error) setReport(data); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [websiteId, API_URL]);

  const downloadPdf = async () => {
    setDownloading(true);
    try {
      const monthParam = selectedMonth ? `?month=${selectedMonth}` : '';
      const r = await fetch(`${API_URL}/api/reports/${websiteId}/pdf${monthParam}`);
      if (r.ok) {
        const blob = await r.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `seo-report-${report?.domain || 'site'}-${selectedMonth || 'latest'}.pdf`;
        a.click();
        window.URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('PDF download error:', err);
    } finally {
      setDownloading(false);
    }
  };

  const getScoreColor = (s: number) => s >= 70 ? 'text-green-400' : s >= 40 ? 'text-yellow-400' : 'text-red-400';
  const getScoreBg = (s: number) => s >= 70 ? 'bg-green-500' : s >= 40 ? 'bg-yellow-500' : 'bg-red-500';

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 text-purple-400 animate-spin" /></div>;

  if (!report) return (
    <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
      <FileText className="w-12 h-12 text-purple-400 mx-auto mb-4" />
      <h3 className="text-xl font-bold text-white mb-2">No Report Data</h3>
      <p className="text-purple-300">Run an audit and sync keywords first to generate a report.</p>
    </div>
  );

  const audit = report.audit;
  const kw = report.keywords;
  const fixes = report.fixes;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <FileText className="w-6 h-6 text-purple-400" /> SEO Report
          </h2>
          <p className="text-purple-300 mt-1 text-sm">{report.domain} · {report.generated_at.slice(0, 10)}</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)}
            className="bg-white/10 text-white border border-white/20 rounded-lg px-3 py-2.5 text-sm">
            {monthOptions.map(m => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
          <button onClick={downloadPdf} disabled={downloading}
            className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-5 py-2.5 rounded-lg font-medium hover:shadow-lg transition-all flex items-center gap-2 disabled:opacity-50">
            {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            {downloading ? 'Generating...' : 'Download PDF'}
          </button>
        </div>
      </div>

      {/* Health Score Hero */}
      {audit && (
        <div className="bg-gradient-to-r from-purple-500/15 to-pink-500/15 backdrop-blur-md rounded-2xl p-6 border border-white/20">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {/* Score */}
            <div className="text-center">
              <div className="relative inline-flex items-center justify-center">
                <svg className="w-28 h-28 transform -rotate-90">
                  <circle cx="56" cy="56" r="48" stroke="rgba(255,255,255,0.1)" strokeWidth="10" fill="none" />
                  <circle cx="56" cy="56" r="48" stroke="url(#rptGrad)" strokeWidth="10" fill="none"
                    strokeDasharray={`${(audit.health_score / 100) * 301.6} 301.6`} strokeLinecap="round" />
                  <defs><linearGradient id="rptGrad"><stop offset="0%" stopColor="#a855f7" /><stop offset="100%" stopColor="#ec4899" /></linearGradient></defs>
                </svg>
                <div className="absolute">
                  <p className={`text-3xl font-bold ${getScoreColor(audit.health_score)}`}>{Math.round(audit.health_score)}</p>
                  <p className="text-[10px] text-gray-400">Health</p>
                </div>
              </div>
              <div className="flex items-center justify-center gap-1 mt-2">
                {audit.health_score > audit.previous_score ? <TrendingUp className="w-3 h-3 text-green-400" /> :
                 audit.health_score < audit.previous_score ? <TrendingDown className="w-3 h-3 text-red-400" /> :
                 <Minus className="w-3 h-3 text-gray-400" />}
                <span className="text-xs text-gray-400">{audit.health_score > audit.previous_score ? '+' : ''}{(audit.health_score - audit.previous_score).toFixed(1)}</span>
              </div>
            </div>

            {/* Category Scores */}
            <div className="col-span-2 grid grid-cols-5 gap-2">
              {[
                { label: 'Technical', score: audit.technical_score, icon: Globe },
                { label: 'Content', score: audit.content_score, icon: FileText },
                { label: 'Performance', score: audit.performance_score, icon: Gauge },
                { label: 'Mobile', score: audit.mobile_score, icon: Activity },
                { label: 'Security', score: audit.security_score, icon: Shield },
              ].map(cat => (
                <div key={cat.label} className="text-center">
                  <cat.icon className="w-4 h-4 text-gray-400 mx-auto mb-1" />
                  <p className={`text-lg font-bold ${getScoreColor(cat.score)}`}>{Math.round(cat.score)}</p>
                  <p className="text-[10px] text-gray-500">{cat.label}</p>
                </div>
              ))}
            </div>

            {/* Issues */}
            <div className="space-y-2">
              <p className="text-white font-medium text-sm">Issues</p>
              <div className="flex items-center gap-2"><XCircle className="w-3 h-3 text-red-400" /><span className="text-gray-300 text-xs">Critical: {audit.critical_issues}</span></div>
              <div className="flex items-center gap-2"><AlertTriangle className="w-3 h-3 text-orange-400" /><span className="text-gray-300 text-xs">Errors: {audit.errors}</span></div>
              <div className="flex items-center gap-2"><Clock className="w-3 h-3 text-yellow-400" /><span className="text-gray-300 text-xs">Warnings: {audit.warnings}</span></div>
              <p className="text-gray-500 text-xs">{audit.pages_crawled} pages crawled</p>
            </div>
          </div>

          {/* CWV */}
          {audit.core_web_vitals && Object.keys(audit.core_web_vitals).length > 0 && (
            <div className="mt-4 pt-4 border-t border-white/10 grid grid-cols-4 gap-3">
              {[
                { label: 'LCP', value: audit.core_web_vitals.lcp + 's', good: audit.core_web_vitals.lcp <= 2.5 },
                { label: 'CLS', value: String(audit.core_web_vitals.cls), good: audit.core_web_vitals.cls <= 0.1 },
                { label: 'TBT', value: audit.core_web_vitals.tbt + 'ms', good: audit.core_web_vitals.tbt <= 200 },
                { label: 'Perf Score', value: audit.core_web_vitals.performance_score + '/100', good: audit.core_web_vitals.performance_score >= 70 },
              ].map(v => (
                <div key={v.label} className="text-center">
                  <p className={`text-sm font-bold ${v.good ? 'text-green-400' : 'text-orange-400'}`}>{v.value}</p>
                  <p className="text-[10px] text-gray-500">{v.label}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Keywords Summary */}
      {kw && (
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-5 border border-white/20">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2"><Search className="w-5 h-5 text-purple-400" /> Keyword Rankings</h3>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-4">
            {[
              { label: 'Keywords', value: kw.total, prev: kw.prev_total, icon: Search },
              { label: 'Clicks', value: kw.total_clicks, prev: kw.prev_clicks, icon: MousePointerClick },
              { label: 'Impressions', value: kw.total_impressions, icon: Eye },
              { label: 'Avg Pos', value: kw.avg_position, icon: Target },
              { label: 'Top 3', value: kw.top3, icon: Star },
              { label: 'Top 10', value: kw.top10, icon: TrendingUp },
            ].map(m => (
              <div key={m.label} className="text-center bg-white/5 rounded-lg p-3">
                <m.icon className="w-4 h-4 text-gray-400 mx-auto mb-1" />
                <p className="text-lg font-bold text-white">{typeof m.value === 'number' ? m.value.toLocaleString() : m.value}</p>
                <p className="text-[10px] text-gray-500">{m.label}</p>
                {m.prev !== undefined && m.prev > 0 && (
                  <p className={`text-[10px] ${m.value > m.prev ? 'text-green-400' : m.value < m.prev ? 'text-red-400' : 'text-gray-500'}`}>
                    {m.value > m.prev ? '+' : ''}{m.value - m.prev}
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* Top Keywords Table */}
          {kw.top_keywords?.length > 0 && (
            <div className="bg-white/5 rounded-lg overflow-hidden">
              <div className="grid grid-cols-12 px-3 py-2 text-xs text-gray-500 border-b border-white/10">
                <div className="col-span-6">Keyword</div>
                <div className="col-span-2 text-right">Pos</div>
                <div className="col-span-2 text-right">Clicks</div>
                <div className="col-span-2 text-right">Country</div>
              </div>
              {kw.top_keywords.slice(0, 10).map((k: any, i: number) => (
                <div key={i} className="grid grid-cols-12 px-3 py-2 text-sm border-b border-white/5">
                  <div className="col-span-6 text-white truncate">{k.query}</div>
                  <div className={`col-span-2 text-right font-bold ${getScoreColor(100 - k.position * 5)}`}>{k.position}</div>
                  <div className="col-span-2 text-right text-blue-400">{k.clicks}</div>
                  <div className="col-span-2 text-right text-gray-400">{k.country || '—'}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tracked Keywords */}
      {report.tracked_keywords?.length > 0 && (
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-5 border border-white/20">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Star className="w-5 h-5 text-yellow-400" /> Road to #1</h3>
          <div className="space-y-2">
            {report.tracked_keywords.map((tk: any, i: number) => (
              <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2">
                <div className="flex items-center gap-2 min-w-0">
                  <Star className="w-3.5 h-3.5 text-yellow-400 fill-yellow-400 shrink-0" />
                  <span className="text-white text-sm truncate">{tk.keyword}</span>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <span className={`text-sm font-bold ${tk.position ? getScoreColor(100 - tk.position * 5) : 'text-gray-500'}`}>
                    {tk.position ? `Pos ${tk.position}` : 'N/R'}
                  </span>
                  <span className="text-blue-400 text-xs">{tk.clicks} clicks</span>
                  {tk.has_strategy && <span className="text-green-400 text-xs">Strategy ✓</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Fix Status */}
      {fixes && (
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-5 border border-white/20">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><Sparkles className="w-5 h-5 text-purple-400" /> Auto-Fix Status</h3>
          <div className="grid grid-cols-5 gap-3">
            {[
              { label: 'Applied', count: fixes.applied || 0, color: 'text-green-400', icon: CheckCircle },
              { label: 'Pending', count: fixes.pending || 0, color: 'text-yellow-400', icon: Clock },
              { label: 'Approved', count: fixes.approved || 0, color: 'text-blue-400', icon: CheckCircle },
              { label: 'Failed', count: fixes.failed || 0, color: 'text-red-400', icon: XCircle },
              { label: 'Rejected', count: fixes.rejected || 0, color: 'text-gray-400', icon: XCircle },
            ].map(f => (
              <div key={f.label} className="text-center bg-white/5 rounded-lg p-3">
                <f.icon className={`w-4 h-4 ${f.color} mx-auto mb-1`} />
                <p className={`text-lg font-bold ${f.color}`}>{f.count}</p>
                <p className="text-[10px] text-gray-500">{f.label}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Score History */}
      {report.audit_history?.length > 1 && (
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-5 border border-white/20">
          <h3 className="text-white font-semibold mb-3 flex items-center gap-2"><BarChart3 className="w-5 h-5 text-purple-400" /> Score History</h3>
          <div className="flex items-end gap-2 h-24">
            {report.audit_history.reverse().map((h: any, i: number) => {
              const height = `${Math.max(h.score, 5)}%`;
              return (
                <div key={i} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-[10px] text-gray-400">{Math.round(h.score)}</span>
                  <div className="w-full rounded-t" style={{ height, background: `linear-gradient(to top, #a855f7, #ec4899)` }} />
                  <span className="text-[9px] text-gray-600">{h.date.slice(5)}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
