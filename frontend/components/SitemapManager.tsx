// frontend/components/SitemapManager.tsx — Sitemap XML Generator & Manager
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileCode, RefreshCw, CheckCircle, AlertTriangle, XCircle,
  Loader2, Globe, Upload, Download, Copy, Check, ChevronDown,
  ChevronUp, Search, Link2, Calendar, Hash
} from 'lucide-react';

interface SitemapUrl {
  loc: string;
  lastmod?: string;
  changefreq?: string;
  priority?: string;
  title?: string;
}

interface SitemapData {
  exists?: boolean;
  domain?: string;
  url_count?: number;
  generated_at?: string;
  valid?: boolean;
  validation?: {
    valid: boolean;
    url_count: number;
    errors: string[];
    warnings: string[];
  };
  urls?: SitemapUrl[];
  sitemap_xml?: string;
  success?: boolean;
  error?: string;
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

function escapeXml(xml: string): string {
  return xml
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function syntaxHighlightXml(xml: string): string {
  let escaped = escapeXml(xml);
  // Highlight tags
  escaped = escaped.replace(
    /(&lt;\/?)([\w:]+)/g,
    '<span style="color:#7c6cf9">$1$2</span>'
  );
  // Highlight attributes (simplified)
  escaped = escaped.replace(
    /(\s)([\w-]+)(=)(&quot;.*?&quot;)/g,
    '$1<span style="color:#fbbf24">$2</span>$3<span style="color:#4ade80">$4</span>'
  );
  // Highlight values inside tags
  escaped = escaped.replace(
    /(&gt;)([^&]+)(&lt;)/g,
    '$1<span style="color:#a1a1aa">$2</span>$3'
  );
  return escaped;
}

export default function SitemapManager({ websiteId }: Props) {
  const [data, setData] = useState<SitemapData | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [validating, setValidating] = useState(false);
  const [showXml, setShowXml] = useState(false);
  const [showUrls, setShowUrls] = useState(true);
  const [copied, setCopied] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState('');

  const fetchSitemap = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/sitemap/${websiteId}`);
      if (res.ok) {
        const d = await res.json();
        setData(d);
      } else {
        const err = await res.json();
        setError(err.detail || 'Failed to load sitemap');
      }
    } catch (e) {
      setError('Network error');
    }
    setLoading(false);
  }, [websiteId]);

  useEffect(() => {
    fetchSitemap();
  }, [fetchSitemap]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/sitemap/${websiteId}/generate`, { method: 'POST' });
      const d = await res.json();
      if (res.ok) {
        setData(d);
      } else {
        setError(d.detail || 'Generation failed');
      }
    } catch (e) {
      setError('Network error during generation');
    }
    setGenerating(false);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/sitemap/${websiteId}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sitemap_url: data?.domain ? `https://${data.domain}/sitemap.xml` : '' }),
      });
      const d = await res.json();
      if (d.success) {
        alert('Sitemap submitted to Google Search Console successfully!');
      } else {
        setError(d.error || 'Submission failed');
      }
    } catch (e) {
      setError('Network error during submission');
    }
    setSubmitting(false);
  };

  const handleValidate = async () => {
    setValidating(true);
    setError('');
    try {
      const res = await fetch(`${API_URL}/api/sitemap/${websiteId}/validate`);
      const d = await res.json();
      if (data) {
        setData({ ...data, valid: d.valid, validation: d });
      }
    } catch (e) {
      setError('Validation error');
    }
    setValidating(false);
  };

  const copyXml = () => {
    if (data?.sitemap_xml) {
      navigator.clipboard.writeText(data.sitemap_xml);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const downloadXml = () => {
    if (!data?.sitemap_xml) return;
    const blob = new Blob([data.sitemap_xml], { type: 'application/xml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sitemap-${data.domain || 'website'}.xml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filteredUrls = (data?.urls || []).filter(u =>
    u.loc.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (u.title || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const hasSitemap = data?.exists || data?.success;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-[#f5f5f7]">Sitemap Generator</h2>
          <p className="text-[#52525b] text-sm mt-1">
            Generate, validate, and submit XML sitemaps to Google Search Console
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hasSitemap && data?.valid !== undefined && (
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border ${
              data.valid
                ? 'bg-[#4ade80]/10 text-[#4ade80] border-[#4ade80]/20'
                : 'bg-[#f87171]/10 text-[#f87171] border-[#f87171]/20'
            }`}>
              {data.valid ? <CheckCircle className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
              {data.valid ? 'Valid' : 'Invalid'}
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

      {/* Stats Cards */}
      {hasSitemap && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Hash className="w-4 h-4 text-[#7c6cf9]" />
              <span className="text-[#52525b] text-xs uppercase tracking-wider">URLs</span>
            </div>
            <p className="text-2xl font-bold text-[#f5f5f7]">{data?.url_count?.toLocaleString() || 0}</p>
          </div>
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="w-4 h-4 text-[#7c6cf9]" />
              <span className="text-[#52525b] text-xs uppercase tracking-wider">Generated</span>
            </div>
            <p className="text-sm font-medium text-[#f5f5f7]">{formatDate(data?.generated_at)}</p>
          </div>
          <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Globe className="w-4 h-4 text-[#7c6cf9]" />
              <span className="text-[#52525b] text-xs uppercase tracking-wider">Domain</span>
            </div>
            <p className="text-sm font-medium text-[#f5f5f7] truncate">{data?.domain || '—'}</p>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="btn-premium flex items-center gap-2 disabled:opacity-50"
        >
          {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
          {generating ? 'Generating...' : hasSitemap ? 'Regenerate Sitemap' : 'Generate Sitemap'}
        </button>

        {hasSitemap && (
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
              onClick={handleSubmit}
              disabled={submitting}
              className="px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-[#f5f5f7] text-sm font-medium hover:bg-white/[0.06] transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4 text-[#7c6cf9]" />}
              Submit to GSC
            </button>

            <button
              onClick={downloadXml}
              className="px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.06] text-[#f5f5f7] text-sm font-medium hover:bg-white/[0.06] transition-colors flex items-center gap-2"
            >
              <Download className="w-4 h-4 text-[#a1a1aa]" />
              Download XML
            </button>
          </>
        )}
      </div>

      {/* Validation Results */}
      <AnimatePresence>
        {data?.validation && (data.validation.errors?.length > 0 || data.validation.warnings?.length > 0) && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className={`rounded-2xl border p-4 ${
              data.validation.errors?.length > 0
                ? 'border-[#f87171]/20 bg-[#f87171]/5'
                : 'border-[#fbbf24]/20 bg-[#fbbf24]/5'
            }`}
          >
            <div className="flex items-center gap-2 mb-3">
              {data.validation.errors?.length > 0 ? (
                <XCircle className="w-4 h-4 text-[#f87171]" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-[#fbbf24]" />
              )}
              <span className={`text-sm font-medium ${
                data.validation.errors?.length > 0 ? 'text-[#f87171]' : 'text-[#fbbf24]'
              }`}>
                {data.validation.errors?.length > 0 ? 'Validation Issues' : 'Warnings'}
              </span>
            </div>
            {data.validation.errors?.map((e: string, i: number) => (
              <p key={`err-${i}`} className="text-[#f87171] text-xs ml-6">• {e}</p>
            ))}
            {data.validation.warnings?.map((w: string, i: number) => (
              <p key={`warn-${i}`} className="text-[#fbbf24] text-xs ml-6">• {w}</p>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty State */}
      {!hasSitemap && !loading && !generating && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="card-liquid p-12 text-center"
        >
          <FileCode className="w-12 h-12 text-[#7c6cf9] mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-[#f5f5f7] mb-2">No Sitemap Generated</h3>
          <p className="text-[#52525b] text-sm mb-6 max-w-md mx-auto">
            Generate an XML sitemap to help search engines discover and index all your pages.
            We support Shopify, WordPress, and custom websites.
          </p>
          <button onClick={handleGenerate} className="btn-premium">
            <RefreshCw className="w-4 h-4" /> Generate Sitemap
          </button>
        </motion.div>
      )}

      {/* Loading State */}
      {loading && !hasSitemap && (
        <div className="flex items-center justify-center h-40">
          <Loader2 className="w-8 h-8 text-[#7c6cf9] animate-spin" />
        </div>
      )}

      {/* URL List */}
      <AnimatePresence>
        {hasSitemap && data?.urls && data.urls.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl overflow-hidden"
          >
            {/* URL List Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
              <button
                onClick={() => setShowUrls(!showUrls)}
                className="flex items-center gap-2 text-[#f5f5f7] text-sm font-medium hover:text-[#a1a1aa] transition-colors"
              >
                <Link2 className="w-4 h-4 text-[#7c6cf9]" />
                URLs Found ({data.url_count?.toLocaleString()})
                {showUrls ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-[#52525b] absolute left-2.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Filter URLs..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="bg-[#0f0f12] border border-white/[0.06] rounded-lg pl-8 pr-3 py-1.5 text-xs text-[#f5f5f7] placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/50 w-48"
                />
              </div>
            </div>

            <AnimatePresence>
              {showUrls && (
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: 'auto' }}
                  exit={{ height: 0 }}
                  className="overflow-hidden"
                >
                  <div className="max-h-96 overflow-y-auto">
                    <table className="w-full text-left">
                      <thead className="sticky top-0 bg-[#0a0a0c]/95 backdrop-blur-xl z-10">
                        <tr className="border-b border-white/[0.06]">
                          <th className="px-5 py-2.5 text-[#52525b] text-xs font-medium uppercase tracking-wider">URL</th>
                          <th className="px-5 py-2.5 text-[#52525b] text-xs font-medium uppercase tracking-wider w-24">Priority</th>
                          <th className="px-5 py-2.5 text-[#52525b] text-xs font-medium uppercase tracking-wider w-28">Change Freq</th>
                          <th className="px-5 py-2.5 text-[#52525b] text-xs font-medium uppercase tracking-wider w-28">Last Mod</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredUrls.slice(0, 100).map((url, idx) => (
                          <tr
                            key={idx}
                            className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors"
                          >
                            <td className="px-5 py-2.5">
                              <a
                                href={url.loc}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[#7c6cf9] text-xs hover:underline truncate block max-w-xs"
                                title={url.loc}
                              >
                                {url.loc.replace(/^https?:\/\//, '')}
                              </a>
                              {url.title && (
                                <p className="text-[#52525b] text-[10px] mt-0.5 truncate max-w-xs">{url.title}</p>
                              )}
                            </td>
                            <td className="px-5 py-2.5">
                              <span className="text-xs text-[#a1a1aa]">{url.priority || '0.5'}</span>
                            </td>
                            <td className="px-5 py-2.5">
                              <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-white/[0.04] text-[#a1a1aa] text-[10px] capitalize">
                                {url.changefreq || 'weekly'}
                              </span>
                            </td>
                            <td className="px-5 py-2.5">
                              <span className="text-xs text-[#52525b]">{url.lastmod || '—'}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {filteredUrls.length === 0 && (
                      <div className="p-8 text-center">
                        <p className="text-[#52525b] text-sm">No URLs match your search</p>
                      </div>
                    )}
                    {filteredUrls.length > 100 && (
                      <div className="px-5 py-3 border-t border-white/[0.06] text-center">
                        <p className="text-[#52525b] text-xs">
                          Showing 100 of {filteredUrls.length} filtered URLs
                        </p>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>

      {/* XML Preview */}
      <AnimatePresence>
        {hasSitemap && data?.sitemap_xml && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-white/[0.06] bg-white/[0.02] backdrop-blur-xl overflow-hidden"
          >
            <div
              className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06] cursor-pointer"
              onClick={() => setShowXml(!showXml)}
            >
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-[#7c6cf9]" />
                <span className="text-[#f5f5f7] text-sm font-medium">XML Output</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => { e.stopPropagation(); copyXml(); }}
                  className="flex items-center gap-1.5 text-[#7c6cf9] text-xs hover:text-[#9b8ffb] transition-colors"
                >
                  {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
                {showXml ? <ChevronUp className="w-4 h-4 text-[#52525b]" /> : <ChevronDown className="w-4 h-4 text-[#52525b]" />}
              </div>
            </div>

            <AnimatePresence>
              {showXml && (
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: 'auto' }}
                  exit={{ height: 0 }}
                  className="overflow-hidden"
                >
                  <pre
                    className="p-5 text-xs font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed"
                    dangerouslySetInnerHTML={{ __html: syntaxHighlightXml(data.sitemap_xml) }}
                  />
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
