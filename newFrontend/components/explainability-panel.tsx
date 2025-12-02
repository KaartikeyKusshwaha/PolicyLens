"use client"

import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Download, Copy, CheckCircle } from "lucide-react"
import { useState } from "react"

interface ExplainabilityPanelProps {
  verdict: "flagged" | "accepted" | "review"
  riskScore: number
  retrievedRules: Array<{ title: string; text: string; relevance: number }>
  reasoningChain: string
  caseMatches: Array<{ id: string; similarity: number; outcome: string }>
  modelInfo: { version: string; timestamp: string; traceId: string }
}

export function ExplainabilityPanel({
  verdict,
  riskScore,
  retrievedRules,
  reasoningChain,
  caseMatches,
  modelInfo,
}: ExplainabilityPanelProps) {
  const [copied, setCopied] = useState(false)

  const handleCopyTrace = () => {
    navigator.clipboard.writeText(modelInfo.traceId)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const downloadReport = (format: "pdf" | "json") => {
    const report = {
      verdict,
      riskScore,
      retrievedRules,
      reasoningChain,
      caseMatches,
      modelInfo,
      exportedAt: new Date().toISOString(),
    }

    if (format === "json") {
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `audit-report-${modelInfo.traceId}.json`
      a.click()
    } else {
      alert("PDF export would be generated here. For now, use JSON export.")
    }
  }

  return (
    <div className="space-y-4">
      {/* Header with Verdict and Model Info */}
      <Card className="p-6 bg-gradient-to-br from-primary/5 via-transparent to-accent/5 border border-primary/20">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <p className="text-xs text-muted-foreground mb-2">DECISION</p>
            <Badge
              className={`text-sm py-1 px-3 ${
                verdict === "flagged"
                  ? "bg-destructive/20 text-destructive border-destructive/30"
                  : verdict === "accepted"
                    ? "bg-accent/20 text-accent border-accent/30"
                    : "bg-primary/20 text-primary border-primary/30"
              }`}
            >
              {verdict.charAt(0).toUpperCase() + verdict.slice(1)}
            </Badge>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-2">RISK SCORE</p>
            <div className="flex items-center gap-3">
              <span className="text-3xl font-bold text-foreground">{riskScore}%</span>
              <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden max-w-[100px]">
                <div
                  className={`h-full ${riskScore > 60 ? "bg-destructive" : riskScore > 30 ? "bg-primary" : "bg-accent"}`}
                  style={{ width: `${riskScore}%` }}
                />
              </div>
            </div>
          </div>
          <div>
            <p className="text-xs text-muted-foreground mb-2">MODEL INFO</p>
            <div className="space-y-1">
              <p className="text-sm font-mono text-foreground">{modelInfo.version}</p>
              <div className="flex items-center gap-2">
                <code className="text-xs bg-muted px-2 py-1 rounded font-mono text-foreground">
                  {modelInfo.traceId}
                </code>
                <button onClick={handleCopyTrace} className="text-muted-foreground hover:text-foreground transition">
                  {copied ? <CheckCircle className="w-4 h-4 text-accent" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Tabs for Different Views */}
      <Card className="p-6 bg-card border border-border">
        <Tabs defaultValue="summary" className="w-full">
          <TabsList className="grid w-full grid-cols-5 bg-muted/30">
            <TabsTrigger value="summary">Summary</TabsTrigger>
            <TabsTrigger value="rules">Rules</TabsTrigger>
            <TabsTrigger value="cases">Cases</TabsTrigger>
            <TabsTrigger value="reasoning">Reasoning</TabsTrigger>
            <TabsTrigger value="audit">Audit</TabsTrigger>
          </TabsList>

          {/* Summary Tab */}
          <TabsContent value="summary" className="space-y-4 mt-4">
            <div className="p-4 bg-muted/20 border border-border rounded-lg">
              <p className="text-sm text-foreground">
                Transaction analyzed using RAG-based policy retrieval. System found {retrievedRules.length} relevant
                policy rules and {caseMatches.length} similar historical cases. Decision confidence based on policy
                match strength and case similarity patterns.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-primary/5 border border-primary/20 rounded-lg">
                <p className="text-xs text-muted-foreground mb-1">Rules Retrieved</p>
                <p className="text-2xl font-bold text-foreground">{retrievedRules.length}</p>
              </div>
              <div className="p-4 bg-accent/5 border border-accent/20 rounded-lg">
                <p className="text-xs text-muted-foreground mb-1">Avg Rule Match</p>
                <p className="text-2xl font-bold text-foreground">
                  {Math.round((retrievedRules.reduce((sum, r) => sum + r.relevance, 0) / retrievedRules.length) * 100)}%
                </p>
              </div>
            </div>
          </TabsContent>

          {/* Rules Tab */}
          <TabsContent value="rules" className="space-y-3 mt-4">
            {retrievedRules.map((rule, idx) => (
              <div key={idx} className="p-4 border border-border rounded-lg hover:bg-muted/20 transition">
                <div className="flex items-start justify-between mb-2">
                  <h4 className="font-medium text-foreground text-sm">{rule.title}</h4>
                  <Badge variant="outline" className="text-xs bg-primary/10 text-primary border-primary/20">
                    {Math.round(rule.relevance * 100)}% match
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">{rule.text}</p>
              </div>
            ))}
          </TabsContent>

          {/* Cases Tab */}
          <TabsContent value="cases" className="space-y-3 mt-4">
            {caseMatches.map((caseItem, idx) => (
              <div key={idx} className="p-4 border border-border rounded-lg hover:bg-muted/20 transition">
                <div className="flex items-start justify-between mb-2">
                  <p className="font-mono text-sm font-semibold text-foreground">{caseItem.id}</p>
                  <Badge variant="outline" className="text-xs bg-accent/10 text-accent border-accent/20">
                    {Math.round(caseItem.similarity * 100)}% similar
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">{caseItem.outcome}</p>
              </div>
            ))}
          </TabsContent>

          {/* Reasoning Tab */}
          <TabsContent value="reasoning" className="mt-4">
            <div className="p-4 bg-muted/20 border border-border rounded-lg font-mono text-sm text-foreground whitespace-pre-wrap">
              {reasoningChain}
            </div>
          </TabsContent>

          {/* Audit Tab */}
          <TabsContent value="audit" className="space-y-4 mt-4">
            <div className="p-4 bg-muted/20 border border-border rounded-lg">
              <h4 className="font-semibold text-foreground mb-3">Export Audit Report</h4>
              <div className="flex gap-3">
                <Button
                  onClick={() => downloadReport("json")}
                  className="flex-1 bg-primary/10 text-primary hover:bg-primary/20 border border-primary/30"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export as JSON
                </Button>
                <Button
                  onClick={() => downloadReport("pdf")}
                  className="flex-1 bg-accent/10 text-accent hover:bg-accent/20 border border-accent/30"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export as PDF
                </Button>
              </div>
              <div className="mt-4 space-y-2 text-xs text-muted-foreground">
                <p>Report includes:</p>
                <ul className="list-disc list-inside space-y-1">
                  <li>Verdict and risk score</li>
                  <li>All retrieved policy rules with citations</li>
                  <li>Similar case references</li>
                  <li>Complete reasoning chain</li>
                  <li>Model version and trace ID for reproducibility</li>
                  <li>Timestamp and audit trail</li>
                </ul>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </Card>
    </div>
  )
}
