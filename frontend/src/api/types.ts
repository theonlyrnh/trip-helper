export type JobState =
  | "PENDING"
  | "QUEUED"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELLED"
  | "RETRYING";

export type UploadState = "PENDING" | "UPLOADING" | "UPLOADED" | "FAILED";

export type ProjectType = "TRAVEL" | "DAILY" | "MIXED";

export interface CurrentUser {
  id: string;
  email: string;
  display_name?: string | null;
  is_admin: boolean;
}

export interface AuthSession {
  user: CurrentUser;
  csrf_token?: string;
}

export interface TripSummary {
  invoice_total_amount: number;
  allowance_amount: number;
  grand_total_amount: number;
  reimbursement_total_amount?: number;
  reimbursed_total_amount?: number;
  unallocated_total_amount?: number;
  document_count: number;
  review_count: number;
  issue_count: number;
}

export interface TripExpenseSummary {
  trip_id: string;
  intercity_transport_amount: number;
  local_transport_amount: number;
  lodging_amount: number;
  meal_amount: number;
  refund_change_fee: number;
  travel_insurance_amount: number;
  other_amount: number;
  invoice_total_amount: number;
  trip_days: number;
  daily_allowance: number;
  allowance_amount: number;
  grand_total_amount: number;
  reimbursement_invoice_total_amount?: number;
  reimbursement_allowance_amount?: number;
  reimbursement_total_amount?: number;
  reimbursed_invoice_amount?: number;
  reimbursed_allowance_amount?: number;
  reimbursed_total_amount?: number;
  unallocated_total_amount?: number;
}

export interface RouteSegment {
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
  amount: number | null;
  confidence: number;
}

export interface Trip {
  id: string;
  title: string;
  source_label: string | null;
  traveler_name: string | null;
  company_name: string | null;
  company_tax_id: string | null;
  project_type: ProjectType;
  status: string;
  reimbursement_status: string;
  input_start_date: string | null;
  input_end_date: string | null;
  inferred_start_date: string | null;
  inferred_end_date: string | null;
  confirmed_start_date: string | null;
  confirmed_end_date: string | null;
  trip_days: number | null;
  date_confidence: number;
  date_evidence: string[];
  start_date: string | null;
  end_date: string | null;
  route_text: string | null;
  created_at: string;
  updated_at: string;
  summary: TripSummary | null;
}

export interface MonthlyTrend {
  month: number;
  project_count: number;
  invoice_amount: number;
  allowance_amount: number;
}

export interface CitySummary {
  city: string;
  count: number;
}

export interface AnnualProject {
  id: string;
  title: string;
  project_type: ProjectType;
  status: string;
  reimbursement_status: string;
  start_date: string | null;
  end_date: string | null;
  route_text: string | null;
  document_count: number;
  trip_days: number;
  invoice_total_amount: number;
  allowance_amount: number;
  grand_total_amount: number;
}

export interface YearlyDashboard {
  year: number;
  available_years: number[];
  total_project_count: number;
  travel_project_count: number;
  daily_project_count: number;
  total_trip_days: number;
  total_invoice_amount: number;
  total_income_amount: number;
  reimbursed_amount: number;
  unreimbursed_amount: number;
  monthly_trends: MonthlyTrend[];
  category_summary: Record<string, number>;
  city_summary: CitySummary[];
  reimbursement_summary: Record<string, number>;
  recent_projects: AnnualProject[];
}

export interface CreateTripInput {
  title: string;
  source_label?: string;
  traveler_name?: string;
  company_name?: string;
  company_tax_id?: string;
  project_type?: Trip["project_type"];
  input_start_date?: string;
  input_end_date?: string;
}

export interface UpdateTripInput {
  title?: string;
  source_label?: string | null;
  traveler_name?: string | null;
  company_name?: string | null;
  company_tax_id?: string | null;
  project_type?: Trip["project_type"];
  input_start_date?: string | null;
  input_end_date?: string | null;
  confirmed_start_date?: string | null;
  confirmed_end_date?: string | null;
  daily_allowance?: number | null;
}

export interface DocumentInvoice {
  id: string;
  invoice_type: string | null;
  expense_category: string | null;
  total_amount: number | null;
  confirmed_amount: number | null;
  reimbursement_status: string;
  include_in_summary: boolean;
  review_status: string;
  document_role: string;
  invoice_number: string | null;
  invoice_date: string | null;
  business_date: string | null;
  seller_name: string | null;
  buyer_name: string | null;
  from_city: string | null;
  to_city: string | null;
  from_place: string | null;
  to_place: string | null;
  transport_no: string | null;
  depart_time_str: string | null;
  seat_class: string | null;
  hotel_name: string | null;
  checkin_date: string | null;
  checkout_date: string | null;
  nights: number | null;
  note: string | null;
}

export interface DocumentRecord {
  id: string;
  trip_id: string;
  original_filename: string;
  relative_path: string | null;
  size_bytes: number;
  sha256?: string | null;
  mime_type: string | null;
  upload_status: UploadState;
  processing_status: string;
  ocr_status: string;
  document_type: string | null;
  error_code: string | null;
  error_message: string | null;
  issue_count: number;
  created_at: string;
  invoice: DocumentInvoice | null;
}

export interface UploadReceipt {
  document: DocumentRecord;
  job: Job | null;
  duplicate: boolean;
}

export interface Job {
  id: string;
  trip_id: string | null;
  document_id: string | null;
  kind: string;
  state: JobState;
  progress: number;
  progress_message: string | null;
  error_code: string | null;
  error_message: string | null;
  retryable: boolean;
  attempt: number;
  max_attempts: number;
  created_at: string;
  updated_at: string;
}

export interface ReviewIssue {
  id: string;
  trip_id: string;
  document_id: string | null;
  issue_type: string;
  severity: "INFO" | "WARNING" | "ERROR";
  message: string;
  suggestion: string | null;
  resolved: boolean;
  ignored: boolean;
  resolution_note: string | null;
  file_name: string | null;
}

export interface ExportRecord {
  id: string;
  trip_id: string;
  format: "XLSX" | "PDF";
  status: JobState;
  filename: string | null;
  created_at: string;
  expires_at: string | null;
  job_id: string | null;
}

export interface UserSettings {
  default_company_name: string | null;
  default_company_tax_id: string | null;
  default_traveler_name: string | null;
  daily_allowance: number;
  include_start_day: boolean;
  include_end_day: boolean;
  lodging_limit_per_day: number | null;
  require_return_ticket: boolean;
  require_lodging_invoice: boolean;
  remote_provider_configured: boolean;
  remote_provider_enabled: boolean;
}

export type UpdateSettingsInput = Omit<UserSettings, "remote_provider_configured">;

export interface InvoiceUpdateInput {
  invoice_type?: string | null;
  expense_category?: string | null;
  total_amount?: number | null;
  confirmed_amount?: number | null;
  reimbursement_status?: string;
  include_in_summary?: boolean;
  review_status?: string;
  document_role?: string;
  invoice_number?: string | null;
  invoice_date?: string | null;
  business_date?: string | null;
  seller_name?: string | null;
  buyer_name?: string | null;
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
  note?: string | null;
}

export interface UpdateIssueInput {
  resolved?: boolean;
  ignored?: boolean;
  resolution_note?: string | null;
}
