// frontend/components/IntegrationsModal.tsx
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { X, Check, Loader } from 'lucide-react';

export default function IntegrationsModal({ onClose }: { onClose: () => void }) {
  const [connecting, setConnecting] = useState<string | null>(null);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        className="bg-gradient-to-br from-gray-900 to-purple-900 rounded-2xl p-6 max-w-2xl w-full border border-white/20"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-white">Integrations</h2>
          <button onClick={onClose} className="text-white hover:text-gray-300">
            <X className="w-6 h-6" />
          </button>
        </div>
        <p className="text-purple-300">Connect your services to unlock full potential.</p>
      </motion.div>
    </motion.div>
  );
}
