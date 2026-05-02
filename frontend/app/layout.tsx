// frontend/app/layout.tsx
import type { Metadata, Viewport } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import './globals.css'

const sans = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-sans',
})

const mono = JetBrains_Mono({
  subsets: ['latin'],
  display: 'swap',
  weight: ['500', '700'],
  variable: '--font-mono',
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
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <head>
        <link rel="preconnect" href={process.env.NEXT_PUBLIC_API_URL || 'https://seo-manager-production.up.railway.app'} />
        <link rel="dns-prefetch" href="https://fonts.googleapis.com" />
        <link rel="dns-prefetch" href="https://fonts.gstatic.com" />
      </head>
      <body className={`${sans.className} bg-[#050505] min-h-screen antialiased`}>
        {children}
      </body>
    </html>
  )
}
