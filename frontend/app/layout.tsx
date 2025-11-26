// frontend/app/layout.tsx
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'  // This is crucial!

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'SEO Intelligence Platform',
  description: 'AI-Powered SEO Automation Tool',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 min-h-screen`}>
        {children}
      </body>
    </html>
  )
}
