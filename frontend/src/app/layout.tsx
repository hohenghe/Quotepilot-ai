import type { Metadata } from "next"
import { I18nProvider } from "@/i18n/I18nProvider"
import { ToastProvider } from "@/components/Toast"
import "./globals.css"

export const metadata: Metadata = {
  title: "ZherMai - B2B Sourcing Platform",
  description: "Connect global buyers with trusted Chinese suppliers",
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
          <ToastProvider>{children}</ToastProvider>
        </I18nProvider>
      </body>
    </html>
  )
}
