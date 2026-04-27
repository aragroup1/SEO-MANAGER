// frontend/components/AuditDashboard.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity, AlertTriangle, CheckCircle, XCircle, Clock,
  TrendingUp, TrendingDown, Minus, Eye, Download,
  RefreshCw, Calendar, Filter, Search, ChevronRight,
  Shield, Gauge, Globe, Link, FileText, Image,
  Zap, Smartphone, Lock, ArrowUp, ArrowDown, Rocket,
  Monitor, Columns, Bug
} from 'lucide-react';
import IntegrationSetupChecklist from './IntegrationSetupChecklist';

interface CoreWebVitals {
  mobile?: {
    lcp: number;
    cls: number;
    tbt: number;
    fcp: number;
    speed_index: number;
    performance_score: number;
    seo_score: number;
    accessibility_score: number;
  };
  desktop?: {
    lcp: number;
    cls: number;
    tbt: number;
    fcp: number;
    speed_index: number;
    performance_score: number;
    seo_score: number;
    accessibility_score: number;
  };
}

interface AuditData {
  audit: {
    id: number;
    health_score: number;
    previous_score: number;
    score_change: number;
    technical_score: number;
    content_score: number;
    performance_score: number;
    mobile_score: number;
    desktop_score: number;
    security_score: number;
    total_issues: number;
    critical_issues: number;
    errors: number;
    warnings: number;
    notices: number;
    new_issues: number;
    fixed_issues: number;
    audit_date: string;
    domain?: string;
    core_web_vitals?: CoreWebVitals;
  } | null;
  issues: Issue[];
  recommendations: Recommendation[];
  message?: string;
}

interface Issue {
  id: number;
  issue_type: string;
  severity: string;
  category: string;
  title: string;
  description?: string;
  affected_pages?: string[];
  how_to_fix: string;
  estimated_impact: number;
  effort_required: string;
  extra_data?: any;
}

interface Recommendation {
  id: number;
  priority: number;
  category?: string;
  title: string;
  description: string;
  expected_impact: string;
  implementation_complexity: string;
  estimated_traffic_gain: number;
}

type DeviceView = 'mobile' | 'desktop' | 'compare';

