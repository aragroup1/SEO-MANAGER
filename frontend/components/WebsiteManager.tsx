// frontend/components/WebsiteManager.tsx
'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Globe, Plus, Trash2, Edit, ExternalLink, 
  ShoppingCart, Code, Layers, CheckCircle,  // Changed Wordpress to Layers
  Settings, TrendingUp, AlertCircle, Loader2
} from 'lucide-react';

interface Website {
  id: number;
  domain: string;
  site_type: 'shopify' | 'wordpress' | 'custom';
  monthly_traffic?: number;
  health_score?: number;
  created_at: string;
}

export default function WebsiteManager() {
  const [websites, setWebsites] = useState<Website[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    domain: '',
    site_type: 'custom',
    shopify_store_url: '',
    shopify_access_token: ''
  });

  useEffect(() => {
    fetchWebsites();
  }, []);

  const fetchWebsites = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/websites`);
      const data = await response.json();
      setWebsites(data);
    } catch (error) {
      console.error('Error fetching websites:', error);
    }
  };

  const addWebsite = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/websites`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          user_id: 1 // You'll want to get this from auth context
        })
      });
      
      if (response.ok) {
        await fetchWebsites();
        setShowAddModal(false);
        setFormData({ domain: '', site_type: 'custom', shopify_store_url: '', shopify_access_token: '' });
      }
    } catch (error) {
      console.error('Error adding website:', error);
    } finally {
      setLoading(false);
    }
  };

  const deleteWebsite = async (id: number) => {
    if (!confirm('Are you sure you want to delete this website?')) return;
    
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_URL}/websites/${id}`, {
        method: 'DELETE'
      });
      await fetchWebsites();
    } catch (error) {
      console.error('Error deleting website:', error);
    }
  };

  const getSiteIcon = (type: string) => {
    switch (type) {
      case 'shopify': return <ShoppingCart className="w-5 h-5" />;
      case 'wordpress': return <Layers className="w-5 h-5" />;  // Changed to Layers icon
      default: return <Code className="w-5 h-5" />;
    }
  };

  const getHealthColor = (score?: number) => {
    if (!score) return 'text-gray-400';
    if (score >= 80) return 'text-green-400';
    if (score >= 60) return 'text-yellow-400';
    if (score >= 40) return 'text-orange-400';
    return 'text-red-400';
  };

  // frontend/components/WebsiteManager.tsx - Update the addWebsite function

const addWebsite = async () => {
  if (!formData.domain) {
    alert('Please enter a domain');
    return;
  }

  setLoading(true);
  try {
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/websites`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ...formData,
        user_id: 1 // Default user for now
      })
    });
    
    const data = await response.json();
    
    if (response.ok) {
      await fetchWebsites();
      setShowAddModal(false);
      setFormData({ domain: '', site_type: 'custom', shopify_store_url: '', shopify_access_token: '' });
    } else {
      alert(data.detail || 'Failed to add website');
    }
  } catch (error) {
    console.error('Error adding website:', error);
    alert('Failed to add website. Please check your connection.');
  } finally {
    setLoading(false);
  }
};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">Website Management</h2>
          <p className="text-purple-300 mt-1">Manage and monitor all your websites in one place</p>
        </div>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setShowAddModal(true)}
          className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 shadow-lg hover:shadow-purple-500/25"
        >
          <Plus className="w-4 h-4" />
          Add Website
        </motion.button>
      </div>

      {/* Websites Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {websites.map((website) => (
          <motion.div
            key={website.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20 hover:bg-white/15 transition-all"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-500/20 rounded-lg">
                  {getSiteIcon(website.site_type)}
                </div>
                <div>
                  <h3 className="text-white font-semibold">{website.domain}</h3>
                  <p className="text-purple-300 text-sm capitalize">{website.site_type}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button 
                  className="text-gray-400 hover:text-white transition-colors"
                  onClick={() => window.open(`https://${website.domain}`, '_blank')}
                >
                  <ExternalLink className="w-4 h-4" />
                </button>
                <button 
                  className="text-gray-400 hover:text-red-400 transition-colors"
                  onClick={() => deleteWebsite(website.id)}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-sm">Health Score</span>
                <span className={`font-bold ${getHealthColor(website.health_score)}`}>
                  {website.health_score || '--'}%
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-sm">Monthly Traffic</span>
                <span className="text-white font-medium">
                  {website.monthly_traffic?.toLocaleString() || '--'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-400 text-sm">Status</span>
                <span className="flex items-center gap-1 text-green-400 text-sm">
                  <CheckCircle className="w-3 h-3" />
                  Active
                </span>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-white/10 flex gap-2">
              <button className="flex-1 bg-purple-500/20 text-purple-400 px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-purple-500/30 transition-all">
                Dashboard
              </button>
              <button className="flex-1 bg-white/10 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-white/20 transition-all">
                Settings
              </button>
            </div>
          </motion.div>
        ))}

        {/* Add Website Card */}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => setShowAddModal(true)}
          className="bg-white/5 backdrop-blur-md rounded-2xl p-6 border border-white/20 hover:bg-white/10 transition-all flex flex-col items-center justify-center min-h-[280px] border-dashed"
        >
          <div className="w-16 h-16 bg-purple-500/20 rounded-full flex items-center justify-center mb-4">
            <Plus className="w-8 h-8 text-purple-400" />
          </div>
          <p className="text-white font-medium">Add New Website</p>
          <p className="text-purple-300 text-sm mt-1">Connect your website to start tracking</p>
        </motion.button>
      </div>

      {/* Add Website Modal */}
      <AnimatePresence>
        {showAddModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={() => setShowAddModal(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              className="bg-gradient-to-br from-gray-900 to-purple-900 rounded-2xl p-6 max-w-md w-full border border-white/20"
              onClick={(e) => e.stopPropagation()}
            >
              <h3 className="text-xl font-bold text-white mb-4">Add New Website</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-purple-300 text-sm font-medium mb-2">
                    Website Domain
                  </label>
                  <input
                    type="text"
                    placeholder="example.com"
                    value={formData.domain}
                    onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-purple-500"
                  />
                </div>

                <div>
                  <label className="block text-purple-300 text-sm font-medium mb-2">
                    Platform Type
                  </label>
                  <select
                    value={formData.site_type}
                    onChange={(e) => setFormData({ ...formData, site_type: e.target.value })}
                    className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-purple-500"
                  >
                    <option value="custom">Custom Website</option>
                    <option value="shopify">Shopify</option>
                    <option value="wordpress">WordPress</option>
                  </select>
                </div>

                {formData.site_type === 'shopify' && (
                  <>
                    <div>
                      <label className="block text-purple-300 text-sm font-medium mb-2">
                        Shopify Store URL
                      </label>
                      <input
                        type="text"
                        placeholder="mystore.myshopify.com"
                        value={formData.shopify_store_url}
                        onChange={(e) => setFormData({ ...formData, shopify_store_url: e.target.value })}
                        className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-purple-500"
                      />
                    </div>
                    <div>
                      <label className="block text-purple-300 text-sm font-medium mb-2">
                        Access Token (Optional)
                      </label>
                      <input
                        type="password"
                        placeholder="shpat_xxxxx"
                        value={formData.shopify_access_token}
                        onChange={(e) => setFormData({ ...formData, shopify_access_token: e.target.value })}
                        className="w-full bg-white/10 border border-white/20 rounded-lg px-4 py-2 text-white placeholder-gray-400 focus:outline-none focus:border-purple-500"
                      />
                    </div>
                  </>
                )}
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 bg-white/10 text-white px-4 py-2 rounded-lg font-medium hover:bg-white/20 transition-all"
                >
                  Cancel
                </button>
                <button
                  onClick={addWebsite}
                  disabled={loading || !formData.domain}
                  className="flex-1 bg-gradient-to-r from-purple-500 to-pink-500 text-white px-4 py-2 rounded-lg font-medium hover:shadow-lg hover:shadow-purple-500/25 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Adding...
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4" />
                      Add Website
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
