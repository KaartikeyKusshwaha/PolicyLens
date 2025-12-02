"use client"

import { User, Menu } from "lucide-react"
import { Button } from "@/components/ui/button"
import { ThemeToggle } from "@/components/theme-toggle"
import { NotificationCenter } from "@/components/notification-center"
import { Shield, BarChart3, FileText, Search, ClipboardList, Brain } from "lucide-react"
import { MetricsPanel } from "@/components/metrics-panel"

interface TopNavbarProps {
  currentPage: string
  onPageChange: (page: any) => void
  onMenuClick?: () => void
}

export function TopNavbar({ currentPage, onPageChange, onMenuClick }: TopNavbarProps) {
  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: BarChart3 },
    { id: "analyze", label: "Analyze", icon: Search },
    { id: "decisions", label: "Decisions", icon: ClipboardList },
    { id: "query", label: "Query", icon: Brain },
    { id: "policies", label: "Policies", icon: FileText },
    { id: "cases", label: "Cases", icon: Shield },
  ]

  return (
    <div className="flex flex-col gap-4 bg-card border-b border-border">
      {/* Main Navbar */}
      <nav className="h-16 bg-gradient-to-r from-card via-card to-card/95 sticky top-0 z-40">
        <div className="h-full px-6 flex items-center justify-between">
          {/* Left side - Logo */}
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" className="lg:hidden" onClick={onMenuClick}>
              <Menu className="w-5 h-5" />
            </Button>

            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-md" />
              <div>
                <h1 className="font-bold text-sm text-foreground">PolicyLens</h1>
                <p className="text-xs text-muted-foreground">Compliance AI</p>
              </div>
            </div>
          </div>

          {/* Center - Navigation */}
          <div className="hidden md:flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = currentPage === item.id
              return (
                <Button
                  key={item.id}
                  variant={isActive ? "default" : "ghost"}
                  size="sm"
                  className={`gap-2 h-8 text-xs ${
                    isActive
                      ? "bg-primary text-primary-foreground shadow-md"
                      : "text-foreground hover:bg-accent/10 hover:text-primary"
                  }`}
                  onClick={() => onPageChange(item.id)}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </Button>
              )
            })}
          </div>

          {/* Right side - Actions */}
          <div className="flex items-center gap-3">
            <NotificationCenter />
            <ThemeToggle />

            <Button variant="ghost" size="sm" className="gap-2 h-8" onClick={() => onPageChange("settings")}>
              <User className="w-4 h-4" />
              <span className="hidden sm:inline text-xs">Profile</span>
            </Button>
          </div>
        </div>
      </nav>

      {/* Metrics Panel */}
      <div className="px-6 pb-4">
        <MetricsPanel />
      </div>
    </div>
  )
}
