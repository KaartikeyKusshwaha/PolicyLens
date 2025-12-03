"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Search, Filter, ChevronUp, ChevronDown } from "lucide-react"

interface Case {
  id: string
  date: string
  sender: string
  receiver: string
  amount: string
  reason: string
  decision: "accepted" | "flagged" | "review"
  riskScore: number
  riskFactors: string[]
  similarity?: number
}

const cases: Case[] = [
  {
    id: "CASE-892",
    date: "2 days ago",
    sender: "Offshore Holdings",
    receiver: "International Trade",
    amount: "$850,000",
    reason: "Sanctions list match - High-risk jurisdiction",
    decision: "flagged",
    riskScore: 92,
    riskFactors: ["High-risk jurisdiction", "Large amount", "Sanctions match"],
    similarity: 92,
  },
  {
    id: "CASE-845",
    date: "5 days ago",
    sender: "Tech Innovations Ltd",
    receiver: "Global Ventures",
    amount: "$295,750",
    reason: "Unusual transaction pattern - Manual review recommended",
    decision: "review",
    riskScore: 58,
    riskFactors: ["Unusual pattern", "New entity", "Multi-hop transfer"],
    similarity: 87,
  },
  {
    id: "CASE-812",
    date: "1 week ago",
    sender: "Local Business Inc",
    receiver: "Partner Corp",
    amount: "$125,500",
    reason: "Pattern matches known low-risk profile",
    decision: "accepted",
    riskScore: 15,
    riskFactors: ["Recurring transaction", "Known entities", "Standard amount"],
    similarity: 45,
  },
]

const decisionVariants = {
  accepted: "bg-accent/10 text-accent border-accent/20",
  flagged: "bg-destructive/10 text-destructive border-destructive/20",
  review: "bg-primary/10 text-primary border-primary/20",
}

export function CaseHistory() {
  const [searchTerm, setSearchTerm] = useState("")
  const [filterRisk, setFilterRisk] = useState<string | null>(null)
  const [filterDecision, setFilterDecision] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<"date" | "risk" | "similarity">("date")
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc")

  const filteredCases = cases
    .filter((c) => {
      const matchesSearch =
        searchTerm === "" ||
        c.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.sender.toLowerCase().includes(searchTerm.toLowerCase()) ||
        c.receiver.toLowerCase().includes(searchTerm.toLowerCase())

      const matchesRisk =
        !filterRisk ||
        (filterRisk === "high" && c.riskScore > 60) ||
        (filterRisk === "medium" && c.riskScore >= 30 && c.riskScore <= 60) ||
        (filterRisk === "low" && c.riskScore < 30)

      const matchesDecision = !filterDecision || c.decision === filterDecision

      return matchesSearch && matchesRisk && matchesDecision
    })
    .sort((a, b) => {
      let compareValue = 0
      if (sortBy === "date") {
        compareValue = new Date(a.date).getTime() - new Date(b.date).getTime()
      } else if (sortBy === "risk") {
        compareValue = a.riskScore - b.riskScore
      } else if (sortBy === "similarity") {
        compareValue = (a.similarity || 0) - (b.similarity || 0)
      }
      return sortOrder === "asc" ? compareValue : -compareValue
    })

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-balance">Case History & Search</h1>
        <p className="text-muted-foreground mt-1">Review historical compliance decisions and similar cases</p>
      </div>

      <div className="space-y-4">
        <div className="relative">
          <Search className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search by case ID, sender, or receiver..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10 h-10 bg-input border border-border rounded-lg text-foreground"
          />
        </div>

        {/* Filter & Sort Controls */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <p className="text-xs text-muted-foreground mb-2">Risk Level</p>
            <div className="flex gap-2">
              {["low", "medium", "high"].map((risk) => (
                <Button
                  key={risk}
                  size="sm"
                  variant={filterRisk === risk ? "default" : "outline"}
                  className="text-xs"
                  onClick={() => setFilterRisk(filterRisk === risk ? null : risk)}
                >
                  {risk.charAt(0).toUpperCase() + risk.slice(1)}
                </Button>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs text-muted-foreground mb-2">Decision</p>
            <div className="flex gap-2">
              {["flagged", "review", "accepted"].map((decision) => (
                <Button
                  key={decision}
                  size="sm"
                  variant={filterDecision === decision ? "default" : "outline"}
                  className="text-xs"
                  onClick={() => setFilterDecision(filterDecision === decision ? null : decision)}
                >
                  {decision === "flagged" ? "Flag" : decision === "review" ? "Review" : "Accept"}
                </Button>
              ))}
            </div>
          </div>

          <div className="md:col-span-2">
            <p className="text-xs text-muted-foreground mb-2">Sort By</p>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="w-full px-3 py-1.5 bg-input border border-border rounded-lg text-foreground text-xs"
            >
              <option value="date">Date</option>
              <option value="risk">Risk Score</option>
              <option value="similarity">Similarity</option>
            </select>
          </div>

          <div className="flex items-end">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setSortOrder(sortOrder === "asc" ? "desc" : "asc")}
              className="w-full gap-2"
            >
              {sortOrder === "asc" ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              {sortOrder === "asc" ? "Ascending" : "Descending"}
            </Button>
          </div>
        </div>
      </div>

      {/* Cases Grid */}
      <div className="space-y-4">
        {filteredCases.length === 0 ? (
          <Card className="p-12 bg-card border border-border text-center">
            <Filter className="w-12 h-12 text-muted-foreground mx-auto mb-4 opacity-50" />
            <p className="text-muted-foreground font-medium">No cases found</p>
            <p className="text-xs text-muted-foreground mt-1">Try adjusting your filters or search terms</p>
          </Card>
        ) : (
          filteredCases.map((caseItem) => (
            <Card
              key={caseItem.id}
              className="p-6 bg-card border border-border hover:border-primary/50 transition cursor-pointer hover:bg-primary/5"
            >
              <div className="grid grid-cols-1 md:grid-cols-6 gap-4 mb-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Case ID</p>
                  <p className="font-mono text-sm font-semibold text-foreground">{caseItem.id}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">From → To</p>
                  <p className="text-sm text-foreground">
                    {caseItem.sender.split(" ")[0]} → {caseItem.receiver.split(" ")[0]}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Amount</p>
                  <p className="text-sm font-semibold text-foreground">{caseItem.amount}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Risk Score</p>
                  <p className="text-sm font-semibold text-foreground">{caseItem.riskScore}%</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Similarity</p>
                  <p className="text-sm font-semibold text-accent">{caseItem.similarity}%</p>
                </div>
                <div className="flex justify-end">
                  <Badge className={decisionVariants[caseItem.decision]}>
                    {caseItem.decision.charAt(0).toUpperCase() + caseItem.decision.slice(1)}
                  </Badge>
                </div>
              </div>

              <div className="pt-4 border-t border-border">
                <p className="text-sm text-muted-foreground mb-3">{caseItem.reason}</p>
                <div className="flex flex-wrap gap-2">
                  {caseItem.riskFactors.map((factor, idx) => (
                    <Badge key={idx} variant="outline" className="text-xs bg-muted/30 border-border">
                      {factor}
                    </Badge>
                  ))}
                </div>
              </div>

              <p className="text-xs text-muted-foreground mt-4">{caseItem.date}</p>
            </Card>
          ))
        )}
      </div>
    </div>
  )
}
