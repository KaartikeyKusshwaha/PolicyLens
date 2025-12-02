"use client"

import { Shield, BarChart3, FileText, Search, Settings, ClipboardList, Brain, X } from "lucide-react"
import { Button } from "@/components/ui/button"

interface SidebarProps {
  currentPage: string
  onPageChange: (page: any) => void
  isOpen?: boolean
  onClose?: () => void
}

export function Sidebar({ currentPage, onPageChange, isOpen = true, onClose }: SidebarProps) {
  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: BarChart3 },
    { id: "analyze", label: "Analyze Transaction", icon: Search },
    { id: "decisions", label: "Decisions", icon: ClipboardList },
    { id: "query", label: "Query Assistant", icon: Brain },
    { id: "policies", label: "Policies", icon: FileText },
    { id: "cases", label: "Case History", icon: Shield },
  ]

  return (
    <>
      {isOpen && <div className="fixed inset-0 bg-black/50 lg:hidden z-30" onClick={onClose} />}

      <aside
        className={`fixed lg:static w-64 h-screen bg-sidebar border-r border-sidebar-border p-6 flex flex-col gap-8 transition-all duration-300 z-40 ${
          isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        {/* Header with close button */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg">
              <Shield className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg text-sidebar-foreground">PolicyLens</h1>
              <p className="text-xs text-sidebar-accent">Compliance AI</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" className="lg:hidden" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex flex-col gap-2 flex-1">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = currentPage === item.id
            return (
              <Button
                key={item.id}
                variant={isActive ? "default" : "ghost"}
                className={`justify-start gap-3 h-10 ${
                  isActive
                    ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-md"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/10 hover:text-sidebar-primary"
                }`}
                onClick={() => onPageChange(item.id)}
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </Button>
            )
          })}
        </nav>

        <Button
          variant="ghost"
          className={`justify-start gap-3 h-10 ${
            currentPage === "settings"
              ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-md"
              : "text-sidebar-foreground hover:bg-sidebar-accent/10"
          }`}
          onClick={() => onPageChange("settings")}
        >
          <Settings className="w-4 h-4" />
          <span>Settings</span>
        </Button>
      </aside>
    </>
  )
}
