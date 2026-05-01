// frontend/app/page.tsx — Premium Ethereal Glass Dashboard
'use client';

import { useState, useEffect, useCallback, Suspense, lazy } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, TrendingUp, Brain, Zap, Globe, ShoppingCart, Bot,
  CheckCircle, XCircle, AlertCircle, Settings, Link2,
  BarChart3, Calendar, Users, FileSearch, FileText, Sparkles,
  Shield, Gauge, Award, Target, Rocket, Eye, Activity, Trophy,
  ChevronDown, Menu, X, MessageSquare, Lock, LogOut,
  ChevronRight, Compass, Layers, Wand2, Loader2,
  FileCode, Image, Split, MapPin, Bell, Download
} from 'lucide-react';

// Eagerly load only the components needed for initial render
import OverviewDashboard from '@/components/OverviewDashboard';
import SummaryDashboard from '@/components/SummaryDashboard';
import SettingsPanel from '@/components/SettingsPanel';

// Lazy load all tab-specific components for code splitting
const AuditDashboard = lazy(() => import('@/components/AuditDashboard'));
const KeywordTracker = lazy(() => import('@/components/KeywordTracker'));
const RoadToOne = lazy(() => import('@/components/RoadToOne'));
const ApprovalQueue = lazy(() => import('@/components/ApprovalQueue'));
const ErrorMonitor = lazy(() => import('@/components/ErrorMonitor'));
const ContentWriter = lazy(() => import('@/components/ContentWriter'));
const CompetitorAnalysis = lazy(() => import('@/components/CompetitorAnalysis'));
const GEODashboard = lazy(() => import('@/components/GEODashboard'));
const AIStrategist = lazy(() => import('@/components/AIStrategist'));
const ReportingDashboard = lazy(() => import('@/components/ReportingDashboard'));
const CoreWebVitalsPanel = lazy(() => import('@/components/CoreWebVitalsPanel'));
const SchemaGenerator = lazy(() => import('@/components/SchemaGenerator'));
const SitemapManager = lazy(() => import('@/components/SitemapManager'));
const RobotsManager = lazy(() => import('@/components/RobotsManager'));
const ImageOptimizer = lazy(() => import('@/components/ImageOptimizer'));
const LinkChecker = lazy(() => import('@/components/LinkChecker'));
const ABTestingPanel = lazy(() => import('@/components/ABTestingPanel'));
const LocalSEOPanel = lazy(() => import('@/components/LocalSEOPanel'));
const NotificationSettings = lazy(() => import('@/components/NotificationSettings'));
const IndexTracker = lazy(() => import('@/components/IndexTracker'));
const WebsiteManager = lazy(() => import('@/components/WebsiteManager'));
const IntegrationSetupChecklist = lazy(() => import('@/components/IntegrationSetupChecklist'));

interface Website {
  id: number;
  domain: string;
  site_type: string;
  health_score: number | null;
  autonomy_mode?: string;
}

const springTransition = { type: "spring", stiffness: 100, damping: 20 };
const fadeUpVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.32, 0.72, 0, 1] } }
};

