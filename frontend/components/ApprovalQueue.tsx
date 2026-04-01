// frontend/components/ApprovalQueue.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Sparkles, CheckCircle, XCircle, Clock, Zap, Image,
  FileText, Link, Globe, ChevronDown, ChevronRight,
  Loader2, Search, Filter, Edit3, Check, X, ArrowRight,
  AlertTriangle, RefreshCw, Layers, ShoppingCart, Type
} from 'lucide-react';

interface Fix {
  id: number;
  fix_type: string;
  platform: string;
  resource_type: string;
  resource_id: string;
  resource_url: string;
  resource_title: string;
  field_name: string;
  current_value: string;
  proposed_value: string;
  ai_reasoning: string;
  status: string;
  severity: string;
  category: string;
  batch_id: string;
  error_message: string | null;
  applied_at: string | null;
  created_at: string;
}

interface FixSummary {
  total: number;
  by_status: { pending: number; approved: number; rejected: number; applied: number; failed: number };
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
}

export default function ApprovalQueue({ websiteId }: { websiteId: number }) {
  const [fixes, setFixes] = useState<Fix[]>([]);
  const [summary, setSummary] = useState<FixSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [statusFilter, setStatusFilter] = useState('pending');
  const [typeFilter, setTypeFilter] = useState('');
  const [expandedFix, setExpandedFix] = useState<number | null>(null);
  const [editingFix, setEditingFix] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const [applyingFix, setApplyingFix] = useState<number | null>(null);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchFixes = useCallback(async () => {
    try {
      let url = `${API_URL}/api/fixes/${websiteId}?limit=200`;
      if (statusFilter) url += `&status=${statusFilter}`;
      if (typeFilter) url += `&fix_type=${typeFilter}`;

      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setFixes(data.fixes || []);
      }
    } catch (error) {
      console.error('Error fetching fixes:', error);
    } finally {
      setLoading(false);
    }
  }, [API_URL, websiteId, statusFilter, typeFilter]);

  const fetchSummary = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/fixes/${websiteId}/summary`);
      if (response.ok) {
        const data = await response.json();
        setSummary(data);
      }
    } catch (error) {
      console.error('Error fetching summary:', error);
    }
  }, [API_URL, websiteId]);

  useEffect(() => {
    fetchFixes();
    fetchSummary();
  }, [fetchFixes, fetchSummary]);

  // Poll while scanning
  useEffect(() => {
    if (!scanning) return;
    const interval = setInterval(() => {
      fetchFixes();
      fetchSummary();
    }, 5000);
    return () => clearInterval(interval);
  }, [scanning, fetchFixes, fetchSummary]);

  const startScan = async () => {
    setScanning(true);
    try {
      await fetch(`${API_URL}/api/fixes/${websiteId}/scan`, { method: 'POST' });
      // Poll for results
      setTimeout(() => {
        fetchFixes();
        fetchSummary();
        setTimeout(() => setScanning(false), 60000); // Stop polling after 1 min
      }, 5000);
    } catch (error) {
      console.error('Error starting scan:', error);
      setScanning(false);
    }
  };

  const approveFix = async (fixId: number) => {
    try {
      await fetch(`${API_URL}/api/fixes/${fixId}/approve`, { method: 'POST' });
      fetchFixes();
      fetchSummary();
    } catch (error) {
      console.error('Error approving fix:', error);
    }
  };

  const rejectFix = async (fixId: number) => {
    try {
      await fetch(`${API_URL}/api/fixes/${fixId}/reject`, { method: 'POST' });
      fetchFixes();
      fetchSummary();
    } catch (error) {
      console.error('Error rejecting fix:', error);
    }
  };

  const applyFix = async (fixId: number) => {
    setApplyingFix(fixId);
    try {
      await fetch(`${API_URL}/api/fixes/${fixId}/apply`, { method: 'POST' });
      setTimeout(() => {
        fetchFixes();
        fetchSummary();
        setApplyingFix(null);
      }, 3000);
    } catch (error) {
      console.error('Error applying fix:', error);
      setApplyingFix(null);
    }
  };

  const saveEdit = async (fixId: number) => {
    try {
      await fetch(`${API_URL}/api/fixes/${fixId}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposed_value: editValue })
      });
      setEditingFix(null);
      fetchFixes();
    } catch (error) {
      console.error('Error saving edit:', error);
    }
  };

  const batchApprove = async (fixType?: string) => {
    try {
      await fetch(`${API_URL}/api/fixes/${websiteId}/batch/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(fixType ? { fix_type: fixType } : { fix_ids: fixes.filter(f => f.status === 'pending').map(f => f.id) })
      });
      fetchFixes();
      fetchSummary();
    } catch (error) {
      console.error('Error batch approving:', error);
    }
  };

  const batchApply = async () => {
    try {
      await fetch(`${API_URL}/api/fixes/${websiteId}/batch/apply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fix_ids: [] }) // Empty = apply all approved
      });
      setTimeout(() => { fetchFixes(); fetchSummary(); }, 5000);
    } catch (error) {
      console.error('Error batch applying:', error);
    }
  };

  const getFixTypeIcon = (type: string) => {
    switch (type) {
      case 'alt_text': return <Image className="w-4 h-4" />;
      case 'meta_title': return <Type className="w-4 h-4" />;
      case 'meta_description': return <FileText className="w-4 h-4" />;
      case 'broken_link': return <Link className="w-4 h-4" />;
      case 'thin_content': return <FileText className="w-4 h-4" />;
      default: return <Globe className="w-4 h-4" />;
    }
  };

  const getFixTypeLabel = (type: string) => {
    switch (type) {
      case 'alt_text': return 'Alt Text';
      case 'meta_title': return 'Meta Title';
      case 'meta_description': return 'Meta Description';
      case 'broken_link': return 'Broken Link';
      case 'thin_content': return 'Thin Content';
      case 'structured_data': return 'Structured Data';
      default: return type;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'approved': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'applied': return 'bg-green-500/20 text-green-400 border-green-500/30';
      case 'rejected': return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
      case 'failed': return 'bg-red-500/20 text-red-400 border-red-500/30';
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'text-red-400';
      case 'high': return 'text-orange-400';
      case 'medium': return 'text-yellow-400';
      case 'low': return 'text-blue-400';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-3">
            <Sparkles className="w-6 h-6 text-yellow-400" />
            Auto-Fix Queue
          </h2>
          <p className="text-purple-300 mt-1">AI-generated fixes awaiting your approval</p>
        </div>
        <div className="flex items-center gap-3">
          {summary && summary.by_status.approved > 0 && (
            <button onClick={batchApply}
              className="bg-green-500/20 text-green-400 px-4 py-2 rounded-lg font-medium hover:bg-green-500/30 transition-all flex items-center gap-2">
              <Zap className="w-4 h-4" />
              Apply All Approved ({summary.by_status.approved})
            </button>
          )}
          <button onClick={startScan} disabled={scanning}
            className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-4 py-2 rounded-lg font-medium hover:shadow-lg transition-all flex items-center gap-2 disabled:opacity-50">
            {scanning ? (<><Loader2 className="w-4 h-4 animate-spin" />Scanning...</>) : (<><Search className="w-4 h-4" />Scan for Fixes</>)}
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && summary.total > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { label: 'Pending', count: summary.by_status.pending, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
            { label: 'Approved', count: summary.by_status.approved, color: 'text-blue-400', bg: 'bg-blue-500/10' },
            { label: 'Applied', count: summary.by_status.applied, color: 'text-green-400', bg: 'bg-green-500/10' },
            { label: 'Rejected', count: summary.by_status.rejected, color: 'text-gray-400', bg: 'bg-gray-500/10' },
            { label: 'Failed', count: summary.by_status.failed, color: 'text-red-400', bg: 'bg-red-500/10' },
          ].map(item => (
            <button key={item.label} onClick={() => setStatusFilter(item.label.toLowerCase())}
              className={`${item.bg} rounded-xl p-4 text-center border transition-all ${statusFilter === item.label.toLowerCase() ? 'border-purple-500' : 'border-white/10 hover:border-white/20'}`}>
              <p className={`text-2xl font-bold ${item.color}`}>{item.count}</p>
              <p className="text-gray-400 text-xs mt-1">{item.label}</p>
            </button>
          ))}
        </div>
      )}

      {/* Filters & Batch Actions */}
      {fixes.length > 0 && (
        <div className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-purple-400" />
              <span className="text-white font-medium text-sm">Filter:</span>
            </div>
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}
              className="bg-white/10 text-white border border-white/20 rounded-lg px-3 py-1.5 text-sm">
              <option value="">All Types</option>
              <option value="alt_text">Alt Text</option>
              <option value="meta_title">Meta Title</option>
              <option value="meta_description">Meta Description</option>
              <option value="broken_link">Broken Links</option>
              <option value="thin_content">Thin Content</option>
            </select>

            {statusFilter === 'pending' && fixes.length > 0 && (
              <div className="ml-auto flex items-center gap-2">
                <button onClick={() => batchApprove()}
                  className="bg-green-500/20 text-green-400 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-green-500/30 transition-all flex items-center gap-1.5">
                  <Check className="w-3 h-3" /> Approve All
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Empty States */}
      {!loading && fixes.length === 0 && !scanning && (
        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
          <div className="w-16 h-16 bg-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <Sparkles className="w-8 h-8 text-purple-400" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">No Fixes Found</h3>
          <p className="text-purple-300 mb-6">
            {statusFilter !== 'pending'
              ? `No ${statusFilter} fixes. Try a different filter.`
              : 'Click "Scan for Fixes" to let AI analyze your site and generate fix proposals.'}
          </p>
          {statusFilter === 'pending' && (
            <button onClick={startScan} disabled={scanning}
              className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-6 py-3 rounded-lg font-medium">
              <Search className="w-4 h-4 inline mr-2" /> Scan for Fixes
            </button>
          )}
        </div>
      )}

      {scanning && fixes.length === 0 && (
        <div className="bg-purple-500/10 border border-purple-500/30 rounded-xl p-8 text-center">
          <Loader2 className="w-10 h-10 text-purple-400 animate-spin mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-white mb-2">Scanning Your Site...</h3>
          <p className="text-purple-300 text-sm">Analyzing products and pages for SEO issues. This may take 1-2 minutes.</p>
        </div>
      )}

      {/* Fix List */}
      <div className="space-y-3">
        <AnimatePresence>
          {fixes.map((fix) => (
            <motion.div key={fix.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              className="bg-white/10 backdrop-blur-md rounded-xl border border-white/20 overflow-hidden">

              {/* Fix Header */}
              <div className="p-4 cursor-pointer hover:bg-white/5 transition-all"
                onClick={() => setExpandedFix(expandedFix === fix.id ? null : fix.id)}>
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3 flex-1">
                    <div className="p-2 bg-purple-500/20 rounded-lg shrink-0">
                      {getFixTypeIcon(fix.fix_type)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-white font-medium">{fix.resource_title || 'Untitled'}</h4>
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${getStatusColor(fix.status)}`}>
                          {fix.status}
                        </span>
                        <span className="text-xs text-gray-500 bg-white/5 px-2 py-0.5 rounded-full">
                          {getFixTypeLabel(fix.fix_type)}
                        </span>
                        <span className={`text-xs ${getSeverityColor(fix.severity)}`}>
                          {fix.severity}
                        </span>
                      </div>
                      <p className="text-gray-400 text-sm mt-1 truncate">{fix.resource_url}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 ml-3 shrink-0">
                    {fix.status === 'pending' && (
                      <>
                        <button onClick={(e) => { e.stopPropagation(); approveFix(fix.id); }}
                          className="bg-green-500/20 text-green-400 p-1.5 rounded-lg hover:bg-green-500/30 transition-all" title="Approve">
                          <Check className="w-4 h-4" />
                        </button>
                        <button onClick={(e) => { e.stopPropagation(); rejectFix(fix.id); }}
                          className="bg-red-500/20 text-red-400 p-1.5 rounded-lg hover:bg-red-500/30 transition-all" title="Reject">
                          <X className="w-4 h-4" />
                        </button>
                      </>
                    )}
                    {fix.status === 'approved' && (
                      <button onClick={(e) => { e.stopPropagation(); applyFix(fix.id); }}
                        disabled={applyingFix === fix.id}
                        className="bg-blue-500/20 text-blue-400 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-blue-500/30 transition-all flex items-center gap-1.5 disabled:opacity-50">
                        {applyingFix === fix.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                        Apply
                      </button>
                    )}
                    <ChevronRight className={`w-4 h-4 text-gray-500 transition-transform ${expandedFix === fix.id ? 'rotate-90' : ''}`} />
                  </div>
                </div>
              </div>

              {/* Expanded Detail */}
              <AnimatePresence>
                {expandedFix === fix.id && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }}
                    className="border-t border-white/10">
                    <div className="p-4 space-y-4">
                      {/* Before / After */}
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
                          <p className="text-red-400 text-xs font-medium mb-2">CURRENT</p>
                          <p className="text-gray-300 text-sm">{fix.current_value || '(empty)'}</p>
                        </div>
                        <div className="bg-green-500/5 border border-green-500/20 rounded-lg p-3">
                          <div className="flex items-center justify-between mb-2">
                            <p className="text-green-400 text-xs font-medium">PROPOSED</p>
                            {fix.status === 'pending' && (
                              <button onClick={() => { setEditingFix(fix.id); setEditValue(fix.proposed_value); }}
                                className="text-gray-400 hover:text-white transition-colors">
                                <Edit3 className="w-3 h-3" />
                              </button>
                            )}
                          </div>
                          {editingFix === fix.id ? (
                            <div className="space-y-2">
                              <textarea value={editValue} onChange={(e) => setEditValue(e.target.value)}
                                className="w-full bg-white/10 border border-white/20 rounded px-3 py-2 text-white text-sm h-20 resize-none" />
                              <div className="flex gap-2">
                                <button onClick={() => saveEdit(fix.id)}
                                  className="bg-green-500/20 text-green-400 px-3 py-1 rounded text-xs hover:bg-green-500/30">Save</button>
                                <button onClick={() => setEditingFix(null)}
                                  className="bg-white/10 text-gray-400 px-3 py-1 rounded text-xs hover:bg-white/20">Cancel</button>
                              </div>
                            </div>
                          ) : (
                            <p className="text-gray-300 text-sm">{fix.proposed_value}</p>
                          )}
                        </div>
                      </div>

                      {/* AI Reasoning */}
                      {fix.ai_reasoning && (
                        <div className="bg-purple-500/5 border border-purple-500/20 rounded-lg p-3">
                          <p className="text-purple-400 text-xs font-medium mb-1">AI REASONING</p>
                          <p className="text-gray-300 text-sm">{fix.ai_reasoning}</p>
                        </div>
                      )}

                      {/* Error message */}
                      {fix.error_message && (
                        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                          <p className="text-red-400 text-xs font-medium mb-1">ERROR</p>
                          <p className="text-red-300 text-sm">{fix.error_message}</p>
                        </div>
                      )}

                      {/* Meta info */}
                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        <span>Platform: {fix.platform}</span>
                        <span>Type: {fix.resource_type}</span>
                        <span>Created: {new Date(fix.created_at).toLocaleString()}</span>
                        {fix.applied_at && <span className="text-green-400">Applied: {new Date(fix.applied_at).toLocaleString()}</span>}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
