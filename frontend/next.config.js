/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'https://seo-manager-production.up.railway.app'
  },
  // Allow Railway's dynamic port
  serverRuntimeConfig: {
    port: process.env.PORT || 8080
  }
}

module.exports = nextConfig
```

### 3. Set Environment Variables in Railway Frontend Service
In your Railway dashboard for the frontend service:
```
PORT=8080
NEXT_PUBLIC_API_URL=https://seo-manager-production.up.railway.app
