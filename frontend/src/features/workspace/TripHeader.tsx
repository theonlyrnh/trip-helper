import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  BadgeCheck,
  CalendarRange,
  ChevronDown,
  FolderKanban,
  RotateCcw,
  Save,
  Settings2,
  Sparkles,
} from "lucide-react";
import { tripsApi } from "../../api/resources";
import type { ProjectType, Trip, TripExpenseSummary, UpdateTripInput } from "../../api/types";
import { formatDateRange, formatMoney, labelForProjectType, labelForReimbursementStatus, labelForState } from "../../lib/format";

interface TripHeaderProps {
  trip: Trip;
  expenseSummary: TripExpenseSummary | undefined;
  summaryLoading: boolean;
  onChanged: () => void;
}

interface TripDraft {
  title: string;
  sourceLabel: string;
  travelerName: string;
  companyName: string;
  companyTaxId: string;
  projectType: ProjectType;
  inputStartDate: string;
  inputEndDate: string;
  confirmedStartDate: string;
  confirmedEndDate: string;
}

function empty(value: string): string | null {
  return value.trim() || null;
}

function draftFor(trip: Trip): TripDraft {
  return {
    title: trip.title,
    sourceLabel: trip.source_label || "",
    travelerName: trip.traveler_name || "",
    companyName: trip.company_name || "",
    companyTaxId: trip.company_tax_id || "",
    projectType: trip.project_type,
    inputStartDate: trip.input_start_date || "",
    inputEndDate: trip.input_end_date || "",
    confirmedStartDate: trip.confirmed_start_date || "",
    confirmedEndDate: trip.confirmed_end_date || "",
  };
}

function hasInvalidRange(start: string, end: string): boolean {
  return Boolean(start && end && start > end);
}

function hasIncompleteRange(start: string, end: string): boolean {
  return Boolean(start) !== Boolean(end);
}

export function TripHeader({ trip, expenseSummary, summaryLoading, onChanged }: TripHeaderProps) {
  return <TripHeaderForm key={`${trip.id}-${trip.updated_at}`} trip={trip} expenseSummary={expenseSummary} summaryLoading={summaryLoading} onChanged={onChanged} />;
}

