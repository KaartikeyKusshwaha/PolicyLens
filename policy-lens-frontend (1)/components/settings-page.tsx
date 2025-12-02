"use client"

import { useState } from "react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Moon, Sun, Bell, Lock, Database } from "lucide-react"
import { useTheme } from "next-themes"

export function SettingsPage() {
  const { theme, setTheme } = useTheme()
  const [settings, setSettings] = useState({
    emailNotifications: true,
    policyUpdates: true,
    flaggedTransactions: true,
    systemAlerts: true,
    retentionDays: 90,
  })

  const handleToggle = (key: string) => {
    setSettings({ ...settings, [key]: !settings[key as keyof typeof settings] })
  }

  return (
    <div className="p-8 space-y-8 max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-balance">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage preferences and configuration</p>
      </div>

      <Tabs defaultValue="theme" className="w-full">
        <TabsList className="grid w-full grid-cols-4 bg-muted/30">
          <TabsTrigger value="theme" className="gap-2">
            <Sun className="w-4 h-4" />
            Theme
          </TabsTrigger>
          <TabsTrigger value="notifications" className="gap-2">
            <Bell className="w-4 h-4" />
            Notifications
          </TabsTrigger>
          <TabsTrigger value="security" className="gap-2">
            <Lock className="w-4 h-4" />
            Security
          </TabsTrigger>
          <TabsTrigger value="data" className="gap-2">
            <Database className="w-4 h-4" />
            Data
          </TabsTrigger>
        </TabsList>

        {/* Theme Tab */}
        <TabsContent value="theme" className="space-y-4 mt-6">
          <Card className="p-6 bg-card border border-border">
            <h3 className="font-semibold text-foreground mb-4">Appearance</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-foreground">Color Theme</p>
                  <p className="text-xs text-muted-foreground mt-1">Choose between light and dark mode</p>
                </div>
                <div className="flex gap-2">
                  <Button
                    onClick={() => setTheme("light")}
                    variant={theme === "light" ? "default" : "outline"}
                    size="sm"
                    className="gap-2"
                  >
                    <Sun className="w-4 h-4" />
                    Light
                  </Button>
                  <Button
                    onClick={() => setTheme("dark")}
                    variant={theme === "dark" ? "default" : "outline"}
                    size="sm"
                    className="gap-2"
                  >
                    <Moon className="w-4 h-4" />
                    Dark
                  </Button>
                </div>
              </div>
              <div className="pt-4 border-t border-border">
                <p className="text-sm font-medium text-foreground mb-2">Current Theme</p>
                <Badge className="bg-primary/10 text-primary">{theme || "system"}</Badge>
              </div>
            </div>
          </Card>
        </TabsContent>

        {/* Notifications Tab */}
        <TabsContent value="notifications" className="space-y-4 mt-6">
          <Card className="p-6 bg-card border border-border">
            <h3 className="font-semibold text-foreground mb-4">Notification Preferences</h3>
            <div className="space-y-4">
              {[
                { key: "emailNotifications", label: "Email Notifications", desc: "Receive updates via email" },
                { key: "policyUpdates", label: "Policy Updates", desc: "Notify when policies are updated" },
                { key: "flaggedTransactions", label: "Flagged Transactions", desc: "Alert on flagged transactions" },
                { key: "systemAlerts", label: "System Alerts", desc: "Critical system notifications" },
              ].map((item) => (
                <div
                  key={item.key}
                  className="flex items-center justify-between p-3 hover:bg-muted/20 rounded-lg transition"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">{item.label}</p>
                    <p className="text-xs text-muted-foreground">{item.desc}</p>
                  </div>
                  <Switch
                    checked={settings[item.key as keyof typeof settings] as boolean}
                    onCheckedChange={() => handleToggle(item.key)}
                  />
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security" className="space-y-4 mt-6">
          <Card className="p-6 bg-card border border-border">
            <h3 className="font-semibold text-foreground mb-4">API & Authentication</h3>
            <div className="space-y-4">
              <div>
                <Label className="text-sm font-medium">API Key</Label>
                <div className="flex gap-2 mt-2">
                  <Input
                    type="password"
                    defaultValue="sk_test_51234567890..."
                    className="bg-input border-border"
                    disabled
                  />
                  <Button variant="outline">Regenerate</Button>
                </div>
              </div>
              <div className="p-4 bg-primary/5 border border-primary/20 rounded-lg">
                <p className="text-xs text-muted-foreground">
                  Keep your API key secure. Regenerating will invalidate the current key.
                </p>
              </div>
            </div>
          </Card>
        </TabsContent>

        {/* Data Tab */}
        <TabsContent value="data" className="space-y-4 mt-6">
          <Card className="p-6 bg-card border border-border">
            <h3 className="font-semibold text-foreground mb-4">Data Management</h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 hover:bg-muted/20 rounded-lg transition">
                <div>
                  <p className="text-sm font-medium text-foreground">Data Retention</p>
                  <p className="text-xs text-muted-foreground">Automatically delete records older than</p>
                </div>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    value={settings.retentionDays}
                    onChange={(e) => setSettings({ ...settings, retentionDays: Number.parseInt(e.target.value) })}
                    className="w-20 bg-input border-border"
                  />
                  <span className="text-sm text-muted-foreground">days</span>
                </div>
              </div>
              <Button
                variant="outline"
                className="w-full text-destructive border-destructive/20 hover:bg-destructive/5 bg-transparent"
              >
                Clear All Data
              </Button>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
