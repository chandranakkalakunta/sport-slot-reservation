import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../components/AppHeader", () => ({ AppHeader: () => null }));

import {
  type OverviewFacility,
  useDailyOverview,
} from "../../hooks/tenantAdminHooks";
import TenantDailyOverview from "./TenantDailyOverview";

vi.mock("../../hooks/tenantAdminHooks", () => ({
  useDailyOverview: vi.fn(),
}));

const FACILITY_ALPHA: OverviewFacility = {
  facility_id: "fac-alpha",
  name: "Alpha Court",
  facility_type_id: "badminton",
  sport: "badminton",
  bookings: [
    {
      booking_id: "fac-alpha_2026-07-07_09:00",
      start: "09:00",
      end: "10:00",
      status: "confirmed",
      resident_name: "Alice",
      resident_email: "alice@demo.com",
    },
  ],
};

const FACILITY_ZULU: OverviewFacility = {
  facility_id: "fac-zulu",
  name: "Zulu Court",
  facility_type_id: "tennis",
  sport: "tennis",
  bookings: [
    {
      booking_id: "fac-zulu_2026-07-07_11:00",
      start: "11:00",
      end: "12:00",
      status: "cancelled",
      resident_name: "Bob",
      resident_email: "bob@demo.com",
    },
  ],
};

const FACILITY_NO_BOOKINGS: OverviewFacility = {
  facility_id: "fac-empty",
  name: "Empty Court",
  facility_type_id: "badminton",
  sport: "badminton",
  bookings: [],
};

function mockData(facilities = [FACILITY_ALPHA]) {
  vi.mocked(useDailyOverview).mockReturnValue({
    data: { date: "2026-07-07", facilities },
    isLoading: false,
  } as unknown as ReturnType<typeof useDailyOverview>);
}

function renderPage() {
  return render(<MemoryRouter><TenantDailyOverview /></MemoryRouter>);
}

/** In Grid view the column header and the slot cell both show the same time text.
 *  The slot cell is the one with aria-describedby (tooltip wiring). */
function getSlotCell(timeText: string): HTMLElement {
  const matches = screen.getAllByText(timeText);
  const cell = matches.find((el) => el.getAttribute("aria-describedby"));
  if (!cell) throw new Error(`No slot cell found with text "${timeText}" and aria-describedby`);
  return cell;
}

