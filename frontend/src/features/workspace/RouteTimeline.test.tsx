import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RouteSegment, Trip } from "../../api/types";
import { RouteTimeline } from "./RouteTimeline";

const trip: Trip = {
  id: "trip-1",
  title: "北京开会",
  source_label: null,
  traveler_name: null,
  company_name: null,
  company_tax_id: null,
  project_type: "TRAVEL",
  status: "READY_FOR_REVIEW",
  reimbursement_status: "NOT_REIMBURSED",
  input_start_date: null,
  input_end_date: null,
  inferred_start_date: "2026-07-01",
  inferred_end_date: "2026-07-01",
  confirmed_start_date: null,
  confirmed_end_date: null,
  trip_days: 1,
  date_confidence: 0.95,
  date_evidence: ["使用城际交通票据的最早和最晚日期"],
  start_date: "2026-07-01",
  end_date: "2026-07-01",
  route_text: "南京 -> 西安",
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z",
  summary: null,
};

function segment(id: string, time: string | null, from: string, to: string): RouteSegment {
  return {
    id,
    trip_id: trip.id,
    invoice_id: `invoice-${id}`,
    transport_type: "TRAIN",
    depart_date: "2026-07-01",
    depart_time: time,
    from_city: from,
    to_city: to,
    from_place: `${from}站`,
    to_place: `${to}站`,
    transport_no: `G${id}`,
    seat_class: "二等座",
    amount: 100,
    confidence: 0.95,
  };
}

describe("RouteTimeline", () => {
  it("uses chronologically sorted ticket segments for the route headline instead of stale route text", () => {
    const { container } = render(
      <RouteTimeline
        trip={trip}
        loading={false}
        segments={[
          segment("2136", "21:36", "天津", "上海"),
          segment("1831", "18:31", "济南", "北京"),
          segment("1915", "19:15", "北京", "天津"),
        ]}
      />,
    );

    expect(screen.getByLabelText("交通路线：济南至北京至天津至上海")).toBeVisible();
    expect(screen.queryByText("南京 -> 西安")).not.toBeInTheDocument();
    expect(Array.from(container.querySelectorAll(".route-ticket-time strong")).map((element) => element.textContent)).toEqual(["18:31", "19:15", "21:36"]);
  });

  it("orders non-padded times numerically and keeps unknown times last", () => {
    const { container } = render(
      <RouteTimeline
        trip={trip}
        loading={false}
        segments={[
          segment("late", "18:00", "北京", "天津"),
          segment("unknown", null, "天津", "上海"),
          segment("early", "8:30", "济南", "北京"),
        ]}
      />,
    );

    expect(Array.from(container.querySelectorAll(".route-ticket-time strong")).map((element) => element.textContent)).toEqual(["8:30", "18:00", "--:--"]);
  });
});
