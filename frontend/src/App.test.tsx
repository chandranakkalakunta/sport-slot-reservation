import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";

// Mock Firebase Auth at the module boundary (no real auth in unit tests).
let idTokenCallback: ((u: unknown) => void) | null = null;
vi.mock("./lib/firebase", () => ({
  auth: { currentUser: null },
  firebaseApp: {},
}));
vi.mock("firebase/auth", () => ({
  onIdTokenChanged: (_auth: unknown, cb: (u: unknown) => void) => {
    idTokenCallback = cb;
    return () => {};
  },
  signInWithEmailAndPassword: vi.fn(),
  signInWithPopup: vi.fn(),
  signOut: vi.fn(),
  GoogleAuthProvider: class {},
}));

import App from "./App";

beforeEach(() => {
  idTokenCallback = null;
});

test("unauthenticated user is redirected to sign-in", async () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
  // Resolve auth state as logged-out.
  idTokenCallback?.(null);
  await waitFor(() =>
    expect(screen.getByPlaceholderText("Email")).toBeInTheDocument(),
  );
});

test("loading state shows before auth resolves", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
  expect(screen.getByText("Loading…")).toBeInTheDocument();
});
