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

export interface SettingsData {
  id: number;
  default_invoice_root_dir: string | null;
  default_company_name: string | null;
  default_company_tax_id: string | null;
  default_traveler_name: string | null;
  daily_allowance: number;
  include_start_day: boolean;
  include_end_day: boolean;
  lodging_limit_per_day: number | null;
  require_return_ticket: boolean;
  require_lodging_invoice: boolean;
  ocr_provider_mode: string;
  paddleocr_api_url: string | null;
  remote_api_base_url: string | null;
  remote_api_key: string | null;
  remote_model_name: string | null;
}

export async function getHealth(): Promise<{ status: string; app: string }> {
  return request("/api/health");
}

export async function getSettings(): Promise<SettingsData> {
  return request("/api/settings");
}

export async function updateSettings(
  data: Partial<SettingsData>
): Promise<SettingsData> {
  return request("/api/settings", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}