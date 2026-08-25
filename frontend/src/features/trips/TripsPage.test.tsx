import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { tripsApi } from "../../api/resources";
import type { Trip } from "../../api/types";
import { TripsPage } from "./TripsPage";

vi.mock("../../api/resources", () => ({
  tripsApi: {
    list: vi.fn(),
    create: vi.fn(),
    remove: vi.fn(),
  },
}));

function trip(index: number, completed = false): Trip {
  return {
    id: `trip-${index}`,
    title: `${completed ? "已完结" : "进行中"}项目 ${index}`,
    source_label: `${index} 月差旅`,
    traveler_name: "张三",
    company_name: "示例公司",
    company_tax_id: null,
    project_type: "TRAVEL",
    status: completed ? "FINALIZED" : "ANALYZED",
    reimbursement_status: completed ? "ALREADY_REIMBURSED" : "NOT_REIMBURSED",
    input_start_date: "2026-07-01",
    input_end_date: "2026-07-02",
    inferred_start_date: "2026-07-01",
    inferred_end_date: "2026-07-02",
    confirmed_start_date: null,
    confirmed_end_date: null,
    trip_days: 2,
    date_confidence: 0.95,
    date_evidence: [],
    start_date: "2026-07-01",
    end_date: "2026-07-02",
    route_text: "北京 - 上海",
    created_at: `2026-07-${String(index).padStart(2, "0")}T00:00:00Z`,
    updated_at: `2026-07-${String(index).padStart(2, "0")}T00:00:00Z`,
    summary: {
      document_count: index,
      review_count: completed ? 0 : 1,
      issue_count: 0,
      invoice_total_amount: 100 * index,
      allowance_amount: 180,
      grand_total_amount: (100 * index) + 180,
    },
  };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter><TripsPage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("TripsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(tripsApi.list).mockResolvedValue([
      trip(1), trip(2), trip(3), trip(4), trip(5), trip(6), trip(7), trip(8, true), trip(9, true),
    ]);
  });

  afterEach(cleanup);

  it("filters, searches, changes display mode, and paginates the real project data", async () => {
    const user = userEvent.setup();
    const { container } = renderPage();

    await screen.findByText("进行中项目 7");
    expect(screen.queryByText("进行中项目 1")).not.toBeInTheDocument();
    expect(screen.getByText("进行中项目 7")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByText("进行中项目 1")).toBeInTheDocument();
    expect(screen.queryByText("进行中项目 7")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: /已完结/ }));
    expect(screen.getByText("已完结项目 9")).toBeInTheDocument();
    expect(screen.getAllByText("已报销").length).toBeGreaterThan(0);
    expect(screen.queryByText("进行中项目 1")).not.toBeInTheDocument();

    await user.type(screen.getByLabelText("搜索项目"), "9");
    expect(screen.getByText("已完结项目 9")).toBeInTheDocument();
    expect(screen.queryByText("已完结项目 8")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "列表视图" }));
    expect(container.querySelector(".projects-results-list")).toBeInTheDocument();
  });
});
