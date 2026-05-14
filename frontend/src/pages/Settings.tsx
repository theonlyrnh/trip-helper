import { useEffect, useState } from "react";
import { getSettings, updateSettings } from "../api/client";
import type { SettingsData } from "../api/client";

export default function Settings() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    getSettings()
      .then(setSettings)
      .catch((err) => setMessage("Failed to load settings: " + err.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setMessage("");
    try {
      const updated = await updateSettings(settings);
      setSettings(updated);
      setMessage("Settings saved successfully.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setMessage("Failed to save: " + msg);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p>Loading settings...</p>;
  if (!settings) return <p>Could not load settings.</p>;

  return (
    <div>
      <h1>Settings</h1>

      {message && (
        <div
          style={{
            padding: "8px 16px",
            marginBottom: 16,
            borderRadius: 6,
            background: message.includes("success") ? "#e8f5e9" : "#ffebee",
            color: message.includes("success") ? "#2e7d32" : "#c62828",
            fontSize: 14,
          }}
        >
          {message}
        </div>
      )}

      <div
        style={{
          background: "#fff",
          borderRadius: 8,
          boxShadow: "0 1px 4px rgba(0,0,0,0.08)",
          padding: 24,
        }}
      >
        <Section title="Company Defaults">
          <Field label="Company Name">
            <input
              value={settings.default_company_name ?? ""}
              onChange={(e) =>
                setSettings({ ...settings, default_company_name: e.target.value })
              }
            />
          </Field>
          <Field label="Tax ID">
            <input
              value={settings.default_company_tax_id ?? ""}
              onChange={(e) =>
                setSettings({ ...settings, default_company_tax_id: e.target.value })
              }
            />
          </Field>
          <Field label="Default Traveler">
            <input
              value={settings.default_traveler_name ?? ""}
              onChange={(e) =>
                setSettings({ ...settings, default_traveler_name: e.target.value })
              }
            />
          </Field>
          <Field label="Invoice Root Directory">
            <input
              value={settings.default_invoice_root_dir ?? ""}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  default_invoice_root_dir: e.target.value,
                })
              }
            />
          </Field>
        </Section>

        <Section title="Allowance">
          <Field label="Daily Allowance (¥)">
            <input
              type="number"
              value={settings.daily_allowance}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  daily_allowance: parseFloat(e.target.value) || 0,
                })
              }
            />
          </Field>
          <Field label="Include Start Day">
            <input
              type="checkbox"
              checked={settings.include_start_day}
              onChange={(e) =>
                setSettings({ ...settings, include_start_day: e.target.checked })
              }
            />
          </Field>
          <Field label="Include End Day">
            <input
              type="checkbox"
              checked={settings.include_end_day}
              onChange={(e) =>
                setSettings({ ...settings, include_end_day: e.target.checked })
              }
            />
          </Field>
          <Field label="Lodging Limit / Day (¥)">
            <input
              type="number"
              value={settings.lodging_limit_per_day ?? ""}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  lodging_limit_per_day: parseFloat(e.target.value) || null,
                })
              }
            />
          </Field>
        </Section>

        <Section title="Validation Rules">
          <Field label="Require Return Ticket">
            <input
              type="checkbox"
              checked={settings.require_return_ticket}
              onChange={(e) =>
                setSettings({ ...settings, require_return_ticket: e.target.checked })
              }
            />
          </Field>
          <Field label="Require Lodging Invoice">
            <input
              type="checkbox"
              checked={settings.require_lodging_invoice}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  require_lodging_invoice: e.target.checked,
                })
              }
            />
          </Field>
        </Section>

        <Section title="OCR Provider">
          <Field label="Provider Mode">
            <select
              value={settings.ocr_provider_mode}
              onChange={(e) =>
                setSettings({ ...settings, ocr_provider_mode: e.target.value })
              }
            >
              <option value="local_first">Local First</option>
              <option value="local_only">Local Only</option>
              <option value="remote_only">Remote Only</option>
            </select>
          </Field>
          <Field label="PaddleOCR API URL">
            <input
              value={settings.paddleocr_api_url ?? ""}
              onChange={(e) =>
                setSettings({ ...settings, paddleocr_api_url: e.target.value })
              }
            />
          </Field>
          <Field label="Remote API Base URL">
            <input
              value={settings.remote_api_base_url ?? ""}
              onChange={(e) =>
                setSettings({ ...settings, remote_api_base_url: e.target.value })
              }
            />
          </Field>
          <Field label="Remote API Key">
            <input
              type="password"
              value={settings.remote_api_key ?? ""}
              onChange={(e) =>
                setSettings({ ...settings, remote_api_key: e.target.value })
              }
            />
          </Field>
          <Field label="Remote Model Name">
            <input
              value={settings.remote_model_name ?? ""}
              onChange={(e) =>
                setSettings({ ...settings, remote_model_name: e.target.value })
              }
            />
          </Field>
        </Section>

        <button
          onClick={handleSave}
          disabled={saving}
          style={{
            marginTop: 16,
            padding: "10px 28px",
            background: "#1a1a2e",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
            fontSize: 14,
          }}
        >
          {saving ? "Saving..." : "Save Settings"}
        </button>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 24 }}>
      <h3
        style={{
          fontSize: 15,
          fontWeight: 600,
          color: "#333",
          borderBottom: "1px solid #eee",
          paddingBottom: 8,
          marginBottom: 12,
        }}
      >
        {title}
      </h3>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {children}
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        fontSize: 14,
      }}
    >
      <span style={{ minWidth: 180, color: "#555" }}>{label}</span>
      {children}
    </label>
  );
}