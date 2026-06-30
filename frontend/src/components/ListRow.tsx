import { type ReactNode } from "react";

import { cn } from "../lib/utils";

export function ListRow({
  children,
  action,
  actionClassName,
  className,
}: {
  children: ReactNode;
  action?: ReactNode;
  actionClassName?: string;
  className?: string;
}) {
  return (
    <div className={cn("rounded-lg border bg-card p-2 flex items-center justify-between gap-3", className)}>
      <div className="min-w-0 flex-1">{children}</div>
      {action && (
        <div className={cn("flex items-center gap-2 shrink-0", actionClassName)}>
          {action}
        </div>
      )}
    </div>
  );
}
