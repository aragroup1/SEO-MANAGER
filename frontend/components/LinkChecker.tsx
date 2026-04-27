// frontend/components/LinkChecker.tsx — Broken Link Checker Dashboard
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Link2, RefreshCw, Loader2, CheckCircle, AlertTriangle,
  ExternalLink, Filter, Download, XCircle, Clock, Globe,
  ShieldAlert, ServerCrash, Unlink, Search
} from 'lucide-react';

interface BrokenLink {
  id: number;
  website_id: number;
  page_url: string;
  link_url: string;
  anchor_text: string;
  status_code: number;
  error_type: string;
  checked_at: string;
  is_fixed: boolean;
}

interface LinkSummary {
  website_id: number;
  total_links_recorded: number;
  broken_count: number;
  fixed_count: number;
  error_breakdown: Record<string, number>;
  last_checked: string | null;
}

interface Props {
  websiteId: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

const errorTypeConfig: Record<string, { label: string; color: string; bg: string; icon: any }> = {
  not_found: {
    label: 'Not Found',
    color: 'text-[#f87171]',
    bg: 'bg-[#f87171]/10 border-[#f87171]/20',
    icon: Unlink,
  },
  server_error: {
    label: 'Server Error',
    color: 'text-[#fbbf24]',
    bg: 'bg-[#fbbf24]/10 border-[#fbbf24]/20',
    icon: ServerCrash,
  },
  timeout: {
    label: 'Timeout',
    color: 'text-[#fb923c]',
    bg: 'bg-[#fb923c]/10 border-[#fb923c]/20',
    icon: Clock,
  },
  ssl_error: {
    label: 'SSL Error',
    color: 'text-[#f472b6]',
    bg: 'bg-[#f472b6]/10 border-[#f472b6]/20',
    icon: ShieldAlert,
  },
  redirect_chain: {
    label: 'Redirect Chain',
    color: 'text-[#a78bfa]',
    bg: 'bg-[#a78bfa]/10 border-[#a78bfa]/20',
    icon: ExternalLink,
  },
  dns_error: {
    label: 'DNS Error',
    color: 'text-[#60a5fa]',
    bg: 'bg-[#60a5fa]/10 border-[#60a5fa]/20',
    icon: Globe,
  },
  connection_error: {
    label: 'Connection Error',
    color: 'text-[#94a3b8]',
    bg: 'bg-[#94a3b8]/10 border-[#94a3b8]/20',
    icon: XCircle,
  },
  unknown: {
    label: 'Unknown',
    color: 'text-[#52525b]',
    bg: 'bg-[#52525b]/10 border-[#52525b]/20',
    icon: AlertTriangle,
  },
};

function getErrorConfig(errorType: string) {
  return errorTypeConfig[errorType] || errorTypeConfig.unknown;
}

function truncateUrl(url: string, maxLen: number = 60) {
  if (url.length <= maxLen) return url;
  return url.slice(0, maxLen) + '...';
}

export default function LinkChecker({ websiteId }: Props) {
  const [brokenLinks, setBrokenLinks] = useState<BrokenLink[]>([]);
  const [summary, setSummary] = useState<LinkSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [errorFilter, setErrorFilter] = useState<string | null>(null);
  const [pageFilter, setPageFilter] = useState('');
  const [markingFixed, setMarkingFixed] = useState<number | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [linksRes, summaryRes] = await Promise.all([
        fetch(`${API_URL}/api/links/${websiteId}/broken`),
        fetch(`${API_URL}/api/links/${websiteId}/summary`),
      ]);
      if (linksRes.ok) {
        const data = await linksRes.json();
        setBrokenLinks(data.broken_links || []);
      }
      if (summaryRes.ok) {
        const data = await summaryRes.json();
        setSummary(data);
      }
    } catch (e) {
      console.error('[LinkChecker] fetch error:', e);
    }
    setLoading(false);
  }, [websiteId]);

  const startScan = async () => {
    setScanning(true);
    try {
      await fetch(`${API_URL}/api/links/${websiteId}/scan`, { method: 'POST' });
      // Poll for results
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        await fetchData();
        if (attempts >= 60) {
          clearInterval(interval);
          setScanning(false);
        }
        // If we got new data and scan seems done, stop polling
        const summaryRes = await fetch(`${API_URL}/api/links/${websiteId}/summary`);
        if (summaryRes.ok) {
          const s = await summaryRes.json();
          if (s.last_checked) {
            const lastChecked = new Date(s.last_checked);
            const now = new Date();
            if (now.getTime() - lastChecked.getTime() < 120000) {
              clearInterval(interval);
              setScanning(false);
            }
          }
        }
      }, 3000);
    } catch (e) {
      console.error('[LinkChecker] scan error:', e);
      setScanning(false);
    }
  };

  const markFixed = async (linkId: number) => {
    setMarkingFixed(linkId);
    try {
      await fetch(`${API_URL}/api/links/${linkId}/mark-fixed`, { method: 'POST' });
      await fetchData();
    } catch (e) {
      console.error('[LinkChecker] mark fixed error:', e);
    }
    setMarkingFixed(null);
  };

  const exportCSV = () => {
    const rows = filteredLinks.map(link => ({
      'Page URL': link.page_url,
      'Broken Link URL': link.link_url,
      'Anchor Text': link.anchor_text || '',
      'Status Code': link.status_code || '',
      'Error Type': link.error_type,
      'Checked At': link.checked_at ? new Date(link.checked_at).toLocaleString() : '',
    }));
    if (rows.length === 0) return;

    const headers = Object.keys(rows[0]);
    const csv = [
      headers.join(','),
      ...rows.map(row =>
        headers.map(h => {
          const val = (row as any)[h];
          const str = val === null || val === undefined ? '' : String(val);
          if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            return '"' + str.replace(/"/g, '""') + '"';
          }
          return str;
        }).join(',')
      ),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `broken-links-${websiteId}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const filteredLinks = brokenLinks.filter(link => {
    if (errorFilter && link.error_type !== errorFilter) return false;
    if (pageFilter && !link.page_url.toLowerCase().includes(pageFilter.toLowerCase())) return false;
    return true;
  });

  const errorTypes = Object.entries(summary?.error_breakdown || {})
    .sort((a, b) => b[1] - a[1]);

  const hasData = summary && (summary.total_links_recorded > 0 || summary.broken_count > 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-[#f5f5f7]">Broken Link Checker</h2>
          <p className="text-[#52525b] text-sm mt-1">
            Crawl your site and find broken outbound links
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={exportCSV}
            disabled={brokenLinks.length === 0}
            className="px-4 py-2 rounded-xl bg-[#0f0f12] border border-white/[0.06] text-[#a1a1aa] text-sm font-medium hover:bg-white/[0.03] transition-colors flex items-center gap-2 disabled:opacity-40"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
          <button
            onClick={startScan}
            disabled={scanning}
            className="px-4 py-2 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            {scanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
            {scanning ? 'Scanning...' : 'Run Scan'}
          </button>
        </div>
      </div>

      {/* Scanning progress */}
      {scanning && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl border border-[#7c6cf9]/20 bg-[#7c6cf9]/5 p-4 flex items-center gap-3"
        >
          <Loader2 className="w-5 h-5 text-[#7c6cf9] animate-spin" />
          <div className="flex-1">
            <p className="text-[#f5f5f7] text-sm font-medium">Scanning for broken links...</p>
            <p className="text-[#52525b] text-xs">Crawling pages and checking outbound links. This may take a few minutes.</p>
          </div>
        </motion.div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 text-[#7c6cf9] animate-spin" />
        </div>
      ) : !hasData ? (
        <div className="text-center py-16">
          <Link2 className="w-12 h-12 text-[#52525b] mx-auto mb-4" />
          <p className="text-[#f5f5f7] font-medium">No link check data yet</p>
          <p className="text-[#52525b] text-sm mt-1">Run a scan to find broken outbound links</p>
          <button
            onClick={startScan}
            disabled={scanning}
            className="mt-4 px-5 py-2 rounded-xl bg-[#7c6cf9]/20 text-[#7c6cf9] text-sm font-medium hover:bg-[#7c6cf9]/30 transition-colors"
          >
            Run First Scan
          </button>
        </div>
      ) : (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            <div className="rounded-xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Link2 className="w-4 h-4 text-[#7c6cf9]" />
                <span className="text-[#52525b] text-xs">Total Links</span>
              </div>
              <p className="text-[#f5f5f7] text-2xl font-bold">{summary?.total_links_recorded || 0}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-4 h-4 text-[#f87171]" />
                <span className="text-[#52525b] text-xs">Broken</span>
              </div>
              <p className="text-[#f87171] text-2xl font-bold">{summary?.broken_count || 0}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Unlink className="w-4 h-4 text-[#f87171]" />
                <span className="text-[#52525b] text-xs">404s</span>
              </div>
              <p className="text-[#f5f5f7] text-2xl font-bold">{summary?.error_breakdown?.not_found || 0}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <ServerCrash className="w-4 h-4 text-[#fbbf24]" />
                <span className="text-[#52525b] text-xs">500s</span>
              </div>
              <p className="text-[#f5f5f7] text-2xl font-bold">{summary?.error_breakdown?.server_error || 0}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-4 h-4 text-[#fb923c]" />
                <span className="text-[#52525b] text-xs">Timeouts</span>
              </div>
              <p className="text-[#f5f5f7] text-2xl font-bold">{summary?.error_breakdown?.timeout || 0}</p>
            </div>
          </div>

          {/* Error Type Breakdown */}
          {errorTypes.length > 0 && (
            <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl p-5">
              <h3 className="text-[#f5f5f7] text-sm font-medium mb-3">Error Breakdown</h3>
              <div className="flex flex-wrap gap-2">
                {errorTypes.map(([etype, count]) => {
                  const cfg = getErrorConfig(etype);
                  const Icon = cfg.icon;
                  const active = errorFilter === etype;
                  return (
                    <button
                      key={etype}
                      onClick={() => setErrorFilter(active ? null : etype)}
                      className={`flex items-center gap-2 px-3 py-2 rounded-xl border text-sm transition-all ${
                        active
                          ? 'border-[#7c6cf9]/40 bg-[#7c6cf9]/10 text-[#f5f5f7]'
                          : `${cfg.bg} ${cfg.color} hover:opacity-80`
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span className="font-medium">{count}</span>
                      <span className="text-xs opacity-80">{cfg.label}</span>
                    </button>
                  );
                })}
                {errorFilter && (
                  <button
                    onClick={() => setErrorFilter(null)}
                    className="flex items-center gap-1 px-3 py-2 rounded-xl border border-white/[0.06] text-[#52525b] text-sm hover:bg-white/[0.03]"
                  >
                    <XCircle className="w-4 h-4" />
                    Clear
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Filters */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525b]" />
              <input
                type="text"
                value={pageFilter}
                onChange={e => setPageFilter(e.target.value)}
                placeholder="Filter by page URL..."
                className="w-full pl-9 pr-4 py-2 rounded-xl bg-[#0f0f12] border border-white/[0.06] text-[#f5f5f7] text-sm placeholder:text-[#52525b] focus:outline-none focus:border-[#7c6cf9]/40"
              />
            </div>
            <span className="text-[#52525b] text-xs">
              {filteredLinks.length} result{filteredLinks.length !== 1 ? 's' : ''}
            </span>
          </div>

          {/* Broken Links Table */}
          <div className="rounded-2xl border border-white/[0.06] bg-[#0a0a0c]/60 backdrop-blur-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="px-4 py-3 text-[#52525b] text-xs font-medium uppercase tracking-wider">Page URL</th>
                    <th className="px-4 py-3 text-[#52525b] text-xs font-medium uppercase tracking-wider">Broken Link</th>
                    <th className="px-4 py-3 text-[#52525b] text-xs font-medium uppercase tracking-wider">Anchor Text</th>
                    <th className="px-4 py-3 text-[#52525b] text-xs font-medium uppercase tracking-wider">Status</th>
                    <th className="px-4 py-3 text-[#52525b] text-xs font-medium uppercase tracking-wider">Error Type</th>
                    <th className="px-4 py-3 text-[#52525b] text-xs font-medium uppercase tracking-wider">Checked</th>
                    <th className="px-4 py-3 text-[#52525b] text-xs font-medium uppercase tracking-wider text-right">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredLinks.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-12 text-center">
                        <CheckCircle className="w-8 h-8 text-[#4ade80] mx-auto mb-2" />
                        <p className="text-[#52525b] text-sm">
                          {brokenLinks.length === 0 ? 'No broken links found!' : 'No links match your filters'}
                        </p>
                      </td>
                    </tr>
                  ) : (
                    filteredLinks.map((link, i) => {
                      const cfg = getErrorConfig(link.error_type);
                      const Icon = cfg.icon;
                      return (
                        <motion.tr
                          key={link.id}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: i * 0.02 }}
                          className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors"
                        >
                          <td className="px-4 py-3">
                            <a
                              href={link.page_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[#7c6cf9] text-sm hover:underline flex items-center gap-1"
                            >
                              {truncateUrl(link.page_url, 40)}
                              <ExternalLink className="w-3 h-3 opacity-60" />
                            </a>
                          </td>
                          <td className="px-4 py-3">
                            <a
                              href={link.link_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[#a1a1aa] text-sm hover:text-[#f5f5f7] flex items-center gap-1"
                            >
                              {truncateUrl(link.link_url, 45)}
                              <ExternalLink className="w-3 h-3 opacity-40" />
                            </a>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-[#a1a1aa] text-sm">
                              {link.anchor_text || <span className="text-[#52525b] italic">none</span>}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium ${
                              link.status_code >= 500
                                ? 'bg-[#fbbf24]/10 text-[#fbbf24]'
                                : link.status_code === 404
                                ? 'bg-[#f87171]/10 text-[#f87171]'
                                : link.status_code === 0
                                ? 'bg-[#fb923c]/10 text-[#fb923c]'
                                : 'bg-[#52525b]/10 text-[#52525b]'
                            }`}>
                              {link.status_code || '—'}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${cfg.bg} ${cfg.color}`}>
                              <Icon className="w-3 h-3" />
                              {cfg.label}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-[#52525b] text-xs">
                              {link.checked_at
                                ? new Date(link.checked_at).toLocaleDateString()
                                : '—'}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              onClick={() => markFixed(link.id)}
                              disabled={markingFixed === link.id}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#4ade80]/10 text-[#4ade80] text-xs font-medium hover:bg-[#4ade80]/20 transition-colors disabled:opacity-50"
                            >
                              {markingFixed === link.id ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <CheckCircle className="w-3 h-3" />
                              )}
                              Fixed
                            </button>
                          </td>
                        </motion.tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Last checked */}
          {summary?.last_checked && (
            <p className="text-[#52525b] text-xs text-right">
              Last scanned: {new Date(summary.last_checked).toLocaleString()}
            </p>
          )}
        </>
      )}
    </div>
  );
}
