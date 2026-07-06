import { Button } from "./ui/button";
import { CredentialDisplay, type Credential } from "./CredentialDisplay";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./ui/dialog";

export function TempPasswordModal({
  creds,
  title,
  onClose,
}: {
  creds: Credential[] | null;
  title: string;
  onClose: () => void;
}) {
  return (
    <Dialog open={creds !== null} onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        {creds && <CredentialDisplay creds={creds} title={title} />}
        <DialogFooter>
          <Button onClick={onClose}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
