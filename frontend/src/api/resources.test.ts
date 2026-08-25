import { afterEach, describe, expect, it, vi } from "vitest";
import { dashboardApi, documentsApi, invoicesApi, issuesApi, jobsApi, settingsApi, tripsApi } from "./resources";

describe("API DTO normalization", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("maps the backend TripRead counters and date candidates into the UI summary", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([{
      id: "trip-1",
      title: "北京差旅",
      source_label: "七月",
      traveler_name: "张三",
      company_name: "示例公司",
      company_tax_id: "91310000TEST",
      project_type: "MIXED",
      status: "ANALYZED",
      input_start_date: "2026-07-01",
      input_end_date: "2026-07-02",
      inferred_start_date: "2026-07-03",
      inferred_end_date: "2026-07-04",
      confirmed_start_date: null,
      confirmed_end_date: null,
      trip_days: 2,
      date_confidence: 0.95,
      date_evidence: ["使用城际交通票据的最早和最晚日期"],
      route_text: "北京 - 上海",
      invoice_total_amount: "100.00",
      allowance_amount: "180.00",
      grand_total_amount: "280.00",
      document_count: 2,
      issue_count: 1,
      summary: {
        invoice_total_amount: "100.00",
        allowance_amount: "180.00",
        grand_total_amount: "280.00",
        document_count: 2,
        review_count: 3,
        issue_count: 1,
      },
      created_at: "2026-07-01T00:00:00Z",
      updated_at: "2026-07-02T00:00:00Z",
    }]), { status: 200, headers: { "content-type": "application/json" } })));

    const [trip] = await tripsApi.list();

    expect(trip).toMatchObject({
      project_type: "MIXED",
      company_tax_id: "91310000TEST",
      input_start_date: "2026-07-01",
      inferred_start_date: "2026-07-03",
      confirmed_start_date: null,
      trip_days: 2,
      date_confidence: 0.95,
      date_evidence: ["使用城际交通票据的最早和最晚日期"],
    });
    expect(trip.start_date).toBe("2026-07-03");
    expect(trip.summary).toMatchObject({ document_count: 2, review_count: 3, issue_count: 1, grand_total_amount: 280 });
  });

  it("normalizes Decimal expense summary fields for the distribution panel", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      trip_id: "trip-1",
      intercity_transport_amount: "605.30",
      local_transport_amount: "35.00",
      lodging_amount: "450.00",
      meal_amount: "88.20",
      refund_change_fee: "0.00",
      travel_insurance_amount: "20.00",
      other_amount: "0.00",
      invoice_total_amount: "1198.50",
      trip_days: 3,
      daily_allowance: "180.00",
      allowance_amount: "540.00",
      grand_total_amount: "1738.50",
    }), { status: 200, headers: { "content-type": "application/json" } })));

    const summary = await tripsApi.summary("trip-1");

    expect(summary).toMatchObject({
      intercity_transport_amount: 605.3,
      lodging_amount: 450,
      allowance_amount: 540,
      grand_total_amount: 1738.5,
    });
  });

  it("deletes an owned project through the versioned API", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await tripsApi.remove("trip-1");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/trips/trip-1",
      expect.objectContaining({ method: "DELETE", credentials: "include" }),
    );
  });

  it("normalizes the owned annual dashboard totals, trends, and project detail rows", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      year: 2026,
      available_years: [2026, 2025],
      total_project_count: 2,
      travel_project_count: 1,
      daily_project_count: 1,
      total_trip_days: 4,
      total_invoice_amount: "680.50",
      total_income_amount: "540.00",
      reimbursed_amount: "80.00",
      unreimbursed_amount: "1220.50",
      monthly_trends: [{ month: 7, project_count: 2, invoice_amount: "680.50", allowance_amount: "540.00" }],
      category_summary: { intercity_transport_amount: "520.50", lodging_amount: "160.00" },
      city_summary: [{ city: "北京", count: 3 }],
      reimbursement_summary: { THIS_TRIP: 1, ALREADY_REIMBURSED: 0, PARTIAL_REIMBURSED: 1, NOT_REIMBURSED: 0, PENDING: 0 },
      recent_projects: [{
        id: "trip-1",
        title: "北京客户拜访",
        project_type: "TRAVEL",
        status: "READY_FOR_REVIEW",
        reimbursement_status: "PARTIAL_REIMBURSED",
        start_date: "2026-07-01",
        end_date: "2026-07-03",
        route_text: "南京 -> 北京",
        document_count: 4,
        trip_days: 3,
        invoice_total_amount: "680.50",
        allowance_amount: "540.00",
        grand_total_amount: "1220.50",
      }],
    }), { status: 200, headers: { "content-type": "application/json" } })));

    const dashboard = await dashboardApi.yearly(2026);

    expect(dashboard).toMatchObject({
      year: 2026,
      total_invoice_amount: 680.5,
      total_income_amount: 540,
      category_summary: { intercity_transport_amount: 520.5 },
      city_summary: [{ city: "北京", count: 3 }],
    });
    expect(dashboard.recent_projects[0]).toMatchObject({
      id: "trip-1",
      project_type: "TRAVEL",
      grand_total_amount: 1220.5,
    });
  });

  it("converts Decimal strings in per-user settings before they reach numeric inputs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      default_company_name: null,
      default_company_tax_id: null,
      default_traveler_name: "张三",
      daily_allowance: "180.00",
      include_start_day: true,
      include_end_day: true,
      lodging_limit_per_day: "450.50",
      require_return_ticket: false,
      require_lodging_invoice: true,
      remote_provider_configured: false,
      remote_provider_enabled: false,
    }), { status: 200, headers: { "content-type": "application/json" } })));

    const settings = await settingsApi.get();

    expect(settings.daily_allowance).toBe(180);
    expect(settings.lodging_limit_per_day).toBe(450.5);
  });

  it("keeps server-resolved issues out of the active issue view while retaining their filename", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([{
      id: "issue-1",
      trip_id: "trip-1",
      document_id: "document-1",
      issue_type: "MISSING_AMOUNT",
      severity: "WARNING",
      message: "金额待确认",
      suggestion: null,
      resolution_status: "AUTO_CLEARED",
      resolved: true,
      ignored: false,
      resolution_note: "规则已不再满足",
      file_name: "receipt.pdf",
    }]), { status: 200, headers: { "content-type": "application/json" } })));

    const [issue] = await issuesApi.list("trip-1");

    expect(issue.resolved).toBe(true);
    expect(issue.file_name).toBe("receipt.pdf");
  });

  it("uses the full invoice endpoint for transport and lodging edits", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([{
      id: "invoice-1",
      invoice_type: "TRAIN_TICKET",
      expense_category: "INTERCITY_TRANSPORT",
      total_amount: "605.30",
      confirmed_amount: null,
      reimbursement_status: "THIS_TRIP",
      include_in_summary: true,
      review_status: "MANUALLY_CONFIRMED",
      document_role: "OFFICIAL_INVOICE",
      invoice_number: "E123456",
      invoice_date: "2026-07-03",
      business_date: "2026-07-02",
      seller_name: "铁路客运",
      buyer_name: "示例公司",
      from_city: "北京",
      to_city: "上海",
      from_place: "北京南",
      to_place: "上海虹桥",
      transport_no: "G123",
      depart_time_str: "08:00",
      seat_class: "二等座",
      hotel_name: null,
      checkin_date: null,
      checkout_date: null,
      nights: null,
      note: "人工确认",
    }]), { status: 200, headers: { "content-type": "application/json" } })));

    const [invoice] = await invoicesApi.list("trip-1");

    expect(invoice).toMatchObject({
      total_amount: 605.3,
      from_place: "北京南",
      transport_no: "G123",
      seat_class: "二等座",
    });
  });

  it("normalizes older compact document invoices without leaking undefined form values", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([{
      id: "document-1",
      trip_id: "trip-1",
      original_filename: "receipt.pdf",
      relative_path: null,
      size_bytes: 512,
      mime_type: "application/pdf",
      document_type: "PDF",
      upload_status: "UPLOADED",
      processing_status: "SUCCEEDED",
      ocr_status: "SUCCEEDED",
      error_code: null,
      error_message: null,
      created_at: "2026-07-03T00:00:00Z",
      invoice_id: "invoice-1",
      issue_count: 0,
      invoice: {
        id: "invoice-1",
        invoice_type: "GENERAL_INVOICE",
        expense_category: "OTHER",
        total_amount: "20.00",
        confirmed_amount: null,
        reimbursement_status: "PENDING",
        include_in_summary: false,
        review_status: "NEEDS_REVIEW",
        document_role: "OFFICIAL_INVOICE",
        invoice_number: null,
        invoice_date: null,
        business_date: null,
        seller_name: null,
        buyer_name: null,
        note: null,
      },
    }]), { status: 200, headers: { "content-type": "application/json" } })));

    const [document] = await documentsApi.list("trip-1");

    expect(document.invoice).toMatchObject({ total_amount: 20, from_city: null, hotel_name: null, nights: null });
  });

  it("loads every server page while preserving query cancellation", async () => {
    const makeDocument = (id: number) => ({
      id: `document-${id}`,
      trip_id: "trip-1",
      original_filename: `receipt-${id}.pdf`,
      relative_path: null,
      size_bytes: 512,
      mime_type: "application/pdf",
      document_type: "PDF",
      upload_status: "UPLOADED",
      processing_status: "SUCCEEDED",
      ocr_status: "SUCCEEDED",
      error_code: null,
      error_message: null,
      created_at: "2026-07-03T00:00:00Z",
      invoice_id: null,
      issue_count: 0,
    });
    const fetchMock = vi.fn().mockImplementation((input: string) => {
      const page = new URL(input, "http://test").searchParams.get("page");
      const rows = page === "1" ? Array.from({ length: 200 }, (_, index) => makeDocument(index)) : [makeDocument(200)];
      return Promise.resolve(new Response(JSON.stringify(rows), { status: 200, headers: { "content-type": "application/json" } }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const abort = new AbortController();
    const documents = await documentsApi.list("trip-1", abort.signal);

    expect(documents).toHaveLength(201);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][1]).toEqual(expect.objectContaining({ signal: abort.signal }));
  });

  it("prefers backend progress messages and explicit retryability", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify([{
      id: "job-1",
      trip_id: "trip-1",
      document_id: "document-1",
      kind: "PROCESS_DOCUMENT",
      state: "FAILED",
      progress: 60,
      attempt: 3,
      max_attempts: 3,
      message: "任务失败",
      progress_message: "正在提取 PDF 原生文字",
      error_code: "OCR_TIMEOUT",
      error_message: "OCR 超时",
      retryable: true,
      created_at: "2026-07-03T00:00:00Z",
      started_at: "2026-07-03T00:01:00Z",
      finished_at: "2026-07-03T00:02:00Z",
    }]), { status: 200, headers: { "content-type": "application/json" } })));

    const [job] = await jobsApi.list("trip-1");

    expect(job.progress_message).toBe("正在提取 PDF 原生文字");
    expect(job.retryable).toBe(true);
  });
});
