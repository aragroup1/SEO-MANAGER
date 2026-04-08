// frontend/components/IntegrationSetupChecklist.tsx
'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, BarChart3, ShoppingCart, Layers,
  CheckCircle, ExternalLink, Loader2, X,
  ChevronDown, ChevronUp, Plug, Sparkles
} from 'lucide-react';

interface IntegrationItem {
  id: string;
  name: string;
  description: string;
  icon: any;
  connected: boolean;
  required: boolean;
  connectUrl?: string;
  relevantFor: string[]; // site_types this integration is relevant for
  dataProvided: string;
}

interface Props {
  websiteId: number;
  siteType: string;
  onIntegrationChange?: () => void;
}

export default function IntegrationSetupChecklist({ websiteId, siteType, onIntegrationChange }: Props) {
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  const getIconForIntegration = (id: string) => {
    switch (id) {
      case 'google_search_console': return Search;
      case 'google_analytics': return BarChart3;
      case 'shopify': return ShoppingCart;
      case 'wordpress': return Layers;
      default: return Search;
    }
  };

  const fetchIntegrationStatus = async () => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/integrations/${websiteId}/status`
      );
      if (response.ok) {
        const data = await response.json();
        const rawList = data.integrations || [];
        if (rawList.length > 0) {
          // Map icon components onto API data — API can't return React components
          const mapped = rawList.map((i: any) => ({
            ...i,
            icon: getIconForIntegration(i.id),
            relevantFor: i.relevantFor || [],
            dataProvided: i.dataProvided || i.description || '',
          }));
          setIntegrations(mapped);
        } else {
          setIntegrations(getDefaultIntegrations());
        }
      } else {
        setIntegrations(getDefaultIntegrations());
      }
    } catch (error) {
      console.error('Error fetching integration status:', error);
      setIntegrations(getDefaultIntegrations());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIntegrationStatus();
  }, [websiteId]);

  const getDefaultIntegrations = (): IntegrationItem[] => [
    {
      id: 'google_search_console',
      name: 'Google Search Console',
      description: 'Track keyword rankings, impressions, and indexing status',
      icon: Search,
      connected: false,
      required: true,
      relevantFor: ['custom', 'shopify', 'wordpress'],
      dataProvided: 'Keyword rankings, click data, indexing errors'
    },
    {
      id: 'google_analytics',
      name: 'Google Analytics 4',
      description: 'Monitor traffic, user behavior, and conversions',
      icon: BarChart3,
      connected: false,
      required: true,
      relevantFor: ['custom', 'shopify', 'wordpress'],
      dataProvided: 'Traffic sources, user engagement, conversion tracking'
    },
    {
      id: 'shopify',
      name: 'Shopify',
      description: 'Sync products, manage meta tags, and optimize listings',
      icon: ShoppingCart,
      connected: false,
      required: true,
      relevantFor: ['shopify'],
      dataProvided: 'Product data, collection structure, meta fields'
    },
    {
      id: 'wordpress',
      name: 'WordPress',
      description: 'Sync posts, manage Yoast/RankMath settings, and optimize content',
      icon: Layers,
      connected: false,
      required: true,
      relevantFor: ['wordpress'],
      dataProvided: 'Posts, pages, plugin settings, sitemap data'
    }
  ];

  const [wpFormVisible, setWpFormVisible] = useState(false);
  const [wpUrl, setWpUrl] = useState('');
  const [wpUsername, setWpUsername] = useState('');
  const [wpAppPassword, setWpAppPassword] = useState('');

  const connectIntegration = async (integrationId: string) => {
    // WordPress needs credentials — show form first
    if (integrationId === 'wordpress') {
      setWpFormVisible(true);
      return;
    }

    setConnecting(integrationId);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/integrations/${websiteId}/connect`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ integration_id: integrationId })
        }
      );

      const data = await response.json();

      if (data.authorization_url) {
        const popup = window.open(
          data.authorization_url,
          'integration_connect',
          'width=600,height=700,scrollbars=yes'
        );

        const pollTimer = setInterval(() => {
          if (popup?.closed) {
            clearInterval(pollTimer);
            fetchIntegrationStatus();
            onIntegrationChange?.();
          }
        }, 1000);
      } else if (data.connected) {
        await fetchIntegrationStatus();
        onIntegrationChange?.();
      }
    } catch (error) {
      console.error('Error connecting integration:', error);
      alert('Failed to connect. Please try again.');
    } finally {
      setConnecting(null);
    }
  };

  const connectWordPress = async () => {
    if (!wpUrl || !wpUsername || !wpAppPassword) {
      alert('All fields are required');
      return;
    }
    setConnecting('wordpress');
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/integrations/${websiteId}/connect`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            integration_id: 'wordpress',
            wordpress_url: wpUrl,
            username: wpUsername,
            app_password: wpAppPassword,
          })
        }
      );
      const data = await response.json();
      if (data.connected) {
        setWpFormVisible(false);
        setWpUrl('');
        setWpUsername('');
        setWpAppPassword('');
        await fetchIntegrationStatus();
        onIntegrationChange?.();
      } else {
        alert('Connection failed: ' + (data.message || 'Unknown error'));
      }
    } catch (error) {
      alert('Connection error. Check your credentials.');
    } finally {
      setConnecting(null);
    }
  };

  // Filter integrations relevant to this site type
  const relevantIntegrations = integrations.filter(
    i => i.relevantFor.includes(siteType)
  );

  const connectedCount = relevantIntegrations.filter(i => i.connected).length;
  const totalCount = relevantIntegrations.length;
  const allConnected = connectedCount === totalCount;
  const pendingIntegrations = relevantIntegrations.filter(i => !i.connected);

  // Don't render if all connected or dismissed
  if (allConnected || dismissed || loading) {
    if (loading) {
      return null; // Don't show a loader, just hide until ready
    }
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="mb-6"
    >
      <div className="relative overflow-hidden rounded-2xl border border-amber-500/30 bg-gradient-to-r from-amber-500/10 via-orange-500/10 to-amber-500/10 backdrop-blur-md">
        {/* Subtle animated gradient border effect */}
        <div className="absolute inset-0 bg-gradient-to-r from-amber-500/5 to-orange-500/5 animate-pulse pointer-events-none" />

        <div className="relative p-5">
          {/* Header */}
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-500/20 rounded-lg">
                <Plug className="w-5 h-5 text-amber-400" />
              </div>
              <div>
                <h3 className="text-white font-semibold text-base flex items-center gap-2">
                  Connect Your Platforms
                  <span className="text-xs font-normal text-amber-400 bg-amber-500/20 px-2 py-0.5 rounded-full">
                    {connectedCount}/{totalCount} connected
                  </span>
                </h3>
                <p className="text-gray-400 text-sm mt-0.5">
                  Connect these to unlock accurate audit data and AI recommendations
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCollapsed(!collapsed)}
                className="text-gray-400 hover:text-white transition-colors p-1"
              >
                {collapsed ? (
                  <ChevronDown className="w-4 h-4" />
                ) : (
                  <ChevronUp className="w-4 h-4" />
                )}
              </button>
              <button
                onClick={() => setDismissed(true)}
                className="text-gray-400 hover:text-white transition-colors p-1"
                title="Dismiss for now"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Progress bar */}
          <div className="mt-3 mb-4">
            <div className="w-full h-1.5 bg-white/10 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${(connectedCount / totalCount) * 100}%` }}
                transition={{ duration: 0.5 }}
                className="h-full bg-gradient-to-r from-amber-500 to-green-500 rounded-full"
              />
            </div>
          </div>

          {/* Integration cards */}
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden"
              >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {pendingIntegrations.map((integration) => {
                    const Icon = integration.icon;
                    const isConnecting = connecting === integration.id;

                    return (
                      <motion.div
                        key={integration.id}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/10 hover:border-amber-500/30 transition-all group"
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-white/10 rounded-lg group-hover:bg-amber-500/20 transition-colors">
                            <Icon className="w-4 h-4 text-gray-400 group-hover:text-amber-400 transition-colors" />
                          </div>
                          <div>
                            <p className="text-white text-sm font-medium">
                              {integration.name}
                            </p>
                            <p className="text-gray-500 text-xs">
                              {integration.dataProvided}
                            </p>
                          </div>
                        </div>
                        <button
                          onClick={() => connectIntegration(integration.id)}
                          disabled={isConnecting}
                          className="bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 disabled:opacity-50 whitespace-nowrap"
                        >
                          {isConnecting ? (
                            <>
                              <Loader2 className="w-3 h-3 animate-spin" />
                              Connecting...
                            </>
                          ) : (
                            <>
                              <ExternalLink className="w-3 h-3" />
                              Connect
                            </>
                          )}
                        </button>
                      </motion.div>
                    );
                  })}
                </div>

                {/* Already connected (shown smaller) */}
                {relevantIntegrations.filter(i => i.connected).length > 0 && (
                  <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/10">
                    <span className="text-gray-500 text-xs">Connected:</span>
                    {relevantIntegrations
                      .filter(i => i.connected)
                      .map(i => (
                        <span
                          key={i.id}
                          className="flex items-center gap-1 text-green-400 text-xs bg-green-500/10 px-2 py-0.5 rounded-full"
                        >
                          <CheckCircle className="w-3 h-3" />
                          {i.name}
                        </span>
                      ))}
                  </div>
                )}

                {/* WordPress Credential Form */}
                {wpFormVisible && (
                  <div className="mt-3 p-4 bg-white/5 rounded-xl border border-blue-500/30">
                    <h4 className="text-white font-medium text-sm mb-3 flex items-center gap-2">
                      <Plug className="w-4 h-4 text-blue-400" />
                      Connect WordPress
                    </h4>
                    <p className="text-gray-400 text-xs mb-3">
                      Generate an Application Password in WordPress: Users → Your Profile → Application Passwords
                    </p>
                    <div className="space-y-2">
                      <input type="text" placeholder="WordPress URL (e.g. barcodemarket.com)" value={wpUrl} onChange={e => setWpUrl(e.target.value)}
                        className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500" />
                      <input type="text" placeholder="Admin username" value={wpUsername} onChange={e => setWpUsername(e.target.value)}
                        className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500" />
                      <input type="password" placeholder="Application password (not your login password)" value={wpAppPassword} onChange={e => setWpAppPassword(e.target.value)}
                        className="w-full bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white text-sm placeholder-gray-500 focus:outline-none focus:border-blue-500" />
                      <div className="flex gap-2 mt-2">
                        <button onClick={connectWordPress} disabled={connecting === 'wordpress'}
                          className="flex-1 bg-blue-500/20 text-blue-400 px-3 py-2 rounded-lg text-sm font-medium hover:bg-blue-500/30 transition-all flex items-center justify-center gap-1.5 disabled:opacity-50">
                          {connecting === 'wordpress' ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                          {connecting === 'wordpress' ? 'Connecting...' : 'Connect'}
                        </button>
                        <button onClick={() => setWpFormVisible(false)}
                          className="bg-white/10 text-gray-400 px-3 py-2 rounded-lg text-sm hover:bg-white/20 transition-all">
                          Cancel
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
