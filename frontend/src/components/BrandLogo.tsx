import Image from "next/image"
import { usePathname } from "next/navigation"

export default function BrandLogo({ className = "" }: { className?: string }) {
  const pathname = usePathname()
  const seller = pathname?.startsWith("/seller")

  return (
    <Image
      src={seller ? "/zhermai-seller-logo.svg" : "/zhermai-logo.png"}
      alt="这儿卖 zhermai.com"
      width={seller ? 360 : 1536}
      height={seller ? 116 : 1024}
      className={seller ? `h-auto object-contain ${className}` : `aspect-[3/1] h-auto object-cover ${className}`}
      priority
    />
  )
}
