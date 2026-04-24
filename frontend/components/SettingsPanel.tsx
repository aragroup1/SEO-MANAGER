// frontend/components/SettingsPanel.tsx
'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Settings, Search, BarChart3, ShoppingCart, Layers,
  CheckCircle, XCircle, Loader2, Trash2, RefreshCw,
  ExternalLink, Clock, Shield, Bell, User, CreditCard,
  ChevronRight, Plug, AlertTriangle, Bot, Zap, Hand
} from 'lucide-react';

interface ConnectedIntegration {
  id: string;
  name: string;
  icon: any;
  connected: boolean;
  connected_at?: string;
  last_synced?: string;
  status: 'active' | 'error' | 'expired';
  scopes?: string[];
  account_name?: string;
}

interface Props {
  websiteId: number;
  onClose?: () => void;
}

export default function SettingsPanel({ websiteId, onClose }: Props) {
  const [activeSection, setActiveSection] = useState('integrations');
  const [integrations, setIntegrations] = useState<ConnectedIntegration[]>([]);
  const [loading, setLoading] = useState(true);
  const [disconnecting, setDisconnecting] = useState<string | null>(null);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [autonomyMode, setAutonomyMode] = useState<string>('manual');
  const [savingMode, setSavingMode] = useState(false);
  const [modeStats, setModeStats] = useState({ auto_approved: 0, auto_applied: 0 });

  useEffect(() => {
    fetchConnectedIntegrations();
    fetchAutonomyMode();
    fetchModeStats();
  }, [websiteId]);

  useEffect(() => {
    fetchConnectedIntegrations();
  }, [websiteId]);

  const fetchConnectedIntegrations = async () => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/integrations/${websiteId}/connected`
      );
      if (response.ok) {
        const data = await response.json();
        setIntegrations(data.integrations || []);
      } else {
        // Mock data for development
        setIntegrations(getMockIntegrations());
      }
    } catch (error) {
      console.error('Error fetching integrations:', error);
      setIntegrations(getMockIntegrations());
    } finally {
      setLoading(false);
    }
  };

  const getMockIntegrations = (): ConnectedIntegration[] => [
    // Returns empty — user hasn't connected anything yet
  ];

  const getIconComponent = (id: string) => {
    switch (id) {
      case 'google_search_console': return Search;
      case 'google_analytics': return BarChart3;
      case 'shopify': return ShoppingCart;
      case 'wordpress': return Layers;
      default: return Plug;
    }
  };

  const disconnectIntegration = async (integrationId: string) => {
    if (!confirm('Are you sure you want to disconnect this integration? Historical data will be preserved.')) {
      return;
    }

    setDisconnecting(integrationId);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/integrations/${websiteId}/disconnect`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ integration_id: integrationId })
        }
      );

      if (response.ok) {
        setIntegrations(prev => prev.filter(i => i.id !== integrationId));
      }
    } catch (error) {
      console.error('Error disconnecting:', error);
    } finally {
      setDisconnecting(null);
    }
  };

  const syncIntegration = async (integrationId: string) => {
    setSyncing(integrationId);
    try {
      await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/integrations/${websiteId}/sync`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ integration_id: integrationId })
        }
      );
      await fetchConnectedIntegrations();
    } catch (error) {
      console.error('Error syncing:', error);
    } finally {
      setSyncing(null);
    }
  };

  const reconnectIntegration = async (integrationId: string) => {
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
        window.open(data.authorization_url, 'integration_connect', 'width=600,height=700,scrollbars=yes');
      }
    } catch (error) {
      console.error('Error reconnecting:', error);
    }
  };

  const fetchAutonomyMode = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/websites?user_id=1`);
      if (response.ok) {
        const data = await response.json();
        const site = data.find((w: any) => w.id === websiteId);
        if (site) setAutonomyMode(site.autonomy_mode || 'manual');
      }
    } catch (error) {
      console.error('Error fetching autonomy mode:', error);
    }
  };

  const fetchModeStats = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/fixes/${websiteId}/summary`);
      if (response.ok) {
        const data = await response.json();
        setModeStats({
          auto_approved: data.auto_approved || 0,
          auto_applied: data.auto_applied || 0,
        });
      }
    } catch (error) {
      console.error('Error fetching mode stats:', error);
    }
  };

  const updateAutonomyMode = async (mode: string) => {
    if (mode === autonomyMode) return;
    const confirmMsg = mode === 'ultra'
      ? 'WARNING: Ultra mode will automatically apply ALL fixes without review. Are you sure?'
      : mode === 'smart'
      ? 'Smart mode will auto-approve safe fixes (alt text, meta tags, structured data). Content changes still need approval. Continue?'
      : 'Switch to Manual mode? All fixes will require your approval.';
    if (!confirm(confirmMsg)) return;

    setSavingMode(true);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/websites/${websiteId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ autonomy_mode: mode })
        }
      );
      if (response.ok) {
        setAutonomyMode(mode);
      }
    } catch (error) {
      console.error('Error updating autonomy mode:', error);
    } finally {
      setSavingMode(false);
    }
  };

  const sections = [
    { id: 'integrations', label: 'Integrations', icon: Plug },
    { id: 'automation', label: 'Automation', icon: Bot },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'account', label: 'Account', icon: User },
    { id: 'billing', label: 'Billing', icon: CreditCard },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Settings</h2>
          <p className="text-purple-300 mt-1">Manage your account and integrations</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar */}
        <div className="lg:col-span-1">
          <div className="bg-white/10 backdrop-blur-md rounded-2xl border border-white/20 overflow-hidden">
            {sections.map((section) => {
              const Icon = section.icon;
              return (
                <button
                  key={section.id}
                  onClick={() => setActiveSection(section.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 text-left transition-all ${
                    activeSection === section.id
                      ? 'bg-purple-500/20 text-white border-l-2 border-purple-500'
                      : 'text-gray-400 hover:bg-white/5 hover:text-white border-l-2 border-transparent'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="text-sm font-medium">{section.label}</span>
                  {section.id === 'integrations' && integrations.length > 0 && (
                    <span className="ml-auto text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded-full">
                      {integrations.length}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Content */}
        <div className="lg:col-span-3">
          {activeSection === 'integrations' && (
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-lg font-semibold text-white">Connected Integrations</h3>
                  <p className="text-gray-400 text-sm mt-1">
                    Manage your connected platforms and data sources
                  </p>
                </div>
              </div>

              {loading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-6 h-6 text-purple-400 animate-spin" />
                </div>
              ) : integrations.length === 0 ? (
                <div className="text-center py-12">
                  <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Plug className="w-8 h-8 text-gray-500" />
                  </div>
                  <p className="text-gray-400 mb-2">No integrations connected yet</p>
                  <p className="text-gray-500 text-sm">
                    Go to your site audit dashboard to connect platforms
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {integrations.map((integration) => {
                    const Icon = getIconComponent(integration.id);
                    const isDisconnecting = disconnecting === integration.id;
                    const isSyncing = syncing === integration.id;

                    return (
                      <div
                        key={integration.id}
                        className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/10"
                      >
                        <div className="flex items-center gap-4">
                          <div className={`p-2.5 rounded-lg ${
                            integration.status === 'active'
                              ? 'bg-green-500/20'
                              : integration.status === 'error'
                              ? 'bg-red-500/20'
                              : 'bg-yellow-500/20'
                          }`}>
                            <Icon className={`w-5 h-5 ${
                              integration.status === 'active'
                                ? 'text-green-400'
                                : integration.status === 'error'
                                ? 'text-red-400'
                                : 'text-yellow-400'
                            }`} />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <p className="text-white font-medium">{integration.name}</p>
                              {integration.status === 'active' && (
                                <CheckCircle className="w-3.5 h-3.5 text-green-400" />
                              )}
                              {integration.status === 'error' && (
                                <AlertTriangle className="w-3.5 h-3.5 text-red-400" />
                              )}
                              {integration.status === 'expired' && (
                                <Clock className="w-3.5 h-3.5 text-yellow-400" />
                              )}
                            </div>
                            {integration.account_name && (
                              <p className="text-gray-500 text-xs mt-0.5">
                                {integration.account_name}
                              </p>
                            )}
                            <div className="flex items-center gap-3 mt-1">
                              {integration.connected_at && (
                                <span className="text-gray-500 text-xs">
                                  Connected {new Date(integration.connected_at).toLocaleDateString()}
                                </span>
                              )}
                              {integration.last_synced && (
                                <span className="text-gray-500 text-xs">
                                  Last synced {new Date(integration.last_synced).toLocaleString()}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2">
                          {integration.status === 'error' || integration.status === 'expired' ? (
                            <button
                              onClick={() => reconnectIntegration(integration.id)}
                              className="bg-yellow-500/20 text-yellow-400 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-yellow-500/30 transition-all flex items-center gap-1.5"
                            >
                              <RefreshCw className="w-3 h-3" />
                              Reconnect
                            </button>
                          ) : (
                            <button
                              onClick={() => syncIntegration(integration.id)}
                              disabled={isSyncing}
                              className="bg-purple-500/20 text-purple-400 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-purple-500/30 transition-all flex items-center gap-1.5 disabled:opacity-50"
                            >
                              {isSyncing ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <RefreshCw className="w-3 h-3" />
                              )}
                              Sync
                            </button>
                          )}
                          <button
                            onClick={() => disconnectIntegration(integration.id)}
                            disabled={isDisconnecting}
                            className="text-gray-500 hover:text-red-400 transition-colors p-1.5 disabled:opacity-50"
                            title="Disconnect"
                          >
                            {isDisconnecting ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <Trash2 className="w-4 h-4" />
                            )}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {activeSection === 'automation' && (
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-lg font-semibold text-white">Automation Mode</h3>
                  <p className="text-gray-400 text-sm mt-1">
                    Control how aggressively the AI applies fixes to your site
                  </p>
                </div>
              </div>

              <div className="space-y-4 mb-8">
                {[
                  {
                    id: 'manual',
                    label: 'Manual',
                    description: 'I review and approve every change before it goes live.',
                    icon: Hand,
                    color: 'blue',
                  },
                  {
                    id: 'smart',
                    label: 'Smart',
                    description: 'Auto-approve safe fixes (alt text, meta tags, structured data). Content changes still need my approval.',
                    icon: Zap,
                    color: 'purple',
                  },
                  {
                    id: 'ultra',
                    label: 'Ultra',
                    description: 'Apply all fixes automatically. I\'ll review the daily summary. Maximum growth mode.',
                    icon: Bot,
                    color: 'green',
                  },
                ].map((mode) => {
                  const Icon = mode.icon;
                  const isSelected = autonomyMode === mode.id;
                  const colorClasses: Record<string, { bg: string; border: string; text: string; ring: string }> = {
                    blue: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-400', ring: 'ring-blue-500' },
                    purple: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400', ring: 'ring-purple-500' },
                    green: { bg: 'bg-green-500/10', border: 'border-green-500/30', text: 'text-green-400', ring: 'ring-green-500' },
                  };
                  const c = colorClasses[mode.color];
                  return (
                    <button
                      key={mode.id}
                      onClick={() => updateAutonomyMode(mode.id)}
                      disabled={savingMode}
                      className={`w-full flex items-start gap-4 p-4 rounded-xl border transition-all text-left ${
                        isSelected
                          ? `${c.bg} ${c.border} ring-1 ${c.ring}`
                          : 'bg-white/5 border-white/10 hover:bg-white/10'
                      }`}
                    >
                      <div className={`p-2 rounded-lg ${c.bg} ${c.border}`}>
                        <Icon className={`w-5 h-5 ${c.text}`} />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <p className={`font-semibold ${isSelected ? 'text-white' : 'text-gray-300'}`}>
                            {mode.label}
                          </p>
                          {isSelected && (
                            <span className={`text-xs px-2 py-0.5 rounded-full ${c.bg} ${c.text} border ${c.border}`}>
                              Active
                            </span>
                          )}
                        </div>
                        <p className="text-gray-500 text-sm mt-1">{mode.description}</p>
                      </div>
                      <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center mt-1 ${
                        isSelected ? `${c.border} ${c.bg}` : 'border-white/20'
                      }`}>
                        {isSelected && <div className={`w-2.5 h-2.5 rounded-full ${c.text.replace('text-', 'bg-')}`} />}
                      </div>
                    </button>
                  );
                })}
              </div>

              <div className="bg-white/5 rounded-xl p-4 border border-white/10">
                <h4 className="text-sm font-medium text-white mb-3">This Week's Automation Stats</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center p-3 bg-white/5 rounded-lg">
                    <p className="text-2xl font-bold text-purple-400">{modeStats.auto_approved}</p>
                    <p className="text-gray-500 text-xs mt-1">Auto-Approved Fixes</p>
                  </div>
                  <div className="text-center p-3 bg-white/5 rounded-lg">
                    <p className="text-2xl font-bold text-green-400">{modeStats.auto_applied}</p>
                    <p className="text-gray-500 text-xs mt-1">Auto-Applied Fixes</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'notifications' && (
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
              <h3 className="text-lg font-semibold text-white mb-4">Notification Preferences</h3>
              <div className="space-y-4">
                {[
                  { label: 'Weekly SEO Report', description: 'Receive a summary every Monday', enabled: true },
                  { label: 'Critical Errors', description: 'Get alerted when critical issues are found', enabled: true },
                  { label: 'Ranking Changes', description: 'Notify when keywords move more than 5 positions', enabled: false },
                  { label: 'Content Reminders', description: 'Remind about scheduled content deadlines', enabled: false },
                ].map((pref) => (
                  <div key={pref.label} className="flex items-center justify-between p-4 bg-white/5 rounded-xl">
                    <div>
                      <p className="text-white font-medium text-sm">{pref.label}</p>
                      <p className="text-gray-500 text-xs mt-0.5">{pref.description}</p>
                    </div>
                    <button
                      className={`relative w-11 h-6 rounded-full transition-colors ${
                        pref.enabled ? 'bg-purple-500' : 'bg-white/20'
                      }`}
                    >
                      <div
                        className={`absolute top-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-sm ${
                          pref.enabled ? 'translate-x-5' : 'translate-x-0.5'
                        }`}
                      />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeSection === 'account' && (
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
              <h3 className="text-lg font-semibold text-white mb-4">Account Settings</h3>
              <p className="text-gray-400 text-sm">Account management coming soon with authentication.</p>
            </div>
          )}

          {activeSection === 'billing' && (
            <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
              <h3 className="text-lg font-semibold text-white mb-4">Billing & Subscription</h3>
              <p className="text-gray-400 text-sm">Billing management coming soon with Stripe integration.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
