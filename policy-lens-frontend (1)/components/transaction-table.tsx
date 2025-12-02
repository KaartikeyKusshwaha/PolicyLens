"use client"

import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Building2, User } from "lucide-react"

interface Transaction {
  id: string
  amount: string
  status: "accepted" | "flagged" | "review"
  riskScore: number
  sender: string
  receiver: string
  timestamp: string
  senderType?: "individual" | "corporate" | "offshore"
}

const mockTransactions: Transaction[] = [
  {
    id: "TXN-001",
    amount: "$45,230",
    status: "accepted",
    riskScore: 12,
    sender: "John Doe",
    receiver: "Acme Corp",
    timestamp: "2 min ago",
    senderType: "individual",
  },
  {
    id: "TXN-002",
    amount: "$850,000",
    status: "flagged",
    riskScore: 78,
    sender: "Unknown Entity",
    receiver: "International Trade",
    timestamp: "5 min ago",
    senderType: "offshore",
  },
  {
    id: "TXN-003",
    amount: "$125,500",
    status: "review",
    riskScore: 45,
    sender: "Tech Innovations Ltd",
    receiver: "Global Ventures",
    timestamp: "12 min ago",
    senderType: "corporate",
  },
  {
    id: "TXN-004",
    amount: "$32,100",
    status: "accepted",
    riskScore: 8,
    sender: "Sarah Smith",
    receiver: "Local Business Inc",
    timestamp: "18 min ago",
    senderType: "individual",
  },
  {
    id: "TXN-005",
    amount: "$295,750",
    status: "flagged",
    riskScore: 82,
    sender: "Offshore Holdings",
    receiver: "Subsidiary Corp",
    timestamp: "25 min ago",
    senderType: "offshore",
  },
]

const statusVariants = {
  accepted: "bg-accent/10 text-accent border-accent/20",
  flagged: "bg-destructive/10 text-destructive border-destructive/20",
  review: "bg-primary/10 text-primary border-primary/20",
}

const getEntityIcon = (type?: string) => {
  if (type === "individual") return <User className="w-4 h-4" />
  return <Building2 className="w-4 h-4" />
}

export function TransactionTable() {
  return (
    <Card className="p-6 bg-card border border-border">
      <h3 className="font-semibold text-foreground mb-4">Recent Transactions</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left py-3 px-2 text-muted-foreground font-medium">ID</th>
              <th className="text-left py-3 px-2 text-muted-foreground font-medium">From</th>
              <th className="text-left py-3 px-2 text-muted-foreground font-medium">To</th>
              <th className="text-left py-3 px-2 text-muted-foreground font-medium">Amount</th>
              <th className="text-left py-3 px-2 text-muted-foreground font-medium">Risk Score</th>
              <th className="text-left py-3 px-2 text-muted-foreground font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {mockTransactions.map((tx) => (
              <tr key={tx.id} className="border-b border-border/50 hover:bg-primary/5 transition">
                <td className="py-3 px-2 text-foreground font-mono text-xs">{tx.id}</td>
                <td className="py-3 px-2 text-foreground">
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">{getEntityIcon(tx.senderType)}</span>
                    <span className="text-xs">{tx.sender}</span>
                  </div>
                </td>
                <td className="py-3 px-2 text-foreground">{tx.receiver}</td>
                <td className="py-3 px-2 text-foreground font-semibold">{tx.amount}</td>
                <td className="py-3 px-2">
                  <div className="flex items-center gap-2">
                    <div className="w-12 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full ${tx.riskScore > 60 ? "bg-destructive" : tx.riskScore > 30 ? "bg-primary" : "bg-accent"}`}
                        style={{ width: `${tx.riskScore}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">{tx.riskScore}%</span>
                  </div>
                </td>
                <td className="py-3 px-2">
                  <Badge variant="outline" className={statusVariants[tx.status]}>
                    {tx.status.charAt(0).toUpperCase() + tx.status.slice(1)}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
