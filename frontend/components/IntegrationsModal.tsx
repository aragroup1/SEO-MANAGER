// frontend/components/IntegrationsModal.tsx
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { X, Check, Loader, BarChart3, Search, ShoppingBag, Users } from 'lucide-react';
import GoogleIntegrations from './GoogleIntegrations';

export default function IntegrationsModal({ onClose }: { onClose: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        className="bg-gradient-to-br from-gray-900 to-purple-900 rounded-2xl p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto border border-white/20"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-white">Integrations</h2>
          <button onClick={onClose} className="text-white hover:text-gray-300">
            <X className="w-6 h-6" />
          </button>
        </div>
        
        <GoogleIntegrations websiteId={1} />
      </motion.div>
    </motion.div>
  );
}
