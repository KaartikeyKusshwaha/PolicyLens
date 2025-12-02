"use client"

import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { RefreshCw } from "lucide-react"

interface PolicyVersion {
  version: string
  date: string
  status: "active" | "deprecated"
  changes: string[]
}

interface PolicyDetailProps {
  policyId: string
  policyName: string
  category: string
  source: string
  coverage: number
  versions: PolicyVersion[]
  onReEvaluate?: () => void
}

export function PolicyDetailView({
  policyId,
  policyName,
  category,
  source,
  coverage,
  versions,
  onReEvaluate,
}: PolicyDetailProps) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <Card className="p-6 bg-gradient-to-br from-primary/5 to-accent/5 border border-primary/20">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs text-muted-foreground mb-2">POLICY ID</p>
            <h2 className="text-2xl font-bold text-foreground mb-2">{policyName}</h2>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="outline" className="text-xs">
                {category}
              </Badge>
              <span className="text-xs text-muted-foreground">•</span>
              <span className="text-xs text-muted-foreground">Source: {source}</span>
              <span className="text-xs text-muted-foreground">•</span>
              <span className="text-xs text-muted-foreground">ID: {policyId}</span>
            </div>
          </div>
          <div className="text-right">
            <p className="text-xs text-muted-foreground mb-1">Coverage</p>
            <div className="flex items-center gap-2">
              <div className="w-20 h-2 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-accent" style={{ width: `${coverage}%` }} />
              </div>
              <span className="text-sm font-semibold text-foreground">{coverage}%</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Version History & Diff */}
      <Card className="p-6 bg-card border border-border">
        <Tabs defaultValue="versions" className="w-full">
          <TabsList className="grid w-full grid-cols-3 bg-muted/30">
            <TabsTrigger value="versions">Version History</TabsTrigger>
            <TabsTrigger value="diff">Recent Changes</TabsTrigger>
            <TabsTrigger value="impact">Impact</TabsTrigger>
          </TabsList>

          {/* Version History */}
          <TabsContent value="versions" className="space-y-3 mt-4">
            {versions.map((v, idx) => (
              <div key={idx} className="p-4 border border-border rounded-lg hover:bg-muted/20 transition">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <p className="font-mono text-sm font-semibold text-foreground">v{v.version}</p>
                    <p className="text-xs text-muted-foreground mt-1">{v.date}</p>
                  </div>
                  <Badge
                    className={v.status === "active" ? "bg-accent/20 text-accent" : "bg-muted/20 text-muted-foreground"}
                  >
                    {v.status === "active" ? "Active" : "Deprecated"}
                  </Badge>
                </div>
              </div>
            ))}
          </TabsContent>

          {/* Changes */}
          <TabsContent value="diff" className="space-y-3 mt-4">
            <div className="p-4 bg-muted/20 border border-border rounded-lg">
              <p className="text-sm font-medium text-foreground mb-3">Changes from v6.1 to v6.2:</p>
              <div className="space-y-2">
                <div className="flex items-start gap-3">
                  <span className="text-xs font-bold text-accent mt-0.5">+</span>
                  <p className="text-sm text-foreground">
                    Increased daily transaction limit from $500K to $750K for verified entities
                  </p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="text-xs font-bold text-destructive mt-0.5">-</span>
                  <p className="text-sm text-foreground">Removed exemption for charitable organizations in FATF list</p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="text-xs font-bold text-primary mt-0.5">~</span>
                  <p className="text-sm text-foreground">Modified KYC requirements for high-risk jurisdictions</p>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Impact */}
          <TabsContent value="impact" className="space-y-4 mt-4">
            <div className="p-4 bg-destructive/5 border border-destructive/20 rounded-lg">
              <p className="text-sm font-medium text-foreground mb-2">Impacted Transactions</p>
              <p className="text-2xl font-bold text-foreground">47</p>
              <p className="text-xs text-muted-foreground mt-1">transactions need re-evaluation with new policy</p>
            </div>
            <Button
              onClick={onReEvaluate}
              className="w-full gap-2 bg-primary/10 text-primary hover:bg-primary/20 border border-primary/30"
            >
              <RefreshCw className="w-4 h-4" />
              Re-evaluate Impacted Transactions
            </Button>
          </TabsContent>
        </Tabs>
      </Card>
    </div>
  )
}
