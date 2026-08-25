import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, DragEvent } from "react";
import { CheckCircle2, FileUp, FolderUp, RotateCcw, UploadCloud, XCircle } from "lucide-react";
import { uploadTripFile } from "../../api/resources";
import type { Job } from "../../api/types";
import { formatBytes } from "../../lib/format";

type QueueState = "READY" | "UPLOADING" | "UPLOADED" | "FAILED";

interface QueuedFile {
  id: string;
  file: File;
  relativePath: string | null;
  state: QueueState;
  loaded: number;
  sha256: string | null;
  error: string | null;
  recognitionState: Job["state"] | null;
}

interface UploadPanelProps {
  tripId: string;
  onUploaded: () => void;
}

const supportedExtensions = new Set(["pdf", "jpg", "jpeg", "png"]);

function createId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function isSupported(file: File): boolean {
  const extension = file.name.split(".").pop()?.toLowerCase() || "";
  return supportedExtensions.has(extension);
}

function relativePathFor(file: File): string | null {
  const path = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
  if (!path || path.startsWith("/") || /^[A-Za-z]:[\\/]/.test(path) || path.includes("\\")) return null;
  const segments = path.split("/");
  if (segments.some((segment) => !segment || segment === "." || segment === "..")) return null;
  return segments.join("/");
}

function recognitionLabel(state: Job["state"] | null): string {
  switch (state) {
    case "SUCCEEDED": return "已上传，识别已完成";
    case "RUNNING": return "已上传，正在自动识别";
    case "RETRYING": return "已上传，正在重试识别";
    case "FAILED": return "自动识别失败，可在票据明细中重试";
    case "PENDING":
    case "QUEUED": return "已上传，自动识别已排队";
    default: return "已上传，自动识别已提交";
  }
}

export function UploadPanel({ tripId, onUploaded }: UploadPanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const directoryInputRef = useRef<HTMLInputElement>(null);
  const activeRef = useRef(false);
  const [items, setItems] = useState<QueuedFile[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    const input = directoryInputRef.current;
    input?.setAttribute("webkitdirectory", "");
    input?.setAttribute("directory", "");
  }, []);

  function addFiles(files: FileList | File[]) {
    const next = Array.from(files).map((file): QueuedFile => ({
      id: createId(),
      file,
      relativePath: relativePathFor(file),
      state: isSupported(file) ? "READY" : "FAILED",
      loaded: 0,
      sha256: null,
      error: isSupported(file) ? null : "仅支持 PDF、JPG、JPEG、PNG 文件。",
      recognitionState: null,
    }));
    setItems((previous) => [...previous, ...next]);
  }

  function pickFiles(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) addFiles(event.target.files);
    event.target.value = "";
  }

  function dragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(true);
  }

  function drop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    if (event.dataTransfer.files.length > 0) addFiles(event.dataTransfer.files);
  }

  function updateItem(id: string, update: Partial<QueuedFile>) {
    setItems((previous) => previous.map((item) => item.id === id ? { ...item, ...update } : item));
  }

  async function uploadPending() {
    if (activeRef.current) return;
    const pending = items.filter((item) => item.state === "READY");
    if (pending.length === 0) return;
    activeRef.current = true;
    setIsUploading(true);
    let completed = false;

    for (const item of pending) {
      updateItem(item.id, { state: "UPLOADING", loaded: 0, error: null });
      try {
        const receipt = await uploadTripFile(tripId, item.file, item.relativePath, (progress) => {
          updateItem(item.id, { loaded: progress.total ? progress.loaded / progress.total : 0 });
        });
        updateItem(item.id, {
          state: "UPLOADED",
          loaded: 1,
          sha256: receipt.document.sha256,
          recognitionState: receipt.job?.state || null,
        });
        completed = true;
      } catch (error) {
        updateItem(item.id, {
          state: "FAILED",
          error: error instanceof Error ? error.message : "上传未能完成，请重试。",
        });
      }
    }

    activeRef.current = false;
    setIsUploading(false);
    if (completed) onUploaded();
  }

  const readyCount = items.filter((item) => item.state === "READY").length;
  const uploadedCount = items.filter((item) => item.state === "UPLOADED").length;
  const failedCount = items.filter((item) => item.state === "FAILED").length;
  const queueLabel = readyCount > 0
    ? `${readyCount} 个待上传文件`
    : failedCount > 0
      ? `已完成 ${uploadedCount} 个，${failedCount} 个需要处理`
      : `已完成 ${uploadedCount} 个文件`;

  return (
    <section className="workspace-section upload-section" aria-labelledby="upload-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">上传</p>
          <h2 id="upload-title">添加票据文件</h2>
        </div>
        <span className="muted">每个文件独立上传，失败文件可单独重试。</span>
      </div>
      <div
        className={`drop-zone${isDragging ? " dragging" : ""}`}
        onDragEnter={dragOver}
        onDragOver={dragOver}
        onDragLeave={() => setIsDragging(false)}
        onDrop={drop}
      >
        <UploadCloud size={30} aria-hidden="true" />
        <strong>拖放票据到这里</strong>
        <span>支持 PDF、JPG、JPEG、PNG。</span>
        <div className="drop-zone-actions">
          <button className="button button-secondary" type="button" onClick={() => fileInputRef.current?.click()}><FileUp size={16} /> 选择文件</button>
          <button className="button button-secondary" type="button" onClick={() => directoryInputRef.current?.click()}><FolderUp size={16} /> 选择目录</button>
        </div>
        <input ref={fileInputRef} className="visually-hidden" type="file" multiple accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={pickFiles} />
        <input ref={directoryInputRef} className="visually-hidden" type="file" multiple onChange={pickFiles} />
      </div>

      {items.length > 0 && (
        <div className="upload-queue">
          <div className="queue-heading">
            <span>{queueLabel}</span>
            {readyCount > 0 && <button className="button button-primary" type="button" disabled={isUploading} onClick={() => void uploadPending()}>
              <UploadCloud size={16} /> {isUploading ? "正在上传" : `上传 ${readyCount} 个文件`}
            </button>}
          </div>
          <ul>
            {items.map((item) => (
              <li key={item.id} className="upload-item">
                <div className="upload-item-main">
                  {item.state === "UPLOADED" ? <CheckCircle2 className="status-success" size={18} /> : item.state === "FAILED" ? <XCircle className="status-error" size={18} /> : <FileUp size={18} />}
                  <div>
                    <strong>{item.file.name}</strong>
                    <span>{item.relativePath || "所选文件"} · {formatBytes(item.file.size)}</span>
                    {item.sha256 && <span>SHA-256 {item.sha256.slice(0, 16)}...</span>}
                    {item.state === "UPLOADED" && <span className={`upload-recognition-state${item.recognitionState === "FAILED" ? " error" : item.recognitionState === "SUCCEEDED" ? " success" : ""}`}>{recognitionLabel(item.recognitionState)}</span>}
                    {item.error && <small className="form-error">{item.error}</small>}
                  </div>
                </div>
                <div className="upload-item-status">
                  {item.state === "UPLOADING" && <div className="progress-track"><span style={{ width: `${Math.round(item.loaded * 100)}%` }} /></div>}
                  {item.state === "FAILED" && isSupported(item.file) && <button className="icon-button" type="button" title="重新加入上传队列" aria-label="重新加入上传队列" onClick={() => updateItem(item.id, { state: "READY", error: null, loaded: 0 })}><RotateCcw size={16} /></button>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
