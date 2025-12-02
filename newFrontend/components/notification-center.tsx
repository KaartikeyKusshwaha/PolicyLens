"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Bell, X, AlertTriangle, Info, CheckCircle } from "lucide-react"

interface Notification {
  id: string
  type: "alert" | "info" | "success"
  title: string
  message: string
  timestamp: string
  read: boolean
}

const initialNotifications: Notification[] = [
  {
    id: "1",
    type: "alert",
    title: "Policy Update in Progress",
    message: "Sanctions list is being updated from OFAC. 2 transactions are being re-evaluated.",
    timestamp: "2 minutes ago",
    read: false,
  },
  {
    id: "2",
    type: "info",
    title: "New Policy Version",
    message: "EU AML Directive v6.3 has been released. Review changes?",
    timestamp: "1 hour ago",
    read: false,
  },
  {
    id: "3",
    type: "success",
    title: "Analysis Complete",
    message: "Transaction CASE-945 analysis completed with risk score 42%.",
    timestamp: "3 hours ago",
    read: true,
  },
]

export function NotificationCenter() {
  const [isOpen, setIsOpen] = useState(false)
  const [notifications, setNotifications] = useState(initialNotifications)

  const unreadCount = notifications.filter((n) => !n.read).length

  const handleDismiss = (id: string) => {
    setNotifications(notifications.filter((n) => n.id !== id))
  }

  const handleMarkAsRead = (id: string) => {
    setNotifications(notifications.map((n) => (n.id === id ? { ...n, read: true } : n)))
  }

  const getIcon = (type: string) => {
    switch (type) {
      case "alert":
        return <AlertTriangle className="w-5 h-5 text-destructive" />
      case "success":
        return <CheckCircle className="w-5 h-5 text-accent" />
      default:
        return <Info className="w-5 h-5 text-primary" />
    }
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 rounded-lg hover:bg-muted transition text-foreground"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 w-5 h-5 bg-destructive text-white text-xs rounded-full flex items-center justify-center">
            {unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-96 bg-card border border-border rounded-lg shadow-lg z-50">
          <div className="p-4 border-b border-border flex items-center justify-between">
            <h3 className="font-semibold text-foreground">Notifications</h3>
            <button onClick={() => setIsOpen(false)} className="text-muted-foreground hover:text-foreground">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="max-h-96 overflow-auto">
            {notifications.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">No notifications</div>
            ) : (
              notifications.map((notif) => (
                <div
                  key={notif.id}
                  className={`p-4 border-b border-border hover:bg-muted/20 transition ${!notif.read ? "bg-primary/5" : ""}`}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0">{getIcon(notif.type)}</div>
                    <div className="flex-1">
                      <p className="font-medium text-foreground text-sm">{notif.title}</p>
                      <p className="text-xs text-muted-foreground mt-1">{notif.message}</p>
                      <p className="text-xs text-muted-foreground mt-2">{notif.timestamp}</p>
                    </div>
                    <button
                      onClick={() => handleDismiss(notif.id)}
                      className="text-muted-foreground hover:text-foreground flex-shrink-0"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  {!notif.read && (
                    <Button
                      onClick={() => handleMarkAsRead(notif.id)}
                      size="sm"
                      variant="outline"
                      className="mt-3 w-full text-xs"
                    >
                      Mark as read
                    </Button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
