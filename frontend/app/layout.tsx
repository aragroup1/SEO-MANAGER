// frontend/app/layout.tsx
import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  display: 'swap', // Prevents FOIT (Flash of Invisible Text)
  variable: '--font-inter',
})

export const metadata: Metadata = {
  title: 'SEO Intelligence Platform',
  description: 'AI-Powered SEO Automation Tool',
}

export const viewport: Viewport = {
  themeColor: '#050505',
  colorScheme: 'dark',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={inter.variable}>
      <head>
        {/* Preconnect to API origin to reduce connection latency */}
        <link rel="preconnect" href={process.env.NEXT_PUBLIC_API_URL || 'https://seo-manager-production.up.railway.app'} />
        {/* DNS prefetch for external services */}
        <link rel="dns-prefetch" href="https://fonts.googleapis.com" />
        <link rel="dns-prefetch" href="https://fonts.gstatic.com" />
      </head>
      <body className={`${inter.className} bg-[#050505] min-h-screen antialiased`}>
        {children}
      </body>
    </html>
  )
}
