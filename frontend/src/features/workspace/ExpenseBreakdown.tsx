import { BarChart3, WalletCards } from "lucide-react";
import type { TripExpenseSummary } from "../../api/types";
import { formatMoney } from "../../lib/format";

interface ExpenseBreakdownProps {
  summary: TripExpenseSummary | undefined;
  loading: boolean;
}

const categories = [
  { key: "intercity_transport_amount", label: "城际交通", color: "#1565c0" },
  { key: "local_transport_amount", label: "市内交通", color: "#42a5f5" },
  { key: "lodging_amount", label: "住宿", color: "#ef8f2f" },
  { key: "meal_amount", label: "餐饮", color: "#d45d5d" },
  { key: "refund_change_fee", label: "退改签", color: "#7c6bb4" },
  { key: "travel_insurance_amount", label: "保险", color: "#267c83" },
  { key: "other_amount", label: "其他", color: "#7a827d" },
] as const;

function ratio(value: number, total: number): number {
  if (total <= 0 || value <= 0) return 0;
  return Math.min(100, (value / total) * 100);
}

export function ExpenseBreakdown({ summary, loading }: ExpenseBreakdownProps) {
  const visibleCategories = summary
    ? categories.map((category) => ({ ...category, value: summary[category.key] })).filter((category) => category.value > 0)
    : [];
  const projectTotal = summary?.grand_total_amount ?? 0;
  const currentClaim = summary?.reimbursement_total_amount ?? projectTotal;
  const reimbursed = summary?.reimbursed_total_amount ?? 0;
  const unallocated = summary?.unallocated_total_amount ?? Math.max(0, projectTotal - currentClaim - reimbursed);

  return (
    <section className="workspace-section expense-breakdown finance-progress-card" aria-labelledby="expense-title">
      <div className="section-heading">
        <div><p className="eyebrow">财务</p><h2 id="expense-title">费用与报销</h2></div>
        <WalletCards size={18} className="section-icon" aria-hidden="true" />
      </div>
      {loading && <div className="compact-empty">正在计算项目费用...</div>}
      {!loading && !summary && <div className="compact-empty">项目费用暂时无法加载。</div>}
      {!loading && summary && (
        <>
          <div className="finance-total-lockup">
            <span>项目总支出</span>
            <strong>{formatMoney(projectTotal)}</strong>
            <small>票据 {formatMoney(summary.invoice_total_amount)} · 出差补助 {formatMoney(summary.allowance_amount)}</small>
          </div>

          <dl className="reimbursement-metrics" aria-label="报销金额进度">
            <div className="reimbursement-metric-pending"><dt><span>本次待报销</span><small>票据 {formatMoney(summary.reimbursement_invoice_total_amount)} · 补助 {formatMoney(summary.reimbursement_allowance_amount)}</small></dt><dd>{formatMoney(currentClaim)}</dd></div>
            <div className="reimbursement-metric-complete"><dt><span>已报销</span><small>票据 {formatMoney(summary.reimbursed_invoice_amount)} · 补助 {formatMoney(summary.reimbursed_allowance_amount)}</small></dt><dd>{formatMoney(reimbursed)}</dd></div>
            <div className="reimbursement-metric-unallocated"><dt>待确认 / 未纳入</dt><dd>{formatMoney(unallocated)}</dd></div>
          </dl>

          <div className="reimbursement-progress" aria-label={`项目总支出 ${formatMoney(projectTotal)}，本次待报销 ${formatMoney(currentClaim)}，已报销 ${formatMoney(reimbursed)}，待确认或未纳入 ${formatMoney(unallocated)}`}>
            <span className="reimbursement-progress-complete" style={{ width: `${ratio(reimbursed, projectTotal)}%` }} />
            <span className="reimbursement-progress-pending" style={{ width: `${ratio(currentClaim, projectTotal)}%` }} />
            <span className="reimbursement-progress-unallocated" style={{ width: `${ratio(unallocated, projectTotal)}%` }} />
          </div>

          <div className="expense-category-heading"><span><BarChart3 size={15} aria-hidden="true" /> 费用构成</span><small>{visibleCategories.length} 类费用</small></div>
          {visibleCategories.length === 0 ? <p className="workspace-action-muted">完成票据处理后会显示费用构成。</p> : (
            <ul className="expense-category-list">
              {visibleCategories.map((category) => (
                <li key={category.key}>
                  <div><span><i style={{ backgroundColor: category.color }} />{category.label}</span><strong>{formatMoney(category.value)}</strong></div>
                  <span className="expense-track"><span style={{ width: `${ratio(category.value, summary.invoice_total_amount)}%`, backgroundColor: category.color }} /></span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
