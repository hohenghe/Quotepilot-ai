import type { Metadata } from "next"
import { I18nProvider } from "@/i18n/I18nProvider"
import AppLayout from "@/components/AppLayout"
import "./globals.css"

export const metadata: Metadata = {
  title: "QuotePilot AI - Sales Assistant",
  description: "AI-powered sales assistant for international trade",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <I18nProvider>
          <AppLayout>{children}</AppLayout>
        </I18nProvider>
      </body>
    </html>
  )
}
