// frontend/components/OverviewDashboard.tsx — Premium Ethereal Glass
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  TrendingUp, TrendingDown, Minus, Search, MousePointerClick,
  Eye, AlertTriangle, CheckCircle, Loader2, Zap, Bot,
  Activity, Target, Star, Sparkles, Globe, BarChart3,
  ArrowRight, Shield, ChevronRight
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

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.08, duration: 0.5, ease: [0.32, 0.72, 0, 1] }
  })
};

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

  const scoreColor = (s: number | null) => !s ? 'text-[#52525b]' : s >= 70 ? 'text-[#4ade80]' : s >= 50 ? 'text-[#fbbf24]' : 'text-[#f87171]';
  const scoreBg = (s: number | null) => !s ? 'from-[#1a1a1e]' : s >= 70 ? 'from-[#4ade80]/20' : s >= 50 ? 'from-[#fbbf24]/20' : 'from-[#f87171]/20';
  const scoreBorder = (s: number | null) => !s ? 'border-[#52525b]/20' : s >= 70 ? 'border-[#4ade80]/20' : s >= 50 ? 'border-[#fbbf24]/20' : 'border-[#f87171]/20';
  const changeIcon = (v: number) => v > 0 ? <TrendingUp className="w-3 h-3 text-[#4ade80]" /> : v < 0 ? <TrendingDown className="w-3 h-3 text-[#f87171]" /> : <Minus className="w-3 h-3 text-[#52525b]" />;
  const changeColor = (v: number) => v > 0 ? 'text-[#4ade80]' : v < 0 ? 'text-[#f87171]' : 'text-[#52525b]';
  const changeStr = (v: number) => v > 0 ? `+${v}` : String(v);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-2 border-[#7c6cf9]/20 border-t-[#7c6cf9] rounded-full animate-spin" />
    </div>
  );

  if (summaries.length === 0) return null;

  const totalKeywords = summaries.reduce((s, w) => s + w.total_keywords, 0);
  const totalClicks = summaries.reduce((s, w) => s + w.total_clicks, 0);
  const totalIssues = summaries.reduce((s, w) => s + w.total_issues, 0);
  const totalPending = summaries.reduce((s, w) => s + w.pending_fixes, 0);

  return (
    <div className="space-y-6">
      {/* Aggregate Summary Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { icon: Globe, label: 'Websites', value: String(summaries.length), color: 'text-[#7c6cf9]' },
          { icon: Search, label: 'Keywords Tracked', value: totalKeywords.toLocaleString(), color: 'text-[#4ade80]' },
          { icon: MousePointerClick, label: 'Total Clicks', value: totalClicks.toLocaleString(), color: 'text-[#60a5fa]' },
          { icon: AlertTriangle, label: 'Open Issues', value: String(totalIssues), color: totalIssues > 0 ? 'text-[#fbbf24]' : 'text-[#4ade80]' },
        ].map((s, i) => (
          <motion.div key={s.label} custom={i} variants={cardVariants} initial="hidden" animate="visible"
            className="card-liquid p-4">
            <div className="flex items-center gap-2 mb-2">
              <s.icon className={`w-4 h-4 ${s.color}`} />
              <span className="text-[#52525b] text-xs">{s.label}</span>
            </div>
            <p className="text-2xl font-bold text-[#f5f5f7] tracking-tight">{s.value}</p>
          </motion.div>
        ))}
      </div>

      {/* Per-Website Cards */}
      <div className="space-y-4">
        {summaries.map((site, idx) => (
          <motion.div key={site.id} custom={idx} variants={cardVariants} initial="hidden" animate="visible"
            onClick={() => onSelectWebsite(site.id)}
            className={`card-liquid cursor-pointer ${selectedWebsite === site.id ? 'border-[#7c6cf9]/30' : ''}`}>
            <div className="p-5">
              {/* Header Row */}
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div className={`w-12 h-12 rounded-2xl bg-gradient-to-br ${scoreBg(site.health_score)} to-transparent/20 flex items-center justify-center border ${scoreBorder(site.health_score)}`}>
                    <span className={`text-lg font-bold ${scoreColor(site.health_score)}`}>
                      {site.health_score ? Math.round(site.health_score) : '--'}
                    </span>
                  </div>
                  <div>
                    <h3 className="text-[#f5f5f7] font-semibold tracking-tight">{site.domain}</h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[10px] text-[#52525b] uppercase tracking-wider font-medium">{site.site_type}</span>
                      {site.autonomy_mode && site.autonomy_mode !== 'manual' && (
                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium border ${
                          site.autonomy_mode === 'ultra'
                            ? 'bg-[#4ade80]/10 text-[#4ade80] border-[#4ade80]/20'
                            : 'bg-[#7c6cf9]/10 text-[#7c6cf9] border-[#7c6cf9]/20'
                        }`}>
                          {site.autonomy_mode === 'ultra' ? 'Ultra' : 'Smart'}
                        </span>
                      )}
                      {site.last_audit && (
                        <span className="text-[10px] text-[#52525b]">Last audit: {new Date(site.last_audit).toLocaleDateString()}</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {site.score_change !== 0 && (
                    <div className={`flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border ${site.score_change > 0 ? 'bg-[#4ade80]/10 text-[#4ade80] border-[#4ade80]/20' : 'bg-[#f87171]/10 text-[#f87171] border-[#f87171]/20'}`}>
                      {changeIcon(site.score_change)}
                      <span className="font-medium">{changeStr(site.score_change)} pts</span>
                    </div>
                  )}
                  <ChevronRight className="w-4 h-4 text-[#52525b]" />
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div className="bg-white/[0.02] rounded-xl p-3 border border-white/[0.04]">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Search className="w-3 h-3 text-[#7c6cf9]" />
                    <span className="text-[#52525b] text-[10px] uppercase tracking-wider font-medium">Keywords</span>
                  </div>
                  <p className="text-[#f5f5f7] font-bold text-lg tracking-tight">{site.total_keywords.toLocaleString()}</p>
                  {site.keywords_change !== 0 && (
                    <p className={`text-[10px] ${changeColor(site.keywords_change)} mt-0.5`}>{changeStr(site.keywords_change)}</p>
                  )}
                </div>

                <div className="bg-white/[0.02] rounded-xl p-3 border border-white/[0.04]">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <MousePointerClick className="w-3 h-3 text-[#60a5fa]" />
                    <span className="text-[#52525b] text-[10px] uppercase tracking-wider font-medium">Clicks</span>
                  </div>
                  <p className="text-[#f5f5f7] font-bold text-lg tracking-tight">{site.total_clicks.toLocaleString()}</p>
                  {site.clicks_change !== 0 && (
                    <p className={`text-[10px] ${changeColor(site.clicks_change)} mt-0.5`}>{changeStr(site.clicks_change)}</p>
                  )}
                </div>

                <div className="bg-white/[0.02] rounded-xl p-3 border border-white/[0.04]">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <AlertTriangle className="w-3 h-3 text-[#fbbf24]" />
                    <span className="text-[#52525b] text-[10px] uppercase tracking-wider font-medium">Issues</span>
                  </div>
                  <p className="text-[#f5f5f7] font-bold text-lg tracking-tight">{site.total_issues}</p>
                  {site.issues_change !== 0 && (
                    <p className={`text-[10px] ${site.issues_change < 0 ? 'text-[#4ade80]' : 'text-[#f87171]'} mt-0.5`}>
                      {site.issues_change < 0 ? '' : '+'}{site.issues_change}
                    </p>
                  )}
                </div>

                <div className="bg-white/[0.02] rounded-xl p-3 border border-white/[0.04]">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Sparkles className="w-3 h-3 text-[#7c6cf9]" />
                    <span className="text-[#52525b] text-[10px] uppercase tracking-wider font-medium">Fixes</span>
                  </div>
                  <p className="text-[#f5f5f7] font-bold text-lg tracking-tight">{site.applied_fixes}</p>
                  {site.pending_fixes > 0 && (
                    <p className="text-[10px] text-[#fbbf24] mt-0.5">{site.pending_fixes} pending</p>
                  )}
                </div>

                <div className="bg-white/[0.02] rounded-xl p-3 border border-white/[0.04]">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <Target className="w-3 h-3 text-[#4ade80]" />
                    <span className="text-[#52525b] text-[10px] uppercase tracking-wider font-medium">Avg Pos</span>
                  </div>
                  <p className="text-[#f5f5f7] font-bold text-lg tracking-tight">{site.avg_position || '--'}</p>
                </div>
              </div>

              {/* Tracked Keywords Preview */}
              {site.tracked_keywords?.length > 0 && (
                <div className="mt-4 pt-4 border-t border-white/[0.04] flex items-center gap-3 overflow-x-auto">
                  <Star className="w-3 h-3 text-[#fbbf24] shrink-0" />
                  {site.tracked_keywords.map((tk, i) => (
                    <span key={i} className="text-[11px] bg-white/[0.03] text-[#a1a1aa] px-2.5 py-1 rounded-full whitespace-nowrap flex items-center gap-1.5 border border-white/[0.04]">
                      {tk.keyword}
                      {tk.position && <span className={`font-bold ${tk.position <= 10 ? 'text-[#4ade80]' : 'text-[#fbbf24]'}`}>#{tk.position}</span>}
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
