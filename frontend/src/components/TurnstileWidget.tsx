"use client"

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react"
import Script from "next/script"

export const turnstileEnabled = Boolean(process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY)

type TurnstileApi = {
  render: (container: HTMLElement, options: Record<string, unknown>) => string
  reset: (widgetId: string) => void
  remove: (widgetId: string) => void
}

declare global {
  interface Window { turnstile?: TurnstileApi }
}

export type TurnstileHandle = { reset: () => void }

type Props = {
  action: string
  onTokenChange: (token: string | null) => void
  errorMessage: string
}

const TurnstileWidget = forwardRef<TurnstileHandle, Props>(function TurnstileWidget(
  { action, onTokenChange, errorMessage }, ref,
) {
  const containerRef = useRef<HTMLDivElement>(null)
  const widgetIdRef = useRef<string | null>(null)
  const onTokenRef = useRef(onTokenChange)
  const [scriptReady, setScriptReady] = useState(false)
  const [scriptFailed, setScriptFailed] = useState(false)
  onTokenRef.current = onTokenChange

  useImperativeHandle(ref, () => ({
    reset() {
      onTokenRef.current(null)
      if (widgetIdRef.current) window.turnstile?.reset(widgetIdRef.current)
    },
  }), [])

  useEffect(() => {
    if (!turnstileEnabled || !scriptReady || !containerRef.current || !window.turnstile) return
    const id = window.turnstile.render(containerRef.current, {
      sitekey: process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY,
      action,
      theme: "auto",
      callback: (token: string) => {
        setScriptFailed(false)
        onTokenRef.current(token)
      },
      "expired-callback": () => {
        onTokenRef.current(null)
        if (widgetIdRef.current) window.turnstile?.reset(widgetIdRef.current)
      },
      "error-callback": () => {
        onTokenRef.current(null)
        setScriptFailed(true)
      },
    })
    widgetIdRef.current = id
    return () => {
      window.turnstile?.remove(id)
      widgetIdRef.current = null
      onTokenRef.current(null)
    }
  }, [action, scriptReady])

  if (!turnstileEnabled) return null
  return (
    <div className="my-4">
      <Script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
        strategy="afterInteractive" onReady={() => setScriptReady(true)}
        onError={() => setScriptFailed(true)} />
      <div ref={containerRef} />
      {scriptFailed && <p className="mt-2 text-sm text-red-600">{errorMessage}</p>}
    </div>
  )
})

export default TurnstileWidget
