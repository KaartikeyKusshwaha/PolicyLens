"use client"

import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { FileText, Calendar, AlertCircle } from "lucide-react"

interface Policy {
  id: string
  name: string
  category: string
  lastUpdated: string
  status: "active" | "updating" | "deprecated"
  coverage: number
  source: string
}

const policies: Policy[] = [
  {
    id: "AML-001",
    name: "Anti-Money Laundering Framework",
    category: "AML",
    lastUpdated: "2 hours ago",
    status: "active",
    coverage: 100,
    source: "RBI Circular",
  },
  {
    id: "KYC-002",
    name: "Know Your Customer Requirements",
    category: "KYC",
    lastUpdated: "1 day ago",
    status: "active",
    coverage: 98,
    source: "Internal Policy",
  },
  {
    id: "SANCTIONS-003",
    name: "Sanctions & Watchlist Compliance",
    category: "Sanctions",
    lastUpdated: "1 hour ago",
    status: "updating",
    coverage: 95,
    source: "OFAC API",
  },
  {
    id: "EU-004",
    name: "EU AML Directive v6.2",
    category: "AML",
    lastUpdated: "3 days ago",
    status: "active",
    coverage: 100,
    source: "EU Regulations",
  },
  {
    id: "FATF-005",
    name: "FATF High-Risk Countries List",
    category: "Risk",
    lastUpdated: "12 hours ago",
    status: "active",
    coverage: 100,
    source: "FATF",
  },
]

const statusVariants = {
  active: "bg-accent/10 text-accent border-accent/20",
  updating: "bg-primary/10 text-primary border-primary/20",
  deprecated: "bg-muted/10 text-muted-foreground border-muted/20",
}

export function PolicyManagement() {
  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-balance">Policy Management</h1>
        <p className="text-muted-foreground mt-1">Monitor and manage compliance policies and regulations</p>
      </div>

      {/* Update Notice */}
      <div className="flex items-start gap-3 p-4 bg-primary/5 border border-primary/20 rounded-lg">
        <AlertCircle className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-foreground text-sm">Policy Update in Progress</p>
          <p className="text-xs text-muted-foreground mt-1">
            Sanctions list is being updated. 2 transactions are being re-evaluated.
          </p>
        </div>
      </div>

      {/* Policies Grid */}
      <div className="grid grid-cols-1 gap-4">
        {policies.map((policy) => (
          <Card key={policy.id} className="p-6 bg-card border border-border hover:border-primary/50 transition">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-start gap-4 flex-1">
                <div className="p-3 bg-primary/10 rounded-lg flex-shrink-0">
                  <FileText className="w-5 h-5 text-primary" />
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-foreground mb-1">{policy.name}</h3>
                  <p className="text-sm text-muted-foreground mb-3">{policy.source}</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <Badge variant="outline" className="text-xs">
                      {policy.category}
                    </Badge>
                    <span className="text-xs text-muted-foreground">•</span>
                    <span className="text-xs text-muted-foreground">ID: {policy.id}</span>
                    <span className="text-xs text-muted-foreground">•</span>
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      {policy.lastUpdated}
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex flex-col items-end gap-3">
                <Badge className={statusVariants[policy.status]}>
                  {policy.status.charAt(0).toUpperCase() + policy.status.slice(1)}
                </Badge>
                <div className="text-right">
                  <p className="text-xs text-muted-foreground mb-1">Coverage</p>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div className="h-full bg-accent" style={{ width: `${policy.coverage}%` }} />
                    </div>
                    <span className="text-xs font-semibold text-foreground">{policy.coverage}%</span>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
