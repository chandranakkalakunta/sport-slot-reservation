import type { ReactNode } from "react";

import { Card, CardContent, CardHeader } from "./ui/card";

export function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-10">
      <Card className="w-full max-w-sm">
        <CardHeader>
          {/* h1 gives correct heading role for queries/accessibility */}
          <h1 className="text-center text-2xl font-semibold text-primary">{title}</h1>
        </CardHeader>
        <CardContent className="space-y-4">{children}</CardContent>
      </Card>
    </main>
  );
}
