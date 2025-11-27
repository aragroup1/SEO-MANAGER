// frontend/components/GoogleIntegrations.tsx
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { 
  BarChart3, TrendingUp, Search, Globe, 
  ShoppingBag, Users, Link2, CheckCircle
} from 'lucide-react';

interface Integration {
  id: string;
  name: string;
  icon: any;
  connected: boolean;
  description: string;
  metrics?: {
    label: string;
    value: string;
  }[];
}

export default function GoogleIntegrations({ websiteId }: { websiteId: number }) {
  const [integrations, setIntegrations] = useState<Integration[]>([
    {
      id: 'analytics',
      name: 'Google Analytics',
      icon: BarChart3,
      connected: false,
      description: 'Track visitor behavior and conversions',
      metrics: [
        { label: 'Sessions', value: '45.2K' },
        { label: 'Bounce Rate', value: '42%' }
      ]
    },
    {
      id: 'search_console',
      name: 'Search Console',
      icon: Search,
      connected: false,
      description: 'Monitor search performance and indexing',
      metrics: [
        { label: 'Impressions', value: '1.2M' },
        { label: 'Avg Position', value: '18.5' }
      ]
    },
    {
      id: 'merchant',
      name: 'Merchant Center',
      icon: ShoppingBag,
      connected: false,
      description: 'Manage product listings and shopping ads',
      metrics: [
        { label: 'Products', value: '1,847' },
        { label: 'Approved', value: '98%' }
      ]
    },
    {
      id: 'business',
      name: 'Business Profile',
      icon: Users,
      connected: false,
      description: 'Manage local presence and reviews',
      metrics: [
        { label: 'Views', value: '12.3K' },
        { label: 'Reviews', value: '4.8★' }
      ]
    }
  ]);

  const connectIntegration = async (integrationId: string) => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/google/init?user_id=1&integration_type=${integrationId}`);
      const data = await response.json();
      
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      }
    } catch (error) {
      console.error('Error connecting integration:', error);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-xl font-bold text-white mb-2">Google Integrations</h3>
        <p className="text-purple-300">Connect your Google services for comprehensive SEO insights</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {integrations.map((integration) => {
          const Icon = integration.icon;
          return (
            <motion.div
              key={integration.id}
              whileHover={{ scale: 1.02 }}
              className="bg-white/10 backdrop-blur-md rounded-xl p-4 border border-white/20"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-purple-500/20 rounded-lg">
                    <Icon className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <h4 className="text-white font-medium">{integration.name}</h4>
                    <p className="text-purple-300 text-sm">{integration.description}</p>
                  </div>
                </div>
                {integration.connected ? (
                  <CheckCircle className="w-5 h-5 text-green-400" />
                ) : (
                  <button
                    onClick={() => connectIntegration(integration.id)}
                    className="text-purple-400 hover:text-purple-300 transition-colors"
                  >
                    <Link2 className="w-5 h-5" />
                  </button>
                )}
              </div>

              {integration.connected && integration.metrics && (
                <div className="grid grid-cols-2 gap-3 mt-3 pt-3 border-t border-white/10">
                  {integration.metrics.map((metric) => (
                    <div key={metric.label}>
                      <p className="text-gray-400 text-xs">{metric.label}</p>
                      <p className="text-white font-semibold">{metric.value}</p>
                    </div>
                  ))}
                </div>
              )}

              {!integration.connected && (
                <button
                  onClick={() => connectIntegration(integration.id)}
                  className="w-full mt-3 bg-purple-500/20 text-purple-400 px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-purple-500/30 transition-all"
                >
                  Connect
                </button>
              )}
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
