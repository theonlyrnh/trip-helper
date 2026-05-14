import { useEffect, useState } from "react";
import { formatMoney, reimbursementLabels } from "../utils/labels";

interface YearlyData {
  year: number;
  total_project_count: number;
  total_trip_days: number;
  total_invoice_amount: number;
  total_allowance_amount: number;
  total_with_allowance: number;
  reimbursed_amount: number;
  unreimbursed_amount: number;
  monthly_trends: { month: number; project_count: number; invoice_amount: number; allowance_amount: number }[];
  category_summary: Record<string, number>;
  city_summary: { city: string; count: number }[];
  reimbursement_summary: Record<string, number>;
  recent_projects: { id: number; title: string; start_date: string; end_date: string; route_text: string; document_count: number; invoice_total_amount: number; allowance_amount: number; reimbursement_status: string }[];
}

const MONTHS = ["1月","2月","3月","4月","5月","6月","7月","8月","9月","10月","11月","12月"];

export default function DashboardPage() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [data, setData] = useState<YearlyData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`http://127.0.0.1:8000/api/dashboard/yearly?year=${year}`)
      .then(r => r.json()).then(setData).catch(() => {})
      .finally(() => setLoading(false));
  }, [year]);

  if (loading) return <div style={{ padding: 32, color: "#888" }}>加载中...</div>;
  if (!data) return <div style={{ padding: 32, color: "#888" }}>暂无数据</div>;

  const maxMonthAmount = Math.max(...data.monthly_trends.map(m => m.invoice_amount + m.allowance_amount), 1);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1>年度统计</h1>
        <select value={year} onChange={e => setYear(parseInt(e.target.value))} style={{ padding: "6px 12px", borderRadius: 6, fontSize: 14 }}>
          {[2024, 2025, 2026, 2027].map(y => <option key={y} value={y}>{y}年</option>)}
        </select>
      </div>

      {/* Summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        <Card label="出差次数" value={`${data.total_project_count} 次`} />
        <Card label="出差总天数" value={`${data.total_trip_days} 天`} />
        <Card label="票据总金额" value={formatMoney(data.total_invoice_amount)} accent />
        <Card label="含补助总计" value={formatMoney(data.total_with_allowance)} accent />
        <Card label="已报销" value={formatMoney(data.reimbursed_amount)} color="#2e7d32" />
        <Card label="未报销" value={formatMoney(data.unreimbursed_amount)} color="#c62828" />
        <Card label="去过城市" value={`${data.city_summary.length} 个`} />
        <Card label="差旅补助" value={formatMoney(data.total_allowance_amount)} />
      </div>

      {/* Monthly trend */}
      <div style={S.section}>
        <div style={S.sectionHead}>📈 月度趋势</div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 4, height: 160, paddingTop: 8 }}>
          {data.monthly_trends.map(m => (
            <div key={m.month} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
              <span style={{ fontSize: 10, color: "#888" }}>{formatMoney(m.invoice_amount + m.allowance_amount)}</span>
              <div style={{ width: "100%", background: "#42a5f5", borderRadius: "4px 4px 0 0", height: `${(m.invoice_amount + m.allowance_amount) / maxMonthAmount * 120}px`, minHeight: 2, transition: "height 0.3s" }} />
              <span style={{ fontSize: 10, color: "#888" }}>{MONTHS[m.month - 1]}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Category + City */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
        <div style={S.section}>
          <div style={S.sectionHead}>💰 费用分类</div>
          {Object.entries(data.category_summary).filter(([,v]) => v > 0).map(([k, v]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid #f0f0f0", fontSize: 13 }}>
              <span>{catLabel(k)}</span><span style={{ fontWeight: 600 }}>{formatMoney(v)}</span>
            </div>
          ))}
        </div>
        <div style={S.section}>
          <div style={S.sectionHead}>🏙 城市排行</div>
          {data.city_summary.slice(0, 10).map(c => (
            <div key={c.city} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid #f0f0f0", fontSize: 13 }}>
              <span>{c.city}</span><span style={{ color: "#888" }}>{c.count} 次</span>
            </div>
          ))}
        </div>
      </div>

      {/* Reimbursement */}
      <div style={S.section}>
        <div style={S.sectionHead}>📋 报销状态</div>
        <div style={{ display: "flex", gap: 24 }}>
          {Object.entries(data.reimbursement_summary).map(([k, v]) => (
            <div key={k} style={{ textAlign: "center" }}>
              <div style={{ fontSize: 24, fontWeight: 700 }}>{v}</div>
              <div style={{ fontSize: 12, color: "#888" }}>{reimbursementLabels[k] || k}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent projects */}
      <div style={S.section}>
        <div style={S.sectionHead}>📂 最近项目</div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead><tr style={{ color: "#888", fontSize: 12 }}>
            <th style={{ padding: "6px 8px", textAlign: "left" }}>项目</th>
            <th style={{ padding: "6px 8px" }}>日期</th>
            <th style={{ padding: "6px 8px" }}>路线</th>
            <th style={{ padding: "6px 8px" }}>票据</th>
            <th style={{ padding: "6px 8px" }}>补助</th>
            <th style={{ padding: "6px 8px" }}>报销</th>
          </tr></thead>
          <tbody>
            {data.recent_projects.map(p => (
              <tr key={p.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                <td style={{ padding: "6px 8px" }}><a href={`/workspace/${p.id}`} style={{ color: "#1565c0", textDecoration: "none" }}>{p.title || "未命名"}</a></td>
                <td style={{ padding: "6px 8px", fontSize: 12 }}>{p.start_date}~{p.end_date}</td>
                <td style={{ padding: "6px 8px", fontSize: 12, maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.route_text || "-"}</td>
                <td style={{ padding: "6px 8px" }}>{formatMoney(p.invoice_total_amount)}</td>
                <td style={{ padding: "6px 8px" }}>{formatMoney(p.allowance_amount)}</td>
                <td style={{ padding: "6px 8px" }}>{reimbursementLabels[p.reimbursement_status] || "未报销"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Card({ label, value, accent, color }: { label: string; value: string; accent?: boolean; color?: string }) {
  return <div style={{ ...S.card }}>
    <div style={{ fontSize: 12, color: "#888", marginBottom: 4 }}>{label}</div>
    <div style={{ fontSize: 20, fontWeight: 700, color: color || (accent ? "#1565c0" : "#333") }}>{value}</div>
  </div>;
}

function catLabel(k: string): string {
  const m: Record<string, string> = {
    intercity_transport: "城际交通", local_transport: "市内交通",
    lodging: "住宿费", meal: "餐饮费", other: "其他",
  };
  return m[k] || k;
}

const S: Record<string, React.CSSProperties> = {
  section: { background: "#fff", borderRadius: 8, boxShadow: "0 1px 4px rgba(0,0,0,0.08)", padding: 20, marginBottom: 16 },
  sectionHead: { fontSize: 15, fontWeight: 600, marginBottom: 12 },
  card: { background: "#fff", borderRadius: 8, boxShadow: "0 1px 4px rgba(0,0,0,0.08)", padding: "16px 20px", textAlign: "center" },
};