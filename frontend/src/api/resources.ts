import {
  ApiError,
  apiRequest,
  apiUrl,
  authenticatedBlob,
  authenticatedDownload,
  getCsrfToken,
  messageFromApiBody,
  setCsrfToken,
} from "./http";
import type {
  AnnualProject,
  AuthSession,
  CitySummary,
  CreateTripInput,
  DocumentInvoice,
  DocumentRecord,
  ExportRecord,
  InvoiceUpdateInput,
  Job,
  RouteSegment,
  ReviewIssue,
  Trip,
  TripExpenseSummary,
  UpdateIssueInput,
  UpdateSettingsInput,
  UpdateTripInput,
  UploadReceipt,
  UserSettings,
  YearlyDashboard,
} from "./types";

interface ApiTripRead {
  id: string;
  title: string;
  source_label: string | null;
  traveler_name: string | null;
  company_name: string | null;
  company_tax_id?: string | null;
  project_type: string;
  status: string;
  reimbursement_status?: string;
  input_start_date: string | null;
  input_end_date: string | null;
  inferred_start_date: string | null;
  inferred_end_date: string | null;
  confirmed_start_date: string | null;
  confirmed_end_date: string | null;
  trip_days?: number | null;
  date_confidence?: number | string | null;
  date_evidence?: string[] | null;
  start_date?: string | null;
  end_date?: string | null;
  route_text: string | null;
  invoice_total_amount: number | string;
  allowance_amount: number | string;
  grand_total_amount: number | string;
  document_count: number;
  issue_count: number;
  summary?: {
    invoice_total_amount: number | string;
    allowance_amount: number | string;
    grand_total_amount: number | string;
    reimbursement_total_amount?: number | string;
    reimbursed_total_amount?: number | string;
    unallocated_total_amount?: number | string;
    document_count: number;
    review_count: number;
    issue_count: number;
  } | null;
  created_at: string;
  updated_at: string;
}

interface ApiDocumentRead {
  id: string;
  trip_id: string;
  original_filename: string;
  relative_path: string | null;
  size_bytes: number;
  sha256?: string | null;
  mime_type: string;
  document_type: string;
  upload_status: string;
  processing_status: string;
  ocr_status: string;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  invoice_id: string | null;
  issue_count: number;
  invoice?: ApiInvoiceRead | null;
}

interface ApiTripExpenseSummary {
  trip_id: string;
  intercity_transport_amount: number | string;
  local_transport_amount: number | string;
  lodging_amount: number | string;
  meal_amount: number | string;
  refund_change_fee: number | string;
  travel_insurance_amount: number | string;
  other_amount: number | string;
  invoice_total_amount: number | string;
  trip_days: number;
  daily_allowance: number | string;
  allowance_amount: number | string;
  grand_total_amount: number | string;
  reimbursement_invoice_total_amount?: number | string;
  reimbursement_allowance_amount?: number | string;
  reimbursement_total_amount?: number | string;
  reimbursed_invoice_amount?: number | string;
  reimbursed_allowance_amount?: number | string;
  reimbursed_total_amount?: number | string;
  unallocated_total_amount?: number | string;
}

interface ApiAnnualProjectRead {
  id: string;
  title: string;
  project_type: string;
  status: string;
  reimbursement_status: string;
  start_date: string | null;
  end_date: string | null;
  route_text: string | null;
  document_count: number;
  trip_days: number;
  invoice_total_amount: number | string;
  allowance_amount: number | string;
  grand_total_amount: number | string;
}

interface ApiYearlyDashboardRead {
  year: number;
  available_years: number[];
  total_project_count: number;
  travel_project_count: number;
  daily_project_count: number;
  total_trip_days: number;
  total_invoice_amount: number | string;
  total_income_amount?: number | string;
  // Accept the pre-income-contract field during a rolling frontend/API release.
  total_allowance_amount?: number | string;
  reimbursed_amount: number | string;
  unreimbursed_amount: number | string;
  monthly_trends: Array<{
    month: number;
    project_count: number;
    invoice_amount: number | string;
    allowance_amount: number | string;
  }>;
  category_summary: Record<string, number | string>;
  city_summary: CitySummary[];
  reimbursement_summary: Record<string, number>;
  recent_projects: ApiAnnualProjectRead[];
}

