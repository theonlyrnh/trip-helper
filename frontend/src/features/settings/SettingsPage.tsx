import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Save, ShieldCheck } from "lucide-react";
import { settingsApi } from "../../api/resources";
import type { UpdateSettingsInput, UserSettings } from "../../api/types";

function editableSettings(settings: UserSettings): UpdateSettingsInput {
  return {
    default_company_name: settings.default_company_name,
    default_company_tax_id: settings.default_company_tax_id,
    default_traveler_name: settings.default_traveler_name,
    daily_allowance: settings.daily_allowance,
    include_start_day: settings.include_start_day,
    include_end_day: settings.include_end_day,
    lodging_limit_per_day: settings.lodging_limit_per_day,
    require_return_ticket: settings.require_return_ticket,
    require_lodging_invoice: settings.require_lodging_invoice,
    remote_provider_enabled: settings.remote_provider_enabled,
  };
}

export function SettingsPage() {
  const settings = useQuery({ queryKey: ["settings"], queryFn: settingsApi.get });

  if (settings.isPending) return <section className="page"><div className="empty-state">正在加载设置...</div></section>;
  if (settings.error) return <section className="page"><div className="empty-state error-state">设置无法加载。<button className="button button-secondary" type="button" onClick={() => void settings.refetch()}>重试</button></div></section>;
  if (!settings.data) return null;

  return <SettingsEditor key={settings.dataUpdatedAt} settings={settings.data} />;
}

function SettingsEditor({ settings }: { settings: UserSettings }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<UpdateSettingsInput>(() => editableSettings(settings));
  const [saved, setSaved] = useState(false);
  const save = useMutation({
    mutationFn: () => settingsApi.update(draft),
    onSuccess: (updated) => {
      setSaved(true);
      queryClient.setQueryData(["settings"], updated);
    },
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaved(false);
    save.mutate();
  }

  return (
    <section className="page settings-page">
      <header className="page-header">
        <div><p className="eyebrow">设置</p><h1>个人偏好</h1><p className="page-subtitle">这些默认值仅作用于当前账号的新项目。</p></div>
      </header>
      <form className="settings-form" onSubmit={submit}>
        <section className="settings-section">
          <h2>公司与出差人</h2>
          <div className="form-grid">
            <label className="field"><span>默认公司名称</span><input value={draft.default_company_name || ""} onChange={(event) => setDraft({ ...draft, default_company_name: event.target.value || null })} /></label>
            <label className="field"><span>公司税号</span><input value={draft.default_company_tax_id || ""} onChange={(event) => setDraft({ ...draft, default_company_tax_id: event.target.value || null })} /></label>
            <label className="field"><span>默认出差人</span><input value={draft.default_traveler_name || ""} onChange={(event) => setDraft({ ...draft, default_traveler_name: event.target.value || null })} /></label>
          </div>
        </section>
        <section className="settings-section">
          <h2>报销规则</h2>
          <div className="form-grid">
            <label className="field"><span>每日补助（元）</span><input type="number" min="0" step="0.01" value={draft.daily_allowance} onChange={(event) => setDraft({ ...draft, daily_allowance: Number(event.target.value) || 0 })} /></label>
            <label className="field"><span>住宿单日限额（元）</span><input type="number" min="0" step="0.01" value={draft.lodging_limit_per_day ?? ""} onChange={(event) => setDraft({ ...draft, lodging_limit_per_day: event.target.value === "" ? null : Number(event.target.value) })} /></label>
            <label className="check-field"><input type="checkbox" checked={draft.include_start_day} onChange={(event) => setDraft({ ...draft, include_start_day: event.target.checked })} /> 计入出发日补助</label>
            <label className="check-field"><input type="checkbox" checked={draft.include_end_day} onChange={(event) => setDraft({ ...draft, include_end_day: event.target.checked })} /> 计入返程日补助</label>
            <label className="check-field"><input type="checkbox" checked={draft.require_return_ticket} onChange={(event) => setDraft({ ...draft, require_return_ticket: event.target.checked })} /> 校验返程票据</label>
            <label className="check-field"><input type="checkbox" checked={draft.require_lodging_invoice} onChange={(event) => setDraft({ ...draft, require_lodging_invoice: event.target.checked })} /> 校验住宿发票</label>
            <label className="check-field"><input type="checkbox" checked={draft.remote_provider_enabled} disabled={!settings.remote_provider_configured} onChange={(event) => setDraft({ ...draft, remote_provider_enabled: event.target.checked })} /> 允许使用已配置的远程识别服务</label>
          </div>
        </section>
        <section className="settings-section provider-status">
          <ShieldCheck size={20} aria-hidden="true" />
          <div><h2>识别服务</h2><p>{settings.remote_provider_configured ? "已由服务端配置可选远程识别服务。" : "未配置可选远程识别服务。"}</p></div>
        </section>
        {save.error && <p className="form-error" role="alert">设置未能保存，请重试。</p>}
        {saved && <p className="form-success" role="status"><CheckCircle2 size={16} /> 设置已保存。</p>}
        <footer className="settings-actions"><button className="button button-primary" type="submit" disabled={save.isPending}><Save size={16} /> {save.isPending ? "正在保存" : "保存设置"}</button></footer>
      </form>
    </section>
  );
}
