"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { Textarea } from "@/components/ui/textarea"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"
import { AlertCircle } from "lucide-react"

interface HumanFeedbackDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  currentDecision: string
  caseId: string
  onSubmitFeedback: (feedback: { newDecision: string; reason: string }) => void
}

export function HumanFeedbackDialog({
  open,
  onOpenChange,
  currentDecision,
  caseId,
  onSubmitFeedback,
}: HumanFeedbackDialogProps) {
  const [newDecision, setNewDecision] = useState(currentDecision)
  const [reason, setReason] = useState("")

  const handleSubmit = () => {
    if (reason.trim()) {
      onSubmitFeedback({ newDecision, reason })
      setReason("")
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Override Decision</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          {/* Current Decision */}
          <div className="p-4 bg-muted/20 border border-border rounded-lg">
            <p className="text-xs text-muted-foreground mb-1">Current Decision</p>
            <p className="text-sm font-semibold text-foreground">{currentDecision}</p>
            <p className="text-xs text-muted-foreground mt-2">Case: {caseId}</p>
          </div>

          {/* New Decision Selection */}
          <div className="space-y-3">
            <p className="text-sm font-medium text-foreground">New Decision</p>
            <RadioGroup value={newDecision} onValueChange={setNewDecision}>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="accepted" id="accepted" />
                <Label htmlFor="accepted" className="text-sm cursor-pointer">
                  Accept
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="flagged" id="flagged" />
                <Label htmlFor="flagged" className="text-sm cursor-pointer">
                  Flag for Review
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="review" id="review" />
                <Label htmlFor="review" className="text-sm cursor-pointer">
                  Requires Review
                </Label>
              </div>
            </RadioGroup>
          </div>

          {/* Reason Input */}
          <div className="space-y-2">
            <Label htmlFor="reason" className="text-sm font-medium">
              Reason for Override
            </Label>
            <Textarea
              id="reason"
              placeholder="Explain why you're overriding this decision..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              className="min-h-24 bg-input border border-border"
            />
          </div>

          {/* Warning */}
          <div className="flex items-start gap-2 p-3 bg-primary/5 border border-primary/20 rounded-lg">
            <AlertCircle className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
            <p className="text-xs text-muted-foreground">
              This feedback will be stored and used to improve future compliance decisions.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!reason.trim()} className="bg-primary hover:bg-primary/90">
            Submit Override
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
