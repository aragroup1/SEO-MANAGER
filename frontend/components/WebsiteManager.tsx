// frontend/components/WebsiteManager.tsx
'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Globe, Plus, Trash2, Edit, ExternalLink, 
  ShoppingCart, Code, Layers, CheckCircle,
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

  // ONLY ONE addWebsite function - with proper error handling
  const addWebsite = async () => {
    if (!formData.domain) {
      alert('Please enter a domain');
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/websites`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      case 'wordpress': return <Layers className="w-5 h-5" />;
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

  // Rest of your component code stays the same...
  return (
    // Your existing JSX
    <div className="space-y-6">
      {/* ... rest of your component */}
    </div>
  );
}
