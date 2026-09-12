"use client"

import { useState } from "react"
import { BookOpen, ArrowRight, Search } from "lucide-react"
import { useT } from "@/i18n/I18nProvider"

const chapters = [
  ["账号与店铺", "Account & store", "注册时填写公司名、省市地区、手机号，并选择是否支持铺货。邮箱注册后需完成验证再登录。个人资料可维护店铺名、头像与营业执照；忘记密码请使用登录页的找回密码入口。", "Register with your company, region, phone and distribution preference, then verify your email. In Profile, maintain your store name, avatar and business licence. Use password recovery on the login page if needed."],
  ["工作台概览", "Your workspace", "概览汇总商品、询盘、待回复及已回复数据。先完善店铺资料，再添加商品，最后通过询盘跟进买家。导航栏可以随时切换功能，不必重复登录。", "Start with your store profile, add products, then follow up on buyer inquiries. Overview brings your product and inquiry activity together. Use the sidebar to switch between tasks."],
  ["新增与编辑商品", "Create & edit products", "进入商品管理，选择新增商品。填写名称、SKU、分类、规格、认证、价格、起订量和交期，最多添加 10 张图片。保存前核对数字与单位，点击已有商品的编辑按钮可更新资料。批量删除前请仔细核对所选商品。", "In Products, choose Add product. Enter name, SKU, category, specifications, certifications, pricing, MOQ and lead time, with up to 10 images. Check numbers and units before saving. Use Edit to update a product and check your selection before bulk deletion."],
  ["拍照识别参数", "Photo recognition", "在商品表单中上传清晰的铭牌、包装或参数表照片。OCR 与视觉模型会整理建议字段并保留原语言。避免反光、模糊和文字缺失。AI 识别可能出错，需确认规格、单位、认证等再保存；识别本身不会发布商品。", "Use a clear photo of the label, packaging or specification sheet in the product form. OCR and vision produce suggested fields in the source language. Avoid glare and blurred text. Review every value before saving; recognition does not publish a product."],
  ["批量导入资料", "Import a catalog", "商品管理支持 CSV、XLSX、DOCX 和 PDF 文件。按商品整理清楚名称、规格与报价，上传后检查导入结果。商品搜索索引在后台处理，刚上传的资料可能需要稍后才能匹配到。失败时检查格式并按提示重试。", "Import CSV, XLSX, DOCX or PDF catalogs from Products. Keep names, specifications and prices clearly grouped per product. Check the import result. Search indexing runs in the background, so newly uploaded products may not match immediately."],
  ["询盘与 AI 回复", "Inquiries & AI replies", "买家发送询盘后，在询盘管理查看采购需求、关联商品和联系信息。生成 AI 回复后核对报价、运输和交期，再复制到双方约定的沟通渠道。生成或复制回复不等于已经发送邮件。", "Open Inquiries to review buyer requirements, related products and contact details. Generate a reply draft, check pricing, shipping and lead time, then copy it into your agreed communication channel. Generating or copying a draft does not send an email."],
  ["评价与账户维护", "Reviews & account care", "评价页展示买家反馈和店铺评分，不当内容可举报。个人资料可更新公司与店铺信息，主手机号暂不能直接修改。使用公共设备后请退出登录。本教程可随时从导航栏或个人资料再次打开。", "Review buyer feedback and your store score in Reviews, and report inappropriate content. Maintain company information in Profile; primary phone changes are not currently supported. Sign out on shared devices. Reopen this guide from the sidebar or Profile."],
  ["买家如何使用", "How buyers use ZherMai", "买家在 zhermai.com/buyer 的发现页输入采购需求，建议包括数量、规格、认证、目的地和交期。系统展示匹配商品与供应商，买家可以调整需求继续搜索。收藏、查看评价及发送询盘需要买家登录。发送询盘后可在我的询盘查看记录，卖家在自己的询盘页跟进。交易价格和履约条款需双方确认。", "Buyers enter requirements at zhermai.com/buyer, including quantity, specifications, certifications, destination and lead time. Matching products and suppliers appear, and buyers can refine their search. Saving products, viewing reviews and sending inquiries require buyer sign-in. Buyers track requests in My inquiries; sellers follow up in their own inbox. Both parties must confirm commercial terms."],
  ["常见问题", "Troubleshooting", "收不到邮件：检查垃圾邮件并使用重发验证邮件。识别错误：换清晰原图或手动补充。导入失败：核对文件格式和大小。网络错误：稍后重试，确认当前账号角色正确。AI 内容只是建议，不能代替实际报价与认证核验。", "Missing email? Check spam and resend verification. Recognition errors? Try a clearer image or enter fields manually. Import errors? Check format and size. Network errors? Retry and check your account role. AI suggestions do not replace actual quotes or certification checks."],
]

export default function SellerTutorial({ onClose }: { onClose: () => void }) {
  const { locale } = useT()
  const zh = locale.startsWith("zh")
  const [query, setQuery] = useState("")
  const filtered = chapters.filter(c => c.join(" ").toLowerCase().includes(query.toLowerCase().trim()))
  return (
    <section aria-label={zh ? "使用教程" : "Getting started"}>
      <header className="card p-5 md:p-6 mb-5 bg-gradient-to-br from-brand-50 to-white">
        <div className="flex flex-wrap justify-between items-start gap-4">
          <div><div className="flex items-center gap-2 text-sm text-brand-700 font-medium"><BookOpen className="w-4 h-4" />{zh ? "卖家学习中心" : "Seller learning center"}</div>
            <h1 className="mt-2 text-2xl font-semibold">{zh ? "从商品上架，到第一封询盘" : "From your first product to your first inquiry"}</h1>
            <p className="mt-2 text-sm text-slate-600">{zh ? "按需展开章节，随时退出；之后可在个人资料中再次查看。" : "Explore chapters at your own pace. Skip now and return from Profile anytime."}</p></div>
          <button className="btn-secondary" onClick={onClose}>{zh ? "跳过 / 返回工作台" : "Skip / Back to workspace"}<ArrowRight className="w-4 h-4" /></button>
        </div>
        <div className="mt-5 relative max-w-lg"><Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" /><input className="input pl-9" aria-label={zh ? "搜索教程" : "Search guide"} placeholder={zh ? "搜索商品、拍照、买家、询盘…" : "Search products, photos, buyers, inquiries…"} value={query} onChange={e => setQuery(e.target.value)} /></div>
      </header>
      <div className="grid md:grid-cols-2 gap-3 items-start">
        {filtered.map(c => <details className="card p-4 group" key={c[1]} open={query.trim() ? true : undefined}>
          <summary className="cursor-pointer font-medium text-slate-800 leading-6">{zh ? c[0] : c[1]}</summary>
          <p className="mt-3 text-sm text-slate-600 leading-7">{zh ? c[2] : c[3]}</p>
        </details>)}
      </div>
      {filtered.length === 0 && <p role="status" className="p-6 text-sm text-slate-500">{zh ? "没有找到相关章节，请换个关键词。" : "No matching chapters. Try another keyword."}</p>}
      <button className="btn-primary mt-5" onClick={onClose}>{zh ? "我了解了，开始使用" : "Ready — open my workspace"}</button>
    </section>
  )
}
