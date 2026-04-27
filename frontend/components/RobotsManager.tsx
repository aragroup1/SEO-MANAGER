// frontend/components/RobotsManager.tsx — Robots.txt Generator & Validator
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, RefreshCw, CheckCircle, AlertTriangle, XCircle,
  Loader2, Globe, Download, Copy, Check, ChevronDown, ChevronUp,
  FileText, Eye, EyeOff, Save, ArrowRight, Ban, Unlock,
  Search, Info, FileCode
} from 'lucide-react';

interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  info: string[];
  has_sitemap?: boolean;
  has_crawl_delay?: boolean;
  sitemap_urls?: string[];
  rule_count?: number;
  blocked_critical?: string[];
}

interface ComparisonResult {
  has_generated: boolean;
  message?: string;
  existing_rule_count?: number;
  generated_rule_count?: number;
  shared_rule_count?: number;
  only_in_existing?: Array<{ agent: string; type: string; path: string }>;
  only_in_generated?: Array<{ agent: string; type: string; path: string }>;
  recommendation?: string;
}

interface RobotsData {
  exists?: boolean;
  domain?: string;
  site_type?: string;
  generated_at?: string;
  robots_txt?: string;
  valid?: boolean;
  validation?: ValidationResult;
  success?: boolean;
  error?: string;
  rule_count?: number;
  sitemap_linked?: boolean;
}

interface ExistingCheck {
  found: boolean;
  url?: string;
  content?: string;
  content_length?: number;
  content_type?: string;
  validation?: ValidationResult;
  comparison?: ComparisonResult;
  warnings?: string[];
  error?: string;
  recommendation?: string;
}

interface Props {
  websiteId: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

function formatDate(iso: string | undefined) {
  if (!iso) return 'Never';
  const d = new Date(iso);
  return d.toLocaleString();
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function syntaxHighlightRobots(text: string): string {
  let html = escapeHtml(text);
  // Comments
  html = html.replace(
    /^(#.*)$/gm,
    '<span style="color:#52525b;font-style:italic">$1</span>'
  );
  // Directives
  html = html.replace(
    /^(User-agent|Disallow|Allow|Sitemap|Crawl-delay|Host)(:)/gim,
    '<span style="color:#7c6cf9;font-weight:600">$1</span><span style="color:#a1a1aa">$2</span>'
  );
  // Values after colon on directive lines
  html = html.replace(
    /^(User-agent|Disallow|Allow|Sitemap|Crawl-delay|Host):\s*(.+)$/gim,
    (match, p1, p2) => {
      const dir = `<span style="color:#7c6cf9;font-weight:600">${p1}</span><span style="color:#a1a1aa">:</span>`;
      let val = p2;
      if (p1.toLowerCase() === 'sitemap') {
        val = `<span style="color:#4ade80">${p2}</span>`;
      } else if (p1.toLowerCase() === 'disallow') {
        val = `<span style="color:#f87171">${p2}</span>`;
      } else if (p1.toLowerCase() === 'allow') {
        val = `<span style="color:#4ade80">${p2}</span>`;
      } else {
        val = `<span style="color:#fbbf24">${p2}</span>`;
      }
      return `${dir} ${val}`;
    }
  );
  return html;
}

export default function RobotsManager({ websiteId }: Props) {
  const [data, setData] = useState<RobotsData | null>(null);
  const [existing, setExisting] = useState<ExistingCheck | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [validating, setValidating] = useState(false);
  const [checking, setChecking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showEditor, setShowEditor] = useState(false);
  const [showExisting, setShowExisting] = useState(false);
  const [showComparison, setShowComparison] = useState(false);
  const [showRules, setShowRules] = useState(true);
  const [copied, setCopied] = useState(false);
  const [editedContent, setEditedContent] = useState('');
  const [error, setError] = useState('');
  const [activeView, setActiveView] = useState<'generated' | 'existing'>('generated');

  const fetchRobots = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/robots/${websiteId}`);
      if (res.ok) {
        const d = await res.json();
        setData(d);
        if (d.robots_txt) setEditedContent(d.robots_txt);
      } else {
        const err = await res.json();
        setError(err.detail || 'Failed to load robots.txt');
      }
    } catch (e) {
      setError('Network error');
    }
    setLoading(false);
  }, [websiteId]);

  useEffect(() => {
    fetchRobots();
  }, [fetchRobots]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/robots/${websiteId}/generate`, { method: 'POST' });
      const d = await res.json();
      if (res.ok) {
        setData(d);
        setEditedContent(d.robots_txt || '');
        setActiveView('generated');
      } else {
        setError(d.detail || 'Generation failed');
      }
    } catch (e) {
      setError('Network error during generation');
    }
    setGenerating(false);
  };

