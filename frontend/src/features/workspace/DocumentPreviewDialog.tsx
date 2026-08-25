import { Download, X } from "lucide-react";
import { apiUrl } from "../../api/http";
import { documentsApi } from "../../api/resources";
import type { DocumentRecord } from "../../api/types";

interface DocumentPreviewDialogProps {
  document: DocumentRecord | null;
  onClose: () => void;
}

export function DocumentPreviewDialog({ document, onClose }: DocumentPreviewDialogProps) {
  if (!document) return null;
  const previewUrl = apiUrl(`/documents/${document.id}/preview`);
  const isPdf = document.mime_type === "application/pdf" || document.original_filename.toLowerCase().endsWith(".pdf");

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="modal preview-dialog" role="dialog" aria-modal="true" aria-labelledby="preview-title" onMouseDown={(event) => event.stopPropagation()}>
        <header className="dialog-header">
          <div>
            <h2 id="preview-title">{document.original_filename}</h2>
            <p>{document.relative_path || "已上传文件"}</p>
          </div>
          <div className="dialog-icon-actions">
            <button className="icon-button" type="button" title="下载原件" aria-label="下载原件" onClick={() => void documentsApi.download(document.id, document.original_filename)}><Download size={18} /></button>
            <button className="icon-button" type="button" title="关闭预览" aria-label="关闭预览" onClick={onClose}><X size={18} /></button>
          </div>
        </header>
        <div className="preview-content">
          {isPdf && <iframe className="document-frame" src={previewUrl} title={`${document.original_filename} 预览`} />}
          {!isPdf && <img className="document-image" src={previewUrl} alt={`${document.original_filename} 预览`} />}
        </div>
      </section>
    </div>
  );
}
