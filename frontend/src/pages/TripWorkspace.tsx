import { useEffect, useState, useCallback, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getTrips, getRecentTrip, createTrip, updateTrip, selectFolder,
  scanTripDocuments, preprocessDocuments, recognizeTrip, analyzeTrip,
  getWorkspace, findTripByFolder,
  type TripData, type WorkspaceData, type WorkspaceDoc,
  type IssueData, type RouteSegment,
} from "../api/trips";
import {
  severityLabels, issueTypeLabels, scanStatusLabels, ocrStatusLabels,
  invoiceTypeLabels, expenseCategoryLabels, tripStatusLabels, reimbursementLabels,
  formatMoney, formatSize,
} from "../utils/labels";

const LS_KEY = "currentTripId";

type FilterKey = "all" | "success" | "failed" | "review" | "hasIssue" | "noAmount"
  | "train" | "flight" | "lodging" | "other";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "success", label: "识别成功" },
  { key: "failed", label: "识别失败" },
  { key: "hasIssue", label: "有异常" },
  { key: "noAmount", label: "金额未识别" },
  { key: "train", label: "高铁票" },
  { key: "flight", label: "机票" },
  { key: "lodging", label: "住宿费" },
  { key: "other", label: "其他" },
];

export default function TripWorkspace() {
  const { tripId: paramId } = useParams<{ tripId?: string }>();
  const navigate = useNavigate();
  const tripId = paramId ? parseInt(paramId) : null;

  const [trips, setTrips] = useState<TripData[]>([]);
  const [trip, setTrip] = useState<TripData | null>(null);
  const [folderPath, setFolderPath] = useState("");
  const [folderSet, setFolderSet] = useState(false);
  const [title, setTitle] = useState("");
  const [docs, setDocs] = useState<WorkspaceDoc[]>([]);
  const [summary, setSummary] = useState<WorkspaceData["summary"] | null>(null);
  const [issues, setIssues] = useState<IssueData[]>([]);
  const [segments, setSegments] = useState<RouteSegment[]>([]);
  const [stats, setStats] = useState({ total_files: 0, recognized: 0, review_count: 0, issues: 0 });

  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [progress, setProgress] = useState("");

  const [detailDoc, setDetailDoc] = useState<WorkspaceDoc | null>(null);
  const [detailIssues, setDetailIssues] = useState<IssueData[]>([]);
  const [filterKey, setFilterKey] = useState<FilterKey>("all");
  const [issueFilterDocId, setIssueFilterDocId] = useState<number | null>(null);

  // ── Auto-restore ──
  useEffect(() => {
    (async () => {
      try { setTrips(await getTrips()); } catch { /* */ }
      if (tripId) return;
      const saved = localStorage.getItem(LS_KEY);
      if (saved) { navigate(`/workspace/${saved}`, { replace: true }); return; }
      try {
        const recent = await getRecentTrip();
        if (recent) navigate(`/workspace/${recent.id}`, { replace: true });
      } catch { /* no trips yet */ }
    })();
  }, []);

  // ── Load workspace ──
  const loadWorkspace = useCallback(async () => {
    if (!tripId) { resetAll(); return; }
    try {
      const ws = await getWorkspace(tripId);
      setTrip(ws.trip); setStats(ws.stats); setSummary(ws.summary);
      setDocs(ws.documents); setIssues(ws.issues); setSegments(ws.route_segments);
      if (!folderSet) { setFolderPath(ws.trip.folder_path); setTitle(ws.trip.title); }
      localStorage.setItem(LS_KEY, String(tripId));
    } catch { setError("加载工作台失败"); }
  }, [tripId, folderSet]);

  useEffect(() => { loadWorkspace(); }, [loadWorkspace]);

  const resetAll = () => {
    setTrip(null); setDocs([]); setSummary(null); setIssues([]); setSegments([]);
    setStats({ total_files: 0, recognized: 0, review_count: 0, issues: 0 });
  };

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 2500); };

  // ── Actions ──
  const handleSelectTrip = (id: number) => {
    setFolderSet(false); setDetailDoc(null); setIssueFilterDocId(null); setFilterKey("all");
    navigate(`/workspace/${id}`);
  };

  const handleSelectFolder = async () => {
    setLoading("选择文件夹");
    setError(null);
    try {
      const r = await selectFolder();
      if (!r.success || !r.folder_path) {
        if (r.message) setError(r.message);
        return;
      }
      const path = r.folder_path;
      setFolderPath(path); setFolderSet(true);

      // Check if folder already has a trip
      const existing = await findTripByFolder(path);
      if (existing) {
        showToast("已切换到已有出差项目");
        navigate(`/workspace/${existing.id}`);
      } else {
        // Create new trip for this folder
        const created = await createTrip({ title: "", folder_path: path });
        await loadTrips();
        showToast("已为该文件夹创建新的出差项目");
        navigate(`/workspace/${created.id}`);
      }
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(null); }
  };

  const handleSave = async () => {
    if (!folderPath.trim()) return;
    setLoading("保存");
    try {
      if (tripId) {
        const t = await updateTrip(tripId, { title, folder_path: folderPath });
        setTrip(t); showToast("已保存当前项目");
      } else {
        const t = await createTrip({ title: title || "未命名出差", folder_path: folderPath });
        setTrip(t); await loadTrips(); navigate(`/workspace/${t.id}`);
        showToast("项目已创建");
      }
    } catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setLoading(null); }
  };

  const loadTrips = async () => { try { setTrips(await getTrips()); } catch { /* */ } };

  const handleScan = async () => { if (!tripId) return; setLoading("扫描"); try { await scanTripDocuments(tripId); await loadWorkspace(); } catch (e: unknown) { setError(String(e)); } finally { setLoading(null); } };
  const handlePreprocess = async () => { if (!tripId) return; setLoading("预处理"); try { await preprocessDocuments(tripId); await loadWorkspace(); } catch (e: unknown) { setError(String(e)); } finally { setLoading(null); } };
  const handleRecognize = async () => { if (!tripId) return; setLoading("OCR"); try { await recognizeTrip(tripId); await loadWorkspace(); } catch (e: unknown) { setError(String(e)); } finally { setLoading(null); } };
  const handleAnalyze = async () => { if (!tripId) return; setLoading("分析"); try { await analyzeTrip(tripId); await loadWorkspace(); } catch (e: unknown) { setError(String(e)); } finally { setLoading(null); } };

  // ── One-click analyze ──
  const handleOneClick = async () => {
    if (!tripId) return;
    const steps = [
      { label: "扫描文件", fn: () => scanTripDocuments(tripId) },
      { label: "预处理", fn: () => preprocessDocuments(tripId) },
      { label: "OCR识别", fn: () => recognizeTrip(tripId) },
      { label: "分析出差", fn: () => analyzeTrip(tripId) },
    ];
    setError(null);
    for (const s of steps) {
      setProgress(s.label);
      try { await s.fn(); } catch (e: unknown) {
        setError(`${s.label}失败: ${e instanceof Error ? e.message : String(e)}`);
        setProgress(""); return;
      }
    }
    setProgress("加载结果");
    await loadWorkspace();
    setProgress("");
    showToast("一键分析完成");
  };

  const openDetail = (doc: WorkspaceDoc) => {
    setDetailDoc(doc);
    setDetailIssues(issues.filter(i => i.document_id === doc.id));
  };

  // ── Filters ──
  const filteredDocs = useMemo(() => {
    if (filterKey === "all") return docs;
    if (filterKey === "success") return docs.filter(d => d.ocr_status === "SUCCESS");
    if (filterKey === "failed") return docs.filter(d => d.ocr_status === "FAILED");
    if (filterKey === "hasIssue") return docs.filter(d => d.issue_count > 0);
    if (filterKey === "noAmount") return docs.filter(d => !d.total_amount);
    if (filterKey === "train") return docs.filter(d => d.invoice_type === "TRAIN_TICKET");
    if (filterKey === "flight") return docs.filter(d => d.invoice_type === "FLIGHT_TICKET");
    if (filterKey === "lodging") return docs.filter(d => d.expense_category === "LODGING");
    if (filterKey === "other") return docs.filter(d =>
      d.invoice_type && !["TRAIN_TICKET", "FLIGHT_TICKET"].includes(d.invoice_type) &&
      d.expense_category !== "LODGING"
    );
    return docs;
  }, [docs, filterKey]);

  const displayIssues = issueFilterDocId ? issues.filter(i => i.document_id === issueFilterDocId) : issues;

  // ── Chart data ──
  const expenseChart = summary ? [
    { label: "城际交通", value: summary.intercity_transport_amount, color: "#42a5f5" },
    { label: "市内交通", value: summary.local_transport_amount, color: "#66bb6a" },
    { label: "住宿费", value: summary.lodging_amount, color: "#ffa726" },
    { label: "餐饮费", value: summary.meal_amount, color: "#ef5350" },
    { label: "退票/改签费", value: summary.refund_change_fee || 0, color: "#bdbdbd" },
    { label: "其他", value: summary.other_amount, color: "#ab47bc" },
    { label: "差旅补助", value: summary.allowance_amount, color: "#78909c" },
  ].filter(c => c.value > 0) : [];

  const maxExpense = Math.max(...expenseChart.map(c => c.value), 1);

  const dailyData = useMemo(() => {
    const map: Record<string, number> = {};
    docs.forEach(d => { if (d.total_amount) map["未知日期"] = (map["未知日期"] || 0) + d.total_amount; });
    segments.forEach(s => {
      if (s.depart_date && s.amount) {
        map[s.depart_date] = (map[s.depart_date] || 0) + s.amount;
      }
    });
    return Object.entries(map).sort().slice(-14);
  }, [docs, segments]);

  const ocrStats = { success: docs.filter(d => d.ocr_status === "SUCCESS").length, failed: docs.filter(d => d.ocr_status === "FAILED").length, pending: docs.filter(d => !["SUCCESS", "FAILED"].includes(d.ocr_status)).length };
  const ocrTotal = ocrStats.success + ocrStats.failed + ocrStats.pending || 1;

  return (
    <div>
      <h1>出差项目工作台</h1>

      {toast && <div style={S.toast}>{toast}</div>}
      {error && <div style={S.errorBanner}>{error}<button onClick={() => setError(null)} style={S.errorClose}>✕</button></div>}
      {loading && <div style={S.loadingBar}>⏳ {loading}...</div>}
      {progress && <div style={S.progressBar}>🔄 {progress}...</div>}

      {/* ── Trip selector ── */}
      <div style={S.section}>
        <div style={S.sectionHead}>
          <span>📋 选择出差项目</span>
          <select value={tripId ?? ""} onChange={e => { if (e.target.value) handleSelectTrip(parseInt(e.target.value)); }} style={S.select}>
            <option value="">-- 选择已有项目或新建 --</option>
            {trips.map(t => (<option key={t.id} value={t.id}>#{t.id} {t.title} ({tripStatusLabels[t.status] || t.status})</option>))}
          </select>
        </div>
      </div>

      {/* ── Info ── */}
      <div style={S.section}>
        <div style={S.sectionHead}>📁 项目信息</div>
        <div style={S.row}>
          <label style={S.lbl}>项目名称 <input value={title} onChange={e => setTitle(e.target.value)} placeholder="例如：上海出差" style={S.inp} /></label>
          <label style={S.lbl}>文件夹路径 <input value={folderPath} onChange={e => { setFolderPath(e.target.value); setFolderSet(true); }} placeholder="选择或输入路径" style={{ ...S.inp, width: 420 }} /></label>
        </div>
        {trip && (
          <div style={S.meta}>
            <span>状态: <b>{tripStatusLabels[trip.status] || trip.status}</b></span>
            <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 4 }}>
              类型:
              <select value={trip.project_type || "TRAVEL"}
                onChange={async (e) => {
                  if (!tripId) return;
                  const updated = await updateTrip(tripId, { project_type: e.target.value });
                  setTrip(updated);
                }}
                style={{ padding: "2px 6px", fontSize: 12, borderRadius: 4 }}>
                <option value="TRAVEL">出差报销</option>
                <option value="DAILY">日常发票</option>
                <option value="MIXED">综合项目</option>
              </select>
            </label>
            <label style={{ fontSize: 13, display: "flex", alignItems: "center", gap: 4 }}>
              报销:
              <select value={trip.reimbursement_status || "NOT_REIMBURSED"}
                onChange={async (e) => {
                  if (!tripId) return;
                  const updated = await updateTrip(tripId, { reimbursement_status: e.target.value });
                  setTrip(updated);
                }}
                style={{ padding: "2px 6px", fontSize: 12, borderRadius: 4 }}>
                {Object.entries(reimbursementLabels).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </label>
            {trip.folder_date_start && <span>📅 文件夹: {trip.folder_date_start} ~ {trip.folder_date_end}</span>}
            {trip.inferred_start_date && <span>推断: {trip.inferred_start_date} ~ {trip.inferred_end_date} ({trip.trip_days}天)</span>}
            {trip.route_text && <span>路线: {trip.route_text}</span>}
          </div>
        )}
      </div>

      {/* ── Actions ── */}
      <div style={S.section}>
        <div style={S.sectionHead}>🔧 操作</div>
        <div style={S.btnRow}>
          <button onClick={handleOneClick} disabled={!tripId || !!loading || !!progress} style={S.btnBig}>
            🚀 一键分析
          </button>
          <Btn onClick={handleSelectFolder} disabled={!!loading}>📂 选择文件夹</Btn>
          <Btn onClick={handleSave} disabled={!folderPath.trim() || !!loading} primary>💾 {tripId ? "保存项目" : "创建项目"}</Btn>
          <Btn onClick={handleScan} disabled={!tripId || !!loading}>🔍 扫描</Btn>
          <Btn onClick={handlePreprocess} disabled={!tripId || !!loading}>🖼 预处理</Btn>
          <Btn onClick={handleRecognize} disabled={!tripId || !!loading}>🤖 OCR</Btn>
          <Btn onClick={handleAnalyze} disabled={!tripId || !!loading}>📊 分析</Btn>
          <Btn onClick={loadWorkspace} disabled={!tripId || !!loading}>🔄 刷新</Btn>
        </div>
      </div>

      {/* ── Stats ── */}
      <div style={S.section}>
        <div style={S.sectionHead}>📊 统计</div>
        <div style={S.statRow}>
          <StatCard label="总文件数" value={stats.total_files} />
          <StatCard label="已识别" value={stats.recognized} />
          <StatCard label="待复核" value={stats.review_count} />
          <StatCard label="异常" value={stats.issues} color={stats.issues > 0 ? "#c62828" : undefined} />
        </div>
      </div>

      {/* ── Charts ── */}
      {(expenseChart.length > 0 || dailyData.length > 0) && (
        <div style={S.section}>
          <div style={S.sectionHead}>📈 可视化统计</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {/* Expense bar chart */}
            <div>
              <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>费用分类</div>
              {expenseChart.map(c => (
                <div key={c.label} style={{ marginBottom: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 2 }}>
                    <span>{c.label}</span><span>{formatMoney(c.value)}</span>
                  </div>
                  <div style={{ background: "#eee", borderRadius: 3, height: 14, overflow: "hidden" }}>
                    <div style={{ background: c.color, height: "100%", width: `${(c.value / maxExpense) * 100}%`, borderRadius: 3, transition: "width 0.3s" }} />
                  </div>
                </div>
              ))}
            </div>
            {/* OCR status ring */}
            <div>
              <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>识别状态</div>
              <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                <div style={{ width: 100, height: 100, borderRadius: "50%", background: `conic-gradient(#66bb6a 0deg ${(ocrStats.success/ocrTotal)*360}deg, #ef5350 ${(ocrStats.success/ocrTotal)*360}deg ${((ocrStats.success+ocrStats.failed)/ocrTotal)*360}deg, #e0e0e0 ${((ocrStats.success+ocrStats.failed)/ocrTotal)*360}deg 360deg)` }} />
                <div>
                  <div style={{ fontSize: 12 }}>🟢 成功: {ocrStats.success}</div>
                  <div style={{ fontSize: 12 }}>🔴 失败: {ocrStats.failed}</div>
                  <div style={{ fontSize: 12 }}>⚪ 待处理: {ocrStats.pending}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Summary ── */}
      {summary && (
        <div style={S.section}>
          <div style={S.sectionHead}>💰 费用汇总</div>
          <div style={S.summaryGrid}>
            <SumItem label="城际交通" value={summary.intercity_transport_amount} />
            <SumItem label="市内交通" value={summary.local_transport_amount} />
            <SumItem label="住宿费" value={summary.lodging_amount} />
            <SumItem label="餐饮费" value={summary.meal_amount} />
            <SumItem label="退票/改签费" value={summary.refund_change_fee || 0} />
            <SumItem label="其他" value={summary.other_amount} />
            <SumItem label="票据合计" value={summary.invoice_total_amount} bold />
            <SumItem label="差旅补助" value={summary.allowance_amount} />
            <SumItem label="含补助总计" value={summary.grand_total_amount} bold accent />
          </div>
        </div>
      )}

      {/* ── Route timeline ── */}
      {segments.length > 0 && trip?.project_type !== "DAILY" && (() => {
        // Group by date
        const groups: Record<string, RouteSegment[]> = {};
        segments.forEach(s => {
          const d = s.depart_date || "日期未识别";
          if (!groups[d]) groups[d] = [];
          groups[d].push(s);
        });
        return (
        <div style={S.section}>
          <div style={S.sectionHead}>🗺 路线时间线</div>
          {Object.entries(groups).map(([date, segs]) => (
            <div key={date} style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: "#1565c0", marginBottom: 6, paddingBottom: 4, borderBottom: "2px solid #e3f2fd" }}>
                📅 {date}
              </div>
              {segs.map(s => (
                <div key={s.id} style={{ display: "flex", alignItems: "center", padding: "6px 0 6px 16px", borderLeft: "3px solid #e0e0e0", marginLeft: 8, fontSize: 13, gap: 12 }}>
                  <span style={{ minWidth: 45, color: "#888", fontSize: 12 }}>{s.depart_time || "--:--"}</span>
                  <span style={{ minWidth: 40, fontWeight: 500, color: s.transport_type === "TRAIN" ? "#42a5f5" : "#ef5350" }}>{s.transport_type === "TRAIN" ? "高铁" : s.transport_type === "FLIGHT" ? "飞机" : s.transport_type}</span>
                  <span style={{ minWidth: 70, fontWeight: 600 }}>{s.transport_no || "车次未识别"}</span>
                  <span style={{ flex: 1 }}>{s.from_place || "?"} → {s.to_place || "?"}</span>
                  {s.amount != null && <span style={{ color: "#1565c0", fontWeight: 600, minWidth: 80, textAlign: "right" }}>{formatMoney(s.amount)}</span>}
                  {!s.depart_time && <span style={{ fontSize: 11, color: "#e65100" }}>时间未识别</span>}
                </div>
              ))}
            </div>
          ))}
        </div>
      )})()}

      {/* ── Documents ── */}
      {docs.length > 0 && (
        <div style={S.section}>
          <div style={S.sectionHead}>
            <span>📄 文件列表 ({filteredDocs.length}/{docs.length})</span>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {FILTERS.map(f => (
                <button key={f.key} onClick={() => setFilterKey(f.key)}
                  style={{ ...S.filterBtn, background: filterKey === f.key ? "#1565c0" : "#f0f0f0", color: filterKey === f.key ? "#fff" : "#555" }}>
                  {f.label}
                </button>
              ))}
            </div>
          </div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ ...S.table, tableLayout: "fixed" }}>
              <colgroup>
                <col /><col style={{ width: 90 }} /><col style={{ width: 80 }} /><col style={{ width: 90 }} />
                <col style={{ width: 90 }} /><col style={{ width: 80 }} /><col style={{ width: 50 }} />
                <col style={{ width: 70 }} /><col style={{ width: 80 }} />
              </colgroup>
              <thead><tr>
                <th>文件名</th><th>发票类型</th><th>费用类别</th><th>金额</th>
                <th>扫描状态</th><th>识别状态</th><th>异常</th><th>大小</th><th>操作</th>
              </tr></thead>
              <tbody>
                {filteredDocs.map(d => (
                  <tr key={d.id}>
                    <td title={d.file_path || d.file_name} style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{truncateName(d.file_name)}</td>
                    <td style={{ textAlign: "center" }}>{d.invoice_type ? (invoiceTypeLabels[d.invoice_type] || d.invoice_type) : "-"}</td>
                    <td style={{ textAlign: "center" }}>{d.expense_category ? (expenseCategoryLabels[d.expense_category] || d.expense_category) : "-"}</td>
                    <td style={{ textAlign: "right" }}>{d.total_amount ? formatMoney(d.total_amount) : "-"}</td>
                    <td style={{ textAlign: "center" }}>{scanStatusLabels[d.scan_status] || d.scan_status}</td>
                    <td style={{ textAlign: "center" }}>{ocrStatusLabels[d.ocr_status] || d.ocr_status}</td>
                    <td style={{ textAlign: "center" }}>
                      {d.issue_count > 0 ? <span style={{ color: "#c62828", cursor: "pointer", fontWeight: 600 }} onClick={() => setIssueFilterDocId(d.id)}>{d.issue_count}</span> : "0"}
                    </td>
                    <td style={{ textAlign: "right" }}>{formatSize(d.file_size)}</td>
                    <td style={{ textAlign: "center" }}>
                      <button onClick={() => openDetail(d)} style={S.linkBtn}>查看</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {issueFilterDocId && (
            <div style={{ marginTop: 8, fontSize: 13, color: "#888" }}>
              已筛选文件异常，<span style={{ color: "#1565c0", cursor: "pointer" }} onClick={() => setIssueFilterDocId(null)}>清除筛选</span>
            </div>
          )}
        </div>
      )}

      {/* ── Issues ── */}
      {displayIssues.length > 0 && (
        <div style={S.section}>
          <div style={S.sectionHead}>⚠️ 异常信息 ({displayIssues.length})</div>
          <div style={{ overflowX: "auto" }}>
            <table style={{ ...S.table, tableLayout: "fixed" }}>
              <colgroup>
                <col style={{ width: 60 }} /><col style={{ width: 160 }} /><col style={{ width: 80 }} />
                <col style={{ width: 100 }} /><col /><col style={{ width: 160 }} />
                <col style={{ width: 60 }} /><col style={{ width: 50 }} />
              </colgroup>
              <thead><tr>
                <th>等级</th><th>关联文件</th><th>发票类型</th><th>问题类型</th><th>说明</th><th>建议</th><th>状态</th><th>操作</th>
              </tr></thead>
              <tbody>
                {displayIssues.map(iss => (
                  <tr key={iss.id}>
                    <td style={{ textAlign: "center" }}>
                      <span style={{ ...S.badge, background: iss.severity === "ERROR" ? "#ffebee" : iss.severity === "WARNING" ? "#fff3e0" : "#e8f5e9", color: iss.severity === "ERROR" ? "#c62828" : iss.severity === "WARNING" ? "#e65100" : "#2e7d32" }}>
                        {severityLabels[iss.severity] || iss.severity}
                      </span>
                    </td>
                    <td style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={iss.file_path || ""}>{iss.file_name || "未关联文件"}</td>
                    <td style={{ textAlign: "center" }}>{iss.invoice_type ? (invoiceTypeLabels[iss.invoice_type] || iss.invoice_type) : "-"}</td>
                    <td style={{ textAlign: "center" }}>{issueTypeLabels[iss.issue_type] || iss.issue_type}</td>
                    <td style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={iss.message}>{iss.message}</td>
                    <td style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 12, color: "#666" }} title={iss.suggestion || ""}>{iss.suggestion || "-"}</td>
                    <td style={{ textAlign: "center" }}>{iss.resolved ? "✅" : "⏳"}</td>
                    <td style={{ textAlign: "center" }}>
                      {iss.document_id && <button onClick={() => { const d = docs.find(x => x.id === iss.document_id); if (d) openDetail(d); }} style={S.linkBtn}>查看</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Detail Drawer ── */}
      {detailDoc && (
        <div style={S.overlay} onClick={() => setDetailDoc(null)}>
          <div style={S.drawer} onClick={e => e.stopPropagation()}>
            <div style={S.drawerHead}><span>📋 发票详情</span><button onClick={() => setDetailDoc(null)} style={S.linkBtn}>✕ 关闭</button></div>
            <div style={S.drawerBody}>
              <DetailRow label="文件名" value={detailDoc.file_name} />
              <DetailRow label="文件路径" value={detailDoc.file_path || "未识别"} />
              <DetailRow label="文件大小" value={formatSize(detailDoc.file_size)} />
              <DetailRow label="扫描状态" value={scanStatusLabels[detailDoc.scan_status] || detailDoc.scan_status} />
              <DetailRow label="识别状态" value={ocrStatusLabels[detailDoc.ocr_status] || detailDoc.ocr_status} />
              <DetailRow label="发票类型" value={detailDoc.invoice_type ? (invoiceTypeLabels[detailDoc.invoice_type] || detailDoc.invoice_type) : "未识别"} />
              <DetailRow label="费用类别" value={detailDoc.expense_category ? (expenseCategoryLabels[detailDoc.expense_category] || detailDoc.expense_category) : "未识别"} />
              <DetailRow label="金额" value={detailDoc.total_amount ? formatMoney(detailDoc.total_amount) : "未识别"} />
              {detailIssues.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontWeight: 600, marginBottom: 6, color: "#c62828" }}>关联异常 ({detailIssues.length})</div>
                  {detailIssues.map(iss => (
                    <div key={iss.id} style={{ fontSize: 12, padding: "4px 0", borderBottom: "1px solid #eee" }}>
                      <span style={S.badge}>{severityLabels[iss.severity] || iss.severity}</span> {issueTypeLabels[iss.issue_type] || iss.issue_type}: {iss.message}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!tripId && !loading && (
        <div style={S.emptyState}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📂</div>
          <div style={{ fontSize: 16, color: "#888", marginBottom: 16 }}>请选择一个出差文件夹开始分析</div>
          <button onClick={handleSelectFolder} style={S.btnBig}>📂 选择文件夹</button>
        </div>
      )}
    </div>
  );
}

// ── Sub-components ──
function StatCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return <div style={S.statCard}><div style={S.statLabel}>{label}</div><div style={{ ...S.statValue, color: color || "#333" }}>{value}</div></div>;
}
function SumItem({ label, value, bold, accent }: { label: string; value: number; bold?: boolean; accent?: boolean }) {
  return <div style={{ ...S.sumItem, fontWeight: bold ? 700 : 400, color: accent ? "#1565c0" : "#333", background: bold ? "#f5f5f5" : "transparent" }}><span>{label}</span><span>{formatMoney(value)}</span></div>;
}
function DetailRow({ label, value }: { label: string; value: string }) {
  return <div style={{ display: "flex", padding: "6px 0", borderBottom: "1px solid #f0f0f0", fontSize: 13 }}><span style={{ minWidth: 100, color: "#888" }}>{label}</span><span style={{ flex: 1, wordBreak: "break-all" }}>{value}</span></div>;
}
function truncateName(name: string, max = 15): string {
  if (name.length <= max) return name;
  const ext = name.lastIndexOf(".");
  if (ext > 0) {
    const suffix = name.slice(ext);
    const prefix = name.slice(0, max - suffix.length - 3);
    return prefix + "..." + suffix;
  }
  return name.slice(0, max - 3) + "...";
}

function Btn({ onClick, disabled, primary, children }: { onClick: () => void; disabled?: boolean; primary?: boolean; children: React.ReactNode }) {
  return <button onClick={onClick} disabled={disabled} style={{ ...S.btn, ...(primary ? S.btnPrimary : {}), opacity: disabled ? 0.5 : 1 }}>{children}</button>;
}

// ── Styles ──
const S: Record<string, React.CSSProperties> = {
  section: { background: "#fff", borderRadius: 8, boxShadow: "0 1px 4px rgba(0,0,0,0.08)", padding: 20, marginBottom: 16 },
  sectionHead: { fontSize: 15, fontWeight: 600, color: "#333", marginBottom: 12, display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 },
  row: { display: "flex", gap: 16, flexWrap: "wrap" },
  lbl: { display: "flex", flexDirection: "column", gap: 4, fontSize: 13, color: "#666" },
  inp: { padding: "6px 10px", border: "1px solid #ccc", borderRadius: 4, fontSize: 14, width: 240 },
  select: { padding: "6px 10px", border: "1px solid #ccc", borderRadius: 4, fontSize: 14, minWidth: 260 },
  meta: { display: "flex", gap: 20, marginTop: 12, fontSize: 13, color: "#555", flexWrap: "wrap" },
  btnRow: { display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" },
  btn: { padding: "8px 16px", border: "1px solid #ccc", borderRadius: 6, background: "#fff", cursor: "pointer", fontSize: 13 },
  btnPrimary: { background: "#1a1a2e", color: "#fff", borderColor: "#1a1a2e" },
  btnBig: { padding: "10px 24px", border: "none", borderRadius: 8, background: "linear-gradient(135deg, #1565c0, #1a1a2e)", color: "#fff", cursor: "pointer", fontSize: 15, fontWeight: 600 },
  linkBtn: { background: "none", border: "none", color: "#1565c0", cursor: "pointer", fontSize: 13, padding: "2px 6px" },
  filterBtn: { padding: "3px 10px", border: "none", borderRadius: 12, cursor: "pointer", fontSize: 12 },
  statRow: { display: "flex", gap: 12 },
  statCard: { flex: 1, textAlign: "center", padding: "12px 8px", borderRadius: 6, background: "#f8f9fa" },
  statLabel: { fontSize: 12, color: "#888", marginBottom: 4 },
  statValue: { fontSize: 22, fontWeight: 700 },
  summaryGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 },
  sumItem: { display: "flex", justifyContent: "space-between", padding: "8px 12px", borderRadius: 4, fontSize: 14 },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  badge: { padding: "2px 8px", borderRadius: 10, fontSize: 11, fontWeight: 600 },
  toast: { position: "fixed", top: 20, right: 20, background: "#2e7d32", color: "#fff", padding: "10px 20px", borderRadius: 8, zIndex: 2000, fontSize: 14, boxShadow: "0 4px 12px rgba(0,0,0,0.2)" },
  errorBanner: { background: "#ffebee", color: "#c62828", padding: "10px 16px", borderRadius: 6, marginBottom: 16, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 14 },
  errorClose: { background: "none", border: "none", cursor: "pointer", fontSize: 16, color: "#c62828" },
  loadingBar: { background: "#e3f2fd", color: "#1565c0", padding: "8px 16px", borderRadius: 6, marginBottom: 16, fontSize: 14 },
  progressBar: { background: "#fff3e0", color: "#e65100", padding: "8px 16px", borderRadius: 6, marginBottom: 16, fontSize: 14 },
  overlay: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 1000, display: "flex", justifyContent: "flex-end" },
  drawer: { width: 480, maxWidth: "90vw", background: "#fff", height: "100%", overflowY: "auto", boxShadow: "-4px 0 20px rgba(0,0,0,0.15)", padding: 24 },
  drawerHead: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, fontSize: 16, fontWeight: 600 },
  drawerBody: { fontSize: 13 },
  emptyState: { textAlign: "center", padding: "80px 20px", background: "#fff", borderRadius: 8, boxShadow: "0 1px 4px rgba(0,0,0,0.08)" },
};