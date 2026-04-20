// frontend/components/GEODashboard.tsx
'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, Loader2, RefreshCw, Target, Shield, Clock,
  FileText, Quote, User, AlertTriangle, CheckCircle,
  Search, ExternalLink, Sparkles, TrendingUp, Zap,
  MessageSquare, Globe
} from 'lucide-react';

interface GEOScores {
  overall: number;
  content_structure: number;
  schema_data: number;
  authority_trust: number;
  freshness: number;
  citability: number;
  signals: Record<string, any>;
  avg_word_count: number;
}

interface PageDetail {
  url: string;
  title: string;
  word_count: number;
  signals: Record<string, any>;
}

interface Recommendation {
  priority: number;
  title: string;
  description: string;
  category: string;
  impact: string;
  effort: string;
}

interface GEOAudit {
  domain: string;
  pages_analyzed: number;
  scores: GEOScores;
  page_details: PageDetail[];
  recommendations: Recommendation[];
  audit_date: string;
}

export default function GEODashboard({ websiteId }: { websiteId: number }) {
  const [audit, setAudit] = useState<GEOAudit | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Citation tester
  const [testQuery, setTestQuery] = useState('');
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  useEffect(() => {
    setAudit(null); setError('');
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${API_URL}/api/geo/${websiteId}/saved`);
        if (!r.ok || cancelled) return;
        const d = await r.json();
        if (!cancelled && d.audit) setAudit(d.audit);
      } catch {}
    })();
    return () => { cancelled = true; };
  }, [websiteId, API_URL]);

  const runAudit = async () => {
    setLoading(true);
    setError('');
    try {
      const r = await fetch(`${API_URL}/api/geo/${websiteId}/audit`, { method: 'POST' });
      if (r.ok) {
        const data = await r.json();
        if (data.error) { setError(data.error); }
        else { setAudit(data); }
      }
    } catch (err) {
      setError('Failed to run GEO audit');
    } finally {
      setLoading(false);
    }
  };

  const testCitation = async () => {
    if (!testQuery.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const r = await fetch(`${API_URL}/api/geo/${websiteId}/test-citation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: testQuery })
      });
      if (r.ok) {
        const data = await r.json();
        setTestResult(data);
      }
    } catch (err) {
      console.error('Citation test error:', err);
    } finally {
      setTesting(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return 'text-green-400';
    if (score >= 40) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getScoreBg = (score: number) => {
    if (score >= 70) return 'from-green-500';
    if (score >= 40) return 'from-yellow-500';
    return 'from-red-500';
  };

  const getCategoryIcon = (cat: string) => {
    switch (cat) {
      case 'content_structure': return <FileText className="w-4 h-4" />;
      case 'schema': return <Zap className="w-4 h-4" />;
      case 'authority': return <Shield className="w-4 h-4" />;
      case 'freshness': return <Clock className="w-4 h-4" />;
      case 'citability': return <Quote className="w-4 h-4" />;
      default: return <Brain className="w-4 h-4" />;
    }
  };

  // No audit yet
  if (!audit && !loading) {
    return (
      <div className="space-y-6">
        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
          <div className="w-20 h-20 bg-gradient-to-br from-cyan-500/20 to-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            <Brain className="w-10 h-10 text-cyan-400" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-3">AI Search Optimization (GEO)</h2>
          <p className="text-purple-300 mb-2 max-w-lg mx-auto">
            Analyze how well your site is optimized for AI search engines like ChatGPT, Perplexity, and Google AI Overviews.
          </p>
          <p className="text-gray-500 text-sm mb-6 max-w-lg mx-auto">
            GEO measures: structured data, FAQ schema, citability, authority signals, content structure, and freshness — the factors AI models use when deciding which sources to reference.
          </p>
          {error && <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-4 max-w-lg mx-auto"><p className="text-red-400 text-sm">{error}</p></div>}
          <button onClick={runAudit}
            className="bg-gradient-to-r from-cyan-500 to-purple-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg hover:shadow-cyan-500/25 transition-all text-lg">
            Run GEO Audit
          </button>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-xl p-8 text-center">
        <Loader2 className="w-10 h-10 text-cyan-400 animate-spin mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-white mb-2">Running GEO Audit...</h3>
        <p className="text-purple-300 text-sm">Analyzing your site for AI search readiness. This takes 15-30 seconds.</p>
      </div>
    );
  }

  if (!audit) return null;

  const scores = audit.scores;
  const categories = [
    { key: 'content_structure', label: 'Content Structure', icon: FileText, desc: 'Q&A format, direct answers, lists, tables' },
    { key: 'schema_data', label: 'Schema & Structured Data', icon: Zap, desc: 'FAQ, HowTo, Article, Organization schema' },
    { key: 'authority_trust', label: 'Authority & Trust', icon: Shield, desc: 'Author bylines, citations, about page, E-E-A-T' },
    { key: 'freshness', label: 'Freshness', icon: Clock, desc: 'Published dates, updated timestamps' },
    { key: 'citability', label: 'Citability', icon: Quote, desc: 'Statistics, data, depth, direct answers' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <Brain className="w-6 h-6 text-cyan-400" /> AI Search Optimization
          </h2>
          <p className="text-purple-300 mt-1 text-sm">
            GEO readiness for {audit.domain} · {audit.pages_analyzed} pages analyzed
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={async () => {
            try {
              await fetch(`${API_URL}/api/geo/${websiteId}/scan-fixes`, { method: 'POST' });
              alert('GEO fix scan started. Check Issues & Fixes for proposals.');
            } catch {}
          }}
            className="bg-gradient-to-r from-yellow-500/20 to-orange-500/20 text-yellow-400 px-4 py-2 rounded-lg font-medium hover:from-yellow-500/30 hover:to-orange-500/30 transition-all flex items-center gap-2 border border-yellow-500/30">
            <Sparkles className="w-4 h-4" />
            Generate GEO Fixes
          </button>
          <button onClick={runAudit} disabled={loading}
            className="bg-gradient-to-r from-cyan-500 to-purple-500 text-white px-4 py-2 rounded-lg font-medium hover:shadow-lg transition-all flex items-center gap-2 disabled:opacity-50">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            Re-run Audit
          </button>
        </div>
      </div>

      {/* Overall Score */}
      <div className="bg-gradient-to-r from-cyan-500/10 to-purple-500/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
        <div className="flex items-center gap-8">
          <div className="text-center">
            <div className="relative inline-flex items-center justify-center">
              <svg className="w-28 h-28 transform -rotate-90">
                <circle cx="56" cy="56" r="48" stroke="rgba(255,255,255,0.1)" strokeWidth="10" fill="none" />
                <circle cx="56" cy="56" r="48" stroke="url(#geoGrad)" strokeWidth="10" fill="none"
                  strokeDasharray={`${(scores.overall / 100) * 301.6} 301.6`} strokeLinecap="round" />
                <defs><linearGradient id="geoGrad"><stop offset="0%" stopColor="#06b6d4" /><stop offset="100%" stopColor="#a855f7" /></linearGradient></defs>
              </svg>
              <div className="absolute">
                <p className={`text-3xl font-bold ${getScoreColor(scores.overall)}`}>{scores.overall}</p>
                <p className="text-[10px] text-gray-400">GEO Score</p>
              </div>
            </div>
          </div>
          <div className="flex-1 grid grid-cols-5 gap-3">
            {categories.map(cat => {
              const score = (scores as any)[cat.key] || 0;
              return (
                <div key={cat.key} className="text-center">
                  <cat.icon className="w-4 h-4 text-gray-400 mx-auto mb-1" />
                  <p className={`text-xl font-bold ${getScoreColor(score)}`}>{score}</p>
                  <p className="text-[10px] text-gray-500 leading-tight">{cat.label}</p>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Category Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
        {categories.map(cat => {
          const score = (scores as any)[cat.key] || 0;
          return (
            <div key={cat.key} className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20">
              <div className="flex items-center gap-2 mb-2">
                <cat.icon className={`w-4 h-4 ${getScoreColor(score)}`} />
                <h4 className="text-white text-xs font-medium">{cat.label}</h4>
              </div>
              <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden mb-2">
                <div className={`h-full rounded-full bg-gradient-to-r ${getScoreBg(score)} to-transparent`}
                  style={{ width: `${score}%` }} />
              </div>
              <p className="text-gray-500 text-[10px]">{cat.desc}</p>
            </div>
          );
        })}
      </div>

      {/* AI Citation Tester */}
      <div className="bg-white/10 backdrop-blur-md rounded-xl p-5 border border-white/20">
        <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-cyan-400" /> AI Citation Tester
        </h3>
        <p className="text-gray-400 text-sm mb-3">Test if AI models mention your site when asked a question. Enter a query your customers might ask.</p>
        <div className="flex gap-3">
          <input type="text" placeholder="e.g. Where can I buy barcodes in the UK?" value={testQuery} onChange={e => setTestQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && testCitation()}
            className="flex-1 bg-white/10 border border-white/20 rounded-lg px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500" />
          <button onClick={testCitation} disabled={testing || !testQuery.trim()}
            className="bg-gradient-to-r from-cyan-500 to-purple-500 text-white px-5 py-2.5 rounded-lg font-medium hover:shadow-lg transition-all disabled:opacity-50 flex items-center gap-2">
            {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Test
          </button>
        </div>

        {testResult && (
          <div className={`mt-4 p-4 rounded-lg border ${testResult.is_cited ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'}`}>
            <div className="flex items-center gap-2 mb-2">
              {testResult.is_cited
                ? <><CheckCircle className="w-5 h-5 text-green-400" /><span className="text-green-400 font-medium">Your site was cited!</span></>
                : <><AlertTriangle className="w-5 h-5 text-red-400" /><span className="text-red-400 font-medium">Your site was not cited</span></>
              }
            </div>
            {testResult.ai_response_preview && (
              <p className="text-gray-300 text-sm mt-2 leading-relaxed">{testResult.ai_response_preview}</p>
            )}
          </div>
        )}
      </div>

      {/* Recommendations */}
      {audit.recommendations.length > 0 && (
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-5 border border-white/20">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-yellow-400" /> GEO Recommendations
          </h3>
          <div className="space-y-3">
            {audit.recommendations.map((rec, i) => (
              <div key={i} className="bg-white/5 rounded-lg p-4 border border-white/10">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded font-bold">#{rec.priority}</span>
                  {getCategoryIcon(rec.category)}
                  <span className={`text-xs px-2 py-0.5 rounded ${rec.impact === 'high' ? 'bg-green-500/20 text-green-400' : rec.impact === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-gray-500/20 text-gray-400'}`}>
                    {rec.impact} impact
                  </span>
                  <span className="text-xs text-gray-500">{rec.effort === 'quick_win' ? '⚡ Quick win' : rec.effort === 'medium' ? '🔧 Medium effort' : '🏗️ Major project'}</span>
                </div>
                <h4 className="text-white font-medium text-sm">{rec.title}</h4>
                <p className="text-gray-400 text-sm mt-1">{rec.description}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Page Details */}
      {audit.page_details.length > 0 && (
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-5 border border-white/20">
          <h3 className="text-white font-semibold mb-3 text-sm">Pages Analyzed</h3>
          <div className="space-y-2">
            {audit.page_details.map((page, i) => (
              <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2">
                <div className="min-w-0 flex-1">
                  <p className="text-white text-sm truncate">{page.title || page.url}</p>
                  <p className="text-gray-500 text-xs truncate">{page.url}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-3 text-xs">
                  <span className="text-gray-400">{page.word_count} words</span>
                  {page.signals.has_faq_schema && <span className="text-green-400">FAQ ✓</span>}
                  {page.signals.has_statistics && <span className="text-blue-400">Stats ✓</span>}
                  {page.signals.has_author_byline && <span className="text-purple-400">Author ✓</span>}
                  {page.signals.has_direct_answers && <span className="text-cyan-400">Answers ✓</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
