import { Sparkles } from "lucide-react";

interface PixelAssistantProps {
  activeProcessing: boolean;
  issueCount: number;
  documentCount: number;
  segmentCount: number;
  onReviewIssues?: () => void;
}

function assistantMessage(activeProcessing: boolean, issueCount: number, documentCount: number, segmentCount: number): { title: string; detail: string } {
  if (activeProcessing) return { title: "正在整理新票据", detail: "识别完成后会自动更新明细" };
  if (issueCount > 0) return { title: `${issueCount} 项信息等待复核`, detail: "点击查看异常处理" };
  if (segmentCount > 0) return { title: `${segmentCount} 段行程已核对`, detail: `${documentCount} 份文件已整理入项目` };
  return { title: "随时接收新票据", detail: "上传后会自动开始识别与归类" };
}

export function PixelAssistant({ activeProcessing, issueCount, documentCount, segmentCount, onReviewIssues }: PixelAssistantProps) {
  const message = assistantMessage(activeProcessing, issueCount, documentCount, segmentCount);
  const canReviewIssues = issueCount > 0 && Boolean(onReviewIssues);

  return (
    <section className={`pixel-assistant${canReviewIssues ? " pixel-assistant-actionable" : ""}`} aria-label="报销小助手">
      {canReviewIssues ? (
        <button className="pixel-assistant-bubble" type="button" onClick={onReviewIssues}>
          <span><Sparkles size={13} aria-hidden="true" /> {message.title}</span>
          <small>{message.detail}</small>
        </button>
      ) : (
        <div className="pixel-assistant-bubble" role="status">
          <span><Sparkles size={13} aria-hidden="true" /> {message.title}</span>
          <small>{message.detail}</small>
        </div>
      )}
      <div className="pixel-assistant-stage" aria-hidden="true">
        <div className="pixel-assistant-art">
          <span className="pixel-assistant-coin" />
          <svg className="pixel-assistant-robot" viewBox="0 0 20 20" fill="none" shapeRendering="crispEdges">
            <rect x="9" y="1" width="2" height="3" fill="#60a5fa" />
            <rect x="8" y="0" width="4" height="1" fill="#ef4444" />
            <rect x="2" y="5" width="2" height="5" fill="#1d4ed8" />
            <rect x="16" y="5" width="2" height="5" fill="#1d4ed8" />
            <rect x="4" y="4" width="12" height="10" fill="#2563eb" />
            <rect x="5" y="5" width="10" height="6" fill="#eff6ff" />
            <rect className="pixel-assistant-eye" x="7" y="6" width="2" height="3" fill="#2563eb" />
            <rect className="pixel-assistant-eye" x="11" y="6" width="2" height="3" fill="#2563eb" />
            <rect x="8" y="6" width="1" height="1" fill="#fff" />
            <rect x="12" y="6" width="1" height="1" fill="#fff" />
            <rect x="5" y="9" width="2" height="1" fill="#fca5a5" />
            <rect x="13" y="9" width="2" height="1" fill="#fca5a5" />
            <rect x="9" y="9" width="2" height="1" fill="#2563eb" />
            <rect x="5" y="14" width="10" height="3" fill="#1e40af" />
            <rect x="13" y="11" width="5" height="5" fill="#3b82f6" />
            <rect x="14" y="12" width="3" height="3" fill="#fff" />
            <rect x="6" y="17" width="3" height="2" fill="#1e3a8a" />
            <rect x="11" y="17" width="3" height="2" fill="#1e3a8a" />
          </svg>
        </div>
        <span className="pixel-assistant-shadow" />
        <div className="pixel-assistant-rail">
          <svg className="pixel-assistant-train" viewBox="0 0 25 6" fill="none" shapeRendering="crispEdges">
            <rect x="0" y="2" width="20" height="4" fill="#60a5fa" />
            <rect x="2" y="3" width="3" height="2" fill="#eff6ff" />
            <rect x="7" y="3" width="3" height="2" fill="#eff6ff" />
            <rect x="12" y="3" width="3" height="2" fill="#eff6ff" />
            <rect x="20" y="1" width="4" height="5" fill="#2563eb" />
            <rect x="24" y="0" width="1" height="2" fill="#ef4444" />
          </svg>
        </div>
      </div>
    </section>
  );
}
