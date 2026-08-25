import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { YearlyDashboard } from "../../api/types";
import { MonthlyTrend } from "./DashboardPage";

const dashboard: YearlyDashboard = {
  year: 2026,
  available_years: [2026],
  total_project_count: 2,
  travel_project_count: 2,
  daily_project_count: 0,
  total_trip_days: 6,
  total_invoice_amount: 700,
  total_income_amount: 380,
  reimbursed_amount: 0,
  unreimbursed_amount: 1080,
  monthly_trends: Array.from({ length: 12 }, (_, index) => ({
    month: index + 1,
    project_count: index === 3 || index === 6 ? 1 : 0,
    invoice_amount: index === 3 ? 600 : index === 6 ? 100 : 0,
    allowance_amount: index === 3 ? 200 : index === 6 ? 180 : 0,
  })),
  category_summary: {},
  city_summary: [],
  reimbursement_summary: {},
  recent_projects: [],
};

describe("MonthlyTrend", () => {
  beforeEach(cleanup);
  afterEach(cleanup);

  it("summarizes the year and supports persistent month selection", () => {
    render(<MonthlyTrend data={dashboard} />);

    expect(screen.getByText("4月 · ¥600.00")).toBeInTheDocument();
    expect(screen.getByLabelText("4月收支明细")).toBeInTheDocument();

    const july = screen.getByRole("button", { name: /7月，1 个项目/ });
    fireEvent.click(july);

    expect(july).toHaveAttribute("aria-pressed", "true");
    const julyDetail = screen.getByLabelText("7月收支明细");
    expect(julyDetail).toHaveTextContent("票据支出");
    expect(julyDetail).toHaveTextContent("-¥80.00");
  });

  it("previews a focused month and selects it with the keyboard", () => {
    render(<MonthlyTrend data={dashboard} />);
    const january = screen.getAllByRole("button").find((element) => element.getAttribute("aria-label")?.startsWith("1月，"));
    expect(january).toBeDefined();
    if (!january) return;

    fireEvent.focus(january);
    expect(screen.getByLabelText("1月收支明细")).toBeInTheDocument();
    fireEvent.keyDown(january, { key: "Enter" });
    fireEvent.blur(january);

    expect(january).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("1月收支明细")).toHaveTextContent("¥0.00");
  });
});
