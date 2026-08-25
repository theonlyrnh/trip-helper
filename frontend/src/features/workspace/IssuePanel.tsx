import { useMutation } from "@tanstack/react-query";
import { Check, CircleAlert, EyeOff } from "lucide-react";
import { issuesApi } from "../../api/resources";
import type { ReviewIssue } from "../../api/types";
import { labelForIssueType } from "../../lib/format";

interface IssuePanelProps {
  issues: ReviewIssue[];
  loading: boolean;
  onChanged: () => void;
}

export function IssuePanel({ issues, loading, onChanged }: IssuePanelProps) {
  const updateIssue = useMutation({
    mutationFn: ({ issueId, ignored }: { issueId: string; ignored: boolean }) => issuesApi.update(issueId, { resolved: true, ignored }),
    onSuccess: onChanged,
  });
  const unresolved = issues.filter((issue) => !issue.resolved);
  const groups = [
    { severity: "ERROR", label: "错误" },
    { severity: "WARNING", label: "警告" },
    { severity: "INFO", label: "提示" },
  ].map((group) => ({ ...group, issues: unresolved.filter((issue) => issue.severity === group.severity) })).filter((group) => group.issues.length > 0);

  return (
    <section className="workspace-section" aria-labelledby="issues-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">复核</p>
          <h2 id="issues-title">异常处理</h2>
        </div>
        <span className="muted">{unresolved.length} 条待处理</span>
      </div>
      {loading && <div className="compact-empty">正在加载异常...</div>}
      {!loading && unresolved.length === 0 && <div className="compact-empty">当前没有待处理异常。</div>}
      {groups.map((group) => (
        <section className={`issue-group issue-group-${group.severity.toLowerCase()}`} key={group.severity} aria-label={`${group.label} ${group.issues.length} 条`}>
          <h3>{group.label} <span>{group.issues.length}</span></h3>
          <ul className="issue-list">
            {group.issues.map((issue) => (
              <li key={issue.id} className="issue-item">
                <CircleAlert className={issue.severity === "ERROR" ? "status-error" : issue.severity === "WARNING" ? "status-warning" : "status-success"} size={18} />
                <div className="issue-copy"><strong>{issue.message}</strong><span>{issue.file_name || labelForIssueType(issue.issue_type)}{issue.suggestion ? ` · ${issue.suggestion}` : ""}</span></div>
                <div className="issue-actions">
                  <button className="icon-button" type="button" title="标记已解决" aria-label="标记已解决" disabled={updateIssue.isPending} onClick={() => updateIssue.mutate({ issueId: issue.id, ignored: false })}><Check size={16} /></button>
                  <button className="icon-button" type="button" title="忽略异常" aria-label="忽略异常" disabled={updateIssue.isPending} onClick={() => updateIssue.mutate({ issueId: issue.id, ignored: true })}><EyeOff size={16} /></button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {updateIssue.error && <p className="form-error" role="alert">异常状态未能更新，请重试。</p>}
    </section>
  );
}
