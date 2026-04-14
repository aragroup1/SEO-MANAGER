// frontend/components/CompetitorAnalysis.tsx
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Network, Clock, Loader2, Link2, AlertTriangle, ExternalLink,
  TrendingDown, RefreshCw, Target, Globe, FileText, ArrowRight,
  ChevronRight, Eye, Zap, Star, Shield, Unlink
} from 'lucide-react';

interface LinkNode {
  url: string; title: string; inbound: number; outbound: number;
  is_hub: boolean; is_orphan: boolean;
}

interface LinkSuggestion {
  from_url: string; to_url: string; anchor_text: string; reason: string;
}

interface LinkingResult {
  total_pages: number; total_internal_links: number;
  hubs: LinkNode[]; orphans: LinkNode[];
  suggestions: LinkSuggestion[];
  avg_links_per_page: number;
}

interface DecayItem {
  url: string; title: string; last_modified: string;
  days_since_update: number; decay_risk: string;
  current_position?: number; position_change?: number;
  recommendation: string; competitor_freshness?: string;
}

interface DecayResult {
  total_pages_analyzed: number;
  high_risk: DecayItem[]; medium_risk: DecayItem[]; low_risk: DecayItem[];
  refresh_recommendations: string[];
}

export default function CompetitorAnalysis({ websiteId }: { websiteId: number }) {
  const [activeTab, setActiveTab] = useState<'linking' | 'decay'>('linking');
  const [linkingData, setLinkingData] = useState<LinkingResult | null>(null);
  const [decayData, setDecayData] = useState<DecayResult | null>(null);
  const [linkingLoading, setLinkingLoading] = useState(false);
  const [decayLoading, setDecayLoading] = useState(false);
  const [expandedOrphan, setExpandedOrphan] = useState<string | null>(null);

  const API = process.env.NEXT_PUBLIC_API_URL || '';

  const runLinking = async () => {
    setLinkingLoading(true); setLinkingData(null);
    try {
      const r = await fetch(`${API}/api/linking/${websiteId}/analyze`, { method: 'POST' });
      if (r.ok) { const d = await r.json(); if (!d.error) setLinkingData(d); }
    } catch {} finally { setLinkingLoading(false); }
  };

  const runDecay = async () => {
    setDecayLoading(true); setDecayData(null);
    try {
      const r = await fetch(`${API}/api/decay/${websiteId}/analyze`, { method: 'POST' });
      if (r.ok) { const d = await r.json(); if (!d.error) setDecayData(d); }
    } catch {} finally { setDecayLoading(false); }
  };

  const riskColor = (risk: string) => {
    if (risk === 'high') return 'text-red-400 bg-red-500/20';
    if (risk === 'medium') return 'text-yellow-400 bg-yellow-500/20';
    return 'text-green-400 bg-green-500/20';
  };

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-bold text-white flex items-center gap-3">
          <div className="w-9 h-9 bg-gradient-to-br from-orange-500 to-red-500 rounded-lg flex items-center justify-center">
            <Network className="w-5 h-5 text-white" />
          </div>
          Site Intelligence
        </h2>
        <p className="text-gray-400 mt-1 text-sm">Internal linking structure and content freshness analysis</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {[
          { id: 'linking' as const, label: 'Hub & Spoke Linking', icon: Network },
          { id: 'decay' as const, label: 'Content Decay', icon: Clock },
        ].map(t => (
          <button key={t.id} onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === t.id ? 'bg-orange-500/30 text-white border border-orange-500/50' : 'bg-white/5 text-gray-400 hover:bg-white/10 border border-transparent'
            }`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {/* ═══ HUB & SPOKE LINKING ═══ */}
      {activeTab === 'linking' && (
        <div className="space-y-4">
          {!linkingData && !linkingLoading && (
            <div className="bg-white/5 rounded-2xl p-10 border border-white/10 text-center">
              <Network className="w-14 h-14 text-orange-400 mx-auto mb-4 opacity-60" />
              <h3 className="text-xl font-bold text-white mb-2">Analyze Internal Linking</h3>
              <p className="text-gray-400 text-sm mb-6 max-w-md mx-auto">
                Crawls your site to map the internal link graph. Finds hub pages, orphaned pages, and suggests new links to build topical authority.
              </p>
              <button onClick={runLinking}
                className="bg-gradient-to-r from-orange-500 to-red-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg transition-all">
                Run Link Analysis
              </button>
            </div>
          )}

          {linkingLoading && (
            <div className="bg-orange-500/10 rounded-xl p-8 text-center border border-orange-500/20">
              <Loader2 className="w-10 h-10 text-orange-400 animate-spin mx-auto mb-4" />
              <p className="text-white font-medium">Crawling site and mapping internal links...</p>
              <p className="text-gray-400 text-sm mt-1">This may take 30-60 seconds</p>
            </div>
          )}

          {linkingData && (
            <div className="space-y-4">
              {/* Summary stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { l: 'Pages Crawled', v: linkingData.total_pages, c: 'text-white' },
                  { l: 'Internal Links', v: linkingData.total_internal_links, c: 'text-blue-400' },
                  { l: 'Hub Pages', v: linkingData.hubs?.length || 0, c: 'text-green-400' },
                  { l: 'Orphan Pages', v: linkingData.orphans?.length || 0, c: 'text-red-400' },
                ].map(s => (
                  <div key={s.l} className="bg-white/5 rounded-xl p-4 text-center border border-white/10">
                    <p className={`text-2xl font-bold ${s.c}`}>{s.v}</p>
                    <p className="text-[10px] text-gray-500 mt-1">{s.l}</p>
                  </div>
                ))}
              </div>

              {/* Avg links per page */}
              <div className="bg-white/5 rounded-lg px-4 py-2 border border-white/10 flex items-center justify-between">
                <span className="text-gray-400 text-sm">Avg links per page</span>
                <span className={`font-bold ${(linkingData.avg_links_per_page || 0) >= 3 ? 'text-green-400' : 'text-yellow-400'}`}>
                  {(linkingData.avg_links_per_page || 0).toFixed(1)}
                </span>
              </div>

              {/* Hub Pages */}
              {linkingData.hubs?.length > 0 && (
                <div className="bg-green-500/5 rounded-xl p-5 border border-green-500/20">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                    <Star className="w-5 h-5 text-green-400" /> Hub Pages (Strong Authority)
                  </h3>
                  {linkingData.hubs.slice(0, 10).map((hub, i) => (
                    <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2 mb-1.5">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <Star className="w-3.5 h-3.5 text-green-400 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-white text-sm truncate">{hub.title || hub.url}</p>
                          <p className="text-gray-500 text-[10px] truncate">{hub.url}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0 ml-3">
                        <span className="text-green-400 text-xs">{hub.inbound} in</span>
                        <span className="text-blue-400 text-xs">{hub.outbound} out</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Orphan Pages */}
              {linkingData.orphans?.length > 0 && (
                <div className="bg-red-500/5 rounded-xl p-5 border border-red-500/20">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                    <Unlink className="w-5 h-5 text-red-400" /> Orphan Pages (No Internal Links)
                  </h3>
                  <p className="text-gray-400 text-xs mb-3">These pages have no or very few internal links pointing to them. Search engines may not discover or value them.</p>
                  {linkingData.orphans.slice(0, 15).map((orphan, i) => (
                    <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2 mb-1.5">
                      <div className="min-w-0 flex-1">
                        <p className="text-white text-sm truncate">{orphan.title || orphan.url}</p>
                        <p className="text-gray-500 text-[10px] truncate">{orphan.url}</p>
                      </div>
                      <span className="text-red-400 text-xs shrink-0 ml-2">{orphan.inbound} links in</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Link Suggestions */}
              {linkingData.suggestions?.length > 0 && (
                <div className="bg-purple-500/5 rounded-xl p-5 border border-purple-500/20">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                    <Link2 className="w-5 h-5 text-purple-400" /> Suggested Internal Links
                  </h3>
                  {linkingData.suggestions.slice(0, 10).map((sug, i) => (
                    <div key={i} className="bg-white/5 rounded-lg p-3 mb-2">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-gray-300 truncate flex-1">{sug.from_url}</span>
                        <ArrowRight className="w-3 h-3 text-purple-400 shrink-0" />
                        <span className="text-purple-400 truncate flex-1">{sug.to_url}</span>
                      </div>
                      <div className="flex items-center gap-3 mt-1.5">
                        <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded">"{sug.anchor_text}"</span>
                        <span className="text-gray-500 text-xs">{sug.reason}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <button onClick={runLinking} className="w-full bg-white/5 text-gray-400 py-2.5 rounded-lg text-sm hover:bg-white/10 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4" /> Re-analyze
              </button>
            </div>
          )}
        </div>
      )}

      {/* ═══ CONTENT DECAY ═══ */}
      {activeTab === 'decay' && (
        <div className="space-y-4">
          {!decayData && !decayLoading && (
            <div className="bg-white/5 rounded-2xl p-10 border border-white/10 text-center">
              <Clock className="w-14 h-14 text-yellow-400 mx-auto mb-4 opacity-60" />
              <h3 className="text-xl font-bold text-white mb-2">Detect Content Decay</h3>
              <p className="text-gray-400 text-sm mb-6 max-w-md mx-auto">
                Checks page freshness, identifies content that's losing rankings, and recommends updates to regain positions.
              </p>
              <button onClick={runDecay}
                className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg transition-all">
                Run Decay Analysis
              </button>
            </div>
          )}

          {decayLoading && (
            <div className="bg-yellow-500/10 rounded-xl p-8 text-center border border-yellow-500/20">
              <Loader2 className="w-10 h-10 text-yellow-400 animate-spin mx-auto mb-4" />
              <p className="text-white font-medium">Analyzing content freshness...</p>
            </div>
          )}

          {decayData && (
            <div className="space-y-4">
              {/* Summary */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { l: 'Pages Analyzed', v: decayData.total_pages_analyzed, c: 'text-white' },
                  { l: 'High Risk', v: decayData.high_risk?.length || 0, c: 'text-red-400' },
                  { l: 'Medium Risk', v: decayData.medium_risk?.length || 0, c: 'text-yellow-400' },
                  { l: 'Low Risk', v: decayData.low_risk?.length || 0, c: 'text-green-400' },
                ].map(s => (
                  <div key={s.l} className="bg-white/5 rounded-xl p-4 text-center border border-white/10">
                    <p className={`text-2xl font-bold ${s.c}`}>{s.v}</p>
                    <p className="text-[10px] text-gray-500 mt-1">{s.l}</p>
                  </div>
                ))}
              </div>

              {/* Decay items by risk */}
              {['high', 'medium', 'low'].map(risk => {
                const items: DecayItem[] = risk === 'high' ? (decayData.high_risk || []) : risk === 'medium' ? (decayData.medium_risk || []) : (decayData.low_risk || []);
                if (!items.length) return null;
                const colors = { high: { bg: 'bg-red-500/5', border: 'border-red-500/20', text: 'text-red-400', icon: AlertTriangle },
                  medium: { bg: 'bg-yellow-500/5', border: 'border-yellow-500/20', text: 'text-yellow-400', icon: Clock },
                  low: { bg: 'bg-green-500/5', border: 'border-green-500/20', text: 'text-green-400', icon: Shield } };
                const c = colors[risk as keyof typeof colors];
                const Icon = c.icon;
                return (
                  <div key={risk} className={`${c.bg} rounded-xl p-5 ${c.border} border`}>
                    <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                      <Icon className={`w-5 h-5 ${c.text}`} /> {risk.charAt(0).toUpperCase() + risk.slice(1)} Risk ({items.length})
                    </h3>
                    {items.slice(0, 8).map((item, i) => (
                      <div key={i} className="bg-white/5 rounded-lg p-3 mb-2">
                        <div className="flex items-start justify-between">
                          <div className="min-w-0 flex-1">
                            <p className="text-white text-sm truncate">{item.title || item.url}</p>
                            <p className="text-gray-500 text-[10px] truncate">{item.url}</p>
                          </div>
                          <div className="flex items-center gap-2 shrink-0 ml-3">
                            <span className={`text-xs px-1.5 py-0.5 rounded ${riskColor(item.decay_risk)}`}>{item.days_since_update}d old</span>
                            {item.position_change && item.position_change < 0 && (
                              <span className="text-red-400 text-xs flex items-center gap-0.5">
                                <TrendingDown className="w-3 h-3" /> {Math.abs(item.position_change)}
                              </span>
                            )}
                          </div>
                        </div>
                        <p className="text-gray-400 text-xs mt-1.5">{item.recommendation}</p>
                      </div>
                    ))}
                  </div>
                );
              })}

              {/* Refresh recommendations */}
              {decayData.refresh_recommendations?.length > 0 && (
                <div className="bg-purple-500/10 rounded-xl p-5 border border-purple-500/20">
                  <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
                    <Zap className="w-5 h-5 text-purple-400" /> AI Recommendations
                  </h3>
                  {decayData.refresh_recommendations.map((rec, i) => (
                    <div key={i} className="flex items-start gap-2 mb-2">
                      <span className="text-purple-400 text-xs font-bold bg-purple-500/20 px-1.5 py-0.5 rounded shrink-0">{i+1}</span>
                      <p className="text-gray-300 text-sm">{rec}</p>
                    </div>
                  ))}
                </div>
              )}

              <button onClick={runDecay} className="w-full bg-white/5 text-gray-400 py-2.5 rounded-lg text-sm hover:bg-white/10 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4" /> Re-analyze
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
