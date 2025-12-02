"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Download, Clock, AlertCircle, CheckCircle, Eye } from "lucide-react"

interface Decision {
  id: string
  transactionId: string
  timestamp: string
  verdict: "flagged" | "needs_review" | "acceptable"
  riskScore: number
  entityName: string
  amount: number
  reason: string
  appliedPolicies: string[]
}

export function DecisionsPanel() {
  const [searchTerm, setSearchTerm] = useState("")
  const [filterVerdict, setFilterVerdict] = useState<string>("all")
  const [selectedDecision, setSelectedDecision] = useState<Decision | null>(null)

  // Mock data
  const decisions: Decision[] = [
    {
      id: "D001",
      transactionId: "TXN-2024-001",
      timestamp: "2024-01-15 14:32:00",
      verdict: "flagged",
      riskScore: 8.7,
      entityName: "Acme Corp",
      amount: 250000,
      reason: "High-value transaction from high-risk jurisdiction",
      appliedPolicies: ["AML-001", "KYC-003", "SANCTIONS-005"],
    },
    {
      id: "D002",
      transactionId: "TXN-2024-002",
      timestamp: "2024-01-15 13:15:00",
      verdict: "needs_review",
      riskScore: 5.2,
      entityName: "Beta Ltd",
      amount: 75000,
      reason: "Transaction pattern matches suspicious profile",
      appliedPolicies: ["AML-002", "PATTERN-001"],
    },
    {
      id: "D003",
      transactionId: "TXN-2024-003",
      timestamp: "2024-01-15 12:08:00",
      verdict: "acceptable",
      riskScore: 2.1,
      entityName: "Gamma Inc",
      amount: 45000,
      reason: "Low-risk verified entity, standard transaction",
      appliedPolicies: ["KYC-001", "STANDARD-CHECK"],
    },
    {
      id: "D004",
      transactionId: "TXN-2024-004",
      timestamp: "2024-01-15 11:45:00",
      verdict: "flagged",
      riskScore: 9.1,
      entityName: "Unknown Offshore",
      amount: 500000,
      reason: "Unverified offshore entity with large transaction",
      appliedPolicies: ["SANCTIONS-001", "KYC-005", "OFFSHORE-001"],
    },
  ]

  const filteredDecisions = decisions.filter((d) => {
    const matchesSearch =
      d.transactionId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      d.entityName.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesFilter = filterVerdict === "all" || d.verdict === filterVerdict
    return matchesSearch && matchesFilter
  })

  const getVerdictColor = (verdict: string) => {
    switch (verdict) {
      case "flagged":
        return "bg-red-500/20 text-red-700 dark:text-red-400 border-red-300 dark:border-red-600"
      case "needs_review":
        return "bg-amber-500/20 text-amber-700 dark:text-amber-400 border-amber-300 dark:border-amber-600"
      case "acceptable":
        return "bg-green-500/20 text-green-700 dark:text-green-400 border-green-300 dark:border-green-600"
      default:
        return ""
    }
  }

  const getVerdictIcon = (verdict: string) => {
    switch (verdict) {
      case "flagged":
        return <AlertCircle className="w-4 h-4" />
      case "needs_review":
        return <Clock className="w-4 h-4" />
      case "acceptable":
        return <CheckCircle className="w-4 h-4" />
      default:
        return null
    }
  }

  const getRiskColor = (score: number) => {
    if (score >= 8) return "text-red-600 dark:text-red-400 font-bold"
    if (score >= 5) return "text-amber-600 dark:text-amber-400 font-bold"
    return "text-green-600 dark:text-green-400 font-bold"
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground mb-2">Decisions Panel</h1>
        <p className="text-muted-foreground">View and manage all compliance decisions</p>
      </div>

      {/* Controls */}
      <div className="flex gap-4 flex-wrap">
        <Input
          placeholder="Search by Transaction ID or Entity..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="flex-1 min-w-xs bg-background border-accent"
        />
        <select
          value={filterVerdict}
          onChange={(e) => setFilterVerdict(e.target.value)}
          className="px-4 py-2 rounded-lg border border-accent bg-background text-foreground"
        >
          <option value="all">All Verdicts</option>
          <option value="flagged">Flagged</option>
          <option value="needs_review">Needs Review</option>
          <option value="acceptable">Acceptable</option>
        </select>
        <Button className="gap-2 bg-blue-600 hover:bg-blue-700">
          <Download className="w-4 h-4" />
          Export Report
        </Button>
      </div>

      {/* Decisions List */}
      <div className="grid gap-4">
        {filteredDecisions.length === 0 ? (
          <Card className="p-8 text-center text-muted-foreground">No decisions match your search criteria</Card>
        ) : (
          filteredDecisions.map((decision) => (
            <Card
              key={decision.id}
              className="p-4 hover:shadow-lg transition-shadow cursor-pointer border-l-4"
              onClick={() => setSelectedDecision(decision)}
              style={{
                borderLeftColor:
                  decision.verdict === "flagged"
                    ? "rgb(239, 68, 68)"
                    : decision.verdict === "needs_review"
                      ? "rgb(217, 119, 6)"
                      : "rgb(34, 197, 94)",
              }}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <h3 className="font-semibold text-foreground">{decision.transactionId}</h3>
                    <Badge className={`gap-1 ${getVerdictColor(decision.verdict)}`}>
                      {getVerdictIcon(decision.verdict)}
                      {decision.verdict === "flagged"
                        ? "Flagged"
                        : decision.verdict === "needs_review"
                          ? "Review"
                          : "Acceptable"}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mb-3">
                    {decision.entityName} • ${decision.amount.toLocaleString()} • {decision.timestamp}
                  </p>
                  <p className="text-sm text-foreground">{decision.reason}</p>
                  <div className="flex gap-2 mt-3 flex-wrap">
                    {decision.appliedPolicies.map((policy) => (
                      <Badge key={policy} variant="outline" className="text-xs">
                        {policy}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-2xl ${getRiskColor(decision.riskScore)}`}>{decision.riskScore.toFixed(1)}</div>
                  <p className="text-xs text-muted-foreground">Risk Score</p>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-2 gap-1"
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedDecision(decision)
                    }}
                  >
                    <Eye className="w-3 h-3" />
                    View
                  </Button>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>

      {/* Detail View */}
      {selectedDecision && (
        <Card className="p-6 border-2 border-blue-500/50 bg-blue-500/5">
          <h2 className="text-xl font-bold mb-4">Decision Details</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">Transaction ID</p>
              <p className="font-semibold text-foreground">{selectedDecision.transactionId}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Risk Score</p>
              <p className={`font-semibold ${getRiskColor(selectedDecision.riskScore)}`}>
                {selectedDecision.riskScore.toFixed(1)}/10
              </p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Entity</p>
              <p className="font-semibold text-foreground">{selectedDecision.entityName}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Amount</p>
              <p className="font-semibold text-foreground">${selectedDecision.amount.toLocaleString()}</p>
            </div>
            <div className="col-span-2">
              <p className="text-sm text-muted-foreground">Decision Reasoning</p>
              <p className="text-foreground mt-1">{selectedDecision.reason}</p>
            </div>
            <div className="col-span-2">
              <p className="text-sm text-muted-foreground mb-2">Applied Policies</p>
              <div className="flex gap-2 flex-wrap">
                {selectedDecision.appliedPolicies.map((policy) => (
                  <Badge key={policy} className="bg-blue-600 hover:bg-blue-700">
                    {policy}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}
