import { useState, type ReactNode } from "react";

import { Input } from "./ui/input";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";

export function ConfirmDialog({
  title, body, confirmLabel = "Confirm", onConfirm, onCancel, busy = false,
  confirmationPhrase,
}: {
  title: string;
  body: ReactNode;
  confirmLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
  confirmationPhrase?: string;
}) {
  const [typedValue, setTypedValue] = useState("");

  const confirmDisabled =
    busy || (confirmationPhrase !== undefined && typedValue !== confirmationPhrase);

  return (
    <Dialog open onOpenChange={(open) => { if (!open && !busy) onCancel(); }}>
      <DialogContent showCloseButton={false} className="max-w-sm">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <div className="text-foreground text-sm">{body}</div>
        {confirmationPhrase !== undefined && (
          <div className="space-y-1">
            <label className="text-sm font-medium text-foreground">
              {`Type ${confirmationPhrase} to confirm`}
            </label>
            <Input
              value={typedValue}
              onChange={(e) => setTypedValue(e.target.value)}
              placeholder={confirmationPhrase}
              autoComplete="off"
            />
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={onConfirm} disabled={confirmDisabled}>
            {busy ? "…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