describe("TenantDailyOverview", () => {
  beforeEach(() => {
    // Default: matchMedia returns isWide=true (grid default on wide viewport).
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("640px"),
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
  });

  // ── Rendering ──────────────────────────────────────────────────────────────

  it("renders page heading", () => {
    mockData();
    renderPage();
    expect(screen.getByRole("heading", { name: /Daily Booking Overview/i })).toBeInTheDocument();
  });

  it("renders date input", () => {
    mockData();
    renderPage();
    expect(screen.getByLabelText(/date/i)).toBeInTheDocument();
  });

  // ── Facility ordering ──────────────────────────────────────────────────────

  it("(a) facilities appear alphabetically — Alpha before Zulu even when passed in reverse", () => {
    // Pass Zulu first; frontend sorts alphabetically regardless of API order.
    mockData([FACILITY_ZULU, FACILITY_ALPHA]);
    renderPage();
    const rows = screen.getAllByRole("row");
    const rowTexts = rows.map((r) => r.textContent ?? "");
    const alphaIdx = rowTexts.findIndex((t) => t.includes("Alpha Court"));
    const zuluIdx = rowTexts.findIndex((t) => t.includes("Zulu Court"));
    expect(alphaIdx).toBeGreaterThan(-1);
    expect(zuluIdx).toBeGreaterThan(-1);
    expect(alphaIdx).toBeLessThan(zuluIdx);
  });

  it("(b) alphabetical order holds when API sends Alpha before Zulu too", () => {
    mockData([FACILITY_ALPHA, FACILITY_ZULU]);
    renderPage();
    const rows = screen.getAllByRole("row");
    const rowTexts = rows.map((r) => r.textContent ?? "");
    const alphaIdx = rowTexts.findIndex((t) => t.includes("Alpha Court"));
    const zuluIdx = rowTexts.findIndex((t) => t.includes("Zulu Court"));
    expect(alphaIdx).toBeLessThan(zuluIdx);
  });

  // ── Cancelled bookings visible ─────────────────────────────────────────────

  it("(a) cancelled booking appears in Grid view — not hidden", () => {
    const facWithCancelled: OverviewFacility = {
      ...FACILITY_ALPHA,
      bookings: [
        {
          booking_id: "fac-alpha_2026-07-07_09:00",
          start: "09:00",
          end: "10:00",
          status: "cancelled",
          resident_name: "Alice",
          resident_email: "alice@demo.com",
        },
      ],
    };
    mockData([facWithCancelled]);
    renderPage();
    // The slot cell (with aria-describedby) renders the start time regardless of status.
    expect(getSlotCell("09:00")).toBeInTheDocument();
  });

  it("(b) cancelled booking appears in List view — not hidden", () => {
    // FACILITY_ZULU has a cancelled booking at 11:00–12:00.
    mockData([FACILITY_ZULU]);
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /list/i }));
    // The time range is unique to the booking row (not in the legend).
    expect(screen.getByText(/11:00.+12:00/)).toBeInTheDocument();
  });

  // ── Cancelled booking distinct styling ────────────────────────────────────

  it("cancelled slot cell has line-through class (Grid view)", () => {
    const facWithCancelled: OverviewFacility = {
      ...FACILITY_ALPHA,
      bookings: [
        {
          booking_id: "fac-alpha_2026-07-07_09:00",
          start: "09:00",
          end: "10:00",
          status: "cancelled",
          resident_name: "Alice",
          resident_email: "alice@demo.com",
        },
      ],
    };
    mockData([facWithCancelled]);
    renderPage();
    expect(getSlotCell("09:00")).toHaveClass("line-through");
  });

  it("confirmed slot cell does NOT have line-through class (Grid view)", () => {
    mockData();
    renderPage();
    expect(getSlotCell("09:00")).not.toHaveClass("line-through");
  });

  // ── Tooltip on hover ───────────────────────────────────────────────────────

  it("tooltip is NOT visible before hover (Grid view)", () => {
    mockData();
    renderPage();
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("tooltip appears on mouseenter (Grid view) — hover trigger", () => {
    mockData();
    renderPage();
    const cell = getSlotCell("09:00");
    fireEvent.mouseEnter(cell);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    expect(screen.getByRole("tooltip")).toHaveTextContent("Alice");
    expect(screen.getByRole("tooltip")).toHaveTextContent("alice@demo.com");
  });

  it("tooltip disappears on mouseleave (Grid view)", () => {
    mockData();
    renderPage();
    const cell = getSlotCell("09:00");
    fireEvent.mouseEnter(cell);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    fireEvent.mouseLeave(cell);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  // ── Tooltip on keyboard focus (SEPARATE test case from hover) ─────────────

  it("tooltip appears on focus (Grid view) — keyboard-focus trigger", () => {
    mockData();
    renderPage();
    const cell = getSlotCell("09:00");
    fireEvent.focus(cell);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    expect(screen.getByRole("tooltip")).toHaveTextContent("Alice");
    expect(screen.getByRole("tooltip")).toHaveTextContent("alice@demo.com");
  });

  it("tooltip disappears on blur (Grid view)", () => {
    mockData();
    renderPage();
    const cell = getSlotCell("09:00");
    fireEvent.focus(cell);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    fireEvent.blur(cell);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("tooltip appears on focus (List view) — keyboard-focus trigger", () => {
    mockData();
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /list/i }));
    // In list view the time span (09:00–10:00) is the focusable element.
    const timeSpan = screen.getByText(/09:00.+10:00/);
    fireEvent.focus(timeSpan);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
    expect(screen.getByRole("tooltip")).toHaveTextContent("Alice");
  });

  it("tooltip appears on mouseenter (List view) — hover trigger", () => {
    mockData();
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /list/i }));
    const timeSpan = screen.getByText(/09:00.+10:00/);
    fireEvent.mouseEnter(timeSpan);
    expect(screen.getByRole("tooltip")).toBeInTheDocument();
  });

  // ── slot has aria-describedby ──────────────────────────────────────────────

  it("slot cell has aria-describedby pointing to the tooltip id", () => {
    mockData();
    renderPage();
    const cell = getSlotCell("09:00");
    const tooltipId = cell.getAttribute("aria-describedby");
    expect(tooltipId).toBeTruthy();
    // Trigger the tooltip so the element is in DOM, then verify the link.
    fireEvent.focus(cell);
    expect(document.getElementById(tooltipId!)).toBeInTheDocument();
  });

  // ── View mode defaults ──────────────────────────────────────────────────────

  it("Grid is default on wide viewport (≥640px)", () => {
    mockData();
    renderPage();
    const gridBtn = screen.getByRole("button", { name: /grid/i });
    expect(gridBtn).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("table")).toBeInTheDocument();
  });

  it("List is default on narrow viewport (<640px)", () => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
    mockData([FACILITY_ALPHA]);
    renderPage();
    const listBtn = screen.getByRole("button", { name: /list/i });
    expect(listBtn).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("manual toggle overrides viewport default — clicking List on wide viewport switches to List", () => {
    mockData();
    renderPage();
    expect(screen.getByRole("table")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /list/i }));
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /list/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("manual toggle overrides viewport default — clicking Grid on narrow viewport switches to Grid", () => {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      })),
    });
    mockData([FACILITY_ALPHA]);
    renderPage();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /grid/i }));
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /grid/i })).toHaveAttribute("aria-pressed", "true");
  });

  // ── Facility type filter ───────────────────────────────────────────────────

  it("type filter hides facilities that do not match the selected type", () => {
    mockData([FACILITY_ALPHA, FACILITY_ZULU]);
    renderPage();
    const select = screen.getByLabelText(/type/i);
    fireEvent.change(select, { target: { value: "badminton" } });
    expect(screen.getByText("Alpha Court")).toBeInTheDocument();
    expect(screen.queryByText("Zulu Court")).not.toBeInTheDocument();
  });

  it("type filter 'All types' restores all facilities", () => {
    mockData([FACILITY_ALPHA, FACILITY_ZULU]);
    renderPage();
    const select = screen.getByLabelText(/type/i);
    fireEvent.change(select, { target: { value: "badminton" } });
    fireEvent.change(select, { target: { value: "all" } });
    expect(screen.getByText("Alpha Court")).toBeInTheDocument();
    expect(screen.getByText("Zulu Court")).toBeInTheDocument();
  });

  // ── Loading state ──────────────────────────────────────────────────────────

  it("shows loading text while data is fetching", () => {
    vi.mocked(useDailyOverview).mockReturnValue({
      data: undefined,
      isLoading: true,
    } as unknown as ReturnType<typeof useDailyOverview>);
    renderPage();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  // ── Empty state ────────────────────────────────────────────────────────────

  it("shows 'No bookings' message when all facilities have no bookings", () => {
    mockData([FACILITY_NO_BOOKINGS]);
    renderPage();
    expect(screen.getByText(/No bookings on this date/i)).toBeInTheDocument();
  });
});
