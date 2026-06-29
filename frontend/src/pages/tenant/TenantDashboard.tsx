import { Link } from "react-router-dom";

import { AppHeader } from "../../components/AppHeader";

const NAV = [
  {
    to: "/tenant/facilities",
    title: "Facilities",
    desc: "Add and configure courts, timings, slots",
  },
  {
    to: "/tenant/branding",
    title: "Branding",
    desc: "Name, colors, logo",
  },
  {
    to: "/tenant/policies",
    title: "Policies",
    desc: "Booking window, quota, cancellation",
  },
  {
    to: "/tenant/users",
    title: "Residents & admins",
    desc: "Add, import, manage users",
  },
];

export default function TenantDashboard() {
  return (
    <>
      <AppHeader />
      <main className="mx-auto max-w-3xl px-4 py-6 space-y-6">
        <h1 className="text-2xl font-semibold text-foreground">Tenant Admin</h1>
        <div className="grid grid-cols-2 gap-3">
          {NAV.map(({ to, title, desc }) => (
            <Link
              key={to}
              to={to}
              className="block rounded-md border border-border bg-card p-5 no-underline hover:bg-accent transition-colors"
              style={{ textDecoration: "none" }}
            >
              <p className="font-semibold text-foreground">{title}</p>
              <p className="text-sm text-muted-foreground mt-0.5">{desc}</p>
            </Link>
          ))}
        </div>
      </main>
    </>
  );
}
