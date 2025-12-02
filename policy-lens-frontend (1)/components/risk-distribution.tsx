"use client"

import { Card } from "@/components/ui/card"
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts"

const data = [
  { name: "Accepted", value: 2824, color: "oklch(0.65 0.25 150)" },
  { name: "Review", value: 12, color: "oklch(0.55 0.31 264)" },
  { name: "Flagged", value: 23, color: "oklch(0.65 0.25 27)" },
]

export function RiskDistribution() {
  return (
    <Card className="p-6 bg-card border border-border">
      <h3 className="font-semibold text-foreground mb-4">Transaction Status</h3>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} cx="50%" cy="50%" innerRadius={45} outerRadius={75} paddingAngle={2} dataKey="value">
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 space-y-2">
        {data.map((item, idx) => (
          <div key={idx} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
              <span className="text-muted-foreground">{item.name}</span>
            </div>
            <span className="font-semibold text-foreground">{item.value}</span>
          </div>
        ))}
      </div>
    </Card>
  )
}
