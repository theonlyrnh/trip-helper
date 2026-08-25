import { useMutation } from "@tanstack/react-query";
import { Download, FileSpreadsheet, FileText, LoaderCircle } from "lucide-react";
import { exportsApi } from "../../api/resources";
import type { ExportRecord } from "../../api/types";
import { formatDate, labelForState } from "../../lib/format";

interface WorkspaceActionsProps {
  tripId: string;
  exports: ExportRecord[];
  documentCount: number;
  loading: boolean;
  onChanged: () => void;
}

export function WorkspaceActions({ tripId, exports, documentCount, loading, onChanged }: WorkspaceActionsProps) {
  const createExport = useMutation({ mutationFn: (format: ExportRecord["format"]) => exportsApi.create(tripId, format), onSuccess: onChanged });
  const latestExports = exports.slice(0, 2);

  return (
    <section className="workspace-section workspace-actions-card" aria-labelledby="workspace-actions-title">
      <div className="section-heading">
        <div><p className="eyebrow">导出</p><h2 id="workspace-actions-title">报销文件</h2></div>
        <span className="workspace-actions-file-count">含 {documentCount} 个文件</span>
      </div>

      <div className="workspace-action-block workspace-export-block">
        <div className="workspace-action-copy"><strong>选择导出格式</strong><span>导出在后台生成，并仅通过当前会话下载。</span></div>
        <div className="workspace-export-buttons">
          <button className="button button-secondary" type="button" disabled={createExport.isPending} onClick={() => createExport.mutate("XLSX")}><FileSpreadsheet size={16} /> Excel</button>
          <button className="button button-secondary" type="button" disabled={createExport.isPending} onClick={() => createExport.mutate("PDF")}><FileText size={16} /> PDF</button>
        </div>
        {loading && <div className="muted-row"><LoaderCircle className="spin" size={15} /> 正在同步导出状态...</div>}
        {!loading && latestExports.length === 0 && <p className="workspace-action-muted">尚未创建导出文件。</p>}
        {latestExports.length > 0 && <ul className="workspace-export-list">
          {latestExports.map((record) => <li key={record.id}>
            <span><strong>{record.format === "XLSX" ? "Excel 明细" : "PDF 报告"}</strong><small>{labelForState(record.status)} · {formatDate(record.created_at)}</small></span>
            {record.status === "SUCCEEDED" && <button className="icon-button" type="button" title="下载导出文件" aria-label="下载导出文件" onClick={() => void exportsApi.download(record)}><Download size={16} /></button>}
          </li>)}
        </ul>}
      </div>
      {createExport.error && <p className="form-error" role="alert">操作未能完成，请稍后重试。</p>}
    </section>
  );
}
