'use client';

import { useEffect, useState } from 'react';
import { Globe, TrendingUp, TrendingDown, AlertCircle, Wand2, Trophy, Search, Loader2 } from 'lucide-react';

interface SiteSummary {
  id: number;
  domain: string;
  site_type: string;
  health_score: number | null;
  score_change: number;
  total_issues: number;
  critical_issues: number;
  issues_change: number;
  total_keywords: number;
  total_clicks: number;
  avg_position: number;
  keywords_change: number;
  clicks_change: number;
  pending_fixes: number;
  applied_fixes: number;
  tracked_count: number;
  tracked_keywords: { keyword: string; position: number | null; clicks: number }[];
  autonomy_mode: string;
  last_audit: string | null;
}

interface Props {
  onSelectWebsite: (id: number) => void;
}

export default function PortfolioOverview({ onSelectWebsite }: Props) {
  const [sites, setSites] = useState<SiteSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_URL}/api/overview`);
        if (r.ok) {
          const d = await r.json();
          setSites(d.websites || []);
        }
      } catch { /* offline */ }
      finally { setLoading(false); }
    })();
  }, [API_URL]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[40vh]">
        <Loader2 className="w-6 h-6 text-[#7c6cf9] animate-spin" />
      </div>
    );
  }

  if (sites.length === 0) {
    return (
      <div className="card-liquid p-12 text-center">
        <Globe className="w-12 h-12 text-[#7c6cf9] mx-auto mb-4" />
        <h3 className="text-xl font-bold text-[#f5f5f7] mb-2">No Sites in Portfolio</h3>
        <p className="text-[#52525b]">Add a website to start tracking.</p>
      </div>
    );
  }

  // ─── Portfolio totals ───
  const totalSites = sites.length;
  const avgHealth = sites.filter(s => s.health_score != null).reduce((a, s) => a + (s.health_score || 0), 0) / Math.max(1, sites.filter(s => s.health_score != null).length);
  const totalPending = sites.reduce((a, s) => a + (s.pending_fixes || 0), 0);
  const totalKeywords = sites.reduce((a, s) => a + (s.total_keywords || 0), 0);
  const totalClicks = sites.reduce((a, s) => a + (s.total_clicks || 0), 0);

  return (
    <div className="space-y-6">
      {/* Portfolio header */}
      <div>
        <h1 className="text-2xl font-bold text-[#f5f5f7] tracking-tight">Portfolio Overview</h1>
        <p className="text-[#52525b] text-sm mt-1">All {totalSites} sites at a glance — health, pending fixes, rank changes.</p>
      </div>

      {/* Roll-up stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <StatCard label="Sites" value={String(totalSites)} />
        <StatCard label="Avg Health" value={avgHealth ? Math.round(avgHealth).toString() : '—'} tone={avgHealth >= 70 ? 'good' : avgHealth >= 50 ? 'warn' : 'bad'} />
        <StatCard label="Pending Fixes" value={String(totalPending)} tone={totalPending > 0 ? 'warn' : 'good'} />
        <StatCard label="Total Keywords" value={totalKeywords.toLocaleString()} />
        <StatCard label="Total Clicks" value={totalClicks.toLocaleString()} />
      </div>

      {/* Per-site grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {sites.map(s => <SiteCard key={s.id} site={s} onSelect={() => onSelectWebsite(s.id)} />)}
      </div>
    </div>
  );
}

function StatCard({ label, value, tone }: { label: string; value: string; tone?: 'good' | 'warn' | 'bad' }) {
  const color = tone === 'good' ? 'text-[#4ade80]' : tone === 'warn' ? 'text-[#fbbf24]' : tone === 'bad' ? 'text-[#f87171]' : 'text-[#f5f5f7]';
  return (
    <div className="card-liquid p-4">
      <p className="text-[10px] text-[#52525b] uppercase tracking-wider font-medium">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
  );
}

function SiteCard({ site, onSelect }: { site: SiteSummary; onSelect: () => void }) {
  const health = site.health_score;
  const healthColor = health == null ? 'text-[#52525b]' : health >= 70 ? 'text-[#4ade80]' : health >= 50 ? 'text-[#fbbf24]' : 'text-[#f87171]';
  const healthDot = health == null ? 'bg-[#52525b]' : health >= 70 ? 'bg-[#4ade80]' : health >= 50 ? 'bg-[#fbbf24]' : 'bg-[#f87171]';
  const scoreUp = (site.score_change || 0) > 0;
  const clicksUp = (site.clicks_change || 0) > 0;

  // Top tracked keyword rank delta (most recent vs target)
  const topTracked = site.tracked_keywords?.[0];

  return (
    <button onClick={onSelect}
      className="card-liquid p-5 text-left hover:bg-white/[0.02] transition-all group">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2 min-w-0">
          <div className={`w-2 h-2 rounded-full shrink-0 ${healthDot}`} />
          <p className="text-[#f5f5f7] font-semibold text-sm truncate">{site.domain}</p>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-[#52525b] font-medium shrink-0 ml-2">
          {site.site_type}
        </span>
      </div>

      {/* Health score */}
      <div className="flex items-end gap-2 mb-4">
        <span className={`text-4xl font-bold ${healthColor}`}>{health != null ? Math.round(health) : '—'}</span>
        {site.score_change !== 0 && (
          <span className={`flex items-center gap-0.5 text-xs font-medium pb-1.5 ${scoreUp ? 'text-[#4ade80]' : 'text-[#f87171]'}`}>
            {scoreUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
            {Math.abs(site.score_change)}
          </span>
        )}
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-3 gap-2 text-center mb-3">
        <Metric icon={<AlertCircle className="w-3 h-3" />} label="Issues" value={site.total_issues} accent={site.critical_issues > 0 ? 'bad' : undefined} />
        <Metric icon={<Wand2 className="w-3 h-3" />} label="Pending" value={site.pending_fixes} accent={site.pending_fixes > 0 ? 'warn' : undefined} />
        <Metric icon={<Search className="w-3 h-3" />} label="Keywords" value={site.total_keywords} />
      </div>

      {/* Clicks change */}
      {site.total_clicks > 0 && (
        <div className="flex items-center justify-between text-xs pt-3 border-t border-white/[0.06]">
          <span className="text-[#52525b]">Clicks</span>
          <span className="flex items-center gap-1 text-[#a1a1aa] font-medium">
            {site.total_clicks.toLocaleString()}
            {site.clicks_change !== 0 && (
              <span className={clicksUp ? 'text-[#4ade80]' : 'text-[#f87171]'}>
                {clicksUp ? '+' : ''}{site.clicks_change}
              </span>
            )}
          </span>
        </div>
      )}

      {/* Top tracked keyword */}
      {topTracked && (
        <div className="flex items-center justify-between text-xs mt-2 pt-2 border-t border-white/[0.06]">
          <span className="flex items-center gap-1 text-[#52525b] truncate">
            <Trophy className="w-3 h-3 shrink-0" />
            <span className="truncate">{topTracked.keyword}</span>
          </span>
          <span className={`shrink-0 ml-2 font-bold ${
            topTracked.position == null ? 'text-[#52525b]' :
            topTracked.position <= 3 ? 'text-[#4ade80]' :
            topTracked.position <= 10 ? 'text-[#fbbf24]' : 'text-[#a1a1aa]'
          }`}>
            #{topTracked.position ?? '—'}
          </span>
        </div>
      )}
    </button>
  );
}

function Metric({ icon, label, value, accent }: { icon: React.ReactNode; label: string; value: number; accent?: 'warn' | 'bad' }) {
  const color = accent === 'bad' ? 'text-[#f87171]' : accent === 'warn' ? 'text-[#fbbf24]' : 'text-[#f5f5f7]';
  return (
    <div className="bg-white/[0.02] rounded-lg py-2">
      <div className="flex items-center justify-center gap-1 text-[#52525b] text-[10px] mb-0.5">
        {icon}<span className="uppercase tracking-wider">{label}</span>
      </div>
      <p className={`text-sm font-semibold ${color}`}>{value}</p>
    </div>
  );
}
