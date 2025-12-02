"use client"

import { useState } from "react"
import { TopNavbar } from "@/components/top-navbar"
import { Dashboard } from "@/components/dashboard"
import { TransactionAnalysis } from "@/components/transaction-analysis"
import { PolicyManagement } from "@/components/policy-management"
import { CaseHistory } from "@/components/case-history"
import { DecisionsPanel } from "@/components/decisions-panel"
import { QueryPanel } from "@/components/query-panel"
import { SettingsPage } from "@/components/settings-page"

type Page = "dashboard" | "analyze" | "policies" | "cases" | "decisions" | "query" | "settings"

export default function Home() {
  const [currentPage, setCurrentPage] = useState<Page>("dashboard")

  const renderPage = () => {
    switch (currentPage) {
      case "dashboard":
        return <Dashboard />
      case "analyze":
        return <TransactionAnalysis />
      case "policies":
        return <PolicyManagement />
      case "cases":
        return <CaseHistory />
      case "decisions":
        return <DecisionsPanel />
      case "query":
        return <QueryPanel />
      case "settings":
        return <SettingsPage />
      default:
        return <Dashboard />
    }
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      <TopNavbar currentPage={currentPage} onPageChange={setCurrentPage} />
      <main className="flex-1 overflow-auto">{renderPage()}</main>
    </div>
  )
}
