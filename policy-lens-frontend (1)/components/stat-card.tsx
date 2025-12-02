import { Card } from "@/components/ui/card"
import type { LucideIcon } from "lucide-react"

interface StatCardProps {
  label: string
  value: string
  change: string
  icon: LucideIcon
  color: "primary" | "secondary" | "accent" | "destructive"
}

export function StatCard({ label, value, change, icon: Icon, color }: StatCardProps) {
  const colorClasses = {
    primary: "bg-gradient-to-br from-primary/20 to-primary/10 text-primary",
    secondary: "bg-gradient-to-br from-secondary/20 to-secondary/10 text-secondary",
    accent: "bg-gradient-to-br from-accent/20 to-accent/10 text-accent",
    destructive: "bg-gradient-to-br from-destructive/20 to-destructive/10 text-destructive",
  }

  return (
    <Card className="p-6 bg-gradient-to-br from-card to-card/80 border border-border hover:border-primary/30 transition-all hover:shadow-lg hover:shadow-primary/10">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{label}</p>
          <p className="text-3xl font-bold text-foreground">{value}</p>
          <p
            className={`text-xs font-semibold mt-2 ${color === "primary" ? "text-primary" : color === "secondary" ? "text-secondary" : color === "accent" ? "text-accent" : "text-destructive"}`}
          >
            {change}
          </p>
        </div>
        <div className={`${colorClasses[color]} p-3 rounded-xl`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </Card>
  )
}
