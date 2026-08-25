import { expect, test } from "@playwright/test";

const user = { id: "user-1", email: "user@example.com", is_admin: false };

const trip = {
  id: "trip-1",
  title: "北京客户拜访",
  source_label: "2026 年 7 月",
  traveler_name: "张三",
  company_name: "示例公司",
  company_tax_id: "91310000TEST",
  project_type: "TRAVEL",
  status: "ANALYZED",
  reimbursement_status: "NOT_REIMBURSED",
  input_start_date: "2026-07-01",
  input_end_date: "2026-07-02",
  inferred_start_date: "2026-07-01",
  inferred_end_date: "2026-07-02",
  confirmed_start_date: null,
  confirmed_end_date: null,
  trip_days: 2,
  date_confidence: 0.95,
  date_evidence: ["使用城际交通票据的最早和最晚日期"],
  start_date: "2026-07-01",
  end_date: "2026-07-02",
  route_text: "北京 - 上海",
  invoice_total_amount: "100.00",
  allowance_amount: "180.00",
  grand_total_amount: "280.00",
  document_count: 1,
  issue_count: 0,
  summary: {
    invoice_total_amount: "100.00",
    allowance_amount: "180.00",
    grand_total_amount: "280.00",
    reimbursement_total_amount: "280.00",
    reimbursed_total_amount: "0.00",
    unallocated_total_amount: "0.00",
    document_count: 1,
    review_count: 1,
    issue_count: 0,
  },
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-02T00:00:00Z",
};

const expenseSummary = {
  trip_id: "trip-1",
  intercity_transport_amount: "100.00",
  local_transport_amount: "0.00",
  lodging_amount: "0.00",
  meal_amount: "0.00",
  refund_change_fee: "0.00",
  travel_insurance_amount: "0.00",
  other_amount: "0.00",
  invoice_total_amount: "100.00",
  trip_days: 2,
  daily_allowance: "180.00",
  allowance_amount: "180.00",
  grand_total_amount: "280.00",
  reimbursement_invoice_total_amount: "100.00",
  reimbursement_allowance_amount: "180.00",
  reimbursement_total_amount: "280.00",
  reimbursed_invoice_amount: "0.00",
  reimbursed_allowance_amount: "0.00",
  reimbursed_total_amount: "0.00",
  unallocated_total_amount: "0.00",
};

const yearlyDashboard = {
  year: 2026,
  available_years: [2026, 2025],
  total_project_count: 1,
  travel_project_count: 1,
  daily_project_count: 0,
  total_trip_days: 2,
  total_invoice_amount: "100.00",
  total_income_amount: "180.00",
  reimbursed_amount: "0.00",
  unreimbursed_amount: "280.00",
  monthly_trends: Array.from({ length: 12 }, (_, index) => ({
    month: index + 1,
    project_count: index === 6 ? 1 : 0,
    invoice_amount: index === 6 ? "100.00" : "0.00",
    allowance_amount: index === 6 ? "180.00" : "0.00",
  })),
  category_summary: {
    intercity_transport_amount: "100.00",
    local_transport_amount: "0.00",
    lodging_amount: "0.00",
    meal_amount: "0.00",
    refund_change_fee: "0.00",
    travel_insurance_amount: "0.00",
    other_amount: "0.00",
  },
  city_summary: [{ city: "北京", count: 1 }, { city: "上海", count: 1 }],
  reimbursement_summary: { THIS_TRIP: 1, ALREADY_REIMBURSED: 0, PARTIAL_REIMBURSED: 0, NOT_REIMBURSED: 0, PENDING: 0 },
  recent_projects: [{
    id: "trip-1",
    title: "北京客户拜访",
    project_type: "TRAVEL",
    status: "ANALYZED",
    reimbursement_status: "THIS_TRIP",
    start_date: "2026-07-01",
    end_date: "2026-07-02",
    route_text: "北京 -> 上海",
    document_count: 1,
    trip_days: 2,
    invoice_total_amount: "100.00",
    allowance_amount: "180.00",
    grand_total_amount: "280.00",
  }],
};

