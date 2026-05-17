import { useEffect, useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  getTrips, getTrip, getRecentTrip, createTrip, updateTrip, selectFolder,
  scanTripDocuments, preprocessDocuments, recognizeTrip, analyzeTrip,
  getWorkspace, findTripByFolder,
  type TripData, type WorkspaceData, type WorkspaceDoc,
  type IssueData, type RouteSegment,
} from "../api/trips";
import {
  severityLabels, scanStatusLabels, ocrStatusLabels,
  invoiceTypeLabels, expenseCategoryLabels, tripStatusLabels, reimbursementLabels,
  formatMoney, formatSize,
} from "../utils/labels";

const LS_KEY = "currentTripId";

type FilterKey = "all" | "invoice" | "supporting" | "hasIssue" | "lodging" | "transport" | "refund" | "meal" | "express" | "office" | "digital" | "daily";

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
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [detailDoc, setDetailDoc] = useState<WorkspaceDoc | null>(null);
  const [filterKey, setFilterKey] = useState<FilterKey>("all");
  const [issueFilterDocId, setIssueFilterDocId] = useState<number | null>(null);

  // ── Auto-restore ──
  useEffect(() => {
    (async () => {
      try { setTrips(await getTrips()); } catch { /* */ }
      if (tripId) return;
      const saved = localStorage.getItem(LS_KEY);
      if (saved) {
        try { await getTrip(parseInt(saved)); navigate(`/workspace/${saved}`, { replace: true }); return; }
        catch { localStorage.removeItem(LS_KEY); }
      }
      try { const r = await getRecentTrip(); if (r) { navigate(`/workspace/${r.id}`, { replace: true }); return; } } catch { /* */ }
      try { const list = await getTrips(); if (list.length > 0) { navigate(`/workspace/${list[0].id}`, { replace: true }); } } catch { /* */ }
    })();
  }, []);

  // ── Load workspace ──
  const loadWorkspace = async () => {
    const id = tripId;
    if (!id) { resetAll(); return; }
    try {
      const ws = await getWorkspace(id);
      setTrip(ws.trip); setStats(ws.stats); setSummary(ws.summary);
      setDocs(ws.documents); setIssues(ws.issues); setSegments(ws.route_segments);
      if (!folderSet) { setFolderPath(ws.trip.folder_path); setTitle(ws.trip.title); }
      localStorage.setItem(LS_KEY, String(id));
    } catch { localStorage.removeItem(LS_KEY); resetAll(); }
  };

  useEffect(() => { loadWorkspace(); }, [tripId]);

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
    setLoading("选择文件夹"); setError(null);
    try {
      const r = await selectFolder();
      if (!r.success || !r.folder_path) { if (r.message) setError(r.message); return; }
      setFolderPath(r.folder_path); setFolderSet(true);
      const existing = await findTripByFolder(r.folder_path);
      if (existing) { showToast("已切换到已有项目"); navigate(`/workspace/${existing.id}`); }
      else { const c = await createTrip({ title: "", folder_path: r.folder_path }); await loadTrips(); showToast("已创建新项目"); navigate(`/workspace/${c.id}`); }
    } catch (e: unknown) { setError(String(e)); }
    finally { setLoading(null); }
  };

  const handleSave = async () => {
    if (!folderPath.trim()) return;
    setLoading("保存");
    try {
      if (tripId) { setTrip(await updateTrip(tripId, { title, folder_path: folderPath })); showToast("已保存"); }
      else { const t = await createTrip({ title: title || "未命名", folder_path: folderPath }); setTrip(t); await loadTrips(); navigate(`/workspace/${t.id}`); }
    } catch (e: unknown) { setError(String(e)); }
    finally { setLoading(null); }
  };

  const loadTrips = async () => { try { setTrips(await getTrips()); } catch { /* */ } };

  const handleOneClick = async () => {
    if (!tripId) return;
    const steps = [
      { label: "扫描文件", fn: () => scanTripDocuments(tripId) },
      { label: "预处理", fn: () => preprocessDocuments(tripId) },
      { label: "OCR识别", fn: () => recognizeTrip(tripId) },
      { label: "分析出差", fn: () => analyzeTrip(tripId) },
    ];
    setError(null);
    for (const s of steps) { setProgress(s.label); try { await s.fn(); } catch (e: unknown) { setError(`${s.label}失败: ${e}`); setProgress(""); return; } }
    setProgress("加载结果"); await loadWorkspace(); setProgress(""); showToast("分析完成");
  };

  const handleScan = async () => { if (!tripId) return; setLoading("扫描"); try { await scanTripDocuments(tripId); await loadWorkspace(); } catch (e: unknown) { setError(String(e)); } finally { setLoading(null); } };
  const handlePreprocess = async () => { if (!tripId) return; setLoading("预处理"); try { await preprocessDocuments(tripId); await loadWorkspace(); } catch (e: unknown) { setError(String(e)); } finally { setLoading(null); } };
  const handleRecognize = async () => { if (!tripId) return; setLoading("OCR"); try { await recognizeTrip(tripId); await loadWorkspace(); } catch (e: unknown) { setError(String(e)); } finally { setLoading(null); } };
  const handleAnalyze = async () => { if (!tripId) return; setLoading("分析"); try { await analyzeTrip(tripId); await loadWorkspace(); } catch (e: unknown) { setError(String(e)); } finally { setLoading(null); } };

  // ── Filters ──
  const filteredDocs = useMemo(() => {
    switch (filterKey) {
      case "all": return docs;
      case "invoice": return docs.filter(d => d.total_amount != null);
      case "supporting": return docs.filter(d => !d.total_amount);
      case "hasIssue": return docs.filter(d => d.issue_count > 0);
      case "lodging": return docs.filter(d => d.expense_category === "LODGING");
      case "transport": return docs.filter(d => d.expense_category === "INTERCITY_TRANSPORT");
      case "refund": return docs.filter(d => d.expense_category === "REFUND_CHANGE_FEE");
      case "meal": return docs.filter(d => d.expense_category === "MEAL");
      case "express": return docs.filter(d => d.expense_category === "EXPRESS_LOGISTICS");
      case "office": return docs.filter(d => d.expense_category === "OFFICE_SUPPLIES");
      case "digital": return docs.filter(d => d.expense_category === "ELECTRONICS_DIGITAL");
      case "daily": return docs.filter(d => d.expense_category === "DAILY_GENERAL");
      default: return docs;
    }
  }, [docs, filterKey]);

  const displayIssues = issueFilterDocId ? issues.filter(i => i.document_id === issueFilterDocId) : issues;
  const infoIssues = displayIssues.filter(i => i.severity === "INFO");
  const warnIssues = displayIssues.filter(i => i.severity === "WARNING");
  const errIssues = displayIssues.filter(i => i.severity === "ERROR");

  // ── Expense chart data ──
  const expenseBars = summary ? [
    { label: "城际交通", value: summary.intercity_transport_amount, color: "#5c9ce6" },
    { label: "市内交通", value: summary.local_transport_amount, color: "#6cbe6f" },
    { label: "住宿费", value: summary.lodging_amount, color: "#f0a050" },
    { label: "餐饮费", value: summary.meal_amount, color: "#e86060" },
    { label: "退票/改签费", value: summary.refund_change_fee || 0, color: "#b0b0b0" },
    { label: "出行保险", value: summary.travel_insurance_amount || 0, color: "#f0a050" },
    { label: "其他", value: summary.other_amount, color: "#a080d0" },
    ...(trip?.project_type !== "DAILY" ? [{ label: "差旅补助", value: summary.allowance_amount, color: "#8090a0" }] : []),
  ].filter(c => c.value > 0) : [];
  const maxBar = Math.max(...expenseBars.map(c => c.value), 1);

  // ── Route groups ──
  const routeGroups: Record<string, RouteSegment[]> = {};
  segments.forEach(s => { const d = s.depart_date || "日期未识别"; if (!routeGroups[d]) routeGroups[d] = []; routeGroups[d].push(s); });

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      {toast && <div style={S.toast}>{toast}</div>}
      {error && <div style={S.err}><span>{error}</span><button onClick={() => setError(null)} style={S.errClose}>✕</button></div>}
      {loading && <div style={S.loading}>⏳ {loading}...</div>}
      {progress && <div style={S.progress}>🔄 {progress}...</div>}

      {/* ── Trip selector ── */}
      <div style={S.card}>
        <select value={tripId ?? ""} onChange={e => { if (e.target.value) handleSelectTrip(parseInt(e.target.value)); }} style={S.select}>
          <option value="">-- 选择项目 --</option>
          {trips.map(t => (<option key={t.id} value={t.id}>#{t.id} {t.title || "未命名"} ({tripStatusLabels[t.status] || t.status})</option>))}
        </select>
      </div>

      {/* ── Project Overview ── */}
      {trip && (
        <div style={S.card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <input
                value={title}
                onChange={e => setTitle(e.target.value)}
                onBlur={() => { if (tripId && title !== trip.title) updateTrip(tripId, { title }).then(setTrip).catch(() => {}); }}
                onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
                placeholder="输入项目名称"
                style={{ fontSize: 20, fontWeight: 700, border: 'none', borderBottom: '2px solid transparent', outline: 'none', padding: '2px 0', width: '100%', background: 'transparent', transition: 'border-color 0.2s' }}
                onFocus={e => e.target.style.borderBottomColor = '#1565c0'}
              />
              <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
                {(trip.project_type || "TRAVEL") === "DAILY" ? "日常发票" : (trip.project_type || "TRAVEL") === "MIXED" ? "综合项目" : "出差报销"}
                {(trip.confirmed_start_date || trip.folder_date_start) && ` · ${trip.confirmed_start_date || trip.folder_date_start} 至 ${trip.confirmed_end_date || trip.folder_date_end}`}
                {trip.trip_days != null && ` · ${trip.trip_days} 天`}
              </div>
              <div style={{ fontSize: 11, color: "#aaa", marginTop: 2, maxWidth: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={trip.folder_path}>
                路径：{trip.folder_path}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <Tag color="#1565c0" bg="#e3f2fd">{tripStatusLabels[trip.status] || trip.status}</Tag>
              <select
                value={trip.project_type || "TRAVEL"}
                onChange={async e => { if (!tripId) return; const u = await updateTrip(tripId, { project_type: e.target.value }); setTrip(u); await loadWorkspace(); }}
                style={{ padding: "2px 6px", borderRadius: 6, fontSize: 11, border: "1px solid #ddd", background: "#fff", cursor: "pointer", width: 100 }}>
                <option value="TRAVEL">出差报销</option>
                <option value="DAILY">日常发票</option>
                <option value="MIXED">综合</option>
              </select>
              <select
                value={trip.reimbursement_status || "NOT_REIMBURSED"}
                onChange={async e => { if (!tripId) return; const u = await updateTrip(tripId, { reimbursement_status: e.target.value }); setTrip(u); }}
                style={{ padding: "2px 6px", borderRadius: 6, fontSize: 11, border: "1px solid #ddd", background: "#fff", cursor: "pointer", width: 90, color: trip.reimbursement_status === "REIMBURSED" ? "#2e7d32" : "#e65100" }}>
                {Object.entries(reimbursementLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              {trip.status === "ANALYZED" && stats.issues > 0 && <Tag color="#c62828" bg="#ffebee">⚠ {stats.issues} 个异常</Tag>}
              {trip.status === "ANALYZED" && stats.issues === 0 && <Tag color="#2e7d32" bg="#e8f5e9">✓ 无异常</Tag>}
            </div>
          </div>
        </div>
      )}

      {/* ── Actions ── */}
      <div style={S.card}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button onClick={handleOneClick} disabled={!tripId || !!loading || !!progress} style={S.btnPrimary}>
            🚀 一键分析
          </button>
          <button onClick={handleSelectFolder} disabled={!!loading} style={S.btn}>📂 选择文件夹</button>
          <button onClick={handleSave} disabled={!folderPath.trim() || !!loading} style={S.btn}>💾 保存</button>
          <button onClick={loadWorkspace} disabled={!tripId || !!loading} style={S.btn}>🔄 刷新</button>
          <button onClick={() => setShowAdvanced(!showAdvanced)} style={{ ...S.btn, fontSize: 12, color: "#888" }}>
            {showAdvanced ? "收起" : "高级"} ▾
          </button>
        </div>
        {showAdvanced && (
          <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
            <button onClick={handleScan} disabled={!tripId || !!loading} style={S.btnSm}>扫描</button>
            <button onClick={handlePreprocess} disabled={!tripId || !!loading} style={S.btnSm}>预处理</button>
            <button onClick={handleRecognize} disabled={!tripId || !!loading} style={S.btnSm}>OCR</button>
            <button onClick={handleAnalyze} disabled={!tripId || !!loading} style={S.btnSm}>分析</button>
          </div>
        )}
      </div>

      {/* ── Stats ── */}
      {trip && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 10, marginBottom: 16 }}>
          <Stat label="文件总数" value={stats.total_files} />
          <Stat label="识别成功" value={stats.recognized} />
          <Stat label="待复核" value={stats.review_count} />
          <Stat label="异常" value={trip?.status === "ANALYZED" ? stats.issues : "-"} warn={stats.issues > 0 && trip?.status === "ANALYZED"} />
          <Stat label="票据合计" value={summary ? formatMoney(summary.invoice_total_amount) : "-"} />
          {trip?.project_type !== "DAILY" && (
            <Stat label="含补助总计" value={summary ? formatMoney(summary.grand_total_amount) : "-"} accent />
          )}
        </div>
      )}

      {/* ── Expense Overview ── */}
      {summary && expenseBars.length > 0 && (
        <div style={S.card}>
          <div style={S.cardTitle}>💰 费用概览</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <div>
              {expenseBars.map(c => (
                <div key={c.label} style={{ marginBottom: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 2 }}>
                    <span>{c.label}</span><span>{formatMoney(c.value)}</span>
                  </div>
                  <div style={{ background: "#eee", borderRadius: 2, height: 10, overflow: "hidden" }}>
                    <div style={{ background: c.color, height: "100%", width: `${(c.value / maxBar) * 100}%`, borderRadius: 2 }} />
                  </div>
                </div>
              ))}
            </div>
            <div>
              {expenseBars.map(c => (
                <div key={c.label} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13, borderBottom: "1px solid #f5f5f5" }}>
                  <span style={{ color: "#666" }}>{c.label}</span>
                  <span style={{ fontWeight: c.label === "含补助总计" ? 700 : 400, color: c.label === "含补助总计" ? "#1565c0" : "#333" }}>{formatMoney(c.value)}</span>
                </div>
              ))}
              <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: 13, fontWeight: 700, borderTop: "2px solid #e0e0e0", marginTop: 4 }}>
                <span>票据合计</span><span>{formatMoney(summary.invoice_total_amount)}</span>
              </div>
              {trip?.project_type !== "DAILY" && (
                <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 14, fontWeight: 700, color: "#1565c0" }}>
                  <span>含补助总计</span><span>{formatMoney(summary.grand_total_amount)}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Route Timeline ── */}
      {Object.keys(routeGroups).length > 0 && trip?.project_type !== "DAILY" && (
        <div style={S.card}>
          <div style={S.cardTitle}>🗺 路线时间线</div>
          {Object.entries(routeGroups).map(([date, segs]) => (
            <div key={date} style={{ marginBottom: 10 }}>
              <div style={{ fontWeight: 600, fontSize: 13, color: "#1565c0", marginBottom: 4, paddingBottom: 2, borderBottom: "1px solid #e3f2fd" }}>📅 {date}</div>
              {segs.map(s => (
                <div key={s.id} style={{ display: "flex", alignItems: "center", padding: "4px 0 4px 12px", borderLeft: "2px solid #e8e8e8", marginLeft: 6, fontSize: 13, gap: 10 }}>
                  <span style={{ minWidth: 40, color: "#888", fontSize: 12 }}>{s.depart_time || "--:--"}</span>
                  <span style={{ minWidth: 32, fontSize: 12, color: s.transport_type === "TRAIN" ? "#5c9ce6" : "#e86060" }}>{s.transport_type === "TRAIN" ? "高铁" : s.transport_type === "FLIGHT" ? "飞机" : s.transport_type}</span>
                  <span style={{ fontWeight: 600, minWidth: 60 }}>{s.transport_no || "?"}</span>
                  <span style={{ flex: 1 }}>{s.from_place || "?"} → {s.to_place || "?"}</span>
                  {s.amount != null && <span style={{ fontWeight: 600, minWidth: 70, textAlign: "right" }}>{formatMoney(s.amount)}</span>}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      {/* ── File List ── */}
      {docs.length > 0 && (
        <div style={S.card}>
          <div style={{ ...S.cardTitle, display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 6 }}>
            <span>📄 文件列表 ({filteredDocs.length}/{docs.length})</span>
            <div style={{ display: "flex", gap: 3, flexWrap: "wrap" }}>
              {[
                ["all","全部"],["invoice","正式发票"],["supporting","辅助凭证"],
                ["hasIssue","有异常"],["meal","餐饮"],["express","快递"],["office","办公"],["digital","电子"],["daily","日常"]
              ].map(([k,v]) => (
                <button key={k} onClick={() => setFilterKey(k as FilterKey)}
                  style={{ padding: "2px 8px", border: "none", borderRadius: 10, cursor: "pointer", fontSize: 11, background: filterKey === k ? "#1565c0" : "#f0f0f0", color: filterKey === k ? "#fff" : "#666" }}>{v}</button>
              ))}
            </div>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead><tr style={{ color: "#888", fontSize: 12, borderBottom: "1px solid #eee" }}>
              <th style={{ padding: "6px 8px", textAlign: "left" }}>文件名</th>
              <th style={{ padding: "6px 8px", width: 70 }}>凭证</th>
              <th style={{ padding: "6px 8px", width: 80 }}>类型</th>
              <th style={{ padding: "6px 8px", width: 70 }}>类别</th>
              <th style={{ padding: "6px 8px", width: 90, textAlign: "right" }}>金额</th>
              <th style={{ padding: "6px 8px", width: 55 }}>计入</th>
              <th style={{ padding: "6px 8px", width: 50 }}>异常</th>
              <th style={{ padding: "6px 8px", width: 50 }}>操作</th>
            </tr></thead>
            <tbody>
              {filteredDocs.map(d => (
                <tr key={d.id} style={{ borderBottom: "1px solid #f5f5f5" }}>
                  <td style={{ padding: "4px 8px", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={d.file_path || d.file_name}>
                    {d.file_name.length > 20 ? d.file_name.slice(0, 17) + "..." + d.file_name.slice(-4) : d.file_name}
                  </td>
                  <td style={{ padding: "4px 8px", textAlign: "center" }}>
                    <Tag color={d.total_amount ? "#2e7d32" : "#888"} bg={d.total_amount ? "#e8f5e9" : "#f5f5f5"} small>
                      {d.total_amount ? "正式发票" : d.order_total_amount ? "订单截图" : "已去重"}
                    </Tag>
                  </td>
                  <td style={{ padding: "4px 8px", textAlign: "center", fontSize: 12 }}>{d.invoice_type ? (invoiceTypeLabels[d.invoice_type] || d.invoice_type) : "-"}</td>
                  <td style={{ padding: "4px 8px", textAlign: "center", fontSize: 12 }}>{d.expense_category ? (expenseCategoryLabels[d.expense_category] || d.expense_category) : "-"}</td>
                  <td style={{ padding: "4px 8px", textAlign: "right" }}>{d.total_amount ? formatMoney(d.total_amount) : d.order_total_amount ? <span style={{ color: "#888" }}>{formatMoney(d.order_total_amount)}</span> : "-"}</td>
                  <td style={{ padding: "4px 8px", textAlign: "center" }}>{d.total_amount ? "✓" : <span style={{ color: "#aaa" }}>—</span>}</td>
                  <td style={{ padding: "4px 8px", textAlign: "center" }}>
                    {d.issue_count > 0 ? <span style={{ color: "#c62828", cursor: "pointer", fontWeight: 600, fontSize: 12 }} onClick={() => setIssueFilterDocId(d.id)}>{d.issue_count}</span> : <span style={{ color: "#ccc" }}>0</span>}
                  </td>
                  <td style={{ padding: "4px 8px", textAlign: "center" }}>
                    <button onClick={() => setDetailDoc(d)} style={{ background: "none", border: "none", color: "#1565c0", cursor: "pointer", fontSize: 12 }}>查看</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Issues ── */}
      {displayIssues.length > 0 && (
        <div style={S.card}>
          <div style={S.cardTitle}>⚠ 提示与异常</div>
          {errIssues.length > 0 && <div style={{ marginBottom: 8 }}><span style={{ fontWeight: 600, color: "#c62828", fontSize: 13 }}>错误 ({errIssues.length})</span></div>}
          {errIssues.map(i => <IssueRow key={i.id} issue={i} docs={docs} onView={setDetailDoc} />)}
          {warnIssues.length > 0 && <div style={{ marginBottom: 8, marginTop: 8 }}><span style={{ fontWeight: 600, color: "#e65100", fontSize: 13 }}>警告 ({warnIssues.length})</span></div>}
          {warnIssues.map(i => <IssueRow key={i.id} issue={i} docs={docs} onView={setDetailDoc} />)}
          {infoIssues.length > 0 && <div style={{ marginBottom: 8, marginTop: 8 }}><span style={{ fontWeight: 600, color: "#2e7d32", fontSize: 13 }}>提示 ({infoIssues.length})</span></div>}
          {infoIssues.map(i => <IssueRow key={i.id} issue={i} docs={docs} onView={setDetailDoc} />)}
        </div>
      )}
      {displayIssues.length === 0 && trip?.status === "ANALYZED" && (
        <div style={{ ...S.card, textAlign: "center", color: "#888", padding: 24 }}>✓ 当前没有需要处理的问题</div>
      )}

      {/* ── Detail Drawer ── */}
      {detailDoc && (
        <div style={S.overlay} onClick={() => setDetailDoc(null)}>
          <div style={S.drawer} onClick={e => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <span style={{ fontSize: 16, fontWeight: 600 }}>📋 发票详情</span>
              <button onClick={() => setDetailDoc(null)} style={{ background: "none", border: "none", fontSize: 18, cursor: "pointer", color: "#888" }}>✕</button>
            </div>
            <div style={{ fontSize: 13 }}>
              <DRow label="文件名" value={detailDoc.file_name} />
              <DRow label="文件路径" value={detailDoc.file_path || "未识别"} />
              <DRow label="文件大小" value={formatSize(detailDoc.file_size)} />
              <DRow label="扫描状态" value={scanStatusLabels[detailDoc.scan_status] || detailDoc.scan_status} />
              <DRow label="识别状态" value={ocrStatusLabels[detailDoc.ocr_status] || detailDoc.ocr_status} />
              <DRow label="发票类型" value={detailDoc.invoice_type ? (invoiceTypeLabels[detailDoc.invoice_type] || detailDoc.invoice_type) : "未识别"} />
              <DRow label="费用类别" value={detailDoc.expense_category ? (expenseCategoryLabels[detailDoc.expense_category] || detailDoc.expense_category) : "未识别"} />
              <DRow label="金额" value={detailDoc.total_amount ? formatMoney(detailDoc.total_amount) : detailDoc.order_total_amount ? formatMoney(detailDoc.order_total_amount) + " (订单)" : "未识别"} />
              {detailDoc.nights != null && <DRow label="住宿晚数" value={`${detailDoc.nights} 晚`} />}
            </div>
          </div>
        </div>
      )}

      {/* ── Empty state ── */}
      {!tripId && !loading && (
        <div style={{ ...S.card, textAlign: "center", padding: 60 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📂</div>
          <div style={{ fontSize: 15, color: "#888", marginBottom: 16 }}>请选择一个文件夹开始分析</div>
          <button onClick={handleSelectFolder} style={S.btnPrimary}>📂 选择文件夹</button>
        </div>
      )}
    </div>
  );
}

// ── Sub-components ──
function Stat({ label, value, warn, accent }: { label: string; value: number | string; warn?: boolean; accent?: boolean }) {
  return <div style={{ background: "#fff", borderRadius: 8, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", padding: "14px 16px", textAlign: "center" }}>
    <div style={{ fontSize: 11, color: "#888", marginBottom: 4 }}>{label}</div>
    <div style={{ fontSize: 20, fontWeight: 700, color: warn ? "#c62828" : accent ? "#1565c0" : "#333" }}>{value}</div>
  </div>;
}

function Tag({ color, bg, small, children }: { color: string; bg: string; small?: boolean; children: React.ReactNode }) {
  return <span style={{ padding: small ? "1px 6px" : "2px 8px", borderRadius: 10, fontSize: small ? 10 : 11, fontWeight: 600, background: bg, color, whiteSpace: "nowrap" }}>{children}</span>;
}

function IssueRow({ issue, docs, onView }: { issue: IssueData; docs: WorkspaceDoc[]; onView: (d: WorkspaceDoc) => void }) {
  const sevColor = issue.severity === "ERROR" ? "#c62828" : issue.severity === "WARNING" ? "#e65100" : "#2e7d32";
  const sevBg = issue.severity === "ERROR" ? "#ffebee" : issue.severity === "WARNING" ? "#fff3e0" : "#e8f5e9";
  return <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0", fontSize: 13, borderBottom: "1px solid #f8f8f8" }}>
    <Tag color={sevColor} bg={sevBg} small>{severityLabels[issue.severity] || issue.severity}</Tag>
    <span style={{ flex: 1 }}>{issue.message}</span>
    {issue.file_name && <span style={{ color: "#888", fontSize: 11, maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{issue.file_name}</span>}
    {issue.document_id && <button onClick={() => { const d = docs.find(x => x.id === issue.document_id); if (d) onView(d); }} style={{ background: "none", border: "none", color: "#1565c0", cursor: "pointer", fontSize: 11 }}>查看</button>}
  </div>;
}

function DRow({ label, value }: { label: string; value: string }) {
  return <div style={{ display: "flex", padding: "5px 0", borderBottom: "1px solid #f5f5f5" }}>
    <span style={{ minWidth: 90, color: "#888", fontSize: 12 }}>{label}</span>
    <span style={{ flex: 1, wordBreak: "break-all", fontSize: 12 }}>{value || "未识别"}</span>
  </div>;
}

// ── Styles ──
const S: Record<string, React.CSSProperties> = {
  card: { background: "#fff", borderRadius: 10, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", padding: 20, marginBottom: 14 },
  cardTitle: { fontSize: 15, fontWeight: 600, marginBottom: 12, color: "#333" },
  select: { padding: "6px 12px", border: "1px solid #ddd", borderRadius: 6, fontSize: 14, minWidth: 240, background: "#fff" },
  btn: { padding: "8px 16px", border: "1px solid #ddd", borderRadius: 6, background: "#fff", cursor: "pointer", fontSize: 13, color: "#555" },
  btnSm: { padding: "4px 10px", border: "1px solid #eee", borderRadius: 4, background: "#f8f8f8", cursor: "pointer", fontSize: 11, color: "#888" },
  btnPrimary: { padding: "10px 24px", border: "none", borderRadius: 8, background: "#1565c0", color: "#fff", cursor: "pointer", fontSize: 14, fontWeight: 600 },
  toast: { position: "fixed", top: 20, right: 20, background: "#2e7d32", color: "#fff", padding: "10px 20px", borderRadius: 8, zIndex: 2000, fontSize: 14 },
  err: { background: "#ffebee", color: "#c62828", padding: "10px 16px", borderRadius: 8, marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 },
  errClose: { background: "none", border: "none", cursor: "pointer", fontSize: 16, color: "#c62828" },
  loading: { background: "#e3f2fd", color: "#1565c0", padding: "8px 16px", borderRadius: 8, marginBottom: 14, fontSize: 13 },
  progress: { background: "#fff3e0", color: "#e65100", padding: "8px 16px", borderRadius: 8, marginBottom: 14, fontSize: 13 },
  overlay: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)", zIndex: 1000, display: "flex", justifyContent: "flex-end" },
  drawer: { width: 440, maxWidth: "95vw", background: "#fff", height: "100%", overflowY: "auto", boxShadow: "-4px 0 20px rgba(0,0,0,0.1)", padding: 24 },
};