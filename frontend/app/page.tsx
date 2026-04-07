// frontend/app/page.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, TrendingUp, Brain, Zap, Globe, ShoppingCart, Bot,
  CheckCircle, XCircle, AlertCircle, Settings, Link2,
  BarChart3, Calendar, Users, FileSearch, Sparkles,
  Shield, Gauge, Award, Target, Rocket, Eye, Activity,
  ChevronDown
} from 'lucide-react';
import ApprovalQueue from '@/components/ApprovalQueue';
import ErrorMonitor from '@/components/ErrorMonitor';
import ContentCalendar from '@/components/ContentCalendar';
import CompetitorAnalysis from '@/components/CompetitorAnalysis';
import AuditDashboard from '@/components/AuditDashboard';
import WebsiteManager from '@/components/WebsiteManager';
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

  const API_URL = process.env.NEXT_PUBLIC_API_URL || '';

  // Fetch websites on load
  const fetchWebsites = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/websites`);
      if (response.ok) {
        const data = await response.json();
        const list = Array.isArray(data) ? data : [];
        setWebsites(list);
        // Auto-select first website if none selected
        if (!selectedWebsite && list.length > 0) {
          setSelectedWebsite(list[0].id);
        }
        // If selected website was deleted, select first available
        if (selectedWebsite && !list.find((w: Website) => w.id === selectedWebsite) && list.length > 0) {
          setSelectedWebsite(list[0].id);
        }
      }
    } catch (error) {
      console.error('Error fetching websites:', error);
    }
  }, [API_URL, selectedWebsite]);

  useEffect(() => {
    fetchWebsites();
  }, []);

  // Re-fetch websites when switching to websites tab (to catch additions/deletions)
  useEffect(() => {
    if (activeTab === 'websites') {
      fetchWebsites();
    }
  }, [activeTab]);

  useEffect(() => {
    const interval = setInterval(() => {
      const messages = [
        'Analyzing competitor strategies...',
        'Optimizing product descriptions...',
        'Fixing technical errors...',
        'Generating content ideas...',
        'Monitoring AI search results...',
        'Updating keyword rankings...'
      ];
      setAiStatus({
        status: 'active',
        message: messages[Math.floor(Math.random() * messages.length)]
      });
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  // Handle website selection from WebsiteManager
  const handleSelectWebsite = (websiteId: number) => {
    setSelectedWebsite(websiteId);
    setActiveTab('audit');
  };

  // Get selected website info
  const selectedSite = websites.find(w => w.id === selectedWebsite);

  // Tabs that need a website selected
  const websiteRequiredTabs = ['audit', 'optimizations', 'errors', 'content', 'competitors', 'settings'];
  const needsWebsite = websiteRequiredTabs.includes(activeTab);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900">
      {/* Animated Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-pink-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>
      </div>

      {/* Header */}
      <header className="relative z-30 border-b border-white/10 backdrop-blur-xl bg-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <motion.div
                initial={{ rotate: 0 }}
                animate={{ rotate: 360 }}
                transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                className="w-10 h-10 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg flex items-center justify-center"
              >
                <Rocket className="w-6 h-6 text-white" />
              </motion.div>
              <div>
                <h1 className="text-2xl font-bold text-white">SEO Intelligence</h1>
                <p className="text-purple-300 text-sm">AI-Powered Autonomous Optimization</p>
              </div>
            </div>

            <div className="flex items-center gap-4">
              {/* Website Selector Dropdown */}
              {websites.length > 0 && (
                <div className="relative">
                  <button
                    onClick={() => setShowWebsitePicker(!showWebsitePicker)}
                    className="flex items-center gap-2 bg-white/10 backdrop-blur-md rounded-lg px-4 py-2 text-white hover:bg-white/20 transition-all"
                  >
                    <Globe className="w-4 h-4 text-purple-400" />
                    <span className="text-sm font-medium max-w-[200px] truncate">
                      {selectedSite?.domain || 'Select Website'}
                    </span>
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                  </button>

                  <AnimatePresence>
                    {showWebsitePicker && (
                      <>
                        <div className="fixed inset-0 z-30" onClick={() => setShowWebsitePicker(false)} />
                        <motion.div
                          initial={{ opacity: 0, y: -5 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -5 }}
                          className="absolute right-0 top-12 z-40 bg-gray-900/95 backdrop-blur-xl border border-white/20 rounded-xl shadow-2xl overflow-hidden min-w-[250px]"
                        >
                          <div className="p-2">
                            {websites.map(site => (
                              <button
                                key={site.id}
                                onClick={() => {
                                  setSelectedWebsite(site.id);
                                  setShowWebsitePicker(false);
                                }}
                                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left ${
                                  selectedWebsite === site.id
                                    ? 'bg-purple-500/20 text-white'
                                    : 'text-gray-300 hover:bg-white/10'
                                }`}
                              >
                                <div className={`w-2 h-2 rounded-full ${site.health_score ? (site.health_score >= 70 ? 'bg-green-400' : site.health_score >= 50 ? 'bg-yellow-400' : 'bg-red-400') : 'bg-gray-500'}`} />
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-medium truncate">{site.domain}</p>
                                  <p className="text-xs text-gray-500 capitalize">{site.site_type}</p>
                                </div>
                                {site.health_score && (
                                  <span className={`text-xs font-bold ${site.health_score >= 70 ? 'text-green-400' : site.health_score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                                    {Math.round(site.health_score)}
                                  </span>
                                )}
                                {selectedWebsite === site.id && <CheckCircle className="w-4 h-4 text-purple-400 shrink-0" />}
                              </button>
                            ))}
                          </div>
                          <div className="border-t border-white/10 p-2">
                            <button
                              onClick={() => { setActiveTab('websites'); setShowWebsitePicker(false); }}
                              className="w-full text-center text-purple-400 text-xs py-1.5 hover:text-purple-300 transition-colors"
                            >
                              Manage Websites
                            </button>
                          </div>
                        </motion.div>
                      </>
                    )}
                  </AnimatePresence>
                </div>
              )}

              {/* AI Status */}
              <motion.div
                className="hidden md:flex items-center gap-3 bg-white/10 backdrop-blur-md rounded-full px-4 py-2"
                animate={{ scale: [1, 1.02, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                <div className="relative">
                  <Bot className="w-5 h-5 text-green-400" />
                  <span className="absolute -top-1 -right-1 w-2 h-2 bg-green-400 rounded-full animate-ping"></span>
                </div>
                <div>
                  <p className="text-xs text-gray-400">AI Agent</p>
                  <p className="text-xs text-white font-medium">{aiStatus.message}</p>
                </div>
              </motion.div>

              {/* Settings */}
              <button
                onClick={() => setActiveTab('settings')}
                className={`p-2 rounded-lg transition-all ${
                  activeTab === 'settings' ? 'bg-purple-500 text-white' : 'bg-white/10 text-gray-400 hover:text-white hover:bg-white/20'
                }`}
              >
                <Settings className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <div className="relative z-10 max-w-7xl mx-auto px-6 py-8">
        <div className="flex gap-2 mb-8 overflow-x-auto pb-2">
          {[
            { id: 'overview', label: 'Overview', icon: BarChart3 },
            { id: 'websites', label: 'Websites', icon: Globe },
            { id: 'audit', label: 'Site Audit', icon: Activity },
            { id: 'optimizations', label: 'Auto-Fix', icon: Sparkles },
            { id: 'errors', label: 'Error Monitor', icon: Shield },
            { id: 'content', label: 'Content Calendar', icon: Calendar },
            { id: 'competitors', label: 'Competitors', icon: Users },
            { id: 'ai-search', label: 'AI Search', icon: Brain }
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg shadow-purple-500/25'
                  : 'bg-white/10 text-purple-300 hover:bg-white/20'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
            </button>
          ))}
        </div>

        {/* No website selected warning for tabs that need one */}
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
            <p className="text-purple-300 mb-6">Choose a website from the dropdown in the header to view its data.</p>
          </div>
        )}

        {/* Content Area */}
        <AnimatePresence mode="wait">
          {activeTab === 'overview' && (
            <motion.div key="overview" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} className="space-y-6">
              {/* Website cards overview */}
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

          {activeTab === 'optimizations' && selectedWebsite && (
            <motion.div key={`optimizations-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
              <ApprovalQueue websiteId={selectedWebsite} />
            </motion.div>
          )}

          {activeTab === 'errors' && selectedWebsite && (
            <motion.div key={`errors-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
              <ErrorMonitor websiteId={selectedWebsite} />
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

          {activeTab === 'ai-search' && (
            <motion.div key="ai-search" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
              <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
                <div className="flex items-center gap-3 mb-4">
                  <Brain className="w-6 h-6 text-purple-400" />
                  <h2 className="text-xl font-bold text-white">AI Search Optimization</h2>
                </div>
                <p className="text-purple-300">
                  Track how your site appears in AI-generated search results (ChatGPT, Perplexity, Google AI Overviews). Coming soon.
                </p>
              </div>
            </motion.div>
          )}

          {activeTab === 'settings' && selectedWebsite && (
            <motion.div key={`settings-${selectedWebsite}`} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}>
              <SettingsPanel websiteId={selectedWebsite} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
