"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { AlertCircle, CheckCircle, Search, Loader2 } from "lucide-react"
import { ExplainabilityPanel } from "@/components/explainability-panel"
import { HumanFeedbackDialog } from "@/components/human-feedback-dialog"

export function TransactionAnalysis() {
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [feedbackOpen, setFeedbackOpen] = useState(false)

  const handleAnalyze = () => {
    setIsAnalyzing(true)
    setTimeout(() => {
      setIsAnalyzing(false)
      setResult({
        decision: "flagged",
        riskScore: 78,
        reason: "Transaction amount exceeds threshold and sender lacks transaction history",
        policies: [
          { title: "AML Policy Section 3.2", citation: "Daily transaction limit of $500K for new entities" },
          { title: "KYC Rule 2.1", citation: "Enhanced due diligence required for high-risk jurisdictions" },
        ],
        caseMatches: [
          { id: "CASE-892", similarity: 0.92, outcome: "Flagged - Sanctions list match" },
          { id: "CASE-845", similarity: 0.87, outcome: "Requires review - Unusual pattern" },
        ],
        reasoning: [
          "Step 1: Check transaction amount against thresholds",
          "Step 2: Verify sender's transaction history",
          "Step 3: Match against sanctions lists",
          "Step 4: Evaluate jurisdiction risk",
        ],
        timestamp: new Date().toLocaleTimeString(),
      })
    }, 2000)
  }

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-balance">Transaction Analysis</h1>
        <p className="text-muted-foreground mt-1">Analyze transactions against policies in real-time</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Input Section */}
        <div className="lg:col-span-1 space-y-4">
          <Card className="p-6 bg-card border border-border">
            <h3 className="font-semibold text-foreground mb-4">Transaction Details</h3>
            <div className="space-y-4">
              <div>
                <label className="text-xs text-muted-foreground block mb-2">Sender</label>
                <input
                  type="text"
                  defaultValue="Offshore Holdings LLC"
                  className="w-full px-3 py-2 bg-input border border-border rounded-lg text-foreground text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-2">Receiver</label>
                <input
                  type="text"
                  defaultValue="International Trade Corp"
                  className="w-full px-3 py-2 bg-input border border-border rounded-lg text-foreground text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-2">Amount (USD)</label>
                <input
                  type="number"
                  defaultValue="850000"
                  className="w-full px-3 py-2 bg-input border border-border rounded-lg text-foreground text-sm"
                />
              </div>
              <div>
                <label className="text-xs text-muted-foreground block mb-2">Jurisdiction</label>
                <input
                  type="text"
                  defaultValue="Cayman Islands"
                  className="w-full px-3 py-2 bg-input border border-border rounded-lg text-foreground text-sm"
                />
              </div>
              <Button
                onClick={handleAnalyze}
                disabled={isAnalyzing}
                className="w-full gap-2 bg-primary hover:bg-primary/90 text-primary-foreground"
              >
                {isAnalyzing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Search className="w-4 h-4" />
                    Analyze Transaction
                  </>
                )}
              </Button>
            </div>
          </Card>
        </div>

        {/* Results Section with Explainability */}
        <div className="lg:col-span-2 space-y-4">
          {result ? (
            <>
              {/* Quick Result Card */}
              <Card
                className={`p-6 border cursor-pointer hover:border-primary/50 transition ${result.decision === "flagged" ? "border-destructive/30 bg-destructive/5" : "border-accent/30 bg-accent/5"}`}
                onClick={() => setFeedbackOpen(true)}
              >
                <div className="flex items-start gap-4 mb-3">
                  {result.decision === "flagged" ? (
                    <AlertCircle className="w-6 h-6 text-destructive flex-shrink-0 mt-1" />
                  ) : (
                    <CheckCircle className="w-6 h-6 text-accent flex-shrink-0 mt-1" />
                  )}
                  <div className="flex-1">
                    <h3 className="font-semibold text-foreground mb-1">
                      {result.decision === "flagged" ? "Flagged for Review" : "Transaction Accepted"}
                    </h3>
                    <p className="text-xs text-muted-foreground">Click to override decision if needed</p>
                  </div>
                </div>
              </Card>

              {/* Explainability Panel */}
              <ExplainabilityPanel
                verdict={result.decision}
                riskScore={result.riskScore}
                retrievedRules={result.policies}
                reasoningChain={result.reasoning}
                caseMatches={result.caseMatches}
                modelInfo={{
                  version: "GPT-4.1 (2025-02)",
                  timestamp: result.timestamp,
                  traceId: `#${Math.random().toString(36).substr(2, 8)}`,
                }}
              />

              {/* Override Button */}
              <Button
                onClick={() => setFeedbackOpen(true)}
                className="w-full gap-2 bg-primary/10 text-primary hover:bg-primary/20 border border-primary/30"
              >
                Override Decision
              </Button>

              {/* Audit Info */}
              <div className="text-xs text-muted-foreground text-right pt-2">
                Analysis completed at {result.timestamp}
              </div>
            </>
          ) : (
            <Card className="p-12 bg-card border border-border text-center">
              <p className="text-muted-foreground mb-4">Enter transaction details to see comprehensive analysis</p>
              <p className="text-xs text-muted-foreground">You'll get:</p>
              <ul className="text-xs text-muted-foreground mt-2 space-y-1">
                <li>• AI-powered compliance decision</li>
                <li>• Risk scoring with explanation</li>
                <li>• Retrieved policy rules with citations</li>
                <li>• Similar historical cases</li>
                <li>• Audit trail & export options</li>
              </ul>
            </Card>
          )}
        </div>
      </div>

      {/* Feedback Dialog */}
      <HumanFeedbackDialog
        open={feedbackOpen}
        onOpenChange={setFeedbackOpen}
        currentDecision={result?.decision || "accepted"}
        caseId="CASE-NEW"
        onSubmitFeedback={(feedback) => {
          console.log("Feedback submitted:", feedback)
        }}
      />
    </div>
  )
}
