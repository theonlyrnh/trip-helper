import { useMutation } from "@tanstack/react-query";
import { Download, FileSpreadsheet, FileText, LoaderCircle } from "lucide-react";
import { exportsApi } from "../../api/resources";
import type { ExportRecord } from "../../api/types";
import { formatDate, labelForState } from "../../lib/format";

interface ExportActionsProps {
  tripId: string;
  exports: ExportRecord[];
  loading: boolean;
  onChanged: () => void;
}

export function ExportActions({ tripId, exports, loading, onChanged }: ExportActionsProps) {
  const createExport = useMutation({
    mutationFn: (format: ExportRecord["format"]) => exportsApi.create(tripId, format),
    onSuccess: onChanged,
  });
  const latest = exports.slice(0, 5);

  return (
    <section className="workspace-section" aria-labelledby="exports-title">
      <div className="section-heading section-heading-actions">
        <div>
          <p className="eyebrow">导出</p>
          <h2 id="exports-title">报销文件</h2>
        </div>
        <div className="button-group">
          <button className="button button-secondary" type="button" disabled={createExport.isPending} onClick={() => createExport.mutate("XLSX")}><FileSpreadsheet size={16} /> 导出 Excel</button>
          <button className="button button-secondary" type="button" disabled={createExport.isPending} onClick={() => createExport.mutate("PDF")}><FileText size={16} /> 导出 PDF</button>
        </div>
      </div>
      <p className="section-copy">导出由后台生成。完成后通过当前会话下载，不会暴露存储位置。</p>
      {loading && <div className="muted-row"><LoaderCircle className="spin" size={16} /> 正在同步导出状态...</div>}
      {!loading && latest.length === 0 && <div className="compact-empty">尚未创建导出任务。</div>}
      {latest.length > 0 && <ul className="export-list">
        {latest.map((record) => (
          <li key={record.id}>
            <div><strong>{record.format === "XLSX" ? "Excel 报销明细" : "PDF 报销报告"}</strong><span>{labelForState(record.status)} · {formatDate(record.created_at)}</span></div>
            {record.status === "SUCCEEDED" && <button className="icon-button" type="button" title="下载导出文件" aria-label="下载导出文件" onClick={() => void exportsApi.download(record)}><Download size={16} /></button>}
          </li>
        ))}
      </ul>}
      {createExport.error && <p className="form-error" role="alert">导出任务未能创建，请重试。</p>}
    </section>
  );
}