const routeSegments = [{
  id: "segment-1",
  trip_id: "trip-1",
  invoice_id: "invoice-1",
  transport_type: "TRAIN",
  depart_date: "2026-07-01",
  depart_time: "08:00",
  from_city: "北京",
  to_city: "上海",
  from_place: "北京南",
  to_place: "上海虹桥",
  transport_no: "G123",
  seat_class: "二等座",
  amount: "100.00",
  confidence: 0.95,
}];

const invoice = {
  id: "invoice-1",
  invoice_type: "GENERAL_INVOICE",
  expense_category: "MEAL",
  total_amount: "100.00",
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
  from_city: null,
  to_city: null,
  from_place: null,
  to_place: null,
  transport_no: null,
  depart_time_str: null,
  seat_class: null,
  hotel_name: null,
  checkin_date: null,
  checkout_date: null,
  nights: null,
  note: null,
};

const detailedInvoice = {
  ...invoice,
  from_city: "北京",
  to_city: "上海",
  from_place: "北京南",
  to_place: "上海虹桥",
  transport_no: "G123",
  depart_time_str: "08:00",
  seat_class: "二等座",
};

function documentRecord(id: string, filename: string) {
  return {
    id,
    trip_id: "trip-1",
    original_filename: filename,
    relative_path: null,
    size_bytes: 512,
    mime_type: "application/pdf",
    document_type: "INVOICE",
    upload_status: "UPLOADED",
    processing_status: "PENDING",
    ocr_status: "PENDING",
    error_code: null,
    error_message: null,
    issue_count: 0,
    created_at: "2026-07-02T00:00:00Z",
    invoice,
  };
}

function jobRecord(id: string) {
  return {
    id,
    trip_id: "trip-1",
    document_id: null,
    kind: "REPROCESS_DOCUMENT",
    state: "QUEUED",
    progress: 0,
    attempt: 0,
    max_attempts: 3,
    message: "已排队",
    error_code: null,
    error_message: null,
    created_at: "2026-07-02T00:00:00Z",
    started_at: null,
    finished_at: null,
  };
}

