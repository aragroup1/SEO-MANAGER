// frontend/components/ImageOptimizer.tsx — Image SEO & Performance Audit
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Image, AlertTriangle, CheckCircle, RefreshCw, Loader2, Eye, FileImage, Layers, Zap } from 'lucide-react';

interface ImageIssue {
  page_url: string; image_url: string; alt_text: string | null;
  format: string | null; severity: string; code: string;
  message: string; fix: string;
}

interface ImageStats {
  has_data: boolean; total_images: number; missing_alt: number;
  no_dimensions: number; wrong_format: number; no_lazy_loading: number;
  bad_filenames: number; score: number; last_checked: string | null;
}

interface Props { websiteId: number; }

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

const severityColor = (s: string) => {
  if (s === 'error') return 'text-[#f87171]';
  if (s === 'warning') return 'text-[#fbbf24]';
  return 'text-[#52525b]';
};
const severityBg = (s: string) => {
  if (s === 'error') return 'bg-[#f87171]/10 border-[#f87171]/20';
  if (s === 'warning') return 'bg-[#fbbf24]/10 border-[#fbbf24]/20';
  return 'bg-[#1a1a1e] border-white/[0.06]';
};

export default function ImageOptimizer({ websiteId }: Props) {
  const [stats, setStats] = useState<ImageStats | null>(null);
  const [issues, setIssues] = useState<ImageIssue[]>([]);
  const [loading, setLoading] = useState(true);
  const [auditing, setAuditing] = useState(false);
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, issuesRes] = await Promise.all([
        fetch(`${API_URL}/api/images/${websiteId}/stats`),
        fetch(`${API_URL}/api/images/${websiteId}/issues?limit=100`),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      if (issuesRes.ok) {
        const data = await issuesRes.json();
        setIssues(data.issues || []);
      }
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const runAudit = async () => {
    setAuditing(true);
    try {
      await fetch(`${API_URL}/api/images/${websiteId}/audit`, { method: 'POST' });
      await fetchData();
    } catch (e) { console.error(e); }
    setAuditing(false);
  };

  useEffect(() => { fetchData(); }, [websiteId]);

  const filteredIssues = activeFilter
    ? issues.filter(i => i.code === activeFilter)
    : issues;

  const issueTypes = [
    { code: 'missing_alt', label: 'Missing Alt', count: stats?.missing_alt || 0, icon: Eye },
    { code: 'no_dimensions', label: 'No Dimensions', count: stats?.no_dimensions || 0, icon: Layers },
    { code: 'wrong_format', label: 'Wrong Format', count: stats?.wrong_format || 0, icon: FileImage },
    { code: 'no_lazy_loading', label: 'No Lazy Load', count: stats?.no_lazy_loading || 0, icon: Zap },
    { code: 'bad_filename', label: 'Bad Filename', count: stats?.bad_filenames || 0, icon: AlertTriangle },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-[#f5f5f7]">Image Optimizer</h2>
          <p className="text-[#52525b] text-sm mt-1">Audit images for SEO and performance issues</p>
        </div>
        <button onClick={runAudit} disabled={auditing} className="px-4 py-2 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors flex items-center gap-2 disabled:opacity-50">
          {auditing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {auditing ? 'Auditing...' : 'Run Audit'}
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-[#7c6cf9] animate-spin" />
        </div>
      ) : !stats?.has_data ? (
        <div className="text-center py-16">
          <Image className="w-12 h-12 text-[#52525b] mx-auto mb-4" />
          <p className="text-[#f5f5f7] font-medium">No image audit data</p>
          <p className="text-[#52525b] text-sm mt-1">Run an audit to check your images</p>
          <button onClick={runAudit} className="mt-4 px-5 py-2 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors">
            Run First Audit
          </button>
        </div>
      ) : (
        <>
          {/* Score Card */}
          <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-6">
            <div className="flex items-center gap-6">
              <div className="relative w-20 h-20">
                <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
                  <circle cx="40" cy="40" r="34" fill="none" stroke="#1a1a1e" strokeWidth="6" />
                  <circle cx="40" cy="40" r="34" fill="none" stroke={stats.score >= 70 ? '#4ade80' : stats.score >= 50 ? '#fbbf24' : '#f87171'} strokeWidth="6"
                    strokeDasharray={`${(stats.score / 100) * 214} 214`} strokeLinecap="round" />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className={`text-xl font-bold ${stats.score >= 70 ? 'text-[#4ade80]' : stats.score >= 50 ? 'text-[#fbbf24]' : 'text-[#f87171]'}`}>{stats.score}</span>
                </div>
              </div>
              <div>
                <p className="text-[#f5f5f7] font-medium">Image Optimization Score</p>
                <p className="text-[#52525b] text-sm">{stats.total_images} images analyzed</p>
                {stats.last_checked && <p className="text-[#52525b] text-xs mt-1">Last checked: {new Date(stats.last_checked).toLocaleDateString()}</p>}
              </div>
            </div>
          </div>

          {/* Issue Type Filters */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {issueTypes.map(type => (
              <button
                key={type.code}
                onClick={() => setActiveFilter(activeFilter === type.code ? null : type.code)}
                className={`rounded-xl border p-4 text-left transition-colors ${activeFilter === type.code ? 'border-[#7c6cf9]/40 bg-[#7c6cf9]/10' : 'border-white/[0.06] bg-[#0a0a0c]/40 hover:bg-[#0f0f12]'}`}
              >
                <type.icon className={`w-5 h-5 mb-2 ${type.count > 0 ? 'text-[#fbbf24]' : 'text-[#4ade80]'}`} />
                <p className="text-[#f5f5f7] text-lg font-semibold">{type.count}</p>
                <p className="text-[#52525b] text-xs">{type.label}</p>
              </button>
            ))}
          </div>

          {/* Issues List */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-[#f5f5f7] text-sm font-medium">Issues {activeFilter ? `(${filteredIssues.length})` : `(${issues.length})`}</h3>
              {activeFilter && (
                <button onClick={() => setActiveFilter(null)} className="text-[#7c6cf9] text-xs hover:underline">
                  Clear filter
                </button>
              )}
            </div>
            {filteredIssues.length === 0 ? (
              <div className="text-center py-8">
                <CheckCircle className="w-8 h-8 text-[#4ade80] mx-auto mb-2" />
                <p className="text-[#52525b] text-sm">No issues found{activeFilter ? ' for this filter' : ''}</p>
              </div>
            ) : (
              filteredIssues.slice(0, 50).map((issue, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.02 }}
                  className={`rounded-xl border p-4 ${severityBg(issue.severity)}`}
                >
                  <div className="flex items-start gap-3">
                    <AlertTriangle className={`w-4 h-4 mt-0.5 flex-shrink-0 ${severityColor(issue.severity)}`} />
                    <div className="min-w-0 flex-1">
                      <p className="text-[#f5f5f7] text-sm font-medium">{issue.message}</p>
                      <p className="text-[#52525b] text-xs mt-1 truncate">{issue.image_url}</p>
                      <p className="text-[#7c6cf9] text-xs mt-1">Fix: {issue.fix}</p>
                    </div>
                    <span className={`text-xs px-2 py-1 rounded-lg flex-shrink-0 ${issue.severity === 'error' ? 'bg-[#f87171]/20 text-[#f87171]' : issue.severity === 'warning' ? 'bg-[#fbbf24]/20 text-[#fbbf24]' : 'bg-[#52525b]/20 text-[#52525b]'}`}>
                      {issue.severity}
                    </span>
                  </div>
                </motion.div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
