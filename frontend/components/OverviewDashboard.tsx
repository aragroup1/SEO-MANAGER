// frontend/components/OverviewDashboard.tsx
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  TrendingUp, TrendingDown, Minus, Search, MousePointerClick,
  Eye, AlertTriangle, CheckCircle, Loader2, Zap, Bot,
  Activity, Target, Star, Sparkles, Globe, BarChart3,
  ArrowRight, Shield
} from 'lucide-react';

interface WebsiteSummary {
  id: number;
  domain: string;
  site_type: string;
  health_score: number | null;
  score_change: number;
  total_issues: number;
  critical_issues: number;
  issues_change: number;
  last_audit: string | null;
  total_keywords: number;
  total_clicks: number;
  total_impressions: number;
  avg_position: number;
  keywords_change: number;
  clicks_change: number;
  pending_fixes: number;
  applied_fixes: number;
  autonomy_mode?: string;
  tracked_count: number;
  tracked_keywords: { keyword: string; position: number | null; clicks: number }[];
}

export default function OverviewDashboard({
  onSelectWebsite,
  selectedWebsite,
}: {
  onSelectWebsite: (id: number) => void;
  selectedWebsite: number | null;
}) {
  const [summaries, setSummaries] = useState<WebsiteSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  useEffect(() => {
    fetch(`${API_URL}/api/overview`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.websites) setSummaries(data.websites); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [API_URL]);

  const scoreColor = (s: number | null) => !s ? 'text-gray-500' : s >= 70 ? 'text-green-400' : s >= 50 ? 'text-yellow-400' : 'text-red-400';
  const scoreBg = (s: number | null) => !s ? 'from-gray-500' : s >= 70 ? 'from-green-500' : s >= 50 ? 'from-yellow-500' : 'from-red-500';
  const changeIcon = (v: number) => v > 0 ? <TrendingUp className="w-3.5 h-3.5 text-green-400" /> : v < 0 ? <TrendingDown className="w-3.5 h-3.5 text-red-400" /> : <Minus className="w-3.5 h-3.5 text-gray-500" />;
  const changeColor = (v: number) => v > 0 ? 'text-green-400' : v < 0 ? 'text-red-400' : 'text-gray-500';
  const changeStr = (v: number) => v > 0 ? `+${v}` : String(v);

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 text-purple-400 animate-spin" /></div>;

  if (summaries.length === 0) return null;

  // Aggregate stats
  const totalKeywords = summaries.reduce((s, w) => s + w.total_keywords, 0);
  const totalClicks = summaries.reduce((s, w) => s + w.total_clicks, 0);
  const totalIssues = summaries.reduce((s, w) => s + w.total_issues, 0);
  const totalPending = summaries.reduce((s, w) => s + w.pending_fixes, 0);

  return (
    <div className="space-y-6">
      {/* Aggregate Summary Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { icon: Globe, label: 'Websites', value: String(summaries.length), color: 'text-purple-400' },
          { icon: Search, label: 'Keywords Tracked', value: totalKeywords.toLocaleString(), color: 'text-blue-400' },
          { icon: MousePointerClick, label: 'Total Clicks', value: totalClicks.toLocaleString(), color: 'text-cyan-400' },
          { icon: AlertTriangle, label: 'Open Issues', value: String(totalIssues), color: totalIssues > 0 ? 'text-orange-400' : 'text-green-400' },
        ].map(s => (
          <div key={s.label} className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/10">
            <div className="flex items-center gap-2 mb-1">
              <s.icon className={`w-4 h-4 ${s.color}`} />
              <span className="text-gray-400 text-xs">{s.label}</span>
            </div>
            <p className="text-2xl font-bold text-white">{s.value}</p>
          </div>
        ))}
      </div>

      {/* Per-Website Cards */}
      <div className="space-y-4">
        {summaries.map((site, idx) => (
          <motion.div
            key={site.id}
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: idx * 0.05 }}
            onClick={() => onSelectWebsite(site.id)}
            className={`bg-white/8 backdrop-blur-md rounded-2xl border cursor-pointer transition-all hover:bg-white/12 ${
              selectedWebsite === site.id ? 'border-purple-500/50 bg-purple-500/5' : 'border-white/10'
            }`}
          >
            <div className="p-5">
              {/* Header Row */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${scoreBg(site.health_score)} to-transparent/20 flex items-center justify-center`}>
                    <span className={`text-lg font-bold ${scoreColor(site.health_score)}`}>
                      {site.health_score ? Math.round(site.health_score) : '--'}
                    </span>
                  </div>
                  <div>
                    <h3 className="text-white font-semibold">{site.domain}</h3>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500 capitalize">{site.site_type}</span>
                      {site.autonomy_mode && site.autonomy_mode !== 'manual' && (
                        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${
                          site.autonomy_mode === 'ultra'
                            ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                            : 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                        }`}>
                          {site.autonomy_mode === 'ultra' ? 'Ultra' : 'Smart'}
                        </span>
                      )}
                      {site.last_audit && (
                        <span className="text-xs text-gray-600">Last audit: {new Date(site.last_audit).toLocaleDateString()}</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {site.score_change !== 0 && (
                    <div className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full ${site.score_change > 0 ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                      {changeIcon(site.score_change)}
                      <span>{changeStr(site.score_change)} pts</span>
                    </div>
                  )}
                  <ArrowRight className="w-4 h-4 text-gray-600" />
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {/* Keywords */}
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Search className="w-3 h-3 text-blue-400" />
                    <span className="text-gray-500 text-[10px]">Keywords</span>
                  </div>
                  <p className="text-white font-bold">{site.total_keywords.toLocaleString()}</p>
                  {site.keywords_change !== 0 && (
                    <p className={`text-[10px] ${changeColor(site.keywords_change)}`}>{changeStr(site.keywords_change)}</p>
                  )}
                </div>

                {/* Clicks */}
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <MousePointerClick className="w-3 h-3 text-cyan-400" />
                    <span className="text-gray-500 text-[10px]">Clicks</span>
                  </div>
                  <p className="text-white font-bold">{site.total_clicks.toLocaleString()}</p>
                  {site.clicks_change !== 0 && (
                    <p className={`text-[10px] ${changeColor(site.clicks_change)}`}>{changeStr(site.clicks_change)}</p>
                  )}
                </div>

                {/* Issues */}
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <AlertTriangle className="w-3 h-3 text-orange-400" />
                    <span className="text-gray-500 text-[10px]">Issues</span>
                  </div>
                  <p className="text-white font-bold">{site.total_issues}</p>
                  {site.issues_change !== 0 && (
                    <p className={`text-[10px] ${site.issues_change < 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {site.issues_change < 0 ? '' : '+'}{site.issues_change}
                    </p>
                  )}
                </div>

                {/* Fixes */}
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Sparkles className="w-3 h-3 text-purple-400" />
                    <span className="text-gray-500 text-[10px]">Fixes</span>
                  </div>
                  <p className="text-white font-bold">{site.applied_fixes}</p>
                  {site.pending_fixes > 0 && (
                    <p className="text-[10px] text-yellow-400">{site.pending_fixes} pending</p>
                  )}
                </div>

                {/* Avg Position */}
                <div className="bg-white/5 rounded-lg p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Target className="w-3 h-3 text-green-400" />
                    <span className="text-gray-500 text-[10px]">Avg Pos</span>
                  </div>
                  <p className="text-white font-bold">{site.avg_position || '--'}</p>
                </div>
              </div>

              {/* Tracked Keywords Preview */}
              {site.tracked_keywords?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-white/5 flex items-center gap-3 overflow-x-auto">
                  <Star className="w-3 h-3 text-yellow-400 shrink-0" />
                  {site.tracked_keywords.map((tk, i) => (
                    <span key={i} className="text-xs bg-white/5 text-gray-300 px-2 py-1 rounded-full whitespace-nowrap flex items-center gap-1">
                      {tk.keyword}
                      {tk.position && <span className={`font-bold ${tk.position <= 10 ? 'text-green-400' : 'text-yellow-400'}`}>#{tk.position}</span>}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
