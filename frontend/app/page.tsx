// frontend/app/page.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, TrendingUp, Brain, Zap, Globe, ShoppingCart, Bot,
  CheckCircle, XCircle, AlertCircle, Settings, Link2,
  BarChart3, Calendar, Users, FileSearch, FileText, Sparkles,
  Shield, Gauge, Award, Target, Rocket, Eye, Activity, Trophy,
  ChevronDown, Menu, X, MessageSquare
} from 'lucide-react';
import ApprovalQueue from '@/components/ApprovalQueue';
import ErrorMonitor from '@/components/ErrorMonitor';
import ContentCalendar from '@/components/ContentCalendar';
import CompetitorAnalysis from '@/components/CompetitorAnalysis';
import AuditDashboard from '@/components/AuditDashboard';
import WebsiteManager from '@/components/WebsiteManager';
import KeywordTracker from '@/components/KeywordTracker';
import RoadToOne from '@/components/RoadToOne';
import GEODashboard from '@/components/GEODashboard';
import AIStrategist from '@/components/AIStrategist';
import ReportingDashboard from '@/components/ReportingDashboard';
import SettingsPanel from '@/components/SettingsPanel';

interface Website {
  id: number;
  domain: string;
  site_type: string;
  health_score: number | null;
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedWebsite, setSelectedWebsite] = useState<number | null>(null);
  const [websites, setWebsites] = useState<Website[]>([]);
  const [aiStatus, setAiStatus] = useState({ status: 'active', message: 'Analyzing rankings...' });
  const [showWebsitePicker, setShowWebsitePicker] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const fetchWebsites = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/websites`);
      if (response.ok) {
        const data = await response.json();
        const list = Array.isArray(data) ? data : [];
        setWebsites(list);
        if (!selectedWebsite && list.length > 0) {
          setSelectedWebsite(list[0].id);
        }
        if (selectedWebsite && !list.find((w: Website) => w.id === selectedWebsite) && list.length > 0) {
          setSelectedWebsite(list[0].id);
        }
      }
    } catch (error) {
      console.error('Error fetching websites:', error);
    }
  }, [API_URL, selectedWebsite]);

  useEffect(() => { fetchWebsites(); }, []);
  useEffect(() => { if (activeTab === 'websites') fetchWebsites(); }, [activeTab]);

  useEffect(() => {
    const interval = setInterval(() => {
      const messages = [
        'Analyzing competitor strategies...', 'Optimizing product descriptions...',
        'Fixing technical errors...', 'Generating content ideas...',
        'Monitoring AI search results...', 'Updating keyword rankings...'
      ];
      setAiStatus({ status: 'active', message: messages[Math.floor(Math.random() * messages.length)] });
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectWebsite = (websiteId: number) => {
    setSelectedWebsite(websiteId);
    setActiveTab('audit');
  };

  const selectedSite = websites.find(w => w.id === selectedWebsite);
  const websiteRequiredTabs = ['audit', 'keywords', 'road-to-one', 'issues', 'content', 'competitors', 'ai-search', 'strategist', 'reports', 'settings'];
  const needsWebsite = websiteRequiredTabs.includes(activeTab);

  const navItems = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'websites', label: 'Websites', icon: Globe },
    { id: 'divider1', label: '', icon: null },
    { id: 'audit', label: 'Site Audit', icon: Activity },
    { id: 'keywords', label: 'Keywords', icon: Search },
    { id: 'road-to-one', label: 'Road to #1', icon: Trophy },
    { id: 'issues', label: 'Issues & Fixes', icon: Sparkles },
    { id: 'divider2', label: '', icon: null },
    { id: 'ai-search', label: 'AI Search (GEO)', icon: Brain },
    { id: 'strategist', label: 'AI Strategist', icon: MessageSquare },
    { id: 'content', label: 'Content', icon: Calendar },
    { id: 'competitors', label: 'Competitors', icon: Users },
    { id: 'divider3', label: '', icon: null },
    { id: 'reports', label: 'Reports', icon: FileText },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900">
      {/* Animated Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-pink-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>
      </div>

      <div className="relative z-10 flex min-h-screen">
        {/* ─── Left Sidebar ─── */}
        <aside className={`fixed left-0 top-0 h-full z-30 border-r border-white/10 backdrop-blur-xl bg-gray-900/80 transition-all duration-300 flex flex-col ${
          sidebarCollapsed ? 'w-16' : 'w-56'
        }`}>
          {/* Logo */}
          <div className="p-4 border-b border-white/10 flex items-center gap-3">
            <motion.div
              initial={{ rotate: 0 }}
              animate={{ rotate: 360 }}
              transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
              className="w-8 h-8 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg flex items-center justify-center shrink-0"
            >
              <Rocket className="w-5 h-5 text-white" />
            </motion.div>
            {!sidebarCollapsed && (
              <div className="min-w-0">
                <h1 className="text-sm font-bold text-white leading-tight">SEO Intelligence</h1>
                <p className="text-purple-400 text-[10px]">AI-Powered</p>
              </div>
            )}
          </div>

          {/* Website Selector */}
          {websites.length > 0 && !sidebarCollapsed && (
            <div className="px-3 py-3 border-b border-white/10">
              <div className="relative">
                <button
                  onClick={() => setShowWebsitePicker(!showWebsitePicker)}
                  className="w-full flex items-center gap-2 bg-white/10 rounded-lg px-3 py-2 text-white hover:bg-white/15 transition-all text-left"
                >
                  <div className={`w-2 h-2 rounded-full shrink-0 ${selectedSite?.health_score ? (selectedSite.health_score >= 70 ? 'bg-green-400' : selectedSite.health_score >= 50 ? 'bg-yellow-400' : 'bg-red-400') : 'bg-gray-500'}`} />
                  <span className="text-xs font-medium truncate flex-1">
                    {selectedSite?.domain || 'Select Website'}
                  </span>
                  <ChevronDown className={`w-3 h-3 text-gray-400 transition-transform ${showWebsitePicker ? 'rotate-180' : ''}`} />
                </button>

                <AnimatePresence>
                  {showWebsitePicker && (
                    <>
                      <div className="fixed inset-0 z-30" onClick={() => setShowWebsitePicker(false)} />
                      <motion.div
                        initial={{ opacity: 0, y: -5 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -5 }}
                        className="absolute left-0 right-0 top-full mt-1 z-40 bg-gray-900/98 backdrop-blur-xl border border-white/20 rounded-xl shadow-2xl overflow-hidden"
                      >
                        <div className="p-1.5 max-h-60 overflow-y-auto">
                          {websites.map(site => (
                            <button
                              key={site.id}
                              onClick={() => { setSelectedWebsite(site.id); setShowWebsitePicker(false); }}
                              className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg transition-all text-left ${
                                selectedWebsite === site.id ? 'bg-purple-500/20 text-white' : 'text-gray-300 hover:bg-white/10'
                              }`}
                            >
                              <div className={`w-2 h-2 rounded-full shrink-0 ${site.health_score ? (site.health_score >= 70 ? 'bg-green-400' : site.health_score >= 50 ? 'bg-yellow-400' : 'bg-red-400') : 'bg-gray-500'}`} />
                              <div className="flex-1 min-w-0">
                                <p className="text-xs font-medium truncate">{site.domain}</p>
                                <p className="text-[10px] text-gray-500 capitalize">{site.site_type}</p>
                              </div>
                              {site.health_score && (
                                <span className={`text-xs font-bold ${site.health_score >= 70 ? 'text-green-400' : site.health_score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                                  {Math.round(site.health_score)}
                                </span>
                              )}
                              {selectedWebsite === site.id && <CheckCircle className="w-3.5 h-3.5 text-purple-400 shrink-0" />}
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
                return <div key={item.id} className="my-2 mx-2 border-t border-white/10" />;
              }
              const Icon = item.icon!;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  title={sidebarCollapsed ? item.label : undefined}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all mb-0.5 ${
                    isActive
                      ? 'bg-gradient-to-r from-purple-500/30 to-pink-500/20 text-white border-l-2 border-purple-400'
                      : 'text-gray-400 hover:bg-white/10 hover:text-white border-l-2 border-transparent'
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-purple-400' : ''}`} />
                  {!sidebarCollapsed && <span>{item.label}</span>}
                </button>
              );
            })}
          </nav>

          {/* Bottom: Settings + Collapse */}
          <div className="border-t border-white/10 p-2">
            <button
              onClick={() => setActiveTab('settings')}
              title={sidebarCollapsed ? 'Settings' : undefined}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'settings' ? 'bg-purple-500/20 text-white' : 'text-gray-400 hover:bg-white/10 hover:text-white'
              }`}
            >
              <Settings className={`w-4 h-4 shrink-0 ${activeTab === 'settings' ? 'text-purple-400' : ''}`} />
              {!sidebarCollapsed && <span>Settings</span>}
            </button>
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-500 hover:bg-white/5 hover:text-gray-300 transition-all mt-1"
            >
              {sidebarCollapsed ? <Menu className="w-4 h-4 shrink-0" /> : <X className="w-4 h-4 shrink-0" />}
              {!sidebarCollapsed && <span className="text-xs">Collapse</span>}
            </button>
          </div>

          {/* AI Status */}
          {!sidebarCollapsed && (
            <div className="p-3 border-t border-white/10">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Bot className="w-4 h-4 text-green-400" />
                  <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 bg-green-400 rounded-full animate-ping"></span>
                </div>
                <p className="text-[10px] text-gray-500 truncate">{aiStatus.message}</p>
              </div>
            </div>
          )}
        </aside>

        {/* ─── Main Content ─── */}
        <main className={`flex-1 transition-all duration-300 ${sidebarCollapsed ? 'ml-16' : 'ml-56'}`}>
          <div className="max-w-7xl mx-auto px-6 py-6">

            {needsWebsite && !selectedWebsite && websites.length === 0 && (
              <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
                <Globe className="w-12 h-12 text-purple-400 mx-auto mb-4" />
                <h3 className="text-xl font-bold text-white mb-2">No Websites Added</h3>
                <p className="text-purple-300 mb-6">Add a website first to start using this feature.</p>
                <button onClick={() => setActiveTab('websites')}
                  className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-6 py-3 rounded-lg font-medium">
                  Go to Websites
                </button>
              </div>
            )}

            {needsWebsite && !selectedWebsite && websites.length > 0 && (
              <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
                <Globe className="w-12 h-12 text-purple-400 mx-auto mb-4" />
                <h3 className="text-xl font-bold text-white mb-2">Select a Website</h3>
                <p className="text-purple-300 mb-6">Choose a website from the sidebar to view its data.</p>
              </div>
            )}

            <AnimatePresence mode="wait">
              {activeTab === 'overview' && (
                <motion.div key="overview" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-6">
                  {websites.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {websites.map(site => (
                        <motion.div key={site.id} whileHover={{ scale: 1.02 }}
                          className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20 cursor-pointer"
                          onClick={() => handleSelectWebsite(site.id)}>
                          <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-3">
                              <div className={`w-3 h-3 rounded-full ${site.health_score ? (site.health_score >= 70 ? 'bg-green-400' : site.health_score >= 50 ? 'bg-yellow-400' : 'bg-red-400') : 'bg-gray-500'}`} />
                              <h3 className="text-white font-semibold">{site.domain}</h3>
                            </div>
                            <span className="text-xs text-gray-400 capitalize bg-white/10 px-2 py-0.5 rounded-full">{site.site_type}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-gray-400 text-sm">Health Score</span>
                            <span className={`text-2xl font-bold ${site.health_score ? (site.health_score >= 70 ? 'text-green-400' : site.health_score >= 50 ? 'text-yellow-400' : 'text-red-400') : 'text-gray-500'}`}>
                              {site.health_score ? Math.round(site.health_score) : '--'}
                            </span>
                          </div>
                          <p className="text-purple-400 text-xs mt-3">Click to view audit →</p>
                        </motion.div>
                      ))}
                    </div>
                  ) : (
                    <div className="bg-white/10 backdrop-blur-md rounded-2xl p-12 border border-white/20 text-center">
                      <Globe className="w-12 h-12 text-purple-400 mx-auto mb-4" />
                      <h3 className="text-xl font-bold text-white mb-2">Welcome to SEO Intelligence</h3>
                      <p className="text-purple-300 mb-6">Add your first website to start tracking SEO performance.</p>
                      <button onClick={() => setActiveTab('websites')}
                        className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-6 py-3 rounded-lg font-medium">
                        Add Website
                      </button>
                    </div>
                  )}
                </motion.div>
              )}

              {activeTab === 'websites' && (
                <motion.div key="websites" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
                  <WebsiteManager onSelectWebsite={handleSelectWebsite} onWebsitesChange={fetchWebsites} />
                </motion.div>
              )}

              {activeTab === 'audit' && selectedWebsite && (
                <motion.div key={`audit-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
                  <AuditDashboard websiteId={selectedWebsite} />
                </motion.div>
              )}

              {activeTab === 'keywords' && selectedWebsite && (
                <motion.div key={`keywords-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
                  <KeywordTracker key={`kt-${selectedWebsite}`} websiteId={selectedWebsite} />
                </motion.div>
              )}

              {activeTab === 'road-to-one' && selectedWebsite && (
                <motion.div key={`r2o-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
                  <RoadToOne websiteId={selectedWebsite} />
                </motion.div>
              )}

              {activeTab === 'issues' && selectedWebsite && (
                <motion.div key={`issues-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
                  <div className="space-y-6">
                    <ErrorMonitor websiteId={selectedWebsite} />
                    <ApprovalQueue websiteId={selectedWebsite} />
                  </div>
                </motion.div>
              )}

              {activeTab === 'content' && selectedWebsite && (
                <motion.div key={`content-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
                  <ContentCalendar websiteId={selectedWebsite} />
                </motion.div>
              )}

              {activeTab === 'competitors' && selectedWebsite && (
                <motion.div key={`competitors-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
                  <CompetitorAnalysis websiteId={selectedWebsite} />
                </motion.div>
              )}

              {activeTab === 'ai-search' && selectedWebsite && (
                <motion.div key={`geo-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
                  <GEODashboard websiteId={selectedWebsite} />
                </motion.div>
              )}

              {activeTab === 'strategist' && selectedWebsite && (
                <motion.div key={`strategist-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
                  <AIStrategist websiteId={selectedWebsite} />
                </motion.div>
              )}

              {activeTab === 'reports' && selectedWebsite && (
                <motion.div key={`reports-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
                  <ReportingDashboard websiteId={selectedWebsite} />
                </motion.div>
              )}

              {activeTab === 'settings' && selectedWebsite && (
                <motion.div key={`settings-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
                  <SettingsPanel websiteId={selectedWebsite} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </main>
      </div>
    </div>
  );
}
