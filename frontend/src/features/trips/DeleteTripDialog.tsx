import { useEffect } from "react";
import { Trash2, X } from "lucide-react";
import type { Trip } from "../../api/types";
import { formatMoney } from "../../lib/format";

interface DeleteTripDialogProps {
  trip: Trip | null;
  busy: boolean;
  error: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function DeleteTripDialog({ trip, busy, error, onClose, onConfirm }: DeleteTripDialogProps) {
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
        className="modal dialog delete-trip-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-trip-title"
        aria-describedby="delete-trip-description"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="dialog-header delete-trip-header">
          <span className="delete-trip-icon"><Trash2 size={20} aria-hidden="true" /></span>
          <div>
            <h2 id="delete-trip-title">删除项目</h2>
            <p id="delete-trip-description">项目及其全部关联资料将被永久删除。</p>
          </div>
          <button className="icon-button" type="button" onClick={onClose} disabled={busy} aria-label="关闭" title="关闭"><X size={18} /></button>
        </header>

        <div className="delete-trip-target">
          <span>即将删除</span>
          <strong>{trip.title}</strong>
          <small>{trip.summary?.document_count ?? 0} 份文件 · 项目合计 {formatMoney(trip.summary?.grand_total_amount)}</small>
        </div>
        <p className="delete-trip-warning">票据原件、OCR 结果、人工复核记录和导出文件都会一并移除，此操作不可撤销。</p>
        {error && <p className="form-error" role="alert">项目未能删除，现有数据仍然保留，请重试。</p>}

        <footer className="dialog-actions">
          <button className="button button-secondary" type="button" onClick={onClose} disabled={busy} autoFocus>取消</button>
          <button className="button button-danger" type="button" onClick={onConfirm} disabled={busy}>
            <Trash2 size={16} /> {busy ? "正在删除" : "确认删除"}
          </button>
        </footer>
      </section>
    </div>
  );
}
