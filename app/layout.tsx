import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Today on Tech Twitter',
  description: 'Daily insights and analytics from Twitter data.',
  keywords: ['tech news', 'twitter', 'social media', 'technology', 'startups', 'AI', 'daily digest'],
  authors: [{ name: 'Neel Somani' }],
  creator: 'Neel Somani',
  publisher: 'Neel Somani',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  metadataBase: new URL('https://www.todayontechtwitter.com'),
  alternates: {
    canonical: '/',
  },
  openGraph: {
    title: 'Today on Tech Twitter',
    description: 'Daily insights and analytics from Twitter data.',
    url: 'https://www.todayontechtwitter.com',
    siteName: 'Today on Tech Twitter',
    images: [
      {
        url: '/bird-icon.svg',
        width: 512,
        height: 512,
        alt: 'Today on Tech Twitter - Daily Tech News Digest',
      },
    ],
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary',
    title: 'Today on Tech Twitter',
    description: 'Daily insights and analytics from Twitter data.',
    images: ['/bird-icon.svg'],
    creator: '@neelsalami',
},
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  icons: {
    icon: '/favicon.ico',
    shortcut: '/favicon.ico',
    apple: '/favicon.ico',
  },
  manifest: '/manifest.json',
  other: {
    'theme-color': '#1da1f2',
    'color-scheme': 'light dark',
    'apple-mobile-web-app-capable': 'yes',
    'apple-mobile-web-app-status-bar-style': 'default',
    'apple-mobile-web-app-title': 'Today on Tech Twitter',
    'application-name': 'Today on Tech Twitter',
    'msapplication-TileColor': '#1da1f2',
    'msapplication-config': '/browserconfig.xml',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="icon" href="/bird-icon.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/favicon.ico" />
      </head>
      <body>{children}</body>
    </html>
  )
}