interface ApiRouteSegmentRead {
  id: string;
  trip_id: string;
  invoice_id: string;
  transport_type: string;
  depart_date: string | null;
  depart_time: string | null;
  from_city: string | null;
  to_city: string | null;
  from_place: string | null;
  to_place: string | null;
  transport_no: string | null;
  seat_class: string | null;
  amount: number | string | null;
  confidence: number | string;
}

interface ApiInvoiceRead {
  id: string;
  invoice_type: string | null;
  expense_category: string | null;
  total_amount: number | string | null;
  confirmed_amount: number | string | null;
  reimbursement_status: string;
  include_in_summary: boolean;
  review_status: string;
  document_role: string;
  invoice_number: string | null;
  invoice_date: string | null;
  business_date: string | null;
  seller_name: string | null;
  buyer_name: string | null;
  from_city?: string | null;
  to_city?: string | null;
  from_place?: string | null;
  to_place?: string | null;
  transport_no?: string | null;
  depart_time_str?: string | null;
  seat_class?: string | null;
  hotel_name?: string | null;
  checkin_date?: string | null;
  checkout_date?: string | null;
  nights?: number | null;
  note: string | null;
}

interface ApiJobRead {
  id: string;
  trip_id: string | null;
  document_id: string | null;
  kind: string;
  state: string;
  progress: number;
  attempt: number;
  max_attempts: number;
  message: string | null;
  progress_message?: string | null;
  error_code: string | null;
  error_message: string | null;
  retryable?: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

interface ApiUploadResponse {
  document: ApiDocumentRead;
  job: ApiJobRead | null;
  job_id?: string | null;
  duplicate: boolean;
}

interface ApiIssueRead {
  id: string;
  trip_id: string;
  document_id: string | null;
  issue_type: string;
  severity: string;
  message: string;
  suggestion: string | null;
  resolution_status: string;
  resolved?: boolean;
  ignored?: boolean;
  resolution_note: string | null;
  file_name?: string | null;
}

interface ApiExportRead {
  id: string;
  trip_id: string;
  job_id: string | null;
  format: string;
  status: string;
  original_filename: string | null;
  created_at: string;
  expires_at: string | null;
}

interface ApiUserSettingsRead {
  default_company_name: string | null;
  default_company_tax_id: string | null;
  default_traveler_name: string | null;
  daily_allowance: number | string;
  include_start_day: boolean;
  include_end_day: boolean;
  lodging_limit_per_day: number | string | null;
  require_return_ticket: boolean;
  require_lodging_invoice: boolean;
  remote_provider_configured: boolean;
  remote_provider_enabled: boolean;
}

function toNumber(value: number | string, fallback = 0): number {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toNullableNumber(value: number | string | null): number | null {
  if (value == null) return null;
  const parsed = toNumber(value, Number.NaN);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeInvoice(raw: ApiInvoiceRead): DocumentInvoice {
  return {
    id: raw.id,
    invoice_type: raw.invoice_type,
    expense_category: raw.expense_category,
    total_amount: toNullableNumber(raw.total_amount),
    confirmed_amount: toNullableNumber(raw.confirmed_amount),
    reimbursement_status: raw.reimbursement_status,
    include_in_summary: raw.include_in_summary,
    review_status: raw.review_status,
    document_role: raw.document_role,
    invoice_number: raw.invoice_number,
    invoice_date: raw.invoice_date,
    business_date: raw.business_date,
    seller_name: raw.seller_name,
    buyer_name: raw.buyer_name,
    from_city: raw.from_city ?? null,
    to_city: raw.to_city ?? null,
    from_place: raw.from_place ?? null,
    to_place: raw.to_place ?? null,
    transport_no: raw.transport_no ?? null,
    depart_time_str: raw.depart_time_str ?? null,
    seat_class: raw.seat_class ?? null,
    hotel_name: raw.hotel_name ?? null,
    checkin_date: raw.checkin_date ?? null,
    checkout_date: raw.checkout_date ?? null,
    nights: raw.nights ?? null,
    note: raw.note,
  };
}

function normalizeSettings(raw: ApiUserSettingsRead): UserSettings {
  return {
    default_company_name: raw.default_company_name,
    default_company_tax_id: raw.default_company_tax_id,
    default_traveler_name: raw.default_traveler_name,
    daily_allowance: toNumber(raw.daily_allowance),
    include_start_day: raw.include_start_day,
    include_end_day: raw.include_end_day,
    lodging_limit_per_day: toNullableNumber(raw.lodging_limit_per_day),
    require_return_ticket: raw.require_return_ticket,
    require_lodging_invoice: raw.require_lodging_invoice,
    remote_provider_configured: raw.remote_provider_configured,
    remote_provider_enabled: raw.remote_provider_enabled,
  };
}

function normalizeTrip(raw: ApiTripRead): Trip {
  const summary = raw.summary;
  return {
    id: raw.id,
    title: raw.title,
    source_label: raw.source_label,
    traveler_name: raw.traveler_name,
    company_name: raw.company_name,
    company_tax_id: raw.company_tax_id ?? null,
    project_type: raw.project_type === "DAILY" || raw.project_type === "MIXED" ? raw.project_type : "TRAVEL",
    status: raw.status,
    reimbursement_status: raw.reimbursement_status || "NOT_REIMBURSED",
    input_start_date: raw.input_start_date,
    input_end_date: raw.input_end_date,
    inferred_start_date: raw.inferred_start_date,
    inferred_end_date: raw.inferred_end_date,
    confirmed_start_date: raw.confirmed_start_date,
    confirmed_end_date: raw.confirmed_end_date,
    trip_days: raw.trip_days ?? null,
    date_confidence: toNumber(raw.date_confidence ?? 0),
    date_evidence: raw.date_evidence || [],
    start_date: raw.start_date || raw.confirmed_start_date || raw.inferred_start_date || raw.input_start_date,
    end_date: raw.end_date || raw.confirmed_end_date || raw.inferred_end_date || raw.input_end_date,
    route_text: raw.route_text,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    summary: {
      document_count: summary?.document_count ?? raw.document_count,
      review_count: summary?.review_count ?? 0,
      issue_count: summary?.issue_count ?? raw.issue_count,
      invoice_total_amount: toNumber(summary?.invoice_total_amount ?? raw.invoice_total_amount),
      allowance_amount: toNumber(summary?.allowance_amount ?? raw.allowance_amount),
      grand_total_amount: toNumber(summary?.grand_total_amount ?? raw.grand_total_amount),
      reimbursement_total_amount: toNumber(summary?.reimbursement_total_amount ?? summary?.grand_total_amount ?? raw.grand_total_amount),
      reimbursed_total_amount: toNumber(summary?.reimbursed_total_amount ?? 0),
      unallocated_total_amount: toNumber(summary?.unallocated_total_amount ?? 0),
    },
  };
}

function normalizeRouteSegment(raw: ApiRouteSegmentRead): RouteSegment {
  return {
    id: raw.id,
    trip_id: raw.trip_id,
    invoice_id: raw.invoice_id,
    transport_type: raw.transport_type,
    depart_date: raw.depart_date,
    depart_time: raw.depart_time,
    from_city: raw.from_city,
    to_city: raw.to_city,
    from_place: raw.from_place,
    to_place: raw.to_place,
    transport_no: raw.transport_no,
    seat_class: raw.seat_class,
    amount: toNullableNumber(raw.amount),
    confidence: toNumber(raw.confidence),
  };
}

function normalizeTripExpenseSummary(raw: ApiTripExpenseSummary): TripExpenseSummary {
  return {
    trip_id: raw.trip_id,
    intercity_transport_amount: toNumber(raw.intercity_transport_amount),
    local_transport_amount: toNumber(raw.local_transport_amount),
    lodging_amount: toNumber(raw.lodging_amount),
    meal_amount: toNumber(raw.meal_amount),
    refund_change_fee: toNumber(raw.refund_change_fee),
    travel_insurance_amount: toNumber(raw.travel_insurance_amount),
    other_amount: toNumber(raw.other_amount),
    invoice_total_amount: toNumber(raw.invoice_total_amount),
    trip_days: raw.trip_days,
    daily_allowance: toNumber(raw.daily_allowance),
    allowance_amount: toNumber(raw.allowance_amount),
    grand_total_amount: toNumber(raw.grand_total_amount),
    reimbursement_invoice_total_amount: toNumber(raw.reimbursement_invoice_total_amount ?? raw.invoice_total_amount),
    reimbursement_allowance_amount: toNumber(raw.reimbursement_allowance_amount ?? raw.allowance_amount),
    reimbursement_total_amount: toNumber(raw.reimbursement_total_amount ?? raw.grand_total_amount),
    reimbursed_invoice_amount: toNumber(raw.reimbursed_invoice_amount ?? 0),
    reimbursed_allowance_amount: toNumber(raw.reimbursed_allowance_amount ?? 0),
    reimbursed_total_amount: toNumber(raw.reimbursed_total_amount ?? 0),
    unallocated_total_amount: toNumber(raw.unallocated_total_amount ?? 0),
  };
}

function normalizeAnnualProject(raw: ApiAnnualProjectRead): AnnualProject {
  return {
    id: raw.id,
    title: raw.title,
    project_type: raw.project_type === "DAILY" || raw.project_type === "MIXED" ? raw.project_type : "TRAVEL",
    status: raw.status,
    reimbursement_status: raw.reimbursement_status,
    start_date: raw.start_date,
    end_date: raw.end_date,
    route_text: raw.route_text,
    document_count: raw.document_count,
    trip_days: raw.trip_days,
    invoice_total_amount: toNumber(raw.invoice_total_amount),
    allowance_amount: toNumber(raw.allowance_amount),
    grand_total_amount: toNumber(raw.grand_total_amount),
  };
}

function normalizeYearlyDashboard(raw: ApiYearlyDashboardRead): YearlyDashboard {
  return {
    year: raw.year,
    available_years: raw.available_years,
    total_project_count: raw.total_project_count,
    travel_project_count: raw.travel_project_count,
    daily_project_count: raw.daily_project_count,
    total_trip_days: raw.total_trip_days,
    total_invoice_amount: toNumber(raw.total_invoice_amount),
    total_income_amount: toNumber(raw.total_income_amount ?? raw.total_allowance_amount ?? 0),
    reimbursed_amount: toNumber(raw.reimbursed_amount),
    unreimbursed_amount: toNumber(raw.unreimbursed_amount),
    monthly_trends: raw.monthly_trends.map((item) => ({
      month: item.month,
      project_count: item.project_count,
      invoice_amount: toNumber(item.invoice_amount),
      allowance_amount: toNumber(item.allowance_amount),
    })),
    category_summary: Object.fromEntries(
      Object.entries(raw.category_summary).map(([key, value]) => [key, toNumber(value)]),
    ),
    city_summary: raw.city_summary,
    reimbursement_summary: raw.reimbursement_summary,
    recent_projects: raw.recent_projects.map(normalizeAnnualProject),
  };
}

function normalizeDocument(raw: ApiDocumentRead): DocumentRecord {
  return {
    id: raw.id,
    trip_id: raw.trip_id,
    original_filename: raw.original_filename,
    relative_path: raw.relative_path,
    size_bytes: raw.size_bytes,
    sha256: raw.sha256 || null,
    mime_type: raw.mime_type,
    upload_status: raw.upload_status as DocumentRecord["upload_status"],
    processing_status: raw.processing_status,
    ocr_status: raw.ocr_status,
    document_type: raw.document_type,
    error_code: raw.error_code,
    error_message: raw.error_message,
    issue_count: raw.issue_count,
    created_at: raw.created_at,
    invoice: raw.invoice ? normalizeInvoice(raw.invoice) : null,
  };
}

function normalizeJob(raw: ApiJobRead): Job {
  return {
    id: raw.id,
    trip_id: raw.trip_id,
    document_id: raw.document_id,
    kind: raw.kind,
    state: raw.state as Job["state"],
    progress: raw.progress,
    progress_message: raw.progress_message ?? raw.message,
    error_code: raw.error_code,
    error_message: raw.error_message,
    retryable: raw.retryable ?? (raw.state === "FAILED" && raw.attempt < raw.max_attempts),
    attempt: raw.attempt,
    max_attempts: raw.max_attempts,
    created_at: raw.created_at,
    updated_at: raw.finished_at || raw.started_at || raw.created_at,
  };
}

function normalizeIssue(raw: ApiIssueRead): ReviewIssue {
  return {
    id: raw.id,
    trip_id: raw.trip_id,
    document_id: raw.document_id,
    issue_type: raw.issue_type,
    severity: raw.severity === "ERROR" || raw.severity === "WARNING" ? raw.severity : "INFO",
    message: raw.message,
    suggestion: raw.suggestion,
    resolved: raw.resolved ?? raw.resolution_status !== "OPEN",
    ignored: raw.ignored ?? raw.resolution_status === "IGNORED",
    resolution_note: raw.resolution_note,
    file_name: raw.file_name || null,
  };
}

function normalizeExport(raw: ApiExportRead): ExportRecord {
  return {
    id: raw.id,
    trip_id: raw.trip_id,
    job_id: raw.job_id,
    format: raw.format === "PDF" ? "PDF" : "XLSX",
    status: raw.status as ExportRecord["status"],
    filename: raw.original_filename,
    created_at: raw.created_at,
    expires_at: raw.expires_at,
  };
}

export const authApi = {
  async login(email: string, password: string): Promise<AuthSession> {
    const session = await apiRequest<AuthSession>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setCsrfToken(session.csrf_token);
    return session;
  },

  async logout(): Promise<void> {
    await apiRequest<void>("/auth/logout", { method: "POST" });
    setCsrfToken(null);
  },

  async currentUser(): Promise<AuthSession> {
    const session = await apiRequest<AuthSession>("/auth/me");
    setCsrfToken(session.csrf_token);
    return session;
  },
};

export const tripsApi = {
  async list(): Promise<Trip[]> {
    return (await apiRequest<ApiTripRead[]>("/trips")).map(normalizeTrip);
  },
  async get(tripId: string): Promise<Trip> {
    return normalizeTrip(await apiRequest<ApiTripRead>(`/trips/${tripId}`));
  },
  async create(input: CreateTripInput): Promise<Trip> {
    const raw = await apiRequest<ApiTripRead>("/trips", {
    method: "POST",
    body: JSON.stringify(input),
    });
    return normalizeTrip(raw);
  },
  async update(tripId: string, input: UpdateTripInput): Promise<Trip> {
    const raw = await apiRequest<ApiTripRead>(`/trips/${tripId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
    });
    return normalizeTrip(raw);
  },
  async markReimbursed(tripId: string): Promise<Trip> {
    return normalizeTrip(await apiRequest<ApiTripRead>(`/trips/${tripId}/mark-reimbursed`, {
      method: "POST",
    }));
  },
  remove: (tripId: string): Promise<void> => apiRequest<void>(`/trips/${tripId}`, { method: "DELETE" }),
  async summary(tripId: string, signal?: AbortSignal): Promise<TripExpenseSummary> {
    return normalizeTripExpenseSummary(await apiRequest<ApiTripExpenseSummary>(`/trips/${tripId}/summary`, { signal }));
  },
  async routeSegments(tripId: string, signal?: AbortSignal): Promise<RouteSegment[]> {
    return (await apiRequest<ApiRouteSegmentRead[]>(`/trips/${tripId}/route-segments`, { signal })).map(normalizeRouteSegment);
  },
};

export const dashboardApi = {
  async yearly(year?: number): Promise<YearlyDashboard> {
    const query = year ? `?year=${encodeURIComponent(year)}` : "";
    return normalizeYearlyDashboard(await apiRequest<ApiYearlyDashboardRead>(`/dashboard/yearly${query}`));
  },
};

export const documentsApi = {
  async list(tripId: string, signal?: AbortSignal): Promise<DocumentRecord[]> {
    const pageSize = 200;
    const all: DocumentRecord[] = [];
    for (let page = 1; page <= 500; page += 1) {
      const batch = (await apiRequest<ApiDocumentRead[]>(
        `/trips/${tripId}/documents?page=${page}&page_size=${pageSize}`,
        { signal },
      )).map(normalizeDocument);
      all.push(...batch);
      if (batch.length < pageSize) break;
    }
    return all;
  },
  remove: (documentId: string): Promise<void> => apiRequest<void>(`/documents/${documentId}`, { method: "DELETE" }),
  async retry(documentId: string): Promise<Job> {
    return normalizeJob(await apiRequest<ApiJobRead>(`/documents/${documentId}/retry`, { method: "POST" }));
  },
  preview: (documentId: string): Promise<Blob> => authenticatedBlob(`/documents/${documentId}/preview`),
  content: (documentId: string): Promise<Blob> => authenticatedBlob(`/documents/${documentId}/content`),
  download: (documentId: string, filename: string): Promise<void> => authenticatedDownload(`/documents/${documentId}/content`, filename),
};

export const jobsApi = {
  async list(tripId: string, signal?: AbortSignal): Promise<Job[]> {
    return (await apiRequest<ApiJobRead[]>(`/trips/${tripId}/jobs`, { signal })).map(normalizeJob);
  },
  async get(jobId: string): Promise<Job> {
    return normalizeJob(await apiRequest<ApiJobRead>(`/jobs/${jobId}`));
  },
  async create(tripId: string, kind: string): Promise<Job> {
    const raw = await apiRequest<ApiJobRead>(`/trips/${tripId}/jobs`, {
    method: "POST",
    body: JSON.stringify({ kind }),
    });
    return normalizeJob(raw);
  },
  async retry(jobId: string): Promise<Job> {
    return normalizeJob(await apiRequest<ApiJobRead>(`/jobs/${jobId}/retry`, { method: "POST" }));
  },
};

export const invoicesApi = {
  async list(tripId: string): Promise<DocumentInvoice[]> {
    return (await apiRequest<ApiInvoiceRead[]>(`/trips/${tripId}/invoices`)).map(normalizeInvoice);
  },
  async update(invoiceId: string, input: InvoiceUpdateInput): Promise<DocumentInvoice> {
    const raw = await apiRequest<ApiInvoiceRead>(`/invoices/${invoiceId}`, {
      method: "PATCH",
      body: JSON.stringify(input),
    });
    return normalizeInvoice(raw);
  },
  async bulkUpdate(tripId: string, invoiceIds: string[], input: InvoiceUpdateInput): Promise<DocumentInvoice[]> {
    const raw = await apiRequest<ApiInvoiceRead[]>(`/trips/${tripId}/invoices/bulk-update`, {
      method: "POST",
      body: JSON.stringify({ invoice_ids: invoiceIds, updates: input }),
    });
    return raw.map(normalizeInvoice);
  },
};

export const issuesApi = {
  async list(tripId: string, signal?: AbortSignal): Promise<ReviewIssue[]> {
    return (await apiRequest<ApiIssueRead[]>(`/trips/${tripId}/issues`, { signal })).map(normalizeIssue);
  },
  async update(issueId: string, input: UpdateIssueInput): Promise<ReviewIssue> {
    const raw = await apiRequest<ApiIssueRead>(`/issues/${issueId}`, {
    method: "PATCH",
    body: JSON.stringify({
      resolution_status: input.ignored ? "IGNORED" : "RESOLVED",
      resolution_note: input.resolution_note,
    }),
    });
    return normalizeIssue(raw);
  },
};

export const exportsApi = {
  async list(tripId: string, signal?: AbortSignal): Promise<ExportRecord[]> {
    return (await apiRequest<ApiExportRead[]>(`/trips/${tripId}/exports`, { signal })).map(normalizeExport);
  },
  async create(tripId: string, format: ExportRecord["format"]): Promise<ExportRecord> {
    const raw = await apiRequest<ApiExportRead>(`/trips/${tripId}/exports`, {
    method: "POST",
    body: JSON.stringify({ format }),
    });
    return normalizeExport(raw);
  },
  download: (record: ExportRecord): Promise<void> => authenticatedDownload(
    `/exports/${record.id}/download`,
    record.filename || `trip-export.${record.format.toLowerCase()}`,
  ),
};

export const settingsApi = {
  async get(): Promise<UserSettings> {
    return normalizeSettings(await apiRequest<ApiUserSettingsRead>("/settings"));
  },
  async update(input: UpdateSettingsInput): Promise<UserSettings> {
    const raw = await apiRequest<ApiUserSettingsRead>("/settings", {
      method: "PATCH",
      body: JSON.stringify(input),
    });
    return normalizeSettings(raw);
  },
};

export interface UploadProgress {
  loaded: number;
  total: number;
}

export function uploadTripFile(
  tripId: string,
  file: File,
  relativePath: string | null,
  onProgress: (progress: UploadProgress) => void,
): Promise<UploadReceipt> {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append("file", file, file.name);
    if (relativePath) formData.append("relative_path", relativePath);

    const request = new XMLHttpRequest();
    request.open("POST", apiUrl(`/trips/${tripId}/uploads`));
    request.withCredentials = true;
    request.responseType = "json";
    request.setRequestHeader("Accept", "application/json");
    const token = getCsrfToken();
    if (token) request.setRequestHeader("X-CSRF-Token", token);

    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress({ loaded: event.loaded, total: event.total });
    });
    request.addEventListener("load", () => {
      const response = request.response || parseJson(request.responseText);
      const nextToken = request.getResponseHeader("x-csrf-token");
      if (nextToken) setCsrfToken(nextToken);
      if (request.status >= 200 && request.status < 300) {
        resolve({
          document: normalizeDocument((response as ApiUploadResponse).document),
          job: (response as ApiUploadResponse).job ? normalizeJob((response as ApiUploadResponse).job!) : null,
          duplicate: Boolean((response as ApiUploadResponse).duplicate),
        });
        return;
      }
      if (request.status === 401 && typeof window !== "undefined") {
        window.dispatchEvent(new Event("trip-helper:session-expired"));
      }
      const details = response && typeof response === "object" ? response as Record<string, unknown> : {};
      reject(new ApiError(
        request.status || 0,
        messageFromApiBody(details) || "上传未能完成，请重试。",
        typeof details.code === "string" ? details.code : null,
      ));
    });
    request.addEventListener("error", () => reject(new ApiError(0, "网络连接中断，文件没有上传完成。")));
    request.addEventListener("abort", () => reject(new ApiError(0, "上传已取消。")));
    request.send(formData);
  });
}

function parseJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}