  const handleValidate = async () => {
    setValidating(true);
    setError('');
    try {
      const content = activeView === 'generated' ? editedContent : (existing?.content || '');
      const res = await fetch(`${API_URL}/api/robots/${websiteId}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      const d = await res.json();
      if (activeView === 'generated' && data) {
        setData({ ...data, validation: d, valid: d.valid });
      } else if (existing) {
        setExisting({ ...existing, validation: d });
      }
    } catch (e) {
      setError('Validation error');
    }
    setValidating(false);
  };

  const handleCheckExisting = async () => {
    setChecking(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/robots/${websiteId}/check`);
      const d = await res.json();
      setExisting(d);
      if (d.found) {
        setActiveView('existing');
        setShowExisting(true);
      }
    } catch (e) {
      setError('Failed to check existing robots.txt');
    }
    setChecking(false);
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/robots/${websiteId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editedContent }),
      });
      const d = await res.json();
      if (res.ok) {
        setData(prev => prev ? { ...prev, robots_txt: editedContent, valid: d.valid, validation: d.validation } : null);
        setShowEditor(false);
      } else {
        setError(d.detail || 'Save failed');
      }
    } catch (e) {
      setError('Network error during save');
    }
    setSaving(false);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadRobots = (text: string, domain?: string) => {
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `robots-${domain || 'website'}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Parse rules from robots.txt for the rules breakdown
  const parseRules = (text: string) => {
    const rules: Array<{ type: string; path: string; agent: string; reason?: string }> = [];
    let currentAgent = '*';
    let lastComment = '';
    for (const line of text.split('\n')) {
      const trimmed = line.trim();
      if (trimmed.startsWith('#')) {
        lastComment = trimmed.replace(/^#\s*/, '');
        continue;
      }
      if (!trimmed || !trimmed.includes(':')) {
        lastComment = '';
        continue;
      }
      const [key, ...rest] = trimmed.split(':');
      const val = rest.join(':').trim();
      const lowerKey = key.trim().toLowerCase();
      if (lowerKey === 'user-agent') {
        currentAgent = val;
      } else if (lowerKey === 'disallow' || lowerKey === 'allow') {
        rules.push({
          type: lowerKey,
          path: val,
          agent: currentAgent,
          reason: lastComment || undefined,
        });
        lastComment = '';
      }
    }
    return rules;
  };

  const currentContent = activeView === 'generated' ? (data?.robots_txt || '') : (existing?.content || '');
  const currentValidation = activeView === 'generated' ? data?.validation : existing?.validation;
  const hasRobots = data?.exists || data?.success;
  const rules = parseRules(currentContent);
  const allowRules = rules.filter(r => r.type === 'allow');
  const disallowRules = rules.filter(r => r.type === 'disallow');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-[#f5f5f7]">Robots.txt Manager</h2>
          <p className="text-[#52525b] text-sm mt-1">
            Generate, validate, and manage your robots.txt file
          </p>
        </div>
        <div className="flex items-center gap-2">
          {currentValidation && (
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border ${
              currentValidation.valid
                ? 'bg-[#4ade80]/10 text-[#4ade80] border-[#4ade80]/20'
                : currentValidation.errors.length > 0
                  ? 'bg-[#f87171]/10 text-[#f87171] border-[#f87171]/20'
                  : 'bg-[#fbbf24]/10 text-[#fbbf24] border-[#fbbf24]/20'
            }`}>
              {currentValidation.valid ? <CheckCircle className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
              {currentValidation.valid ? 'Valid' : currentValidation.errors.length > 0 ? 'Invalid' : 'Warnings'}
            </div>
          )}
        </div>
      </div>

      {/* Error Banner */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            className="rounded-xl border border-[#f87171]/20 bg-[#f87171]/5 p-4 flex items-start gap-3"
          >
            <AlertTriangle className="w-5 h-5 text-[#f87171] shrink-0 mt-0.5" />
            <div>
              <p className="text-[#f87171] text-sm font-medium">Error</p>
              <p className="text-[#f87171]/80 text-xs mt-0.5">{error}</p>
            </div>
            <button onClick={() => setError('')} className="ml-auto text-[#f87171]/60 hover:text-[#f87171]">
              <XCircle className="w-4 h-4" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="btn-premium flex items-center gap-2 disabled:opacity-50"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {generating ? 'Generating...' : hasRobots ? 'Regenerate' : 'Generate robots.txt'}
        </button>

        <button
          onClick={handleCheckExisting}
          disabled={checking}
          className="px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-[#f5f5f7] text-sm font-medium hover:bg-white/[0.06] transition-colors flex items-center gap-2 disabled:opacity-50"
        >
          {checking ? <Loader2 className="w-4 h-4 animate-spin" /> : <Globe className="w-4 h-4 text-[#7c6cf9]" />}
          Check Live Site
        </button>

        {currentContent && (
          <>
            <button
              onClick={handleValidate}
              disabled={validating}
              className="px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-[#f5f5f7] text-sm font-medium hover:bg-white/[0.06] transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {validating ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4 text-[#4ade80]" />}
              Validate
            </button>

            <button
              onClick={() => downloadRobots(currentContent, data?.domain || existing?.url?.replace(/^https?:\/\//, ''))}
              className="px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-[#f5f5f7] text-sm font-medium hover:bg-white/[0.06] transition-colors flex items-center gap-2"
            >
              <Download className="w-4 h-4 text-[#a1a1aa]" />
              Download
            </button>
          </>
        )}
      </div>

      {/* View Toggle */}
      {existing?.found && (
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveView('generated')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeView === 'generated'
                ? 'bg-[#7c6cf9]/10 text-[#7c6cf9] border border-[#7c6cf9]/20'
                : 'text-[#52525b] hover:text-[#a1a1aa]'
            }`}
          >
            Generated
          </button>
          <button
            onClick={() => setActiveView('existing')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeView === 'existing'
                ? 'bg-[#7c6cf9]/10 text-[#7c6cf9] border border-[#7c6cf9]/20'
                : 'text-[#52525b] hover:text-[#a1a1aa]'
            }`}
          >
            Live Site
          </button>
          {existing.comparison?.has_generated && (
            <button
              onClick={() => setShowComparison(!showComparison)}
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-[#52525b] hover:text-[#a1a1aa] transition-colors flex items-center gap-1"
            >
              <FileCode className="w-3 h-3" />
              Compare
            </button>
          )}
        </div>
      )}

      {/* Stats Cards */}
      {currentContent && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-4 h-4 text-[#7c6cf9]" />
              <span className="text-[#52525b] text-xs uppercase tracking-wider">Rules</span>
            </div>
            <p className="text-2xl font-bold text-[#f5f5f7]">{rules.length}</p>
          </div>
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Ban className="w-4 h-4 text-[#f87171]" />
              <span className="text-[#52525b] text-xs uppercase tracking-wider">Disallowed</span>
            </div>
            <p className="text-2xl font-bold text-[#f5f5f7]">{disallowRules.length}</p>
          </div>
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Unlock className="w-4 h-4 text-[#4ade80]" />
              <span className="text-[#52525b] text-xs uppercase tracking-wider">Allowed</span>
            </div>
            <p className="text-2xl font-bold text-[#f5f5f7]">{allowRules.length}</p>
          </div>
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-4 h-4 text-[#7c6cf9]" />
              <span className="text-[#52525b] text-xs uppercase tracking-wider">Status</span>
            </div>
            <p className="text-sm font-bold text-[#f5f5f7]">
              {currentValidation?.valid ? 'Valid' : currentValidation?.errors.length ? 'Errors' : 'OK'}
            </p>
          </div>
        </div>
      )}

      {/* Comparison View */}
      <AnimatePresence>
        {showComparison && existing?.comparison && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl p-5"
          >
            <div className="flex items-center gap-2 mb-4">
              <FileCode className="w-4 h-4 text-[#7c6cf9]" />
              <h3 className="text-sm font-semibold text-[#f5f5f7]">Comparison: Generated vs Live</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center mb-4">
              <div className="rounded-xl bg-white/[0.03] p-3">
                <p className="text-2xl font-bold text-[#f5f5f7]">{existing.comparison.existing_rule_count}</p>
                <p className="text-[#52525b] text-xs">Live Rules</p>
              </div>
              <div className="rounded-xl bg-white/[0.03] p-3">
                <p className="text-2xl font-bold text-[#f5f5f7]">{existing.comparison.shared_rule_count}</p>
                <p className="text-[#52525b] text-xs">Shared</p>
              </div>
              <div className="rounded-xl bg-white/[0.03] p-3">
                <p className="text-2xl font-bold text-[#7c6cf9]">{existing.comparison.generated_rule_count}</p>
                <p className="text-[#52525b] text-xs">Generated Rules</p>
              </div>
            </div>
            {existing.comparison.only_in_generated && existing.comparison.only_in_generated.length > 0 && (
              <div className="mb-3">
                <p className="text-xs font-medium text-[#4ade80] mb-2">Only in Generated ({existing.comparison.only_in_generated.length})</p>
                <div className="space-y-1">
                  {existing.comparison.only_in_generated.slice(0, 8).map((r, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className="text-[#52525b] w-16 shrink-0">{r.agent}</span>
                      <span className={r.type === 'disallow' ? 'text-[#f87171]' : 'text-[#4ade80]'}>
                        {r.type}: {r.path}
                      </span>
                    </div>
                  ))}
                  {existing.comparison.only_in_generated.length > 8 && (
                    <p className="text-[#52525b] text-xs">...and {existing.comparison.only_in_generated.length - 8} more</p>
                  )}
                </div>
              </div>
            )}
            {existing.comparison.only_in_existing && existing.comparison.only_in_existing.length > 0 && (
              <div>
                <p className="text-xs font-medium text-[#fbbf24] mb-2">Only in Live ({existing.comparison.only_in_existing.length})</p>
                <div className="space-y-1">
                  {existing.comparison.only_in_existing.slice(0, 8).map((r, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <span className="text-[#52525b] w-16 shrink-0">{r.agent}</span>
                      <span className={r.type === 'disallow' ? 'text-[#f87171]' : 'text-[#4ade80]'}>
                        {r.type}: {r.path}
                      </span>
                    </div>
                  ))}
                  {existing.comparison.only_in_existing.length > 8 && (
                    <p className="text-[#52525b] text-xs">...and {existing.comparison.only_in_existing.length - 8} more</p>
                  )}
                </div>
              </div>
            )}
            {existing.comparison.recommendation && (
              <p className="text-[#a1a1aa] text-xs mt-3 pt-3 border-t border-white/[0.06]">
                <Info className="w-3 h-3 inline mr-1" />
                {existing.comparison.recommendation}
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Validation Results */}
      <AnimatePresence>
        {currentValidation && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="space-y-3"
          >
            {currentValidation.errors.length > 0 && (
              <div className="rounded-2xl border border-[#f87171]/20 bg-[#f87171]/5 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <XCircle className="w-4 h-4 text-[#f87171]" />
                  <span className="text-sm font-medium text-[#f87171]">Errors ({currentValidation.errors.length})</span>
                </div>
                {currentValidation.errors.map((e, i) => (
                  <p key={i} className="text-[#f87171] text-xs ml-6">• {e}</p>
                ))}
              </div>
            )}
            {currentValidation.warnings.length > 0 && (
              <div className="rounded-2xl border border-[#fbbf24]/20 bg-[#fbbf24]/5 p-4">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-[#fbbf24]" />
                  <span className="text-sm font-medium text-[#fbbf24]">Warnings ({currentValidation.warnings.length})</span>
                </div>
                {currentValidation.warnings.map((w, i) => (
                  <p key={i} className="text-[#fbbf24] text-xs ml-6">• {w}</p>
                ))}
              </div>
            )}
            {currentValidation.info && currentValidation.info.length > 0 && (
              <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4">
                <div className="flex items-center gap-2 mb-2">
                  <Info className="w-4 h-4 text-[#a1a1aa]" />
                  <span className="text-sm font-medium text-[#a1a1aa]">Info ({currentValidation.info.length})</span>
                </div>
                {currentValidation.info.map((info, i) => (
                  <p key={i} className="text-[#52525b] text-xs ml-6">• {info}</p>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty State */}
      {!hasRobots && !loading && !generating && activeView === 'generated' && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="card-liquid p-12 text-center"
        >
          <Shield className="w-12 h-12 text-[#7c6cf9] mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-[#f5f5f7] mb-2">No robots.txt Generated</h3>
          <p className="text-[#52525b] text-sm mb-6 max-w-md mx-auto">
            Generate an optimized robots.txt file with platform-specific rules for
            Shopify, WordPress, or custom sites.
          </p>
          <button onClick={handleGenerate} className="btn-premium">
            <RefreshCw className="w-4 h-4" /> Generate robots.txt
          </button>
        </motion.div>
      )}

      {/* Existing Not Found */}
      {activeView === 'existing' && existing && !existing.found && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="card-liquid p-12 text-center"
        >
          <Globe className="w-12 h-12 text-[#f87171] mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-[#f5f5f7] mb-2">No robots.txt Found on Live Site</h3>
          <p className="text-[#52525b] text-sm mb-2">{existing.error}</p>
          {existing.recommendation && (
            <p className="text-[#a1a1aa] text-xs mb-6">{existing.recommendation}</p>
          )}
          <button onClick={() => setActiveView('generated')} className="btn-premium">
            View Generated Version
          </button>
        </motion.div>
      )}

      {/* Loading */}
      {loading && !hasRobots && activeView === 'generated' && (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="w-8 h-8 text-[#7c6cf9] animate-spin" />
        </div>
      )}

      {/* Content Editor / Preview */}
      <AnimatePresence>
        {currentContent && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl overflow-hidden"
          >
            {/* Toolbar */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-[#7c6cf9]" />
                <span className="text-[#f5f5f7] text-sm font-medium">
                  {activeView === 'generated' ? 'Generated robots.txt' : 'Live robots.txt'}
                </span>
                {activeView === 'existing' && existing?.url && (
                  <span className="text-[#52525b] text-xs">{existing.url}</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {activeView === 'generated' && (
                  <button
                    onClick={() => setShowEditor(!showEditor)}
                    className="flex items-center gap-1.5 text-[#7c6cf9] text-xs hover:text-[#9b8ffb] transition-colors"
                  >
                    {showEditor ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    {showEditor ? 'Preview' : 'Edit'}
                  </button>
                )}
                <button
                  onClick={() => copyToClipboard(currentContent)}
                  className="flex items-center gap-1.5 text-[#7c6cf9] text-xs hover:text-[#9b8ffb] transition-colors"
                >
                  {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            {/* Editor */}
            <AnimatePresence>
              {showEditor && activeView === 'generated' ? (
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: 'auto' }}
                  exit={{ height: 0 }}
                  className="overflow-hidden"
                >
                  <textarea
                    value={editedContent}
                    onChange={e => setEditedContent(e.target.value)}
                    className="w-full h-96 bg-[#0f0f12] text-[#a1a1aa] text-xs font-mono p-5 resize-none focus:outline-none"
                    spellCheck={false}
                  />
                  <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-white/[0.06]">
                    <button
                      onClick={() => { setShowEditor(false); setEditedContent(data?.robots_txt || ''); }}
                      className="px-3 py-1.5 rounded-lg text-xs text-[#52525b] hover:text-[#a1a1aa] transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="btn-premium flex items-center gap-1.5 text-xs py-1.5 disabled:opacity-50"
                    >
                      {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                      Save
                    </button>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: 'auto' }}
                  exit={{ height: 0 }}
                  className="overflow-hidden"
                >
                  <pre
                    className="p-5 text-xs font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-[500px] overflow-y-auto"
                    dangerouslySetInnerHTML={{ __html: syntaxHighlightRobots(currentContent) }}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Rules Breakdown */}
      <AnimatePresence>
        {currentContent && rules.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl overflow-hidden"
          >
            <button
              onClick={() => setShowRules(!showRules)}
              className="w-full flex items-center justify-between px-5 py-3 border-b border-white/[0.06]"
            >
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-[#7c6cf9]" />
                <span className="text-[#f5f5f7] text-sm font-medium">Rules Breakdown</span>
              </div>
              {showRules ? <ChevronUp className="w-4 h-4 text-[#52525b]" /> : <ChevronDown className="w-4 h-4 text-[#52525b]" />}
            </button>

            <AnimatePresence>
              {showRules && (
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: 'auto' }}
                  exit={{ height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="p-5 space-y-4">
                    {/* Disallowed */}
                    {disallowRules.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium text-[#f87171] mb-2 flex items-center gap-1.5">
                          <Ban className="w-3 h-3" /> Disallowed Paths ({disallowRules.length})
                        </h4>
                        <div className="space-y-1.5">
                          {disallowRules.map((r, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs">
                              <span className="text-[#52525b] w-14 shrink-0">{r.agent}</span>
                              <span className="text-[#f87171] font-mono">{r.path}</span>
                              {r.reason && <span className="text-[#52525b] ml-auto">{r.reason}</span>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Allowed */}
                    {allowRules.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium text-[#4ade80] mb-2 flex items-center gap-1.5">
                          <Unlock className="w-3 h-3" /> Allowed Paths ({allowRules.length})
                        </h4>
                        <div className="space-y-1.5">
                          {allowRules.map((r, i) => (
                            <div key={i} className="flex items-start gap-2 text-xs">
                              <span className="text-[#52525b] w-14 shrink-0">{r.agent}</span>
                              <span className="text-[#4ade80] font-mono">{r.path}</span>
                              {r.reason && <span className="text-[#52525b] ml-auto">{r.reason}</span>}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Sitemaps */}
                    {currentValidation?.sitemap_urls && currentValidation.sitemap_urls.length > 0 && (
                      <div className="pt-3 border-t border-white/[0.06]">
                        <h4 className="text-xs font-medium text-[#7c6cf9] mb-2 flex items-center gap-1.5">
                          <FileCode className="w-3 h-3" /> Sitemaps
                        </h4>
                        {currentValidation.sitemap_urls.map((url, i) => (
                          <a
                            key={i}
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-[#7c6cf9] hover:underline block"
                          >
                            {url}
                          </a>
                        ))}
                      </div>
                    )}

                    {/* Crawl Delay */}
                    {currentValidation?.has_crawl_delay && (
                      <div className="pt-3 border-t border-white/[0.06] flex items-center gap-2">
                        <Info className="w-3 h-3 text-[#a1a1aa]" />
                        <span className="text-xs text-[#a1a1aa]">Crawl-delay directive present</span>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
