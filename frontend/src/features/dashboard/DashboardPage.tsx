import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BarChart3, CalendarRange, CircleAlert, FileText, HandCoins, MapPinned, WalletCards } from "lucide-react";
import { Link } from "react-router-dom";
import { dashboardApi } from "../../api/resources";
import type { AnnualProject, MonthlyTrend as MonthlyTrendItem, YearlyDashboard } from "../../api/types";
import { formatDateRange, formatMoney, labelForExpenseCategory, labelForProjectType, labelForReimbursementStatus, labelForState } from "../../lib/format";

const MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];
const categories = [
  { key: "intercity_transport_amount", color: "#1769c2" },
  { key: "local_transport_amount", color: "#2f9bd8" },
  { key: "lodging_amount", color: "#ed8b32" },
  { key: "meal_amount", color: "#d45d66" },
  { key: "refund_change_fee", color: "#8069ad" },
  { key: "travel_insurance_amount", color: "#26838a" },
  { key: "other_amount", color: "#7b8798" },
] as const;
const reimbursementStates = [
  { key: "THIS_TRIP", color: "#1769c2" },
  { key: "ALREADY_REIMBURSED", color: "#338360" },
  { key: "PARTIAL_REIMBURSED", color: "#d99a2b" },
  { key: "NOT_REIMBURSED", color: "#778598" },
  { key: "PENDING", color: "#c96a45" },
] as const;

