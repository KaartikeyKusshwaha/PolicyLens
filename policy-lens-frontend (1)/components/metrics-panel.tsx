"use client"

import { AlertCircle, CheckCircle, Clock, Activity } from "lucide-react"

export function MetricsPanel() {
  const metrics = [
    {
      label: "Transactions Analyzed",
      value: "2,847",
      change: "+12.5%",
      positive: true,
      icon: Activity,
      color: "from-blue-500 to-cyan-500",
    },
    {
      label: "Flagged Cases",
      value: "23",
      change: "-2.3%",
      positive: true,
      icon: AlertCircle,
      color: "from-orange-500 to-red-500",
    },
    {
      label: "Compliance Score",
      value: "94.2%",
      change: "+3.1%",
      positive: true,
      icon: CheckCircle,
      color: "from-green-500 to-emerald-500",
    },
    {
      label: "Avg Review Time",
      value: "2.3s",
      change: "-15.8%",
      positive: true,
      icon: Clock,
      color: "from-purple-500 to-pink-500",
    },
  ]

  return (
    <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide">
      {metrics.map((metric, idx) => {
        const Icon = metric.icon
        return (
          <div
            key={idx}
            className="flex-shrink-0 min-w-max px-4 py-3 rounded-lg border border-border bg-card/50 hover:bg-card transition-colors"
          >
            <div className="flex items-center gap-3">
              <div
                className={`w-10 h-10 rounded-lg bg-gradient-to-br ${metric.color} flex items-center justify-center shadow-lg`}
              >
                <Icon className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground">{metric.label}</p>
                <div className="flex items-baseline gap-2">
                  <span className="text-lg font-bold text-foreground">{metric.value}</span>
                  <span
                    className={`text-xs font-medium ${metric.positive ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
                  >
                    {metric.change}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}
