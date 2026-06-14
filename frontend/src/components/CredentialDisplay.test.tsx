import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { CredentialDisplay } from "./CredentialDisplay";

const CRED = { email: "alice@demo.com", temp_password: "TempP@ss1234" };

describe("CredentialDisplay", () => {
  it("shows the temp password in the pre block", () => {
    render(<CredentialDisplay creds={[CRED]} />);
    expect(screen.getByText(/TempP@ss1234/)).toBeInTheDocument();
    expect(screen.getByText(/alice@demo\.com/)).toBeInTheDocument();
    expect(screen.getByText(/shown only once/)).toBeInTheDocument();
  });

  it("shows 'Copied!' after clicking copy button", async () => {
    // setup.ts provides navigator.clipboard.writeText as a resolving stub,
    // so the component sets copied=true → button text changes to "Copied!".
    const user = userEvent.setup();
    render(<CredentialDisplay creds={[CRED]} />);

    expect(screen.getByRole("button", { name: /copy credentials/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /copy credentials/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /copied!/i })).toBeInTheDocument();
    });
  });

  it("renders multiple credentials", () => {
    render(<CredentialDisplay creds={[
      CRED,
      { email: "bob@demo.com", temp_password: "OtherP@ss99" },
    ]} title="2 users created" />);
    expect(screen.getByText(/2 users created/)).toBeInTheDocument();
    expect(document.body).toHaveTextContent("bob@demo.com");
    expect(document.body).toHaveTextContent("OtherP@ss99");
  });
});
