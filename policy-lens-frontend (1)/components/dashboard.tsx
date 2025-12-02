"use client"

import { AlertCircle, TrendingUp, CheckCircle, Clock, Zap } from "lucide-react"
import { Card } from "@/components/ui/card"
import { StatCard } from "@/components/stat-card"
import { TransactionTable } from "@/components/transaction-table"
import { RiskDistribution } from "@/components/risk-distribution"

export function Dashboard() {
  return (
    <div className="p-8 space-y-8 bg-background">
      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-center gap-3">
          <div className="w-2 h-8 bg-gradient-to-b from-primary to-accent rounded-full" />
          <h1 className="text-4xl font-bold text-foreground">Compliance Dashboard</h1>
        </div>
        <p className="text-muted-foreground ml-5">Real-time transaction monitoring and intelligent policy analysis</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Transactions Analyzed" value="2,847" change="+12%" icon={TrendingUp} color="primary" />
        <StatCard label="Flagged for Review" value="23" change="+3" icon={AlertCircle} color="destructive" />
        <StatCard label="Accepted" value="2,824" change="+98.2%" icon={CheckCircle} color="accent" />
        <StatCard label="Pending Review" value="12" change="-2" icon={Clock} color="secondary" />
      </div>

      <Card className="p-4 bg-gradient-to-r from-accent/10 via-primary/5 to-accent/10 border border-accent/20">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-accent animate-pulse" />
          <div>
            <p className="text-sm font-semibold text-foreground">System Status</p>
            <p className="text-xs text-muted-foreground">All systems operational • Last sync 2 minutes ago</p>
          </div>
          <div className="ml-auto text-xs text-accent font-semibold">LIVE</div>
        </div>
      </Card>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Transactions */}
        <div className="lg:col-span-2">
          <TransactionTable />
        </div>

        {/* Risk Distribution */}
        <div>
          <RiskDistribution />
        </div>
      </div>

      {/* Policy Updates */}
      <Card className="p-6 border border-border bg-gradient-to-br from-card via-card to-card/90 backdrop-blur-sm">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-accent" />
            <h3 className="font-semibold text-lg text-foreground">Policy Updates</h3>
          </div>
          <span className="text-xs bg-accent text-accent-foreground px-3 py-1 rounded-full font-semibold">New</span>
        </div>
        <div className="space-y-3">
          <div className="flex items-start gap-3 p-4 bg-gradient-to-r from-primary/10 to-accent/10 rounded-xl border border-primary/20 hover:border-primary/40 transition-all">
            <div className="w-2 h-2 rounded-full bg-primary mt-2 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-foreground">RBI AML Circular Updated</p>
              <p className="text-xs text-muted-foreground mt-1">2 hours ago - Transaction threshold adjusted</p>
            </div>
          </div>
          <div className="flex items-start gap-3 p-4 bg-gradient-to-r from-secondary/10 to-accent/5 rounded-xl border border-secondary/20 hover:border-secondary/40 transition-all">
            <div className="w-2 h-2 rounded-full bg-secondary mt-2 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-foreground">EU AML Directive v6.2</p>
              <p className="text-xs text-muted-foreground mt-1">Yesterday - New sanctions check implemented</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}
