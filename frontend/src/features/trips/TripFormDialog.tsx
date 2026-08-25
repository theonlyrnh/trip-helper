import { useState } from "react";
import type { FormEvent } from "react";
import { X } from "lucide-react";
import type { CreateTripInput } from "../../api/types";

interface TripFormDialogProps {
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onSubmit: (input: CreateTripInput) => void;
}

export function TripFormDialog({ open, busy, onClose, onSubmit }: TripFormDialogProps) {
  if (!open) return null;
  return <TripFormDialogForm busy={busy} onClose={onClose} onSubmit={onSubmit} />;
}

function TripFormDialogForm({ busy, onClose, onSubmit }: Omit<TripFormDialogProps, "open">) {
  const [title, setTitle] = useState("");
  const [sourceLabel, setSourceLabel] = useState("");
  const [travelerName, setTravelerName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [inputStartDate, setInputStartDate] = useState("");
  const [inputEndDate, setInputEndDate] = useState("");
  const [projectType, setProjectType] = useState<CreateTripInput["project_type"]>("TRAVEL");
  const [dateError, setDateError] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) return;
    if (Boolean(inputStartDate) !== Boolean(inputEndDate)) {
      setDateError("计划日期需要同时填写开始和结束日期。");
      return;
    }
    if (inputStartDate && inputEndDate && inputStartDate > inputEndDate) {
      setDateError("计划结束日期不能早于开始日期。");
      return;
    }
    setDateError(null);
    onSubmit({
      title: title.trim(),
      source_label: sourceLabel.trim() || undefined,
      traveler_name: travelerName.trim() || undefined,
      company_name: companyName.trim() || undefined,
      project_type: projectType,
      input_start_date: inputStartDate || undefined,
      input_end_date: inputEndDate || undefined,
    });
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="modal dialog" role="dialog" aria-modal="true" aria-labelledby="trip-dialog-title" onMouseDown={(event) => event.stopPropagation()}>
        <header className="dialog-header">
          <div>
            <h2 id="trip-dialog-title">新建项目</h2>
            <p>先创建项目，再从浏览器上传票据文件。</p>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭" title="关闭"><X size={18} /></button>
        </header>
        <form className="form-grid" onSubmit={submit}>
          <label className="field field-full">
            <span>项目名称</span>
            <input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：北京客户拜访" required maxLength={160} />
          </label>
          <label className="field">
            <span>项目类型</span>
            <select value={projectType} onChange={(event) => setProjectType(event.target.value as CreateTripInput["project_type"])}>
              <option value="TRAVEL">出差报销</option>
              <option value="DAILY">日常票据</option>
              <option value="MIXED">综合项目</option>
            </select>
          </label>
          <label className="field">
            <span>来源标签</span>
            <input value={sourceLabel} onChange={(event) => setSourceLabel(event.target.value)} placeholder="可选，例如 2026 年 7 月" maxLength={160} />
          </label>
          <label className="field">
            <span>出差人</span>
            <input value={travelerName} onChange={(event) => setTravelerName(event.target.value)} maxLength={120} />
          </label>
          <label className="field">
            <span>公司名称</span>
            <input value={companyName} onChange={(event) => setCompanyName(event.target.value)} maxLength={200} />
          </label>
          <label className="field">
            <span>计划开始日期</span>
            <input type="date" value={inputStartDate} onChange={(event) => setInputStartDate(event.target.value)} max={inputEndDate || undefined} />
          </label>
          <label className="field">
            <span>计划结束日期</span>
            <input type="date" value={inputEndDate} onChange={(event) => setInputEndDate(event.target.value)} min={inputStartDate || undefined} />
          </label>
          {dateError && <p className="form-error field-full" role="alert">{dateError}</p>}
          <footer className="dialog-actions field-full">
            <button className="button button-secondary" type="button" onClick={onClose} disabled={busy}>取消</button>
            <button className="button button-primary" type="submit" disabled={busy || !title.trim()}>{busy ? "正在创建" : "创建项目"}</button>
          </footer>
        </form>
      </section>
    </div>
  );
}
