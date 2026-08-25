import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { tripsApi } from "../../api/resources";
import type { Trip, TripExpenseSummary } from "../../api/types";
import { TripHeader } from "./TripHeader";

vi.mock("../../api/resources", () => ({
  tripsApi: { update: vi.fn() },
}));

const trip: Trip = {
  id: "trip-1",
  title: "北京客户拜访",
  source_label: "七月差旅",
  traveler_name: "张三",
  company_name: "示例公司",
  company_tax_id: "91310000TEST",
  project_type: "TRAVEL",
  status: "READY_FOR_REVIEW",
  reimbursement_status: "NOT_REIMBURSED",
  input_start_date: "2026-07-01",
  input_end_date: "2026-07-03",
  inferred_start_date: "2026-07-02",
  inferred_end_date: "2026-07-04",
  confirmed_start_date: null,
  confirmed_end_date: null,
  trip_days: 3,
  date_confidence: 0.95,
  date_evidence: ["使用城际交通票据的最早和最晚日期"],
  start_date: "2026-07-02",
  end_date: "2026-07-04",
  route_text: "北京 -> 上海",
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-04T00:00:00Z",
  summary: {
    document_count: 4,
    review_count: 1,
    issue_count: 0,
    invoice_total_amount: 1000,
    allowance_amount: 180,
    grand_total_amount: 1180,
  },
};

const expenseSummary: TripExpenseSummary = {
  trip_id: trip.id,
  intercity_transport_amount: 1000,
  local_transport_amount: 0,
  lodging_amount: 0,
  meal_amount: 0,
  refund_change_fee: 0,
  travel_insurance_amount: 0,
  other_amount: 0,
  invoice_total_amount: 1000,
  trip_days: 3,
  daily_allowance: 60,
  allowance_amount: 180,
  grand_total_amount: 1180,
  reimbursement_invoice_total_amount: 1000,
  reimbursement_allowance_amount: 180,
  reimbursement_total_amount: 1180,
  reimbursed_invoice_amount: 0,
  reimbursed_allowance_amount: 0,
  reimbursed_total_amount: 0,
  unallocated_total_amount: 0,
};

function renderHeader(onChanged = vi.fn(), currentTrip = trip, currentSummary = expenseSummary) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <TripHeader trip={currentTrip} expenseSummary={currentSummary} summaryLoading={false} onChanged={onChanged} />
    </QueryClientProvider>,
  );
}

describe("TripHeader", () => {
  afterEach(cleanup);

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(tripsApi.update).mockResolvedValue(trip);
  });

  it("shows inference evidence and persists editable metadata and confirmed dates", async () => {
    const user = userEvent.setup();
    const onChanged = vi.fn();
    renderHeader(onChanged);

    await user.click(screen.getByText("项目资料与日期校验"));
    expect(screen.getByText("使用城际交通票据的最早和最晚日期")).toBeVisible();
    await user.clear(screen.getByLabelText("项目名称"));
    await user.type(screen.getByLabelText("项目名称"), "上海客户拜访");
    await user.clear(screen.getByLabelText("来源标签"));
    await user.type(screen.getByLabelText("来源标签"), "八月差旅");
    await user.clear(screen.getByLabelText("确认覆盖开始日期"));
    await user.type(screen.getByLabelText("确认覆盖开始日期"), "2026-08-10");
    await user.clear(screen.getByLabelText("确认覆盖结束日期"));
    await user.type(screen.getByLabelText("确认覆盖结束日期"), "2026-08-12");
    await user.click(screen.getByRole("button", { name: "保存项目资料" }));

    await waitFor(() => expect(tripsApi.update).toHaveBeenCalledWith("trip-1", expect.objectContaining({
      title: "上海客户拜访",
      source_label: "八月差旅",
      confirmed_start_date: "2026-08-10",
      confirmed_end_date: "2026-08-12",
      input_start_date: "2026-07-01",
      input_end_date: "2026-07-03",
    })));
    expect(onChanged).toHaveBeenCalled();
  });

  it("clears confirmed dates so the server returns to inferred dates", async () => {
    const user = userEvent.setup();
    renderHeader(vi.fn(), { ...trip, confirmed_start_date: "2026-07-02", confirmed_end_date: "2026-07-04" });

    await user.click(screen.getByText("项目资料与日期校验"));
    await user.click(screen.getByRole("button", { name: "清除确认覆盖并跟随系统推断" }));
    await user.click(screen.getByRole("button", { name: "保存项目资料" }));

    await waitFor(() => expect(tripsApi.update).toHaveBeenCalledWith("trip-1", expect.objectContaining({
      confirmed_start_date: null,
      confirmed_end_date: null,
    })));
  });

  it("uses the authoritative expense summary instead of the trip list snapshot", () => {
    renderHeader(vi.fn(), {
      ...trip,
      summary: { ...trip.summary!, grand_total_amount: 9999, reimbursement_total_amount: 8888, reimbursed_total_amount: 7777 },
    }, expenseSummary);

    expect(screen.getAllByText("¥1,180.00")).toHaveLength(2);
    expect(screen.queryByText("¥9,999.00")).not.toBeInTheDocument();
    expect(screen.queryByText("¥8,888.00")).not.toBeInTheDocument();
  });
});
