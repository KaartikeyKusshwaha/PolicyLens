"use client"

import type React from "react"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Send, Sparkles, MessageSquare } from "lucide-react"

interface QueryResult {
  id: string
  query: string
  response: string
  confidence: number
  sources: string[]
  timestamp: string
}

interface SuggestedQuery {
  id: string
  text: string
  category: string
}

export function QueryPanel() {
  const [query, setQuery] = useState("")
  const [results, setResults] = useState<QueryResult[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [selectedResult, setSelectedResult] = useState<QueryResult | null>(null)

  const suggestedQueries: SuggestedQuery[] = [
    {
      id: "q1",
      text: "What are the latest AML policy updates?",
      category: "Policy",
    },
    {
      id: "q2",
      text: "Show transactions flagged in the last 24 hours",
      category: "Transactions",
    },
    {
      id: "q3",
      text: "Which entities are on the OFAC sanctions list?",
      category: "Sanctions",
    },
    {
      id: "q4",
      text: "What policies apply to high-risk countries?",
      category: "Risk",
    },
    {
      id: "q5",
      text: "Explain the KYC verification process",
      category: "KYC",
    },
    {
      id: "q6",
      text: "Compare decision patterns across regions",
      category: "Analytics",
    },
  ]

  const handleQuerySubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setIsLoading(true)
    // Simulate API call
    setTimeout(() => {
      const newResult: QueryResult = {
        id: `result-${Date.now()}`,
        query: query,
        response: `PolicyLens AI Response: Based on the latest policy database and transaction records, I've analyzed your query. The system has reviewed over 500 relevant policy documents and identified key compliance considerations. Recent AML regulations emphasize enhanced due diligence for high-risk jurisdictions, with particular focus on beneficial ownership verification and transaction monitoring. The system recommends implementing additional screening for entities from Tier-1 risk countries.`,
        confidence: 0.92,
        sources: ["AML-DIRECTIVE-2024", "KYC-POLICY-UPDATED", "SANCTIONS-LIST-Q1"],
        timestamp: new Date().toLocaleString(),
      }
      setResults([newResult, ...results])
      setQuery("")
      setSelectedResult(newResult)
      setIsLoading(false)
    }, 1500)
  }

  const handleSuggestedQuery = (suggestedText: string) => {
    setQuery(suggestedText)
  }

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.9) return "text-green-600 dark:text-green-400"
    if (confidence >= 0.7) return "text-amber-600 dark:text-amber-400"
    return "text-orange-600 dark:text-orange-400"
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground mb-2">Query Panel</h1>
        <p className="text-muted-foreground">
          Ask the AI compliance assistant anything about policies and transactions
        </p>
      </div>

      {/* Query Input */}
      <Card className="p-6 bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-pink-500/10 border border-accent">
        <form onSubmit={handleQuerySubmit} className="space-y-4">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Ask about policies, transactions, compliance requirements..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="flex-1 px-4 py-3 rounded-lg border border-accent bg-background text-foreground placeholder-muted-foreground"
            />
            <Button
              type="submit"
              disabled={isLoading || !query.trim()}
              className="gap-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700"
            >
              <Send className="w-4 h-4" />
              {isLoading ? "Analyzing..." : "Query"}
            </Button>
          </div>
        </form>
      </Card>

      {/* Suggested Queries */}
      {results.length === 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-amber-500" />
            Suggested Queries
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {suggestedQueries.map((sq) => (
              <Button
                key={sq.id}
                variant="outline"
                className="justify-start h-auto p-4 text-left hover:bg-accent/50 bg-transparent"
                onClick={() => handleSuggestedQuery(sq.text)}
              >
                <div>
                  <p className="font-semibold text-foreground text-sm">{sq.text}</p>
                  <p className="text-xs text-muted-foreground mt-1">{sq.category}</p>
                </div>
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* Results */}
      {results.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
            <MessageSquare className="w-5 h-5" />
            Query History ({results.length})
          </h2>

          <div className="grid gap-4">
            {results.map((result) => (
              <Card
                key={result.id}
                className="p-4 cursor-pointer hover:shadow-lg transition-shadow border-l-4 border-blue-500"
                onClick={() => setSelectedResult(result)}
              >
                <div className="flex items-start justify-between gap-4 mb-3">
                  <p className="font-semibold text-foreground">{result.query}</p>
                  <Badge className={`${getConfidenceColor(result.confidence)} bg-transparent border`}>
                    {(result.confidence * 100).toFixed(0)}% Confidence
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground line-clamp-2">{result.response}</p>
                <div className="flex gap-2 mt-3 flex-wrap">
                  {result.sources.map((source) => (
                    <Badge key={source} variant="secondary" className="text-xs">
                      {source}
                    </Badge>
                  ))}
                </div>
              </Card>
            ))}
          </div>

          {/* Detailed Response */}
          {selectedResult && (
            <Card className="p-6 border-2 border-purple-500/50 bg-purple-500/5">
              <div className="flex items-start justify-between mb-4">
                <h2 className="text-xl font-bold text-foreground">Query Response</h2>
                <div className="text-right">
                  <div className={`text-2xl font-bold ${getConfidenceColor(selectedResult.confidence)}`}>
                    {(selectedResult.confidence * 100).toFixed(0)}%
                  </div>
                  <p className="text-xs text-muted-foreground">Confidence</p>
                </div>
              </div>
              <div className="mb-4">
                <p className="text-sm font-semibold text-muted-foreground mb-1">Question:</p>
                <p className="text-foreground">{selectedResult.query}</p>
              </div>
              <div className="mb-4">
                <p className="text-sm font-semibold text-muted-foreground mb-1">Response:</p>
                <p className="text-foreground leading-relaxed">{selectedResult.response}</p>
              </div>
              <div>
                <p className="text-sm font-semibold text-muted-foreground mb-2">Source Documents:</p>
                <div className="flex gap-2 flex-wrap">
                  {selectedResult.sources.map((source) => (
                    <Badge key={source} className="bg-purple-600 hover:bg-purple-700">
                      {source}
                    </Badge>
                  ))}
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-4">Queried at: {selectedResult.timestamp}</p>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}
