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
    <div className={cn("rounded-lg border bg-card p-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3", className)}>
      <div className="min-w-0 flex-1">{children}</div>
      {action && (
        <div className={cn("flex flex-wrap items-center gap-2 sm:shrink-0", actionClassName)}>
          {action}
        </div>
      )}
    </div>
  );
}