// Loading fallback for lazy-loaded tabs
function TabLoader() {
  return (
    <div className="flex items-center justify-center h-[60vh]">
      <div className="text-center">
        <div className="w-10 h-10 rounded-2xl bg-[#0f0f12] border border-white/[0.06] flex items-center justify-center mx-auto mb-4">
          <Loader2 className="w-5 h-5 text-[#7c6cf9] animate-spin" />
        </div>
        <p className="text-[#52525b] text-sm">Loading...</p>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [authChecking, setAuthChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [authRequired, setAuthRequired] = useState(true);
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  const [activeTab, setActiveTab] = useState('overview');
  const [selectedWebsite, setSelectedWebsite] = useState<number | null>(null);
  const [websites, setWebsites] = useState<Website[]>([]);
  const [aiStatus, setAiStatus] = useState<{ phase: string; message: string }>({ phase: 'idle', message: 'Idle' });
  const [showWebsitePicker, setShowWebsitePicker] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';
  const getToken = () => typeof window !== 'undefined' ? localStorage.getItem('seo_token') || '' : '';

  const checkAuth = useCallback(async () => {
    try {
      const token = getToken();
      const r = await fetch(`${API_URL}/api/auth/check`, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {}
      });
      if (r.ok) {
        const d = await r.json();
        setAuthRequired(d.auth_required);
        setAuthenticated(d.authenticated || !d.auth_required);
      }
    } catch {
      setAuthenticated(true);
      setAuthRequired(false);
    } finally { setAuthChecking(false); }
  }, [API_URL]);

  useEffect(() => { checkAuth(); }, [checkAuth]);

  const handleLogin = async () => {
    setLoginLoading(true); setLoginError('');
    try {
      const r = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername, password: loginPassword })
      });
      const d = await r.json();
      if (d.success && d.token) {
        localStorage.setItem('seo_token', d.token);
        setAuthenticated(true);
      } else {
        setLoginError(d.message || 'Invalid credentials');
      }
    } catch { setLoginError('Cannot reach server'); }
    finally { setLoginLoading(false); }
  };

  const handleLogout = () => {
    const token = getToken();
    if (token) {
      fetch(`${API_URL}/api/auth/logout`, {
        method: 'POST', headers: { 'Authorization': `Bearer ${token}` }
      }).catch(() => {});
    }
    localStorage.removeItem('seo_token');
    setAuthenticated(false);
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as any).__seoToken = getToken;
      const originalFetch = window.fetch;
      window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : (input as Request).url;
        if (url.includes('/api/') || url.includes('/websites')) {
          const token = getToken();
          if (token) {
            init = init || {};
            init.headers = { ...init.headers, 'Authorization': `Bearer ${token}` };
          }
        }
        const response = await originalFetch(input, init);
        if (response.status === 401 && !url.includes('/auth/')) {
          localStorage.removeItem('seo_token');
          setAuthenticated(false);
        }
        return response;
      };
      return () => { window.fetch = originalFetch; };
    }
  }, [authenticated]);

  const fetchWebsites = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/websites`, {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      });
      if (response.ok) {
        const data = await response.json();
        const list = Array.isArray(data) ? data : [];
        setWebsites(list);
        if (!selectedWebsite && list.length > 0) setSelectedWebsite(list[0].id);
      }
    } catch (error) { console.error('Error fetching websites:', error); }
  }, [API_URL, selectedWebsite]);

  useEffect(() => { if (authenticated) fetchWebsites(); }, [authenticated]);
  useEffect(() => { if ((activeTab === 'settings' || activeTab === 'overview') && authenticated) fetchWebsites(); }, [activeTab]);

  useEffect(() => {
    if (!authenticated) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const url = selectedWebsite
          ? `${API_URL}/api/overseer/status?website_id=${selectedWebsite}`
          : `${API_URL}/api/overseer/status`;
        const r = await fetch(url);
        if (!r.ok) return;
        const d = await r.json();
        if (cancelled) return;
        setAiStatus({
          phase: d.phase || 'idle',
          message: d.message || 'Idle',
        });
      } catch { /* offline — stay on previous status */ }
    };
    poll();
    const interval = setInterval(poll, 5000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [authenticated, selectedWebsite, API_URL]);

  const handleSelectWebsite = (websiteId: number) => {
    setSelectedWebsite(websiteId);
    setActiveTab('audit');
  };

  const selectedSite = websites.find(w => w.id === selectedWebsite);
  const websiteRequiredTabs = [
    'audit', 'keywords', 'road-to-one', 'issues', 'index-tracker',
    'content', 'competitors', 'ai-search', 'strategist', 'reports',
    'settings', 'summary', 'link-checker',
    'web-vitals', 'schema', 'sitemap', 'robots', 'images', 'ab-tests',
    'local-seo', 'notifications',
  ];
  const needsWebsite = websiteRequiredTabs.includes(activeTab);

  const navItems = [
    { id: 'sites', label: 'Sites', icon: Globe },
    { id: 'overview', label: 'Overview', icon: Compass },
    { id: 'summary', label: 'Summary', icon: Layers },
    { id: 'divider1', label: '', icon: null },
    { id: 'audit', label: 'Site Audit', icon: FileSearch },
    { id: 'keywords', label: 'Keywords', icon: Target },
    { id: 'road-to-one', label: 'Road to #1', icon: Trophy },
    { id: 'issues', label: 'Issues & Fixes', icon: Wand2 },
    { id: 'index-tracker', label: 'Index Tracker', icon: Search },
    { id: 'divider2', label: '', icon: null },
    { id: 'web-vitals', label: 'Web Vitals', icon: Gauge },
    { id: 'schema', label: 'Schema', icon: FileCode },
    { id: 'sitemap', label: 'Sitemap', icon: FileCode },
    { id: 'robots', label: 'Robots.txt', icon: Shield },
    { id: 'images', label: 'Images', icon: Image },
    { id: 'link-checker', label: 'Link Checker', icon: Link2 },
    { id: 'ab-tests', label: 'A/B Tests', icon: Split },
    { id: 'local-seo', label: 'Local SEO', icon: MapPin },
    { id: 'divider3', label: '', icon: null },
    { id: 'ai-search', label: 'AI Search (GEO)', icon: Brain },
    { id: 'strategist', label: 'AI Strategist', icon: MessageSquare },
    { id: 'content', label: 'Content Writer', icon: FileText },
    { id: 'competitors', label: 'Competitors', icon: Users },
    { id: 'divider4', label: '', icon: null },
    { id: 'reports', label: 'Reports', icon: BarChart3 },
    { id: 'notifications', label: 'Notifications', icon: Bell },
  ];

  // ─── Auth Loading ───
  if (authChecking) {
    return (
      <div className="min-h-[100dvh] bg-[#050505] flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 rounded-2xl bg-[#0f0f12] border border-white/[0.06] flex items-center justify-center mx-auto mb-4">
            <Shield className="w-6 h-6 text-[#7c6cf9]" />
          </div>
          <p className="text-[#52525b] text-sm">Checking authentication...</p>
        </div>
      </div>
    );
  }

  // ─── Login Screen ───
  if (authRequired && !authenticated) {
    return (
      <div className="min-h-[100dvh] bg-[#050505] flex items-center justify-center relative">
        <div className="relative z-10 w-full max-w-sm mx-4">
          <div className="card-liquid p-8">
            <div className="text-center mb-6">
              <div className="w-14 h-14 rounded-2xl bg-[#0f0f12] border border-white/[0.06] flex items-center justify-center mx-auto mb-4">
                <Lock className="w-7 h-7 text-[#7c6cf9]" />
              </div>
              <h1 className="text-2xl font-bold text-[#f5f5f7] tracking-tight">SEO Intelligence</h1>
              <p className="text-[#52525b] text-sm mt-1">Sign in to access your dashboard</p>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-[#52525b] text-xs mb-1.5 font-medium">Username</label>
                <input type="text" value={loginUsername} onChange={e => setLoginUsername(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleLogin()}
                  placeholder="Username" autoFocus
                  className="w-full" />
              </div>
              <div>
                <label className="block text-[#52525b] text-xs mb-1.5 font-medium">Password</label>
                <input type="password" value={loginPassword} onChange={e => setLoginPassword(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleLogin()}
                  placeholder="Password" className="w-full" />
              </div>
              {loginError && (
                <div className="bg-red-500/10 border border-red-500/20 rounded-xl px-3 py-2">
                  <p className="text-red-400 text-xs">{loginError}</p>
                </div>
              )}
              <button onClick={handleLogin} disabled={loginLoading || !loginUsername || !loginPassword}
                className="w-full btn-premium justify-center disabled:opacity-50">
                {loginLoading ? (
                  <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                ) : 'Sign In'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[100dvh] bg-[#050505] relative">
      <div className="relative z-10 flex min-h-[100dvh]">
        {/* ─── Left Sidebar ─── */}
        <aside className={`fixed left-0 top-0 h-full z-30 border-r border-white/[0.06] bg-[#0a0a0a]/80 backdrop-blur-2xl transition-all duration-500 flex flex-col ${
          sidebarCollapsed ? 'w-16' : 'w-60'
        }`}>
          {/* Logo */}
          <div className="p-4 border-b border-white/[0.06] flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-[#0f0f12] border border-white/[0.06] flex items-center justify-center shrink-0">
              <Rocket className="w-4 h-4 text-[#7c6cf9]" />
            </div>
            {!sidebarCollapsed && (
              <div className="min-w-0">
                <h1 className="text-sm font-bold text-[#f5f5f7] leading-tight tracking-tight">SEO Intelligence</h1>
                <p className="text-[#7c6cf9] text-[10px] font-medium tracking-wide">AI-POWERED</p>
              </div>
            )}
          </div>

          {/* Website Selector */}
          {websites.length > 0 && !sidebarCollapsed && (
            <div className="px-3 py-3 border-b border-white/[0.06]">
              <div className="relative">
                <button onClick={() => setShowWebsitePicker(!showWebsitePicker)}
                  className="w-full flex items-center gap-2 bg-white/[0.03] hover:bg-white/[0.06] rounded-xl px-3 py-2.5 text-[#f5f5f7] transition-all text-left border border-white/[0.06]">
                  <div className={`w-2 h-2 rounded-full shrink-0 ${selectedSite?.health_score ? (selectedSite.health_score >= 70 ? 'bg-[#4ade80]' : selectedSite.health_score >= 50 ? 'bg-[#fbbf24]' : 'bg-[#f87171]') : 'bg-[#52525b]'}`} />
                  <span className="text-xs font-medium truncate flex-1">{selectedSite?.domain || 'Select Website'}</span>
                  <ChevronDown className={`w-3 h-3 text-[#52525b] transition-transform ${showWebsitePicker ? 'rotate-180' : ''}`} />
                </button>
                <AnimatePresence>
                  {showWebsitePicker && (
                    <>
                      <div className="fixed inset-0 z-30" onClick={() => setShowWebsitePicker(false)} />
                      <motion.div initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }}
                        className="absolute left-0 right-0 top-full mt-1 z-40 card-liquid overflow-hidden">
                        <div className="p-1.5 max-h-60 overflow-y-auto">
                          {websites.map(site => (
                            <button key={site.id}
                              onClick={() => { setSelectedWebsite(site.id); setShowWebsitePicker(false); }}
                              className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-xl transition-all text-left ${
                                selectedWebsite === site.id ? 'bg-[#7c6cf9]/10 text-[#f5f5f7]' : 'text-[#a1a1aa] hover:bg-white/[0.03]'
                              }`}>
                              <div className={`w-2 h-2 rounded-full shrink-0 ${site.health_score ? (site.health_score >= 70 ? 'bg-[#4ade80]' : site.health_score >= 50 ? 'bg-[#fbbf24]' : 'bg-[#f87171]') : 'bg-[#52525b]'}`} />
                              <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium truncate">{site.domain}</p>
                                <p className="text-[10px] text-[#52525b] capitalize">{site.site_type}</p>
                              </div>
                              {site.health_score && (
                                <span className={`text-xs font-bold ${site.health_score >= 70 ? 'text-[#4ade80]' : site.health_score >= 50 ? 'text-[#fbbf24]' : 'text-[#f87171]'}`}>
                                  {Math.round(site.health_score)}
                                </span>
                              )}
                            </button>
                          ))}
                        </div>
                      </motion.div>
                    </>
                  )}
                </AnimatePresence>
              </div>
            </div>
          )}

          {/* Nav Items */}
          <nav className="flex-1 py-2 px-2 overflow-y-auto">
            {navItems.map((item) => {
              if (item.id.startsWith('divider')) {
                return <div key={item.id} className="my-2 mx-2 border-t border-white/[0.06]" />;
              }
              const Icon = item.icon!;
              const isActive = activeTab === item.id;
              return (
                <button key={item.id} onClick={() => setActiveTab(item.id)} title={sidebarCollapsed ? item.label : undefined}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-300 mb-0.5 ${
                    isActive
                      ? 'bg-[#7c6cf9]/10 text-[#f5f5f7] border border-[#7c6cf9]/20'
                      : 'text-[#52525b] hover:bg-white/[0.03] hover:text-[#a1a1aa] border border-transparent'
                  }`}>
                  <Icon className={`w-4 h-4 shrink-0 transition-colors ${isActive ? 'text-[#7c6cf9]' : ''}`} />
                  {!sidebarCollapsed && <span>{item.label}</span>}
                </button>
              );
            })}
          </nav>

          {/* Bottom: Settings + Collapse */}
          <div className="border-t border-white/[0.06] p-2">
            <button onClick={() => setActiveTab('settings')} title={sidebarCollapsed ? 'Settings' : undefined}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                activeTab === 'settings' ? 'bg-[#7c6cf9]/10 text-[#f5f5f7] border border-[#7c6cf9]/20' : 'text-[#52525b] hover:bg-white/[0.03] hover:text-[#a1a1aa]'
              }`}>
              <Settings className={`w-4 h-4 shrink-0 ${activeTab === 'settings' ? 'text-[#7c6cf9]' : ''}`} />
              {!sidebarCollapsed && <span>Settings</span>}
            </button>
            <button onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-[#52525b] hover:bg-white/[0.03] hover:text-[#a1a1aa] transition-all mt-1">
              {sidebarCollapsed ? <Menu className="w-4 h-4 shrink-0" /> : <X className="w-4 h-4 shrink-0" />}
              {!sidebarCollapsed && <span className="text-xs">Collapse</span>}
            </button>
          </div>

          {/* AI Status */}
          {!sidebarCollapsed && (
            <div className="p-3 border-t border-white/[0.06]">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Bot className={`w-4 h-4 ${aiStatus.phase !== 'idle' ? 'text-[#4ade80]' : 'text-[#52525b]'}`} />
                  {aiStatus.phase !== 'idle' && (
                    <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-[#4ade80] rounded-full animate-ping" />
                  )}
                </div>
                <p className="text-[10px] text-[#52525b] truncate">{aiStatus.message}</p>
              </div>
            </div>
          )}

          {/* Logout */}
          {authRequired && (
            <div className="p-3 border-t border-white/[0.06]">
              <button onClick={handleLogout}
                className="w-full flex items-center gap-2 text-[#52525b] hover:text-[#f87171] transition-all px-2 py-1.5 rounded-xl hover:bg-white/[0.03]">
                <LogOut className="w-4 h-4 shrink-0" />
                {!sidebarCollapsed && <span className="text-xs">Sign Out</span>}
              </button>
            </div>
          )}
        </aside>

        {/* ─── Main Content ─── */}
        <main className={`flex-1 transition-all duration-500 ${sidebarCollapsed ? 'ml-16' : 'ml-60'}`}>
          <div className="max-w-[1400px] mx-auto px-6 py-6">

            {needsWebsite && !selectedWebsite && websites.length === 0 && (
              <motion.div variants={fadeUpVariants} initial="hidden" animate="visible"
                className="card-liquid p-12 text-center">
                <Globe className="w-12 h-12 text-[#7c6cf9] mx-auto mb-4" />
                <h3 className="text-xl font-bold text-[#f5f5f7] mb-2">No Websites Added</h3>
                <p className="text-[#52525b] mb-6">Add a website first to start using this feature.</p>
                <button onClick={() => setActiveTab('sites')} className="btn-premium">
                  Go to Sites <ChevronRight className="w-4 h-4" />
                </button>
              </motion.div>
            )}

            {needsWebsite && !selectedWebsite && websites.length > 0 && (
              <motion.div variants={fadeUpVariants} initial="hidden" animate="visible"
                className="card-liquid p-12 text-center">
                <Globe className="w-12 h-12 text-[#7c6cf9] mx-auto mb-4" />
                <h3 className="text-xl font-bold text-[#f5f5f7] mb-2">Select a Website</h3>
                <p className="text-[#52525b]">Choose a website from the sidebar to view its data.</p>
              </motion.div>
            )}

            <AnimatePresence mode="wait">
              {activeTab === 'overview' && (
                <motion.div key="overview" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                  transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }} className="space-y-6">
                  {/* AI Overseer */}
                  {websites.length > 0 && selectedWebsite && (
                    <div className="bezel-outer">
                      <div className="bezel-inner p-5 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-[#7c6cf9]/10 border border-[#7c6cf9]/20 flex items-center justify-center">
                            <Bot className="w-5 h-5 text-[#7c6cf9]" />
                          </div>
                          <div>
                            <h3 className="text-[#f5f5f7] font-semibold text-sm">AI Overseer</h3>
                            <p className="text-[#52525b] text-xs">Runs: audit → keywords → GEO scan → fixes → strategy refresh</p>
                          </div>
                        </div>
                        <button onClick={async () => {
                          try {
                            await fetch(`${API_URL}/api/overseer/${selectedWebsite}/run`, { method: 'POST' });
                            alert('AI Overseer started. This will take 2-5 minutes. Check Issues & Fixes for results.');
                          } catch { alert('Failed to start overseer'); }
                        }} className="btn-premium">
                          <Zap className="w-4 h-4" /> Run Full Cycle
                        </button>
                      </div>
                    </div>
                  )}

                  {websites.length > 0 ? (
                    <>
                      {selectedWebsite && selectedSite && (
                        <Suspense fallback={null}>
                          <IntegrationSetupChecklist
                            websiteId={selectedWebsite}
                            siteType={selectedSite.site_type}
                            onIntegrationChange={fetchWebsites}
                          />
                        </Suspense>
                      )}
                      <OverviewDashboard
                        onSelectWebsite={handleSelectWebsite}
                        selectedWebsite={selectedWebsite}
                        onAddWebsite={() => setActiveTab('sites')}
                        onOpenSettings={() => setActiveTab('settings')}
                      />
                    </>
                  ) : (
                    <motion.div variants={fadeUpVariants} initial="hidden" animate="visible" className="card-liquid p-12 text-center">
                      <Globe className="w-12 h-12 text-[#7c6cf9] mx-auto mb-4" />
                      <h3 className="text-xl font-bold text-[#f5f5f7] mb-2">Welcome to SEO Intelligence</h3>
                      <p className="text-[#52525b] mb-6">Add your first website to start tracking SEO performance.</p>
                      <button onClick={() => setActiveTab('sites')} className="btn-premium">
                        Add Website <ChevronRight className="w-4 h-4" />
                      </button>
                    </motion.div>
                  )}
                </motion.div>
              )}

              {activeTab === 'sites' && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key="sites" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <WebsiteManager
                      onSelectWebsite={(id) => { setSelectedWebsite(id); setActiveTab('overview'); }}
                      onWebsitesChange={fetchWebsites}
                    />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'summary' && selectedWebsite && (
                <motion.div key={`summary-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                  transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                  <SummaryDashboard websiteId={selectedWebsite} onNavigate={(tab) => setActiveTab(tab)} />
                </motion.div>
              )}

              {activeTab === 'summary' && !selectedWebsite && (
                <motion.div key="summary-empty" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                  transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                  <div className="card-liquid p-12 text-center">
                    <Globe className="w-12 h-12 text-[#7c6cf9] mx-auto mb-4" />
                    <h3 className="text-xl font-bold text-[#f5f5f7] mb-2">Select a Website</h3>
                    <p className="text-[#52525b]">Choose a website from the sidebar to view its summary dashboard.</p>
                  </div>
                </motion.div>
              )}

              {activeTab === 'audit' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`audit-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <AuditDashboard websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'keywords' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`keywords-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <KeywordTracker key={`kt-${selectedWebsite}`} websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'road-to-one' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`r2o-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <RoadToOne websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'issues' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`issues-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <div className="space-y-6">
                      <ErrorMonitor websiteId={selectedWebsite} />
                      <ApprovalQueue websiteId={selectedWebsite} />
                    </div>
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'content' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`content-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <ContentWriter websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'competitors' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`competitors-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <CompetitorAnalysis websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'ai-search' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`geo-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <GEODashboard websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'strategist' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`strategist-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <AIStrategist websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'reports' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`reports-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <ReportingDashboard websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'settings' && selectedWebsite && (
                <motion.div key={`settings-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                  transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                  <SettingsPanel websiteId={selectedWebsite} />
                </motion.div>
              )}

              {activeTab === 'web-vitals' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`cwv-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <CoreWebVitalsPanel websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'schema' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`schema-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <SchemaGenerator websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'sitemap' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`sitemap-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <SitemapManager websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'images' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`images-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <ImageOptimizer websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'ab-tests' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`ab-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <ABTestingPanel websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'local-seo' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`local-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <LocalSEOPanel websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'robots' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`robots-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <RobotsManager websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'link-checker' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`link-checker-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <LinkChecker websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'index-tracker' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`index-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <IndexTracker websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}

              {activeTab === 'notifications' && selectedWebsite && (
                <Suspense fallback={<TabLoader />}>
                  <motion.div key={`notif-${selectedWebsite}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }}
                    transition={{ duration: 0.4, ease: [0.32, 0.72, 0, 1] }}>
                    <NotificationSettings websiteId={selectedWebsite} />
                  </motion.div>
                </Suspense>
              )}
            </AnimatePresence>
          </div>
        </main>
      </div>
    </div>
  );
}