test("logs in, opens a project, and uploads a browser-selected document", async ({ page }) => {
  let authenticated = false;
  let uploaded = false;
  let deleted = false;
  let invoicePatch: Record<string, unknown> | null = null;
  let tripPatch: Record<string, unknown> | null = null;

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (path.endsWith("/auth/me")) {
      if (!authenticated) return json({ code: "SESSION_EXPIRED" }, 401);
      return json({ user, csrf_token: "csrf-token" });
    }
    if (path.endsWith("/auth/login") && request.method() === "POST") {
      authenticated = true;
      return json({ user, csrf_token: "csrf-token" });
    }
    if (path.endsWith("/trips") && request.method() === "GET") return json(deleted ? [] : [trip]);
    if (path.endsWith("/dashboard/yearly") && request.method() === "GET") return json(yearlyDashboard);
    if (path.endsWith("/trips/trip-1") && request.method() === "DELETE") {
      deleted = true;
      return route.fulfill({ status: 204, body: "" });
    }
    if (path.endsWith("/trips/trip-1") && request.method() === "GET") return json(trip);
    if (path.endsWith("/trips/trip-1") && request.method() === "PATCH") {
      tripPatch = request.postDataJSON() as Record<string, unknown>;
      return json({ ...trip, ...tripPatch, start_date: tripPatch.confirmed_start_date || trip.start_date, end_date: tripPatch.confirmed_end_date || trip.end_date });
    }
    if (path.endsWith("/trips/trip-1/summary") && request.method() === "GET") return json(expenseSummary);
    if (path.endsWith("/trips/trip-1/route-segments") && request.method() === "GET") return json(routeSegments);
    if (path.endsWith("/trips/trip-1/documents") && request.method() === "GET") {
      return json(uploaded ? [documentRecord("document-1", "receipt.pdf"), documentRecord("document-2", "new-receipt.pdf")] : [documentRecord("document-1", "receipt.pdf")]);
    }
    if (path.endsWith("/trips/trip-1/jobs") && request.method() === "GET") return json([]);
    if (path.endsWith("/trips/trip-1/issues") && request.method() === "GET") return json([]);
    if (path.endsWith("/trips/trip-1/exports") && request.method() === "GET") return json([]);
    if (path.endsWith("/trips/trip-1/invoices") && request.method() === "GET") return json([detailedInvoice]);
    if (path.endsWith("/invoices/invoice-1") && request.method() === "PATCH") {
      invoicePatch = request.postDataJSON() as Record<string, unknown>;
      return json({ ...detailedInvoice, ...invoicePatch });
    }
    if (path.endsWith("/trips/trip-1/uploads") && request.method() === "POST") {
      uploaded = true;
      return json({ document: documentRecord("document-2", "new-receipt.pdf"), job: jobRecord("job-1"), duplicate: false }, 202);
    }
    return json({ message: `Unhandled mock route: ${request.method()} ${path}` }, 404);
  });

  await page.goto("/login");
  await page.getByLabel("账号").fill("user@example.com");
  await page.getByLabel("密码").fill("correct-password");
  await page.getByRole("button", { name: "登录" }).click();

  await expect(page.getByRole("heading", { name: "报销项目" })).toBeVisible();
  await page.getByRole("button", { name: "打开" }).click();
  await expect(page.getByRole("heading", { name: "北京客户拜访" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "费用与报销" })).toBeVisible();
  await expect(page.getByRole("button", { name: "开始识别与分析" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "报销文件" })).toBeVisible();
  await expect(page.getByText("项目总支出").first()).toBeVisible();
  await expect(page.getByText("本次待报销").first()).toBeVisible();
  await expect(page.getByText("G123")).toBeVisible();
  await page.getByText("项目资料与日期校验").click();
  await expect(page.getByLabel("日期确认").getByText("使用城际交通票据的最早和最晚日期")).toBeVisible();
  await page.getByLabel("确认覆盖开始日期").fill("2026-07-03");
  await page.getByLabel("确认覆盖结束日期").fill("2026-07-04");
  await page.getByRole("button", { name: "保存项目资料" }).click();
  await expect.poll(() => tripPatch?.confirmed_start_date).toBe("2026-07-03");
  await expect(page.locator(".document-table").getByText("receipt.pdf")).toBeVisible();

  await page.locator('input[type="file"]').first().setInputFiles({
    name: "new-receipt.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.4"),
  });
  await expect(page.getByText("new-receipt.pdf")).toBeVisible();
  await page.getByRole("button", { name: "上传 1 个文件" }).click();
  await expect(page.getByText("已上传，自动识别已排队")).toBeVisible();
  await expect(page.locator(".document-table").getByText("new-receipt.pdf")).toBeVisible();

  await page.getByRole("button", { name: "人工复核" }).first().click();
  await expect(page.getByLabel("车次或航班号")).toHaveValue("G123");
  await page.getByLabel("车次或航班号").fill("G456");
  await page.getByRole("button", { name: "保存复核结果" }).click();
  await expect.poll(() => invoicePatch?.transport_no).toBe("G456");

  await page.getByRole("link", { name: "年度出差" }).click();
  await expect(page.getByRole("heading", { name: "年度出差详情" })).toBeVisible();
  await expect(page.getByText("月度收支趋势")).toBeVisible();
  await expect(page.getByText("北京 -> 上海")).toBeVisible();
  await expect(page.getByText("城市排行")).toBeVisible();

  await page.getByRole("link", { name: "项目", exact: true }).click();
  await page.getByRole("button", { name: "删除项目：北京客户拜访" }).click();
  await expect(page.getByRole("dialog", { name: "删除项目" })).toContainText("北京客户拜访");
  await page.getByRole("button", { name: "确认删除" }).click();
  await expect(page.getByRole("heading", { name: "还没有项目" })).toBeVisible();
  expect(deleted).toBe(true);
});
