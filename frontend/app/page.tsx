// frontend/app/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Search, TrendingUp, Brain, Zap, Globe, ShoppingCart, Bot,
  CheckCircle, XCircle, AlertCircle, Settings, Link2,
  BarChart3, Calendar, Users, FileSearch, Sparkles,
  Shield, Gauge, Award, Target, Rocket, Eye, Activity
} from 'lucide-react';
import IntegrationsModal from '@/components/IntegrationsModal';
import OptimizationQueue from '@/components/OptimizationQueue';
import ErrorMonitor from '@/components/ErrorMonitor';
import ContentCalendar from '@/components/ContentCalendar';
import CompetitorAnalysis from '@/components/CompetitorAnalysis';
import AuditDashboard from '@/components/AuditDashboard';
import WebsiteManager from '@/components/WebsiteManager';

// Add this import
import WebsiteManager from '@/components/WebsiteManager';

// Add a new tab for websites
{ id: 'websites', label: 'Websites', icon: Globe },

// Add the case for rendering
{activeTab === 'websites' && (
  <WebsiteManager />
)}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState('overview');
  const [showIntegrations, setShowIntegrations] = useState(false);
  const [selectedWebsite, setSelectedWebsite] = useState<number>(1);
  const [aiStatus, setAiStatus] = useState({ status: 'active', message: 'Analyzing rankings...' });
  const [stats, setStats] = useState({
    keywords: 1847,
    topTen: 234,
    avgPosition: 18.4,
    aiVisibility: 72,
    pendingOptimizations: 43,
    autoFixedErrors: 12,
    scheduledContent: 8
  });

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

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900">
      {/* Animated Background */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob"></div>
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-pink-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000"></div>
        <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 w-80 h-80 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-4000"></div>
      </div>

      {/* Header */}
      <header className="relative z-10 border-b border-white/10 backdrop-blur-xl bg-white/5">
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
            
            <div className="flex items-center gap-6">
              <motion.div 
                className="flex items-center gap-3 bg-white/10 backdrop-blur-md rounded-full px-4 py-2"
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

              <button
                onClick={() => setShowIntegrations(true)}
                className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-4 py-2 rounded-lg font-medium hover:shadow-lg hover:shadow-purple-500/25 transition-all duration-300 flex items-center gap-2"
              >
                <Link2 className="w-4 h-4" />
                Integrations
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
            { id: 'audit', label: 'Site Audit', icon: Activity },
            { id: 'optimizations', label: 'Optimizations', icon: Sparkles },
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

        {/* Content Area */}
        <AnimatePresence mode="wait">
          {activeTab === 'overview' && (
            <motion.div
              key="overview"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="grid grid-cols-1 md:grid-cols-4 gap-4"
            >
              <motion.div
                whileHover={{ scale: 1.02 }}
                className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20"
              >
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-purple-300 text-sm font-medium">Keywords Tracked</p>
                    <p className="text-3xl font-bold text-white mt-2">{stats.keywords.toLocaleString()}</p>
                  </div>
                  <Search className="w-6 h-6 text-purple-400" />
                </div>
              </motion.div>
            </motion.div>
          )}

          {activeTab === 'audit' && (
            <AuditDashboard websiteId={selectedWebsite} />
          )}

          {activeTab === 'optimizations' && (
            <OptimizationQueue websiteId={selectedWebsite} />
          )}

          {activeTab === 'errors' && (
            <ErrorMonitor websiteId={selectedWebsite} />
          )}

          {activeTab === 'content' && (
            <ContentCalendar websiteId={selectedWebsite} />
          )}

          {activeTab === 'competitors' && (
            <CompetitorAnalysis websiteId={selectedWebsite} />
          )}
        </AnimatePresence>
      </div>

      {/* Integrations Modal */}
      {showIntegrations && (
        <IntegrationsModal onClose={() => setShowIntegrations(false)} />
      )}
    </div>
  );
}
