import Image from "next/image"

export default function BrandLogo({ className = "" }: { className?: string }) {
  return (
    <Image
      src="/zhermai-logo.png"
      alt="ZherMai"
      width={640}
      height={230}
      className={`h-auto ${className}`}
      priority
    />
  )
}