export default function AuditDashboard({ websiteId }: { websiteId: number }) {
  const [auditData, setAuditData] = useState<AuditData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedSeverity, setSelectedSeverity] = useState('all');
  const [isRunningAudit, setIsRunningAudit] = useState(false);
  const [expandedIssue, setExpandedIssue] = useState<number | null>(null);
  const [siteType, setSiteType] = useState('custom');
  const [pollCount, setPollCount] = useState(0);
  const [initialAuditId, setInitialAuditId] = useState<number | null>(null);
  const [deviceView, setDeviceView] = useState<DeviceView>('mobile');

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchLatestAudit = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/audit/${websiteId}`);
      if (response.ok) {
        const data = await response.json();
        setAuditData(data);
        return data;
      }
    } catch (error) {
      console.error('Error fetching audit:', error);
    } finally {
      setLoading(false);
    }
    return null;
  }, [API_URL, websiteId]);

  useEffect(() => {
    setLoading(true);
    fetchLatestAudit().then(data => {
      if (data?.audit) {
        setInitialAuditId(data.audit.id);
      }
    });
    fetchWebsiteInfo();
  }, [websiteId, fetchLatestAudit]);

  // Poll for results when audit is running
  useEffect(() => {
    if (!isRunningAudit) return;

    const interval = setInterval(async () => {
      const data = await fetchLatestAudit();
      setPollCount(prev => {
        // Stop polling if we got a NEW audit result or timed out
        if (data?.audit && data.audit.id !== initialAuditId) {
          setIsRunningAudit(false);
          return 0;
        }
        if (prev >= 15) {
          setIsRunningAudit(false);
          return 0;
        }
        return prev + 1;
      });
    }, 4000);

    return () => clearInterval(interval);
  }, [isRunningAudit, fetchLatestAudit, initialAuditId]);

  const fetchWebsiteInfo = async () => {
    try {
      const response = await fetch(`${API_URL}/websites`);
      if (response.ok) {
        const websites = await response.json();
        const current = websites.find((w: any) => w.id === websiteId);
        if (current) {
          setSiteType(current.site_type || 'custom');
        }
      }
    } catch (error) {
      console.error('Error fetching website info:', error);
    }
  };

  const runAudit = async () => {
    // Remember current audit ID so we can detect when a new one arrives
    if (auditData?.audit) {
      setInitialAuditId(auditData.audit.id);
    }
    setIsRunningAudit(true);
    setPollCount(0);
    try {
      await fetch(`${API_URL}/api/audit/${websiteId}/start`, { method: 'POST' });
    } catch (error) {
      console.error('Error starting audit:', error);
      setIsRunningAudit(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return 'text-green-400';
    if (score >= 70) return 'text-yellow-400';
    if (score >= 50) return 'text-orange-400';
    return 'text-red-400';
  };

  const getScoreBadgeColor = (score: number) => {
    if (score >= 90) return 'bg-green-500/20 text-green-400 border-green-500/30';
    if (score >= 70) return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
    if (score >= 50) return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
    return 'bg-red-500/20 text-red-400 border-red-500/30';
  };

  const getSeverityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'error': return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
      case 'warning': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'notice': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  const getCategoryIcon = (category: string) => {
    switch (category?.toLowerCase()) {
      case 'technical': return <Globe className="w-4 h-4" />;
      case 'content': return <FileText className="w-4 h-4" />;
      case 'performance': return <Gauge className="w-4 h-4" />;
      case 'mobile': return <Smartphone className="w-4 h-4" />;
      case 'security': return <Lock className="w-4 h-4" />;
      case 'accessibility': return <Eye className="w-4 h-4" />;
      default: return <AlertTriangle className="w-4 h-4" />;
    }
  };

  const filteredIssues = auditData?.issues?.filter(issue => {
    if (selectedCategory !== 'all' && issue.category?.toLowerCase() !== selectedCategory) return false;
    if (selectedSeverity !== 'all' && issue.severity?.toLowerCase() !== selectedSeverity) return false;
    return true;
  }) || [];

  // Device-filtered issues
  const getDeviceFilteredIssues = () => {
    if (deviceView === 'compare') return filteredIssues;
    if (deviceView === 'mobile') {
      return filteredIssues.filter(issue =>
        issue.category?.toLowerCase() === 'mobile' ||
        issue.issue_type?.toLowerCase().includes('mobile') ||
        issue.title?.toLowerCase().includes('mobile')
      );
    }
    // desktop
    return filteredIssues.filter(issue =>
      issue.category?.toLowerCase() !== 'mobile' &&
      !issue.issue_type?.toLowerCase().includes('mobile') &&
      !issue.title?.toLowerCase().includes('mobile')
    );
  };

  const deviceIssues = getDeviceFilteredIssues();

  const cwv = auditData?.audit?.core_web_vitals;
  const mobileCwv = cwv?.mobile;
  const desktopCwv = cwv?.desktop;

  const renderMobileScoreCard = () => {
    const score = auditData?.audit?.mobile_score ?? 0;
    return (
      <div className="bg-white/10 rounded-xl p-4 text-center border border-white/10">
        <div className="flex items-center justify-center gap-2 mb-2">
          <Smartphone className="w-5 h-5 text-purple-400" />
          <span className="text-xs text-gray-400">Mobile Score</span>
        </div>
        <p className={`text-3xl font-bold ${getScoreColor(score)}`}>{Math.round(score)}</p>
        <span className={`inline-block mt-2 text-xs px-2 py-0.5 rounded-full border ${getScoreBadgeColor(score)}`}>
          {score >= 90 ? 'Excellent' : score >= 70 ? 'Good' : score >= 50 ? 'Needs Work' : 'Poor'}
        </span>
      </div>
    );
  };

  const renderDesktopScoreCard = () => {
    const score = auditData?.audit?.desktop_score ?? 0;
    return (
      <div className="bg-white/10 rounded-xl p-4 text-center border border-white/10">
        <div className="flex items-center justify-center gap-2 mb-2">
          <Monitor className="w-5 h-5 text-purple-400" />
          <span className="text-xs text-gray-400">Desktop Score</span>
        </div>
        <p className={`text-3xl font-bold ${getScoreColor(score)}`}>{Math.round(score)}</p>
        <span className={`inline-block mt-2 text-xs px-2 py-0.5 rounded-full border ${getScoreBadgeColor(score)}`}>
          {score >= 90 ? 'Excellent' : score >= 70 ? 'Good' : score >= 50 ? 'Needs Work' : 'Poor'}
        </span>
      </div>
    );
  };

  const renderCWVMetric = (label: string, value: number, unit: string, thresholdGood: number, thresholdPoor: number, mobileValue?: number, desktopValue?: number) => {
    let color = 'text-green-400';
    if (value >= thresholdPoor) color = 'text-red-400';
    else if (value >= thresholdGood) color = 'text-yellow-400';

    if (deviceView === 'compare' && mobileValue !== undefined && desktopValue !== undefined) {
      let mColor = 'text-green-400';
      if (mobileValue >= thresholdPoor) mColor = 'text-red-400';
      else if (mobileValue >= thresholdGood) mColor = 'text-yellow-400';
      let dColor = 'text-green-400';
      if (desktopValue >= thresholdPoor) dColor = 'text-red-400';
      else if (desktopValue >= thresholdGood) dColor = 'text-yellow-400';

      return (
        <div className="bg-white/5 rounded-lg p-3">
          <p className="text-xs text-gray-400 mb-1">{label}</p>
          <div className="flex items-center justify-between">
            <div className="text-center">
              <p className={`text-lg font-bold ${mColor}`}>{mobileValue}{unit}</p>
              <p className="text-[10px] text-gray-500">Mobile</p>
            </div>
            <div className="text-center">
              <p className={`text-lg font-bold ${dColor}`}>{desktopValue}{unit}</p>
              <p className="text-[10px] text-gray-500">Desktop</p>
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="bg-white/5 rounded-lg p-3">
        <p className="text-xs text-gray-400 mb-1">{label}</p>
        <p className={`text-xl font-bold ${color}`}>{value}{unit}</p>
      </div>
    );
  };

  const renderDeviceViewToggle = () => (
    <div className="flex items-center bg-white/10 rounded-lg p-1 border border-white/10">
      <button
        onClick={() => setDeviceView('mobile')}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
          deviceView === 'mobile'
            ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/25'
            : 'text-gray-300 hover:text-white'
        }`}
      >
        <Smartphone className="w-4 h-4" />
        Mobile
      </button>
      <button
        onClick={() => setDeviceView('desktop')}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
          deviceView === 'desktop'
            ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/25'
            : 'text-gray-300 hover:text-white'
        }`}
      >
        <Monitor className="w-4 h-4" />
        Desktop
      </button>
      <button
        onClick={() => setDeviceView('compare')}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
          deviceView === 'compare'
            ? 'bg-purple-500 text-white shadow-lg shadow-purple-500/25'
            : 'text-gray-300 hover:text-white'
        }`}
      >
        <Columns className="w-4 h-4" />
        Compare
      </button>
    </div>
  );

  const renderMobileIssuesHighlight = () => {
    const mobileIssues = auditData?.issues?.filter(i => i.category?.toLowerCase() === 'mobile') || [];
    if (mobileIssues.length === 0) return null;

    const criticalMobile = mobileIssues.filter(i => i.severity?.toLowerCase() === 'critical' || i.severity?.toLowerCase() === 'error');
    const warningMobile = mobileIssues.filter(i => i.severity?.toLowerCase() === 'warning');

    return (
      <div className="bg-gradient-to-r from-purple-500/10 to-pink-500/10 rounded-xl p-4 border border-purple-500/20">
        <div className="flex items-center gap-2 mb-3">
          <Bug className="w-5 h-5 text-purple-400" />
          <h3 className="text-white font-medium">Mobile-Specific Issues</h3>
          <span className="text-xs text-purple-300 bg-purple-500/20 px-2 py-0.5 rounded-full">{mobileIssues.length} found</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {criticalMobile.length > 0 && (
            <div className="flex items-center gap-2 text-red-400 text-sm">
              <XCircle className="w-4 h-4 shrink-0" />
              <span>{criticalMobile.length} critical mobile issue{criticalMobile.length !== 1 ? 's' : ''}</span>
            </div>
          )}
          {warningMobile.length > 0 && (
            <div className="flex items-center gap-2 text-yellow-400 text-sm">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{warningMobile.length} mobile warning{warningMobile.length !== 1 ? 's' : ''}</span>
            </div>
          )}
          {mobileIssues.some(i => i.issue_type?.toLowerCase().includes('viewport')) && (
            <div className="flex items-center gap-2 text-orange-400 text-sm">
              <Smartphone className="w-4 h-4 shrink-0" />
              <span>Viewport issues detected</span>
            </div>
          )}
          {mobileIssues.some(i => i.issue_type?.toLowerCase().includes('tap')) && (
            <div className="flex items-center gap-2 text-orange-400 text-sm">
              <Smartphone className="w-4 h-4 shrink-0" />
              <span>Touch target issues</span>
            </div>
          )}
          {mobileIssues.some(i => i.issue_type?.toLowerCase().includes('font')) && (
            <div className="flex items-center gap-2 text-orange-400 text-sm">
              <FileText className="w-4 h-4 shrink-0" />
              <span>Font size issues on mobile</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-500"></div>
      </div>
    );
  }

  // No audit has been run yet
  if (!auditData?.audit) {
    return (
      <div className="space-y-6">
        <IntegrationSetupChecklist websiteId={websiteId} siteType={siteType} onIntegrationChange={fetchLatestAudit} />

        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
          <div className="w-20 h-20 bg-purple-500/20 rounded-full flex items-center justify-center mx-auto mb-6">
            {isRunningAudit ? (
              <RefreshCw className="w-10 h-10 text-purple-400 animate-spin" />
            ) : (
              <Rocket className="w-10 h-10 text-purple-400" />
            )}
          </div>

          {isRunningAudit ? (
            <>
              <h2 className="text-2xl font-bold text-white mb-3">Audit In Progress...</h2>
              <p className="text-purple-300 mb-2">Crawling your site and analyzing SEO factors. This usually takes 10-30 seconds.</p>
              <p className="text-gray-500 text-sm">Checking: meta tags, headings, images, links, robots.txt, sitemap, SSL, structured data, performance...</p>
            </>
          ) : (
            <>
              <h2 className="text-2xl font-bold text-white mb-3">No Audit Yet</h2>
              <p className="text-purple-300 mb-6">{auditData?.message || "Run your first SEO audit to get actionable insights about your website."}</p>
              <button onClick={runAudit}
                className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-8 py-3 rounded-lg font-medium hover:shadow-lg hover:shadow-purple-500/25 transition-all text-lg">
                Run First Audit
              </button>
            </>
          )}
        </div>
      </div>
    );
  }

  const audit = auditData.audit;

  return (
    <div className="space-y-6">
      <IntegrationSetupChecklist websiteId={websiteId} siteType={siteType} onIntegrationChange={fetchLatestAudit} />

      {/* Running audit overlay */}
      {isRunningAudit && (
        <div className="bg-purple-500/10 border border-purple-500/30 rounded-xl p-4 flex items-center gap-3">
          <RefreshCw className="w-5 h-5 text-purple-400 animate-spin shrink-0" />
          <p className="text-purple-300 text-sm">New audit is running... results will update automatically.</p>
        </div>
      )}

      {/* Header with Health Score */}
      <div className="bg-gradient-to-r from-purple-500/20 to-pink-500/20 backdrop-blur-md rounded-2xl p-6 border border-white/20">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
          <div>
            <h2 className="text-2xl font-bold text-white mb-1">
              Site Health Audit
              {audit.domain && <span className="text-purple-300 text-lg font-normal ml-3">— {audit.domain}</span>}
            </h2>
            <p className="text-purple-300 text-sm">Last audit: {new Date(audit.audit_date).toLocaleString()}</p>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            {renderDeviceViewToggle()}
            <button onClick={runAudit} disabled={isRunningAudit}
              className="bg-purple-500 text-white px-4 py-2 rounded-lg font-medium hover:bg-purple-600 transition-all flex items-center gap-2 disabled:opacity-50">
              {isRunningAudit ? (<><RefreshCw className="w-4 h-4 animate-spin" />Running...</>) : (<><RefreshCw className="w-4 h-4" />Run New Audit</>)}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center">
            <div className="relative inline-flex items-center justify-center">
              <svg className="w-32 h-32 transform -rotate-90">
                <circle cx="64" cy="64" r="56" stroke="rgba(255,255,255,0.1)" strokeWidth="12" fill="none" />
                <circle cx="64" cy="64" r="56" stroke="url(#scoreGrad)" strokeWidth="12" fill="none"
                  strokeDasharray={`${(audit.health_score / 100) * 351.86} 351.86`} strokeLinecap="round" />
                <defs><linearGradient id="scoreGrad"><stop offset="0%" stopColor="#a855f7" /><stop offset="100%" stopColor="#ec4899" /></linearGradient></defs>
              </svg>
              <div className="absolute">
                <p className={`text-4xl font-bold ${getScoreColor(audit.health_score)}`}>{Math.round(audit.health_score)}</p>
                <p className="text-xs text-gray-400">Health Score</p>
              </div>
            </div>
            <div className="mt-4 flex items-center justify-center gap-2">
              {audit.score_change > 0 ? <ArrowUp className="w-4 h-4 text-green-400" /> : audit.score_change < 0 ? <ArrowDown className="w-4 h-4 text-red-400" /> : <Minus className="w-4 h-4 text-gray-400" />}
              <span className={audit.score_change > 0 ? 'text-green-400' : audit.score_change < 0 ? 'text-red-400' : 'text-gray-400'}>
                {audit.score_change > 0 ? '+' : ''}{audit.score_change} points
              </span>
            </div>
          </div>

          <div className="space-y-3">
            <h3 className="text-white font-medium mb-2">Issue Breakdown</h3>
            {[
              { label: 'Critical', count: audit.critical_issues, color: 'text-red-400', Icon: XCircle },
              { label: 'Errors', count: audit.errors, color: 'text-orange-400', Icon: AlertTriangle },
              { label: 'Warnings', count: audit.warnings, color: 'text-yellow-400', Icon: Clock },
              { label: 'Notices', count: audit.notices, color: 'text-blue-400', Icon: Eye },
            ].map(item => (
              <div key={item.label} className="flex items-center justify-between">
                <span className={`${item.color} flex items-center gap-2`}><item.Icon className="w-4 h-4" /> {item.label}</span>
                <span className="text-white font-bold">{item.count}</span>
              </div>
            ))}
          </div>

          <div className="space-y-3">
            <h3 className="text-white font-medium mb-2">Summary</h3>
            <div className="flex items-center justify-between"><span className="text-purple-300">Total Issues</span><span className="text-white font-bold">{audit.total_issues}</span></div>
            <div className="flex items-center justify-between"><span className="text-purple-300">Report ID</span><span className="text-white font-bold">#{audit.id}</span></div>
          </div>
        </div>

        {/* Mobile/Desktop Score Cards */}
        {deviceView === 'compare' ? (
          <div className="grid grid-cols-2 gap-4 mt-6">
            {renderMobileScoreCard()}
            {renderDesktopScoreCard()}
          </div>
        ) : deviceView === 'mobile' ? (
          <div className="grid grid-cols-1 gap-4 mt-6">
            {renderMobileScoreCard()}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 mt-6">
            {renderDesktopScoreCard()}
          </div>
        )}

        <div className="grid grid-cols-5 gap-4 mt-6">
          {[
            { label: 'Technical', score: audit.technical_score, Icon: Globe },
            { label: 'Content', score: audit.content_score, Icon: FileText },
            { label: 'Performance', score: audit.performance_score, Icon: Gauge },
            { label: 'Mobile', score: audit.mobile_score, Icon: Smartphone },
            { label: 'Security', score: audit.security_score, Icon: Lock }
          ].map((cat) => (
            <div key={cat.label} className="bg-white/10 rounded-xl p-4 text-center">
              <cat.Icon className="w-5 h-5 text-purple-400 mx-auto mb-2" />
              <p className="text-xs text-gray-400 mb-1">{cat.label}</p>
              <p className={`text-2xl font-bold ${getScoreColor(cat.score)}`}>{Math.round(cat.score)}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Core Web Vitals Section */}
      {(mobileCwv || desktopCwv) && (
        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
          <h3 className="text-white font-medium mb-4 flex items-center gap-2">
            <Gauge className="w-5 h-5 text-purple-400" />
            Core Web Vitals
            {deviceView === 'mobile' && <span className="text-xs text-purple-300 bg-purple-500/20 px-2 py-0.5 rounded-full">Mobile</span>}
            {deviceView === 'desktop' && <span className="text-xs text-blue-300 bg-blue-500/20 px-2 py-0.5 rounded-full">Desktop</span>}
            {deviceView === 'compare' && <span className="text-xs text-gray-300 bg-white/10 px-2 py-0.5 rounded-full">Side by Side</span>}
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {deviceView === 'compare' && mobileCwv && desktopCwv ? (
              <>
                {renderCWVMetric('LCP', 0, 's', 2.5, 4.0, mobileCwv.lcp, desktopCwv.lcp)}
                {renderCWVMetric('CLS', 0, '', 0.1, 0.25, mobileCwv.cls, desktopCwv.cls)}
                {renderCWVMetric('TBT', 0, 'ms', 200, 600, mobileCwv.tbt, desktopCwv.tbt)}
                {renderCWVMetric('FCP', 0, 's', 1.8, 3.0, mobileCwv.fcp, desktopCwv.fcp)}
                {renderCWVMetric('Speed Index', 0, 's', 3.4, 5.8, mobileCwv.speed_index, desktopCwv.speed_index)}
              </>
            ) : deviceView === 'mobile' && mobileCwv ? (
              <>
                {renderCWVMetric('LCP', mobileCwv.lcp, 's', 2.5, 4.0)}
                {renderCWVMetric('CLS', mobileCwv.cls, '', 0.1, 0.25)}
                {renderCWVMetric('TBT', mobileCwv.tbt, 'ms', 200, 600)}
                {renderCWVMetric('FCP', mobileCwv.fcp, 's', 1.8, 3.0)}
                {renderCWVMetric('Speed Index', mobileCwv.speed_index, 's', 3.4, 5.8)}
              </>
            ) : desktopCwv ? (
              <>
                {renderCWVMetric('LCP', desktopCwv.lcp, 's', 2.5, 4.0)}
                {renderCWVMetric('CLS', desktopCwv.cls, '', 0.1, 0.25)}
                {renderCWVMetric('TBT', desktopCwv.tbt, 'ms', 200, 600)}
                {renderCWVMetric('FCP', desktopCwv.fcp, 's', 1.8, 3.0)}
                {renderCWVMetric('Speed Index', desktopCwv.speed_index, 's', 3.4, 5.8)}
              </>
            ) : null}
          </div>
        </div>
      )}

      {/* Mobile Issues Highlight */}
      {deviceView !== 'desktop' && renderMobileIssuesHighlight()}

      {/* Filters */}
      {auditData.issues.length > 0 && (
        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-4 border border-white/20">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2"><Filter className="w-4 h-4 text-purple-400" /><span className="text-white font-medium text-sm">Filters:</span></div>
            <select value={selectedCategory} onChange={(e) => setSelectedCategory(e.target.value)} className="bg-white/10 text-white border border-white/20 rounded-lg px-3 py-1.5 text-sm">
              <option value="all">All Categories</option><option value="technical">Technical</option><option value="content">Content</option><option value="performance">Performance</option><option value="mobile">Mobile</option><option value="security">Security</option><option value="accessibility">Accessibility</option>
            </select>
            <select value={selectedSeverity} onChange={(e) => setSelectedSeverity(e.target.value)} className="bg-white/10 text-white border border-white/20 rounded-lg px-3 py-1.5 text-sm">
              <option value="all">All Severities</option><option value="critical">Critical</option><option value="error">Errors</option><option value="warning">Warnings</option><option value="notice">Notices</option>
            </select>
            <div className="ml-auto text-white text-sm">
              Showing {deviceIssues.length} of {auditData.issues.length} issues
              {deviceView === 'mobile' && ' (mobile only)'}
              {deviceView === 'desktop' && ' (desktop only)'}
            </div>
          </div>
        </div>
      )}

      {/* Issues List */}
      <div className="space-y-3">
        <AnimatePresence>
          {deviceIssues.map((issue) => (
            <motion.div key={issue.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}
              className="bg-white/10 backdrop-blur-md rounded-xl border border-white/20 overflow-hidden">
              <div className="p-4 cursor-pointer hover:bg-white/5 transition-all" onClick={() => setExpandedIssue(expandedIssue === issue.id ? null : issue.id)}>
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3 flex-1">
                    <div className={`p-2 rounded-lg border shrink-0 ${getSeverityColor(issue.severity)}`}>{getCategoryIcon(issue.category)}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h4 className="text-white font-medium">{issue.issue_type || issue.title}</h4>
                        <span className={`text-xs px-2 py-0.5 rounded-full border ${getSeverityColor(issue.severity)}`}>{issue.severity}</span>
                        <span className="text-xs text-gray-500 bg-white/5 px-2 py-0.5 rounded-full">{issue.category}</span>
                        {issue.category?.toLowerCase() === 'mobile' && (
                          <span className="text-xs text-purple-300 bg-purple-500/20 px-2 py-0.5 rounded-full flex items-center gap-1">
                            <Smartphone className="w-3 h-3" /> Mobile
                          </span>
                        )}
                      </div>
                      <p className="text-purple-300 text-sm mt-1">{issue.title}</p>
                      <div className="flex items-center gap-4 mt-2">
                        <span className="text-xs text-gray-400">Impact: {issue.estimated_impact}%</span>
                        <span className="text-xs text-gray-400">Effort: {issue.effort_required}</span>
                      </div>
                    </div>
                  </div>
                  <ChevronRight className={`w-5 h-5 text-gray-400 transition-transform shrink-0 ml-2 ${expandedIssue === issue.id ? 'rotate-90' : ''}`} />
                </div>
              </div>

              <AnimatePresence>
                {expandedIssue === issue.id && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="border-t border-white/10">
                    <div className="p-4 space-y-4">
                      <div>
                        <h5 className="text-white font-medium mb-2 flex items-center gap-2"><Zap className="w-4 h-4 text-yellow-400" />How to Fix</h5>
                        <p className="text-purple-300 text-sm leading-relaxed">{issue.how_to_fix}</p>
                      </div>
                      {issue.affected_pages && issue.affected_pages.length > 0 && (
                        <div>
                          <h5 className="text-white font-medium mb-2">Affected Pages</h5>
                          {issue.affected_pages.slice(0, 5).map((page, idx) => (
                            <div key={idx} className="flex items-center gap-2">
                              <Link className="w-3 h-3 text-gray-400 shrink-0" />
                              <a href={page} target="_blank" rel="noopener noreferrer" className="text-purple-300 text-sm hover:text-purple-400 truncate">{page}</a>
                            </div>
                          ))}
                        </div>
                      )}
                      {issue.extra_data?.images && (
                        <div>
                          <h5 className="text-white font-medium mb-2">Images Without Alt Text</h5>
                          <div className="space-y-1 max-h-32 overflow-y-auto">
                            {issue.extra_data.images.map((img: string, idx: number) => (
                              <p key={idx} className="text-gray-400 text-xs font-mono truncate">{img}</p>
                            ))}
                          </div>
                        </div>
                      )}
                      {issue.extra_data?.broken_links && (
                        <div>
                          <h5 className="text-white font-medium mb-2">Broken Links</h5>
                          {issue.extra_data.broken_links.map((bl: any, idx: number) => (
                            <div key={idx} className="flex items-center gap-2">
                              <XCircle className="w-3 h-3 text-red-400 shrink-0" />
                              <span className="text-gray-400 text-xs truncate">{bl.url}</span>
                              <span className="text-red-400 text-xs">(status: {bl.status})</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </AnimatePresence>

        {deviceIssues.length === 0 && auditData.issues.length > 0 && (
          <div className="text-center py-12 bg-white/5 rounded-xl">
            <Filter className="w-12 h-12 text-gray-500 mx-auto mb-3" />
            <p className="text-white font-medium">No issues match your filters</p>
            {deviceView === 'mobile' && <p className="text-gray-400 text-sm mt-1">No mobile-specific issues found. Great job!</p>}
            {deviceView === 'desktop' && <p className="text-gray-400 text-sm mt-1">No desktop-specific issues found. Great job!</p>}
          </div>
        )}
        {auditData.issues.length === 0 && (
          <div className="text-center py-12 bg-white/5 rounded-xl">
            <CheckCircle className="w-12 h-12 text-green-400 mx-auto mb-3" />
            <p className="text-white font-medium">No issues found!</p>
            <p className="text-gray-400 text-sm mt-1">Your site looks great.</p>
          </div>
        )}
      </div>

      {/* Recommendations */}
      {auditData.recommendations?.length > 0 && (
        <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
          <h3 className="text-xl font-bold text-white mb-4">Top Recommendations</h3>
          <div className="space-y-3">
            {auditData.recommendations.slice(0, 8).map((rec) => (
              <div key={rec.id} className="flex items-start gap-3 p-3 bg-white/5 rounded-lg">
                <span className={`flex items-center justify-center w-8 h-8 rounded-full font-bold text-sm shrink-0 ${
                  rec.priority === 1 ? 'bg-red-500/20 text-red-400' : rec.priority === 2 ? 'bg-orange-500/20 text-orange-400' : rec.priority === 3 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-blue-500/20 text-blue-400'
                }`}>{rec.priority}</span>
                <div className="flex-1">
                  <h4 className="text-white font-medium">{rec.title}</h4>
                  <p className="text-purple-300 text-sm mt-1">{rec.description}</p>
                  <div className="flex items-center gap-4 mt-2">
                    <span className="text-xs text-gray-400">Impact: {rec.expected_impact}</span>
                    <span className="text-xs text-gray-400">Effort: {rec.implementation_complexity}</span>
                    {rec.estimated_traffic_gain > 0 && <span className="text-xs text-green-400">+{rec.estimated_traffic_gain} visitors/mo est.</span>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
