import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";
import { Button } from "../../components/ui/button";
import { ListRow } from "../../components/ListRow";
import { useTenants } from "../../hooks/adminHooks";

export default function TenantList() {
  const { data, isLoading, error } = useTenants();

  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-6xl px-4 py-6 space-y-4">
        <h1 className="text-2xl font-semibold text-foreground">Platform Admin</h1>

        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Tenants</h2>
          <Button asChild variant="outline" size="sm">
            <Link to="/admin/tenants/new" style={{ textDecoration: "none" }}>
              + New tenant
            </Link>
          </Button>
        </div>

        {isLoading && <p className="text-sm text-muted-foreground">Loading tenants…</p>}
        {error && <p className="text-sm text-destructive">Couldn't load tenants.</p>}
        {!isLoading && !error && data && data.items.length === 0 && (
          <p className="text-sm text-muted-foreground">No tenants yet.</p>
        )}

        <div className="space-y-2">
          {data?.items.map((t) => (
            <ListRow
              key={t.tenant_id}
              action={
                <Link
                  to={`/admin/tenants/${t.tenant_id}/users/new`}
                  className="text-sm text-primary hover:underline"
                  style={{ textDecoration: "none" }}
                >
                  + Add admin/user
                </Link>
              }
            >
              <p className="font-semibold text-foreground truncate">
                {t.display_name ?? t.name ?? t.slug}
              </p>
              <p className="text-sm text-muted-foreground tabular-nums mt-0.5">
                slug: {t.slug} · {t.active === false ? "inactive" : "active"}
              </p>
            </ListRow>
          ))}
        </div>
      </main>
    </>
  );
}
