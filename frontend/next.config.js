// frontend/next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://seo-manager-production.up.railway.app'
  },
  // If you need server runtime config, use this syntax:
  serverRuntimeConfig: {
    mySecret: 'secret',
    port: process.env.PORT || 8080
  },
  publicRuntimeConfig: {
    apiUrl: process.env.NEXT_PUBLIC_API_URL || 'https://seo-manager-production.up.railway.app'
  }
}

module.exports = nextConfig
