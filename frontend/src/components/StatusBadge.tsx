interface StatusBadgeProps {
  status: string
  label?: string
}

export default function StatusBadge({ status, label }: StatusBadgeProps) {
  const text = label ?? status
  const s = status.toLowerCase()
  if (s === "replied" || s === "completed" || s === "active") {
    return <span className="badge badge-success">{text}</span>
  }
  if (s === "pending" || s === "processing") {
    return <span className="badge badge-warning">{text}</span>
  }
  if (s === "failed" || s === "expired" || s === "revoked") {
    return <span className="badge badge-danger">{text}</span>
  }
  return <span className="badge badge-neutral">{text}</span>
}
