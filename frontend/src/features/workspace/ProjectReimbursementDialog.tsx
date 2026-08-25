import { useEffect } from "react";
import { BadgeCheck, X } from "lucide-react";
import type { Trip } from "../../api/types";
import { formatMoney } from "../../lib/format";

interface ProjectReimbursementDialogProps {
  trip: Trip | null;
  invoiceCount: number;
  busy: boolean;
  error: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function ProjectReimbursementDialog({ trip, invoiceCount, busy, error, onClose, onConfirm }: ProjectReimbursementDialogProps) {
  useEffect(() => {
    if (!trip) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [busy, onClose, trip]);

  if (!trip) return null;

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={() => { if (!busy) onClose(); }}>
      <section
        className="modal dialog project-reimbursement-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-reimbursement-title"
        aria-describedby="project-reimbursement-description"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="dialog-header project-reimbursement-header">
          <span className="project-reimbursement-icon"><BadgeCheck size={20} aria-hidden="true" /></span>
          <div>
            <h2 id="project-reimbursement-title">标记项目已报销</h2>
            <p id="project-reimbursement-description">将可报销票据与本项目补助记为已报销，项目总支出不会变化。</p>
          </div>
          <button className="icon-button" type="button" onClick={onClose} disabled={busy} aria-label="关闭" title="关闭"><X size={18} /></button>
        </header>

        <div className="project-reimbursement-target">
          <span>即将更新</span>
          <strong>{trip.title}</strong>
          <small>{invoiceCount} 张可报销票据 · 项目总支出 {formatMoney(trip.summary?.grand_total_amount)}</small>
        </div>
        <p className="project-reimbursement-note">订单截图、预订凭证和其他辅助附件不会作为报销票据修改状态。</p>
        {error && <p className="form-error" role="alert">项目报销状态未能更新，请重试。</p>}

        <footer className="dialog-actions">
          <button className="button button-secondary" type="button" onClick={onClose} disabled={busy} autoFocus>取消</button>
          <button className="button button-primary" type="button" onClick={onConfirm} disabled={busy || invoiceCount === 0}>
            <BadgeCheck size={16} /> {busy ? "正在更新" : "确认已报销"}
          </button>
        </footer>
      </section>
    </div>
  );
}
