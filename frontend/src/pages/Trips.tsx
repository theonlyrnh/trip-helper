import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { getTrips, type TripData } from "../api/trips";
import { tripStatusLabels, reimbursementLabels, formatMoney } from "../utils/labels";

type ReimbFilter = "all" | "NOT_REIMBURSED" | "REIMBURSED" | "PARTIAL_REIMBURSED" | "NOT_REQUIRED";

export default function Trips() {
  const [trips, setTrips] = useState<TripData[]>([]);
  const [filter, setFilter] = useState<ReimbFilter>("all");
  const navigate = useNavigate();

  useEffect(() => {
    getTrips().then(setTrips).catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    if (filter === "all") return trips;
    return trips.filter(t => (t.reimbursement_status || "NOT_REIMBURSED") === filter);
  }, [trips, filter]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1>项目列表</h1>
        <button onClick={() => navigate("/workspace")} style={{ padding: "8px 20px", background: "#1a1a2e", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 14 }}>
          + 新建项目
        </button>
      </div>

      {/* Reimbursement filter */}
      <div style={{ marginBottom: 16, display: "flex", gap: 6, flexWrap: "wrap" }}>
        {([["all", "全部"], ["NOT_REIMBURSED", "未报销"], ["REIMBURSED", "已报销"], ["PARTIAL_REIMBURSED", "部分报销"], ["NOT_REQUIRED", "无需报销"]] as [ReimbFilter, string][]).map(([k, v]) => (
          <button key={k} onClick={() => setFilter(k)}
            style={{ padding: "4px 14px", border: "none", borderRadius: 14, cursor: "pointer", fontSize: 12, background: filter === k ? "#1565c0" : "#f0f0f0", color: filter === k ? "#fff" : "#555" }}>
            {v}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div style={{ textAlign: "center", padding: 60, background: "#fff", borderRadius: 8, color: "#aaa" }}>
          暂无匹配的出差项目
        </div>
      ) : (
        <div style={{ background: "#fff", borderRadius: 8, boxShadow: "0 1px 4px rgba(0,0,0,0.08)", overflow: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #eee", textAlign: "left", fontSize: 12, color: "#888" }}>
                <th style={{ padding: "10px 12px" }}>项目名称</th>
                <th style={{ padding: "10px 12px" }}>文件夹</th>
                <th style={{ padding: "10px 12px" }}>出差时间</th>
                <th style={{ padding: "10px 12px" }}>文件数</th>
                <th style={{ padding: "10px 12px" }}>票据合计</th>
                <th style={{ padding: "10px 12px" }}>补助</th>
                <th style={{ padding: "10px 12px" }}>异常</th>
                <th style={{ padding: "10px 12px" }}>状态</th>
                <th style={{ padding: "10px 12px" }}>报销</th>
                <th style={{ padding: "10px 12px" }}>更新时间</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(t => (
                <tr key={t.id} onClick={() => navigate(`/workspace/${t.id}`)}
                  style={{ cursor: "pointer", borderBottom: "1px solid #f0f0f0" }}
                  onMouseEnter={e => (e.currentTarget.style.background = "#f8f9fa")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                  <td style={{ padding: "10px 12px", fontWeight: 500 }}>{t.title || "未命名"}</td>
                  <td style={{ padding: "10px 12px", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#888" }} title={t.folder_path}>{t.folder_name || t.folder_path}</td>
                  <td style={{ padding: "10px 12px", whiteSpace: "nowrap" }}>
                    {t.confirmed_start_date ? `${t.confirmed_start_date} ~ ${t.confirmed_end_date}` : t.folder_date_start ? `${t.folder_date_start} ~ ${t.folder_date_end}` : "-"}
                  </td>
                  <td style={{ padding: "10px 12px", textAlign: "center" }}>{t.document_count}</td>
                  <td style={{ padding: "10px 12px" }}>{formatMoney(t.invoice_total_amount)}</td>
                  <td style={{ padding: "10px 12px" }}>{formatMoney(t.allowance_amount)}</td>
                  <td style={{ padding: "10px 12px", textAlign: "center" }}>
                    {t.issue_count > 0 ? <span style={{ color: "#c62828", fontWeight: 600 }}>{t.issue_count}</span> : "0"}
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <span style={{ padding: "2px 8px", borderRadius: 10, fontSize: 11, background: t.status === "ANALYZED" ? "#e8f5e9" : "#fff3e0", color: t.status === "ANALYZED" ? "#2e7d32" : "#e65100" }}>
                      {tripStatusLabels[t.status] || t.status}
                    </span>
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <span style={{ padding: "2px 8px", borderRadius: 10, fontSize: 11, background: t.reimbursement_status === "REIMBURSED" ? "#e8f5e9" : "#fff3e0", color: t.reimbursement_status === "REIMBURSED" ? "#2e7d32" : "#e65100" }}>
                      {reimbursementLabels[t.reimbursement_status || "NOT_REIMBURSED"] || "未报销"}
                    </span>
                  </td>
                  <td style={{ padding: "10px 12px", color: "#888", fontSize: 12 }}>{t.updated_at?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}