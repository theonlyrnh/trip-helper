const API_BASE = "http://127.0.0.1:8000";

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json();
}

// ── Types ──────────────────────────────────────────────────────────

export interface TripData {
  id: number;
  title: string;
  folder_path: string;
  folder_name: string;
  folder_date_start: string | null;
  folder_date_end: string | null;
  traveler_name: string | null;
  company_name: string | null;
  inferred_start_date: string | null;
  inferred_end_date: string | null;
  confirmed_start_date: string | null;
  confirmed_end_date: string | null;
  trip_days: number | null;
  route_text: string | null;
  document_count: number;
  recognized_count: number;
  review_count: number;
  issue_count: number;
  invoice_total_amount: number;
  allowance_amount: number;
  grand_total_amount: number;
  status: string;
  reimbursement_status: string;
  project_type: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentData {
  id: number;
  trip_id: number;
  file_name: string;
  file_path: string;
  file_ext: string;
  file_hash: string;
  file_size: number;
  page_count: number;
  document_type: string;
  scan_status: string;
  ocr_status: string;
  thumbnail_path: string | null;
  preview_image_path: string | null;
  error_message: string | null;
  created_at: string;
}

export interface ScanResult {
  trip_id: number;
  total_scanned: number;
  new_documents: number;
  documents: DocumentData[];
}

export interface SummaryData {
  trip_id: number;
  trip_title: string;
  start_date: string | null;
  end_date: string | null;
  trip_days: number;
  route_text: string | null;
  daily_allowance: number;
  allowance_amount: number;
  intercity_transport_amount: number;
  local_transport_amount: number;
  lodging_amount: number;
  meal_amount: number;
  refund_change_fee: number;
  travel_insurance_amount: number;
  other_amount: number;
  invoice_total_amount: number;
  grand_total_amount: number;
}

export interface IssueData {
  id: number;
  trip_id: number;
  document_id: number | null;
  invoice_id: number | null;
  issue_type: string;
  severity: string;
  message: string;
  suggestion: string | null;
  auto_generated: boolean;
  resolved: boolean;
  // Joined from Document
  file_name: string | null;
  file_path: string | null;
  // Joined from Invoice
  invoice_type: string | null;
  expense_category: string | null;
  invoice_total_amount: number | null;
}

export interface AnalysisResult {
  trip_id: number;
  status: string;
  inferred_start_date: string | null;
  inferred_end_date: string | null;
  trip_days: number | null;
  date_confidence: number;
  date_evidence: string[];
  route_text: string | null;
  travel_segments_count: number;
  lodging_stays_count: number;
  invoices_count: number;
}

export interface SelectFolderResult {
  success: boolean;
  folder_path: string | null;
  message: string | null;
}

// ── API functions ──────────────────────────────────────────────────

export async function selectFolder(): Promise<SelectFolderResult> {
  return request("/api/system/select-folder", { method: "POST" });
}

export async function createTrip(payload: {
  title: string;
  folder_path: string;
  traveler_name?: string;
  company_name?: string;
}): Promise<TripData> {
  return request("/api/trips", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getTrips(): Promise<TripData[]> {
  return request("/api/trips");
}

export async function getTrip(tripId: number): Promise<TripData> {
  return request(`/api/trips/${tripId}`);
}

export async function updateTrip(
  tripId: number,
  payload: Partial<TripData>
): Promise<TripData> {
  return request(`/api/trips/${tripId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function scanTripDocuments(tripId: number): Promise<ScanResult> {
  return request(`/api/trips/${tripId}/documents/scan`, { method: "POST" });
}

export async function preprocessDocuments(
  tripId: number
): Promise<{ trip_id: number; processed_count: number; documents: DocumentData[] }> {
  return request(`/api/trips/${tripId}/documents/preprocess`, {
    method: "POST",
  });
}

export async function recognizeTrip(
  tripId: number
): Promise<{ trip_id: number; recognized_count: number; message: string }> {
  return request(`/api/trips/${tripId}/recognize`, { method: "POST" });
}

export async function analyzeTrip(tripId: number): Promise<AnalysisResult> {
  return request(`/api/trips/${tripId}/analyze`, { method: "POST" });
}

export async function getTripDocuments(tripId: number): Promise<DocumentData[]> {
  return request(`/api/trips/${tripId}/documents`);
}

export async function getTripSummary(tripId: number): Promise<SummaryData> {
  return request(`/api/trips/${tripId}/summary`);
}

export async function getTripIssues(tripId: number): Promise<IssueData[]> {
  return request(`/api/trips/${tripId}/issues`);
}

export async function exportExcel(
  tripId: number
): Promise<{ trip_id: number; format: string; file_path: string; message: string }> {
  return request(`/api/trips/${tripId}/export/excel`, { method: "POST" });
}

export interface WorkspaceData {
  trip: TripData;
  stats: { total_files: number; recognized: number; review_count: number; issues: number };
  summary: SummaryData;
  documents: WorkspaceDoc[];
  issues: IssueData[];
  route_segments: RouteSegment[];
}

export interface WorkspaceDoc {
  id: number;
  file_name: string;
  file_path: string;
  file_ext: string;
  file_size: number;
  document_type: string;
  scan_status: string;
  ocr_status: string;
  invoice_id: number | null;
  invoice_type: string | null;
  expense_category: string | null;
  total_amount: number | null;
  order_total_amount: number | null;
  nights: number | null;
  issue_count: number;
}

export interface RouteSegment {
  id: number;
  depart_date: string | null;
  depart_time: string | null;
  transport_type: string;
  from_place: string | null;
  to_place: string | null;
  transport_no: string | null;
  seat_class: string | null;
  amount: number | null;
  source_document_id: number | null;
}

export async function getWorkspace(tripId: number): Promise<WorkspaceData> {
  return request(`/api/trips/${tripId}/workspace`);
}

export async function getRecentTrip(): Promise<TripData> {
  return request("/api/trips/recent");
}

export async function findTripByFolder(folderPath: string): Promise<TripData | null> {
  try {
    return await request("/api/trips/find-by-folder", {
      method: "POST",
      body: JSON.stringify({ folder_path: folderPath }),
    });
  } catch {
    return null;
  }
}