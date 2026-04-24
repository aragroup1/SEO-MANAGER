// frontend/next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://seo-manager-production.up.railway.app'
  },
  serverRuntimeConfig: {
    mySecret: 'secret',
    port: process.env.PORT || 8080
  },
  publicRuntimeConfig: {
    apiUrl: process.env.NEXT_PUBLIC_API_URL || 'https://seo-manager-production.up.railway.app'
  },
  // Performance optimizations
  images: {
    formats: ['image/avif', 'image/webp'],
    minimumCacheTTL: 86400, // 24 hours
    deviceSizes: [640, 750, 828, 1080, 1200, 1920, 2048, 3840],
    imageSizes: [16, 32, 48, 64, 96, 128, 256, 384],
  },
  // Enable SWC minification (already default in Next 14)
  swcMinify: true,
  // Experimental features for performance
  experimental: {
    // Turbopack for faster builds (dev only)
  },
  // Compress responses
  compress: true,
  // Powered by header
  poweredByHeader: false,
}

module.exports = nextConfig
