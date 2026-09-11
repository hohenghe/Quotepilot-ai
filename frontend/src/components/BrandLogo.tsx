import Image from "next/image"

export default function BrandLogo({ className = "" }: { className?: string }) {
  return (
    <Image
      src="/zhermai-logo.png"
      alt="ZherMai"
      width={1536}
      height={1024}
      className={`aspect-[3/1] h-auto object-cover ${className}`}
      priority
    />
  )
}
