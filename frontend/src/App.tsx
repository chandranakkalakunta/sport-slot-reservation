import { Route, Routes } from "react-router-dom";

function Home() {
  return (
    <main style={{ padding: "calc(var(--spacing) * 3)" }}>
      <h1 style={{ color: "var(--color-primary)" }}>SportSlot</h1>
      <p style={{ color: "var(--color-text-muted)" }}>
        Community sports facility booking — frontend foundation
        (Phase 4.1). Sign-in arrives in 4.2.
      </p>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
    </Routes>
  );
}