function amount(value: number | string | null | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function DashboardPage() {
  const [year, setYear] = useState(() => new Date().getFullYear());
  const dashboard = useQuery({ queryKey: ["dashboard", "yearly", year], queryFn: () => dashboardApi.yearly(year) });

  if (dashboard.isPending) return <section className="page"><div className="empty-state">正在汇总年度出差数据...</div></section>;
  if (dashboard.error || !dashboard.data) {
    return (
      <section className="page">
        <div className="empty-state error-state"><CircleAlert size={20} /> 年度出差数据暂时无法加载。<button className="button button-secondary" type="button" onClick={() => void dashboard.refetch()}>重试</button></div>
      </section>
    );
  }

  const data = dashboard.data;
  const years = data.available_years.includes(year) ? data.available_years : [year, ...data.available_years];
  const projectCountLabel = data.recent_projects.length < data.total_project_count
    ? `最近 ${data.recent_projects.length} / 共 ${data.total_project_count}`
    : `${data.recent_projects.length} 个项目`;
  return (
    <section className="page annual-page">
      <header className="page-header annual-page-header">
        <div>
          <p className="eyebrow">年度概览</p>
          <h1>年度出差详情</h1>
          <p className="page-subtitle">{data.travel_project_count} 个差旅项目，{data.daily_project_count} 个日常项目，共覆盖 {data.total_trip_days} 个出差日。</p>
        </div>
        <label className="annual-year-select">
          <span>统计年度</span>
          <select aria-label="统计年度" value={year} onChange={(event) => setYear(Number(event.target.value))}>
            {years.map((option) => <option key={option} value={option}>{option} 年</option>)}
          </select>
        </label>
      </header>

      <section className="annual-metrics" aria-label={`${data.year} 年核心指标`}>
        <Metric icon={<CalendarRange size={19} />} label="年度项目" value={`${data.total_project_count} 个`} detail={`${data.total_trip_days} 个出差日`} />
        <Metric icon={<FileText size={19} />} label="年度总支出" value={formatMoney(amount(data.total_invoice_amount))} detail="票据与交通住宿等费用" tone="primary" />
        <Metric icon={<HandCoins size={19} />} label="年度总收入" value={formatMoney(amount(data.total_income_amount))} detail="差旅补助收入" tone="income" />
        <Metric icon={<WalletCards size={19} />} label="本年度待报销" value={formatMoney(amount(data.unreimbursed_amount))} detail={`已报销 ${formatMoney(amount(data.reimbursed_amount))}`} tone="warning" />
      </section>

      <section className="annual-panel annual-trend-panel" aria-labelledby="annual-trend-title">
        <div className="annual-panel-heading annual-trend-heading">
          <div>
            <p className="eyebrow">收支趋势</p>
            <h2 id="annual-trend-title">月度收支趋势</h2>
            <p>票据费用计入支出，差旅补助单列为收入。</p>
          </div>
          <div className="annual-finance-lockup" aria-label="年度收支汇总">
            <div className="annual-total-lockup"><span>年度总支出</span><strong>{formatMoney(amount(data.total_invoice_amount))}</strong></div>
            <div className="annual-total-lockup annual-income-lockup"><span>年度总收入</span><strong>{formatMoney(amount(data.total_income_amount))}</strong></div>
          </div>
        </div>
        <MonthlyTrend key={data.year} data={data} />
      </section>

      <div className="annual-insights-grid">
        <section className="annual-panel annual-insight-panel" aria-labelledby="annual-category-title">
          <div className="annual-panel-heading"><div><p className="eyebrow">费用构成</p><h2 id="annual-category-title">费用分类</h2></div><BarChart3 size={19} aria-hidden="true" /></div>
          <CategoryBreakdown data={data} />
        </section>
        <section className="annual-panel annual-insight-panel" aria-labelledby="annual-city-title">
          <div className="annual-panel-heading"><div><p className="eyebrow">目的地洞察</p><h2 id="annual-city-title">城市排行</h2></div><MapPinned size={19} aria-hidden="true" /></div>
          <CityRanking data={data} />
        </section>
      </div>

      <section className="annual-panel annual-status-panel" aria-labelledby="annual-status-title">
        <div className="annual-panel-heading"><div><p className="eyebrow">报销进度</p><h2 id="annual-status-title">项目报销状态</h2></div><span>共 {data.total_project_count} 个项目</span></div>
        <ReimbursementOverview data={data} />
      </section>

      <section className="annual-panel annual-projects-panel" aria-labelledby="annual-projects-title">
        <div className="annual-panel-heading"><div><p className="eyebrow">项目明细</p><h2 id="annual-projects-title">年度项目</h2></div><span>{projectCountLabel}</span></div>
        {data.recent_projects.length === 0 ? <div className="compact-empty annual-empty">该年度还没有带日期的项目。</div> : <AnnualProjectTable projects={data.recent_projects} />}
      </section>
    </section>
  );
}

function Metric({ icon, label, value, detail, tone = "default" }: { icon: React.ReactNode; label: string; value: string; detail: string; tone?: "default" | "primary" | "income" | "warning" }) {
  return (
    <div className={`annual-metric annual-metric-${tone}`}>
      <span className="annual-metric-icon">{icon}</span>
      <div className="annual-metric-copy"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>
    </div>
  );
}

type NormalizedMonth = MonthlyTrendItem & { invoice: number; income: number; netExpense: number };

export function MonthlyTrend({ data }: { data: YearlyDashboard }) {
  const months: NormalizedMonth[] = data.monthly_trends.map((item) => {
    const invoice = amount(item.invoice_amount);
    const income = amount(item.allowance_amount);
    return { ...item, invoice, income, netExpense: invoice - income };
  });
  const peak = months.reduce((current, item) => item.invoice > current.invoice ? item : current, months[0] ?? { month: 1, project_count: 0, invoice_amount: 0, allowance_amount: 0, invoice: 0, income: 0, netExpense: 0 });
  const [selectedMonth, setSelectedMonth] = useState(peak.month);
  const [previewMonth, setPreviewMonth] = useState<number | null>(null);
  const selected = months.find((item) => item.month === (previewMonth ?? selectedMonth)) ?? peak;
  const activeMonthCount = months.filter((item) => item.invoice > 0 || item.income > 0 || item.project_count > 0).length;
  const yearlyExpense = months.reduce((total, item) => total + item.invoice, 0);
  const monthlyAverage = yearlyExpense / 12;
  const scale = chartScale(Math.max(...months.flatMap((item) => [item.invoice, item.income]), 0));

  const width = 980;
  const height = 306;
  const left = 70;
  const right = 18;
  const top = 24;
  const baseline = 238;
  const plotHeight = baseline - top;
  const bucketWidth = (width - left - right) / 12;
  const barWidth = 17;
  const barGap = 5;
  const barHeight = (value: number) => value <= 0 ? 0 : Math.max(2, (value / scale.maximum) * plotHeight);

  return (
    <div className="annual-chart-module">
      <div className="annual-trend-facts" aria-label="年度趋势摘要">
        <div><span>活跃月份</span><strong>{activeMonthCount}<small> / 12</small></strong></div>
        <div><span>月均支出</span><strong>{formatMoney(monthlyAverage)}</strong></div>
        <div><span>峰值月份</span><strong>{peak.invoice > 0 ? `${MONTHS[peak.month - 1]} · ${formatMoney(peak.invoice)}` : "暂无支出"}</strong></div>
      </div>

      <div className="annual-chart-toolbar" aria-label="图例">
        <span><i className="annual-legend-swatch annual-legend-invoice" />票据支出</span>
        <span><i className="annual-legend-swatch annual-legend-income" />差旅补助收入</span>
      </div>

      <div className="annual-chart-scroll" tabIndex={0} aria-label="月度收支图表，可横向滚动">
        <svg className="annual-chart" viewBox={`0 0 ${width} ${height}`} role="group" aria-labelledby="annual-chart-title annual-chart-description">
          <title id="annual-chart-title">{data.year} 年月度支出与收入</title>
          <desc id="annual-chart-description">分组柱状图，蓝色表示票据支出，绿色表示差旅补助收入。可选择月份查看详细金额。</desc>
          {scale.ticks.map((tick) => {
            const y = baseline - (tick / scale.maximum) * plotHeight;
            return (
              <g className="annual-chart-gridline" key={tick}>
                <line x1={left} x2={width - right} y1={y} y2={y} />
                <text x={left - 12} y={y + 4} textAnchor="end">{formatAxisAmount(tick)}</text>
              </g>
            );
          })}
          {months.map((item, index) => {
            const center = left + bucketWidth * (index + 0.5);
            const invoiceHeight = barHeight(item.invoice);
            const incomeHeight = barHeight(item.income);
            const isSelected = selected.month === item.month;
            const isPeak = peak.invoice > 0 && peak.month === item.month;
            const labelY = Math.min(baseline - invoiceHeight, baseline - incomeHeight) - 9;
            const accessibleLabel = `${MONTHS[item.month - 1]}，${item.project_count} 个项目，票据支出 ${formatMoney(item.invoice)}，补助收入 ${formatMoney(item.income)}，净支出 ${formatMoney(item.netExpense)}`;
            return (
              <g
                className={`annual-chart-month${isSelected ? " is-selected" : ""}`}
                key={item.month}
                role="button"
                tabIndex={0}
                aria-label={accessibleLabel}
                aria-pressed={selectedMonth === item.month}
                onMouseEnter={() => setPreviewMonth(item.month)}
                onMouseLeave={() => setPreviewMonth(null)}
                onFocus={() => setPreviewMonth(item.month)}
                onBlur={() => setPreviewMonth(null)}
                onClick={() => setSelectedMonth(item.month)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    setSelectedMonth(item.month);
                  }
                }}
              >
                <rect className="annual-chart-month-focus" x={center - bucketWidth / 2 + 4} y={top - 11} width={bucketWidth - 8} height={plotHeight + 57} rx="5" />
                {isPeak && <text className="annual-chart-peak-label" x={center} y={Math.max(top - 5, labelY)} textAnchor="middle">峰值</text>}
                <rect className="annual-chart-bar annual-chart-bar-invoice" x={center - barGap / 2 - barWidth} y={baseline - invoiceHeight} width={barWidth} height={invoiceHeight} rx="3" />
                <rect className="annual-chart-bar annual-chart-bar-income" x={center + barGap / 2} y={baseline - incomeHeight} width={barWidth} height={incomeHeight} rx="3" />
                <text className="annual-chart-month-label" x={center} y={baseline + 24} textAnchor="middle">{MONTHS[item.month - 1]}</text>
                <text className="annual-chart-project-label" x={center} y={baseline + 42} textAnchor="middle">{item.project_count} 项</text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="annual-chart-selection" aria-live="polite" aria-label={`${MONTHS[selected.month - 1]}收支明细`}>
        <div className="annual-selected-month"><span>{data.year} 年</span><strong>{MONTHS[selected.month - 1]}</strong></div>
        <dl>
          <div><dt>净支出</dt><dd>{formatMoney(selected.netExpense)}</dd></div>
          <div><dt><i className="annual-detail-dot annual-detail-invoice" />票据支出</dt><dd>{formatMoney(selected.invoice)}</dd></div>
          <div><dt><i className="annual-detail-dot annual-detail-income" />补助收入</dt><dd>{formatMoney(selected.income)}</dd></div>
          <div><dt>项目数量</dt><dd>{selected.project_count} 个</dd></div>
        </dl>
      </div>
    </div>
  );
}

function chartScale(value: number): { maximum: number; ticks: number[] } {
  if (value <= 0) return { maximum: 1000, ticks: [0, 250, 500, 750, 1000] };
  const roughStep = value / 4;
  const magnitude = 10 ** Math.floor(Math.log10(roughStep));
  const normalized = roughStep / magnitude;
  const niceNormalized = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10;
  const step = niceNormalized * magnitude;
  const maximum = Math.ceil(value / step) * step;
  const count = Math.round(maximum / step);
  return { maximum, ticks: Array.from({ length: count + 1 }, (_, index) => index * step) };
}

function formatAxisAmount(value: number): string {
  if (value === 0) return "¥0";
  if (value >= 10_000) return `¥${Number((value / 10_000).toFixed(1))}万`;
  if (value >= 1_000) return `¥${Number((value / 1_000).toFixed(1))}千`;
  return `¥${value}`;
}

function CategoryBreakdown({ data }: { data: YearlyDashboard }) {
  const items = categories.map((category) => ({ ...category, value: amount(data.category_summary[category.key]) })).filter((category) => category.value > 0);
  const total = items.reduce((sum, item) => sum + item.value, 0);
  if (items.length === 0) return <div className="compact-empty annual-empty">该年度暂无可汇总费用。</div>;
  return (
    <>
      <div className="annual-category-composition" aria-label={`票据费用合计 ${formatMoney(total)}`}>
        {items.map((item) => <span key={item.key} style={{ width: `${(item.value / total) * 100}%`, backgroundColor: item.color }} title={`${categoryLabel(item.key)} ${formatMoney(item.value)}`} />)}
      </div>
      <ol className="annual-breakdown-list">
        {items.map((item) => {
          const share = (item.value / total) * 100;
          return (
            <li key={item.key}>
              <div className="annual-breakdown-row">
                <span className="annual-breakdown-name"><i style={{ backgroundColor: item.color }} />{categoryLabel(item.key)}<small>{formatPercent(share)}</small></span>
                <strong>{formatMoney(item.value)}</strong>
              </div>
              <span className="annual-breakdown-track"><span style={{ width: `${Math.max(1.5, share)}%`, backgroundColor: item.color }} /></span>
            </li>
          );
        })}
      </ol>
    </>
  );
}

function categoryLabel(key: string): string {
  return labelForExpenseCategory(key.replace("_amount", "").toUpperCase());
}

function formatPercent(value: number): string {
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)}%`;
}

function CityRanking({ data }: { data: YearlyDashboard }) {
  const cities = data.city_summary.slice(0, 8);
  const maximum = Math.max(...cities.map((city) => city.count), 1);
  const totalVisits = data.city_summary.reduce((sum, city) => sum + city.count, 0);
  if (cities.length === 0) return <div className="compact-empty annual-empty">识别到交通票据后会显示城市排行。</div>;
  return (
    <ol className="annual-city-list">
      {cities.map((city, index) => (
        <li className={index < 3 ? `is-top is-top-${index + 1}` : ""} key={city.city}>
          <span className="annual-city-rank">{index + 1}</span>
          <div className="annual-city-copy">
            <div><strong>{city.city}</strong><small>{formatPercent((city.count / totalVisits) * 100)}</small></div>
            <span className="annual-city-track"><span style={{ width: `${(city.count / maximum) * 100}%` }} /></span>
          </div>
          <span className="annual-city-count"><strong>{city.count}</strong> 次</span>
        </li>
      ))}
    </ol>
  );
}

function ReimbursementOverview({ data }: { data: YearlyDashboard }) {
  const items = reimbursementStates.map((state) => ({ ...state, count: amount(data.reimbursement_summary[state.key]) }));
  const total = items.reduce((sum, item) => sum + item.count, 0);
  return (
    <div className="annual-status-overview">
      <div className="annual-status-distribution" aria-label="报销状态分布">
        {total === 0 ? <span className="annual-status-empty-segment" /> : items.filter((item) => item.count > 0).map((item) => (
          <span key={item.key} style={{ width: `${(item.count / total) * 100}%`, backgroundColor: item.color }} title={`${labelForReimbursementStatus(item.key)} ${item.count} 个`} />
        ))}
      </div>
      <div className="annual-status-list">
        {items.map((item) => {
          const percentage = total > 0 ? (item.count / total) * 100 : 0;
          return (
            <div key={item.key}>
              <span className="annual-status-name"><i style={{ backgroundColor: item.color }} />{labelForReimbursementStatus(item.key)}</span>
              <strong>{item.count}<small> 个项目</small></strong>
              <span className="annual-status-share">{formatPercent(percentage)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AnnualProjectTable({ projects }: { projects: AnnualProject[] }) {
  return (
    <div className="annual-project-table-scroll">
      <table className="annual-project-table">
        <thead><tr><th>项目</th><th>日期</th><th>路线</th><th>文件</th><th>票据支出</th><th>补助收入</th><th>净支出</th><th>报销状态</th><th aria-label="打开项目" /></tr></thead>
        <tbody>{projects.map((project) => <tr key={project.id}>
          <td className="annual-project-name"><Link to={`/trips/${project.id}`}><strong>{project.title}</strong><span>{labelForProjectType(project.project_type)}</span></Link></td>
          <td>{formatDateRange(project.start_date, project.end_date)}<small>{project.trip_days} 天</small></td>
          <td className="annual-route-cell" title={project.route_text || undefined}>{project.route_text || "路线待确认"}</td>
          <td><strong>{project.document_count}</strong><small>份文件</small></td>
          <td><strong>{formatMoney(amount(project.invoice_total_amount))}</strong></td>
          <td><strong>{formatMoney(amount(project.allowance_amount))}</strong></td>
          <td><strong>{formatMoney(amount(project.invoice_total_amount) - amount(project.allowance_amount))}</strong></td>
          <td><span className={`annual-reimbursement-state annual-reimbursement-${project.reimbursement_status.toLowerCase()}`}>{labelForReimbursementStatus(project.reimbursement_status)}</span><small>{labelForState(project.status)}</small></td>
          <td><Link className="annual-open-link" to={`/trips/${project.id}`} aria-label={`打开 ${project.title}`}><ArrowRight size={16} /></Link></td>
        </tr>)}</tbody>
      </table>
    </div>
  );
}