function TripHeaderForm({ trip, expenseSummary, summaryLoading, onChanged }: TripHeaderProps) {
  const [draft, setDraft] = useState<TripDraft>(() => draftFor(trip));
  const [formError, setFormError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (input: UpdateTripInput) => tripsApi.update(trip.id, input),
    onSuccess: () => {
      setFormError(null);
      onChanged();
    },
  });
  const isManuallyConfirmed = Boolean(draft.confirmedStartDate || draft.confirmedEndDate);
  const confidence = Math.max(0, Math.min(1, trip.date_confidence || 0));
  const projectTotal = summaryLoading ? null : expenseSummary?.grand_total_amount ?? null;
  const currentClaim = summaryLoading ? null : expenseSummary?.reimbursement_total_amount ?? null;
  const reimbursed = summaryLoading ? null : expenseSummary?.reimbursed_total_amount ?? null;

  function update<K extends keyof TripDraft>(key: K, value: TripDraft[K]) {
    setFormError(null);
    setDraft((previous) => ({ ...previous, [key]: value }));
  }

  function clearManualConfirmation() {
    setFormError(null);
    setDraft((previous) => ({ ...previous, confirmedStartDate: "", confirmedEndDate: "" }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.title.trim()) {
      setFormError("项目名称不能为空。");
      return;
    }
    if (hasIncompleteRange(draft.inputStartDate, draft.inputEndDate)) {
      setFormError("项目输入日期需要同时填写开始和结束日期。");
      return;
    }
    if (hasInvalidRange(draft.inputStartDate, draft.inputEndDate)) {
      setFormError("项目输入的结束日期不能早于开始日期。");
      return;
    }
    if (hasIncompleteRange(draft.confirmedStartDate, draft.confirmedEndDate)) {
      setFormError("确认覆盖需要同时填写开始和结束日期，或全部清除。");
      return;
    }
    if (hasInvalidRange(draft.confirmedStartDate, draft.confirmedEndDate)) {
      setFormError("确认覆盖的结束日期不能早于开始日期。");
      return;
    }

    const input: UpdateTripInput = {
      title: draft.title.trim(),
      source_label: empty(draft.sourceLabel),
      traveler_name: empty(draft.travelerName),
      company_name: empty(draft.companyName),
      company_tax_id: empty(draft.companyTaxId),
      project_type: draft.projectType,
      input_start_date: empty(draft.inputStartDate),
      input_end_date: empty(draft.inputEndDate),
      confirmed_start_date: empty(draft.confirmedStartDate),
      confirmed_end_date: empty(draft.confirmedEndDate),
    };
    save.mutate(input);
  }

  return (
    <section className="workspace-overview" aria-labelledby="workspace-title">
      <form onSubmit={submit}>
        <header className="workspace-header">
          <div className="workspace-primary">
            <div className="workspace-heading">
              <p className="workspace-kicker"><FolderKanban size={14} aria-hidden="true" /> 项目工作台</p>
              <span className="status-badge">{labelForState(trip.status)}</span>
              <span className="status-badge neutral-badge">{labelForProjectType(trip.project_type)}</span>
              <span className={`project-reimbursement-state project-reimbursement-${trip.reimbursement_status.toLowerCase()}`}>{labelForReimbursementStatus(trip.reimbursement_status)}</span>
            </div>
            <h1 id="workspace-title" className="trip-title-heading" aria-label={draft.title || "未命名项目"}>
              <input className="trip-title-input" value={draft.title} onChange={(event) => update("title", event.target.value)} aria-label="项目名称" maxLength={255} />
            </h1>
            <div className="workspace-context">
              <p className="workspace-effective-date"><CalendarRange size={15} aria-hidden="true" /> {formatDateRange(trip.start_date, trip.end_date)}{trip.trip_days != null ? ` · ${trip.trip_days} 天` : ""}</p>
              {draft.sourceLabel && <span className="workspace-source">{draft.sourceLabel}</span>}
            </div>
          </div>
          <div className="workspace-summary-panel">
            <dl className="workspace-summary">
              <div className="workspace-total"><dt>项目总支出</dt><dd>{formatMoney(projectTotal)}</dd></div>
              <div className="workspace-pending"><dt><span className="summary-label-wide">本次待报销</span><span className="summary-label-compact" aria-hidden="true">待报销</span></dt><dd>{formatMoney(currentClaim)}</dd></div>
              <div className="workspace-reimbursed"><dt>已报销</dt><dd>{formatMoney(reimbursed)}</dd></div>
            </dl>
          </div>
        </header>

        <details className="trip-editor">
          <summary>
            <span className="trip-editor-summary-copy"><Settings2 size={16} aria-hidden="true" /><span><strong>项目资料与日期校验</strong><small>编辑出差人、报销主体和行程日期</small></span></span>
            <ChevronDown className="trip-editor-chevron" size={18} aria-hidden="true" />
          </summary>
          <div className="trip-details-grid">
            <section className="trip-details-section" aria-labelledby="trip-profile-title">
              <div className="trip-details-heading">
                <div><p className="eyebrow">资料</p><h2 id="trip-profile-title">项目元数据</h2></div>
              </div>
              <div className="trip-profile-grid">
                <label className="field"><span>来源标签</span><input value={draft.sourceLabel} onChange={(event) => update("sourceLabel", event.target.value)} placeholder="例如：2026 年 7 月" maxLength={255} /></label>
                <label className="field"><span>项目类型</span><select value={draft.projectType} onChange={(event) => update("projectType", event.target.value as ProjectType)}><option value="TRAVEL">出差报销</option><option value="DAILY">日常票据</option><option value="MIXED">综合项目</option></select></label>
                <label className="field"><span>出差人</span><input value={draft.travelerName} onChange={(event) => update("travelerName", event.target.value)} maxLength={128} /></label>
                <label className="field"><span>公司名称</span><input value={draft.companyName} onChange={(event) => update("companyName", event.target.value)} maxLength={255} /></label>
                <label className="field field-span-2"><span>公司税号</span><input value={draft.companyTaxId} onChange={(event) => update("companyTaxId", event.target.value)} maxLength={64} /></label>
              </div>
            </section>

            <section className="trip-details-section trip-dates-section" aria-labelledby="trip-dates-title">
              <div className="trip-details-heading">
                <div><p className="eyebrow">行程</p><h2 id="trip-dates-title">日期确认</h2></div>
                {isManuallyConfirmed ? <span className="date-source confirmed"><BadgeCheck size={14} /> 已人工确认</span> : <span className="date-source inferred"><Sparkles size={14} /> 跟随系统推断</span>}
              </div>
              <div className="trip-dates-grid">
                <div className="date-lane">
                  <div className="date-lane-label"><span>项目输入</span><small>创建项目时的日期范围</small></div>
                  <div className="date-input-pair">
                    <label className="field"><span>开始</span><input aria-label="项目输入开始日期" type="date" value={draft.inputStartDate} onChange={(event) => update("inputStartDate", event.target.value)} max={draft.inputEndDate || undefined} /></label>
                    <label className="field"><span>结束</span><input aria-label="项目输入结束日期" type="date" value={draft.inputEndDate} onChange={(event) => update("inputEndDate", event.target.value)} min={draft.inputStartDate || undefined} /></label>
                  </div>
                </div>
                <div className="date-lane inferred-lane">
                  <div className="date-lane-label"><span>系统推断</span><small>置信度 {Math.round(confidence * 100)}%</small></div>
                  <strong>{formatDateRange(trip.inferred_start_date, trip.inferred_end_date)}</strong>
                  <ul className="date-evidence">
                    {trip.date_evidence.length > 0 ? trip.date_evidence.map((item, index) => <li key={`${index}-${item}`}>{item}</li>) : <li>尚无可用推断证据</li>}
                  </ul>
                </div>
                <div className="date-lane confirmation-lane">
                  <div className="date-lane-label"><span>确认覆盖</span><small>留空则使用系统推断</small></div>
                  <div className="date-input-pair">
                    <label className="field"><span>开始</span><input aria-label="确认覆盖开始日期" type="date" value={draft.confirmedStartDate} onChange={(event) => update("confirmedStartDate", event.target.value)} max={draft.confirmedEndDate || undefined} /></label>
                    <label className="field"><span>结束</span><input aria-label="确认覆盖结束日期" type="date" value={draft.confirmedEndDate} onChange={(event) => update("confirmedEndDate", event.target.value)} min={draft.confirmedStartDate || undefined} /></label>
                  </div>
                  <button className="icon-button compact-icon-button" type="button" title="清除确认覆盖并跟随系统推断" aria-label="清除确认覆盖并跟随系统推断" disabled={!isManuallyConfirmed || save.isPending} onClick={clearManualConfirmation}><RotateCcw size={15} /></button>
                </div>
              </div>
            </section>
          </div>

          <footer className="trip-details-actions">
            <div>{formError && <p className="form-error" role="alert">{formError}</p>}{save.error && <p className="form-error" role="alert">项目资料未能保存，请重试。</p>}</div>
            <button className="button button-primary" type="submit" disabled={save.isPending}><Save size={16} /> {save.isPending ? "正在保存" : "保存项目资料"}</button>
          </footer>
        </details>
      </form>
    </section>
  );
}
