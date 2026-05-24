import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  analyzeTrip,
  bulkUpdateInvoices,
  createTrip,
  exportExcel,
  exportPdf,
  findTripByFolder,
  getRecentTrip,
  getTrip,
  getTrips,
  getWorkspace,
  preprocessDocuments,
  recognizeTrip,
  scanTripDocuments,
  selectFolder,
  updateInvoice,
  updateIssue,
  updateTrip,
  type InvoiceUpdatePayload,
  type IssueData,
  type RouteSegment,
  type TripData,
  type WorkspaceData,
  type WorkspaceDoc,
} from "../api/trips";
import {
  documentRoleLabels,
  expenseCategoryLabels,
  formatMoney,
  formatSize,
  invoiceReimbursementLabels,
  invoiceTypeLabels,
  issueTypeLabels,
  ocrStatusLabels,
  reimbursementLabels,
  reviewStatusLabels,
  scanStatusLabels,
  severityLabels,
  tripStatusLabels,
} from "../utils/labels";

const LS_KEY = "currentTripId";

type FilterKey =
  | "all"
  | "thisTrip"
  | "already"
  | "notReimbursed"
  | "pending"
  | "invoice"
  | "supporting"
  | "hasIssue"
  | "lodging"
  | "transport"
  | "refund"
  | "meal"
  | "express"
  | "office"
  | "digital"
  | "daily";

const invoiceStatusOptions = [
  "THIS_TRIP",
  "ALREADY_REIMBURSED",
  "NOT_REIMBURSED",
  "PENDING",
];

const invoiceTypeOptions = [
  "GENERAL_INVOICE",
  "VAT_INVOICE",
  "TRAIN_TICKET",
  "FLIGHT_TICKET",
  "HOTEL_INVOICE",
  "TAXI_INVOICE",
  "RIDE_HAILING_INVOICE",
  "MEAL_INVOICE",
  "OTHER",
  "UNKNOWN",
];

const expenseCategoryOptions = [
  "INTERCITY_TRANSPORT",
  "LOCAL_TRANSPORT",
  "LODGING",
  "MEAL",
  "REFUND_CHANGE_FEE",
  "TRAVEL_INSURANCE",
  "EXPRESS_LOGISTICS",
  "OFFICE_SUPPLIES",
  "ELECTRONICS_DIGITAL",
  "SOFTWARE_SERVICE",
  "COMMUNICATION",
  "GENERAL_SERVICE",
  "DAILY_GENERAL",
  "OTHER",
];

export default function TripWorkspace() {
  const { tripId: paramId } = useParams<{ tripId?: string }>();
  const navigate = useNavigate();
  const tripId = paramId ? parseInt(paramId, 10) : null;

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
  const [detailDraft, setDetailDraft] = useState<InvoiceUpdatePayload>({});
  const [filterKey, setFilterKey] = useState<FilterKey>("all");
  const [issueFilterDocId, setIssueFilterDocId] = useState<number | null>(null);
  const [selectedInvoiceIds, setSelectedInvoiceIds] = useState<number[]>([]);

  useEffect(() => {
    (async () => {
      try {
        setTrips(await getTrips());
      } catch {
        /* keep empty */
      }
      if (tripId) return;
      const saved = localStorage.getItem(LS_KEY);
      if (saved) {
        try {
          await getTrip(parseInt(saved, 10));
          navigate(`/workspace/${saved}`, { replace: true });
          return;
        } catch {
          localStorage.removeItem(LS_KEY);
        }
      }
      try {
        const recent = await getRecentTrip();
        if (recent) {
          navigate(`/workspace/${recent.id}`, { replace: true });
          return;
        }
      } catch {
        /* no recent trip */
      }
      try {
        const list = await getTrips();
        if (list.length > 0) navigate(`/workspace/${list[0].id}`, { replace: true });
      } catch {
        /* keep empty */
      }
    })();
  }, []);

  const resetAll = () => {
    setTrip(null);
    setDocs([]);
    setSummary(null);
    setIssues([]);
    setSegments([]);
    setSelectedInvoiceIds([]);
    setStats({ total_files: 0, recognized: 0, review_count: 0, issues: 0 });
  };

  const loadWorkspace = async () => {
    const id = tripId;
    if (!id) {
      resetAll();
      return;
    }
    try {
      const ws = await getWorkspace(id);
      setTrip(ws.trip);
      setStats(ws.stats);
      setSummary(ws.summary);
      setDocs(ws.documents);
      setIssues(ws.issues);
      setSegments(ws.route_segments);
      setSelectedInvoiceIds(prev => prev.filter(invoiceId => ws.documents.some(d => d.invoice_id === invoiceId)));
      if (!folderSet) {
        setFolderPath(ws.trip.folder_path);
        setTitle(ws.trip.title);
      }
      localStorage.setItem(LS_KEY, String(id));
    } catch (e: unknown) {
      localStorage.removeItem(LS_KEY);
      resetAll();
      setError(`加载工作台失败：${String(e)}`);
    }
  };

  useEffect(() => {
    loadWorkspace();
  }, [tripId]);

  useEffect(() => {
    if (!detailDoc) {
      setDetailDraft({});
      return;
    }
    setDetailDraft({
      invoice_type: detailDoc.invoice_type || "UNKNOWN",
      expense_category: detailDoc.expense_category || "OTHER",
      invoice_number: detailDoc.invoice_number,
      invoice_date: detailDoc.invoice_date,
      business_date: detailDoc.business_date,
      seller_name: detailDoc.seller_name,
      buyer_name: detailDoc.buyer_name,
      total_amount: detailDoc.total_amount,
      confirmed_amount: detailDoc.confirmed_amount,
      reimbursement_status: detailDoc.reimbursement_status || "PENDING",
      include_in_summary: detailDoc.include_in_summary,
      review_status: detailDoc.review_status || "NEEDS_REVIEW",
      note: detailDoc.note,
      from_city: detailDoc.from_city,
      to_city: detailDoc.to_city,
      from_place: detailDoc.from_place,
      to_place: detailDoc.to_place,
      transport_no: detailDoc.transport_no,
      depart_time_str: detailDoc.depart_time_str,
      seat_class: detailDoc.seat_class,
      hotel_name: detailDoc.hotel_name,
      checkin_date: detailDoc.checkin_date,
      checkout_date: detailDoc.checkout_date,
      nights: detailDoc.nights,
      document_role: detailDoc.document_role || "OFFICIAL_INVOICE",
    });
  }, [detailDoc]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 2500);
  };

  const loadTrips = async () => {
    try {
      setTrips(await getTrips());
    } catch {
      /* keep old list */
    }
  };

  const handleSelectTrip = (id: number) => {
    setFolderSet(false);
    setDetailDoc(null);
    setIssueFilterDocId(null);
    setFilterKey("all");
    setSelectedInvoiceIds([]);
    navigate(`/workspace/${id}`);
  };

  const handleSelectFolder = async () => {
    setLoading("选择文件夹");
    setError(null);
    try {
      const result = await selectFolder();
      if (!result.success || !result.folder_path) {
        if (result.message) setError(result.message);
        return;
      }
      setFolderPath(result.folder_path);
      setFolderSet(true);
      const existing = await findTripByFolder(result.folder_path);
      if (existing) {
        showToast("已切换到已有项目");
        navigate(`/workspace/${existing.id}`);
      } else {
        const created = await createTrip({ title: "", folder_path: result.folder_path });
        await loadTrips();
        showToast("已创建新项目");
        navigate(`/workspace/${created.id}`);
      }
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const handleSave = async () => {
    if (!folderPath.trim()) return;
    setLoading("保存");
    try {
      if (tripId) {
        setTrip(await updateTrip(tripId, { title, folder_path: folderPath }));
        showToast("已保存");
      } else {
        const created = await createTrip({ title: title || "未命名", folder_path: folderPath });
        setTrip(created);
        await loadTrips();
        navigate(`/workspace/${created.id}`);
      }
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const handleOneClick = async () => {
    if (!tripId) return;
    const steps = [
      { label: "扫描文件", fn: () => scanTripDocuments(tripId), optional: false },
      { label: "预处理", fn: () => preprocessDocuments(tripId), optional: false },
      { label: "OCR识别", fn: () => recognizeTrip(tripId), optional: true },
      { label: "分析出差", fn: () => analyzeTrip(tripId), optional: false },
    ];
    setError(null);
    for (const step of steps) {
      setProgress(step.label);
      try {
        await step.fn();
      } catch (e: unknown) {
        if (step.optional) {
          setError("当前未配置 OCR / OCR 不可用，已跳过自动识别；你仍可人工录入或修正票据信息。");
          continue;
        }
        setError(`${step.label}失败: ${String(e)}`);
        setProgress("");
        return;
      }
    }
    setProgress("加载结果");
    await loadWorkspace();
    setProgress("");
    showToast("分析完成");
  };

  const handleScan = async () => {
    if (!tripId) return;
    setLoading("扫描");
    try {
      await scanTripDocuments(tripId);
      await loadWorkspace();
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const handlePreprocess = async () => {
    if (!tripId) return;
    setLoading("预处理");
    try {
      await preprocessDocuments(tripId);
      await loadWorkspace();
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const handleRecognize = async () => {
    if (!tripId) return;
    setLoading("OCR");
    try {
      await recognizeTrip(tripId);
      await loadWorkspace();
    } catch {
      setError("当前未配置 OCR / OCR 不可用；非 OCR 的票据管理、人工修正、报销选择和导出仍可继续使用。");
    } finally {
      setLoading(null);
    }
  };

  const handleAnalyze = async () => {
    if (!tripId) return;
    setLoading("分析");
    try {
      await analyzeTrip(tripId);
      await loadWorkspace();
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const handleSingleStatus = async (doc: WorkspaceDoc, reimbursementStatus: string) => {
    if (!doc.invoice_id) return;
    setLoading("更新票据状态");
    try {
      await updateInvoice(doc.invoice_id, { reimbursement_status: reimbursementStatus });
      await loadWorkspace();
      showToast("票据状态已更新");
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const handleIncludeChange = async (doc: WorkspaceDoc, includeInSummary: boolean) => {
    if (!doc.invoice_id) return;
    setLoading("更新计入状态");
    try {
      await updateInvoice(doc.invoice_id, { include_in_summary: includeInSummary });
      await loadWorkspace();
      showToast("计入状态已更新");
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const handleBulkStatus = async (reimbursementStatus: string) => {
    if (!tripId || selectedInvoiceIds.length === 0) return;
    setLoading("批量更新票据");
    try {
      await bulkUpdateInvoices(tripId, selectedInvoiceIds, { reimbursement_status: reimbursementStatus });
      await loadWorkspace();
      showToast(`已批量设为${invoiceReimbursementLabels[reimbursementStatus] || reimbursementStatus}`);
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const handleSaveDetail = async () => {
    if (!detailDoc?.invoice_id) return;
    setLoading("保存人工修正");
    try {
      await updateInvoice(detailDoc.invoice_id, {
        ...detailDraft,
        review_status: "MANUALLY_CONFIRMED",
      });
      await loadWorkspace();
      setDetailDoc(null);
      showToast("人工修正已保存");
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const handleIssueUpdate = async (issue: IssueData, ignored: boolean) => {
    setLoading(ignored ? "忽略异常" : "解决异常");
    try {
      await updateIssue(issue.id, { resolved: true, ignored });
      await loadWorkspace();
      showToast(ignored ? "异常已忽略" : "异常已标记解决");
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const hasBlockingIssues = issues.some(i => !i.resolved && (i.severity === "ERROR" || i.severity === "WARNING"));

  const confirmExportIfIssues = () => {
    if (!hasBlockingIssues) return true;
    return window.confirm("当前仍有未处理的错误或警告，确定继续导出吗？");
  };

  const handleExportExcel = async () => {
    if (!tripId || !confirmExportIfIssues()) return;
    setLoading("导出 Excel");
    try {
      await exportExcel(tripId);
      showToast("Excel 已开始下载");
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const handleExportPdf = async () => {
    if (!tripId || !confirmExportIfIssues()) return;
    setLoading("导出 PDF");
    try {
      await exportPdf(tripId);
      showToast("PDF 已开始下载");
    } catch (e: unknown) {
      setError(String(e));
    } finally {
      setLoading(null);
    }
  };

  const filteredDocs = useMemo(() => {
    switch (filterKey) {
      case "all":
        return docs;
      case "thisTrip":
        return docs.filter(d => d.reimbursement_status === "THIS_TRIP" && d.include_in_summary);
      case "already":
        return docs.filter(d => d.reimbursement_status === "ALREADY_REIMBURSED");
      case "notReimbursed":
        return docs.filter(d => d.reimbursement_status === "NOT_REIMBURSED");
      case "pending":
        return docs.filter(d => d.reimbursement_status === "PENDING");
      case "invoice":
        return docs.filter(d => d.document_role === "OFFICIAL_INVOICE");
      case "supporting":
        return docs.filter(d => d.document_role !== "OFFICIAL_INVOICE");
      case "hasIssue":
        return docs.filter(d => d.issue_count > 0);
      case "lodging":
        return docs.filter(d => d.expense_category === "LODGING");
      case "transport":
        return docs.filter(d => d.expense_category === "INTERCITY_TRANSPORT");
      case "refund":
        return docs.filter(d => d.expense_category === "REFUND_CHANGE_FEE");
      case "meal":
        return docs.filter(d => d.expense_category === "MEAL");
      case "express":
        return docs.filter(d => d.expense_category === "EXPRESS_LOGISTICS");
      case "office":
        return docs.filter(d => d.expense_category === "OFFICE_SUPPLIES");
      case "digital":
        return docs.filter(d => d.expense_category === "ELECTRONICS_DIGITAL");
      case "daily":
        return docs.filter(d => d.expense_category === "DAILY_GENERAL");
      default:
        return docs;
    }
  }, [docs, filterKey]);

  const visibleInvoiceIds = filteredDocs
    .map(d => d.invoice_id)
    .filter((id): id is number => id != null);
  const allVisibleSelected = visibleInvoiceIds.length > 0 && visibleInvoiceIds.every(id => selectedInvoiceIds.includes(id));

  const toggleInvoiceSelection = (invoiceId: number, checked: boolean) => {
    setSelectedInvoiceIds(prev => checked ? [...new Set([...prev, invoiceId])] : prev.filter(id => id !== invoiceId));
  };

  const toggleAllVisible = (checked: boolean) => {
    setSelectedInvoiceIds(prev => {
      if (!checked) return prev.filter(id => !visibleInvoiceIds.includes(id));
      return [...new Set([...prev, ...visibleInvoiceIds])];
    });
  };

  const displayIssues = (issueFilterDocId ? issues.filter(i => i.document_id === issueFilterDocId) : issues)
    .filter(i => !i.resolved);
  const infoIssues = displayIssues.filter(i => i.severity === "INFO");
  const warnIssues = displayIssues.filter(i => i.severity === "WARNING");
  const errIssues = displayIssues.filter(i => i.severity === "ERROR");

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

  const routeGroups: Record<string, RouteSegment[]> = {};
  segments.forEach(s => {
    const date = s.depart_date || "日期未识别";
    if (!routeGroups[date]) routeGroups[date] = [];
    routeGroups[date].push(s);
  });

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto" }}>
      {toast && <div style={S.toast}>{toast}</div>}
      {error && <div style={S.err}><span>{error}</span><button onClick={() => setError(null)} style={S.errClose}>✕</button></div>}
      {loading && <div style={S.loading}>⏳ {loading}...</div>}
      {progress && <div style={S.progress}>🔄 {progress}...</div>}

      <div style={S.card}>
        <select value={tripId ?? ""} onChange={e => { if (e.target.value) handleSelectTrip(parseInt(e.target.value, 10)); }} style={S.select}>
          <option value="">-- 选择项目 --</option>
          {trips.map(t => <option key={t.id} value={t.id}>#{t.id} {t.title || "未命名"} ({tripStatusLabels[t.status] || t.status})</option>)}
        </select>
      </div>

      {trip && (
        <div style={S.card}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
            <div style={{ flex: 1, minWidth: 260 }}>
              <input
                value={title}
                onChange={e => setTitle(e.target.value)}
                onBlur={() => { if (tripId && title !== trip.title) updateTrip(tripId, { title }).then(setTrip).catch(() => {}); }}
                onKeyDown={e => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
                placeholder="输入项目名称"
                style={S.titleInput}
              />
              <div style={{ fontSize: 12, color: "#888", marginTop: 4 }}>
                {(trip.project_type || "TRAVEL") === "DAILY" ? "日常发票" : (trip.project_type || "TRAVEL") === "MIXED" ? "综合项目" : "出差报销"}
                {(trip.confirmed_start_date || trip.folder_date_start) && ` · ${trip.confirmed_start_date || trip.folder_date_start} 至 ${trip.confirmed_end_date || trip.folder_date_end}`}
                {trip.trip_days != null && ` · ${trip.trip_days} 天`}
              </div>
              <div style={S.pathText} title={trip.folder_path}>路径：{trip.folder_path}</div>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <Tag color="#1565c0" bg="#e3f2fd">{tripStatusLabels[trip.status] || trip.status}</Tag>
              <select
                value={trip.project_type || "TRAVEL"}
                onChange={async e => { if (!tripId) return; const updated = await updateTrip(tripId, { project_type: e.target.value }); setTrip(updated); await loadWorkspace(); }}
                style={S.selectSm}
              >
                <option value="TRAVEL">出差报销</option>
                <option value="DAILY">日常发票</option>
                <option value="MIXED">综合</option>
              </select>
              <select
                value={trip.reimbursement_status || "NOT_REIMBURSED"}
                onChange={async e => { if (!tripId) return; const updated = await updateTrip(tripId, { reimbursement_status: e.target.value }); setTrip(updated); }}
                style={S.selectSm}
              >
                {Object.entries(reimbursementLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              {trip.status === "ANALYZED" && stats.issues > 0 && <Tag color="#c62828" bg="#ffebee">⚠ {stats.issues} 个未处理异常</Tag>}
              {trip.status === "ANALYZED" && stats.issues === 0 && <Tag color="#2e7d32" bg="#e8f5e9">✓ 无未处理异常</Tag>}
            </div>
          </div>
        </div>
      )}

      <div style={S.card}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button onClick={handleOneClick} disabled={!tripId || !!loading || !!progress} style={S.btnPrimary}>🚀 一键分析</button>
          <button onClick={handleSelectFolder} disabled={!!loading} style={S.btn}>📂 选择文件夹</button>
          <button onClick={handleSave} disabled={!folderPath.trim() || !!loading} style={S.btn}>💾 保存</button>
          <button onClick={loadWorkspace} disabled={!tripId || !!loading} style={S.btn}>🔄 刷新</button>
          <button onClick={handleExportExcel} disabled={!tripId || !!loading} style={S.btnSuccess}>📥 导出 Excel</button>
          <button onClick={handleExportPdf} disabled={!tripId || !!loading} style={S.btn}>📄 导出 PDF</button>
          <button onClick={() => setShowAdvanced(!showAdvanced)} style={{ ...S.btn, fontSize: 12, color: "#888" }}>{showAdvanced ? "收起" : "高级"} ▾</button>
        </div>
        <div style={S.ocrHint}>提示：本轮不要求 PaddleOCR 可用；OCR 不可用时，仍可通过人工录入/修正完成报销选择、汇总和导出。</div>
        {showAdvanced && (
          <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
            <button onClick={handleScan} disabled={!tripId || !!loading} style={S.btnSm}>扫描</button>
            <button onClick={handlePreprocess} disabled={!tripId || !!loading} style={S.btnSm}>预处理</button>
            <button onClick={handleRecognize} disabled={!tripId || !!loading} style={S.btnSm}>OCR（可选）</button>
            <button onClick={handleAnalyze} disabled={!tripId || !!loading} style={S.btnSm}>分析</button>
          </div>
        )}
      </div>

      {trip && (
        <div style={S.statGrid}>
          <Stat label="文件总数" value={stats.total_files} />
          <Stat label="识别成功" value={stats.recognized} />
          <Stat label="待复核" value={stats.review_count} />
          <Stat label="未处理异常" value={trip.status === "ANALYZED" ? stats.issues : "-"} warn={stats.issues > 0 && trip.status === "ANALYZED"} />
          <Stat label="本次票据合计" value={summary ? formatMoney(summary.invoice_total_amount) : "-"} />
          {trip.project_type !== "DAILY" && <Stat label="含补助总计" value={summary ? formatMoney(summary.grand_total_amount) : "-"} accent />}
        </div>
      )}

      {summary && expenseBars.length > 0 && (
        <div style={S.card}>
          <div style={S.cardTitle}>💰 费用概览</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <div>
              {expenseBars.map(c => (
                <div key={c.label} style={{ marginBottom: 6 }}>
                  <div style={S.barLabel}><span>{c.label}</span><span>{formatMoney(c.value)}</span></div>
                  <div style={S.barTrack}><div style={{ background: c.color, height: "100%", width: `${(c.value / maxBar) * 100}%`, borderRadius: 2 }} /></div>
                </div>
              ))}
            </div>
            <div>
              {expenseBars.map(c => (
                <div key={c.label} style={S.summaryRow}>
                  <span style={{ color: "#666" }}>{c.label}</span>
                  <span style={{ fontWeight: 600 }}>{formatMoney(c.value)}</span>
                </div>
              ))}
              <div style={S.summaryTotal}><span>本次票据合计</span><span>{formatMoney(summary.invoice_total_amount)}</span></div>
              {trip?.project_type !== "DAILY" && <div style={S.summaryGrand}><span>含补助总计</span><span>{formatMoney(summary.grand_total_amount)}</span></div>}
            </div>
          </div>
        </div>
      )}

      {docs.length > 0 && (
        <div style={S.card}>
          <div style={{ ...S.cardTitle, display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <span>🧾 全部票据池 ({filteredDocs.length}/{docs.length})</span>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {[
                ["all", "全部"],
                ["thisTrip", "本次报销"],
                ["already", "已报销"],
                ["notReimbursed", "暂不报销"],
                ["pending", "待确认"],
                ["invoice", "正式发票"],
                ["supporting", "辅助凭证"],
                ["hasIssue", "异常"],
                ["meal", "餐饮"],
                ["transport", "交通"],
                ["lodging", "住宿"],
                ["daily", "日常"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setFilterKey(key as FilterKey)}
                  style={{ ...S.filterBtn, background: filterKey === key ? "#1565c0" : "#f0f0f0", color: filterKey === key ? "#fff" : "#666" }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div style={S.bulkBar}>
            <span>已选 {selectedInvoiceIds.length} 张票据</span>
            <button onClick={() => handleBulkStatus("THIS_TRIP")} disabled={selectedInvoiceIds.length === 0 || !!loading} style={S.btnSm}>批量本次报销</button>
            <button onClick={() => handleBulkStatus("ALREADY_REIMBURSED")} disabled={selectedInvoiceIds.length === 0 || !!loading} style={S.btnSm}>批量已报销</button>
            <button onClick={() => handleBulkStatus("NOT_REIMBURSED")} disabled={selectedInvoiceIds.length === 0 || !!loading} style={S.btnSm}>批量暂不报销</button>
            <button onClick={() => handleBulkStatus("PENDING")} disabled={selectedInvoiceIds.length === 0 || !!loading} style={S.btnSm}>批量待确认</button>
          </div>

          <div style={{ overflowX: "auto" }}>
            <table style={{ minWidth: 1180, width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={S.tableHead}>
                  <th style={S.thCenter}><input type="checkbox" checked={allVisibleSelected} onChange={e => toggleAllVisible(e.target.checked)} /></th>
                  <th style={S.thLeft}>文件名</th>
                  <th style={S.thCenter}>凭证</th>
                  <th style={S.thCenter}>类型</th>
                  <th style={S.thCenter}>类别</th>
                  <th style={S.thRight}>识别金额</th>
                  <th style={S.thRight}>确认金额</th>
                  <th style={S.thCenter}>报销状态</th>
                  <th style={S.thCenter}>计入</th>
                  <th style={S.thCenter}>异常</th>
                  <th style={S.thCenter}>操作</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocs.map(d => {
                  const invoiceId = d.invoice_id;
                  const selected = invoiceId != null && selectedInvoiceIds.includes(invoiceId);
                  const included = d.reimbursement_status === "THIS_TRIP" && d.include_in_summary;
                  return (
                    <tr key={d.id} style={{ borderBottom: "1px solid #f5f5f5", background: included ? "#fbfffb" : "#fff" }}>
                      <td style={S.tdCenter}>
                        <input type="checkbox" disabled={!invoiceId} checked={selected} onChange={e => invoiceId && toggleInvoiceSelection(invoiceId, e.target.checked)} />
                      </td>
                      <td style={S.tdFile} title={d.file_path || d.file_name}>{shortName(d.file_name)}</td>
                      <td style={S.tdCenter}><Tag color={d.document_role === "OFFICIAL_INVOICE" ? "#2e7d32" : "#888"} bg={d.document_role === "OFFICIAL_INVOICE" ? "#e8f5e9" : "#f5f5f5"} small>{documentRoleLabels[d.document_role || "UNKNOWN"] || d.document_role || "未识别"}</Tag></td>
                      <td style={S.tdCenter}>{d.invoice_type ? (invoiceTypeLabels[d.invoice_type] || d.invoice_type) : "-"}</td>
                      <td style={S.tdCenter}>{d.expense_category ? (expenseCategoryLabels[d.expense_category] || d.expense_category) : "-"}</td>
                      <td style={S.tdRight}>{d.total_amount != null ? formatMoney(d.total_amount) : d.order_total_amount != null ? <span style={{ color: "#888" }}>{formatMoney(d.order_total_amount)}</span> : "-"}</td>
                      <td style={S.tdRight}>{d.confirmed_amount != null ? formatMoney(d.confirmed_amount) : <span style={{ color: "#aaa" }}>待确认</span>}</td>
                      <td style={S.tdCenter}>
                        <select value={d.reimbursement_status || "PENDING"} disabled={!invoiceId || !!loading} onChange={e => handleSingleStatus(d, e.target.value)} style={S.tableSelect}>
                          {invoiceStatusOptions.map(status => <option key={status} value={status}>{invoiceReimbursementLabels[status]}</option>)}
                        </select>
                      </td>
                      <td style={S.tdCenter}>
                        <input type="checkbox" disabled={!invoiceId || d.reimbursement_status !== "THIS_TRIP"} checked={included} onChange={e => handleIncludeChange(d, e.target.checked)} />
                      </td>
                      <td style={S.tdCenter}>{d.issue_count > 0 ? <button onClick={() => setIssueFilterDocId(d.id)} style={S.linkBtn}>{d.issue_count}</button> : <span style={{ color: "#ccc" }}>0</span>}</td>
                      <td style={S.tdCenter}><button onClick={() => setDetailDoc(d)} style={S.linkBtn}>编辑</button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {Object.keys(routeGroups).length > 0 && trip?.project_type !== "DAILY" && (
        <div style={S.card}>
          <div style={S.cardTitle}>🗺 路线时间线</div>
          {Object.entries(routeGroups).map(([date, segs]) => (
            <div key={date} style={{ marginBottom: 10 }}>
              <div style={S.routeDate}>📅 {date}</div>
              {segs.map(s => (
                <div key={s.id} style={S.routeRow}>
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

      {displayIssues.length > 0 && (
        <div style={S.card}>
          <div style={S.cardTitle}>⚠ 异常处理</div>
          {issueFilterDocId && <button onClick={() => setIssueFilterDocId(null)} style={S.btnSm}>显示全部异常</button>}
          {errIssues.length > 0 && <IssueGroup title={`错误 (${errIssues.length})`} color="#c62828" issues={errIssues} docs={docs} onView={setDetailDoc} onResolve={handleIssueUpdate} />}
          {warnIssues.length > 0 && <IssueGroup title={`警告 (${warnIssues.length})`} color="#e65100" issues={warnIssues} docs={docs} onView={setDetailDoc} onResolve={handleIssueUpdate} />}
          {infoIssues.length > 0 && <IssueGroup title={`提示 (${infoIssues.length})`} color="#2e7d32" issues={infoIssues} docs={docs} onView={setDetailDoc} onResolve={handleIssueUpdate} />}
        </div>
      )}
      {displayIssues.length === 0 && trip?.status === "ANALYZED" && <div style={{ ...S.card, textAlign: "center", color: "#888", padding: 24 }}>✓ 当前没有未处理问题</div>}

      {detailDoc && (
        <div style={S.overlay} onClick={() => setDetailDoc(null)}>
          <div style={S.drawer} onClick={e => e.stopPropagation()}>
            <div style={S.drawerHead}>
              <span style={{ fontSize: 16, fontWeight: 600 }}>📋 发票详情与人工复核</span>
              <button onClick={() => setDetailDoc(null)} style={S.closeBtn}>✕</button>
            </div>
            <div style={S.sectionTitle}>基础信息</div>
            <DRow label="文件名" value={detailDoc.file_name} />
            <DRow label="文件路径" value={detailDoc.file_path || "未识别"} />
            <DRow label="文件大小" value={formatSize(detailDoc.file_size)} />
            <DRow label="扫描/OCR" value={`${scanStatusLabels[detailDoc.scan_status] || detailDoc.scan_status} / ${ocrStatusLabels[detailDoc.ocr_status] || detailDoc.ocr_status}`} />
            <DRow label="解析器" value={detailDoc.parser_name || "无"} />
            <DRow label="置信度" value={detailDoc.confidence == null ? "无" : `${Math.round(detailDoc.confidence * 100)}%`} />

            <div style={S.sectionTitle}>报销状态</div>
            <EditSelect label="报销状态" value={String(detailDraft.reimbursement_status || "PENDING")} options={invoiceStatusOptions} labels={invoiceReimbursementLabels} onChange={value => setDetailDraft(prev => ({ ...prev, reimbursement_status: value }))} />
            <EditSelect label="复核状态" value={String(detailDraft.review_status || "NEEDS_REVIEW")} options={Object.keys(reviewStatusLabels)} labels={reviewStatusLabels} onChange={value => setDetailDraft(prev => ({ ...prev, review_status: value }))} />
            <EditSelect label="凭证角色" value={String(detailDraft.document_role || "OFFICIAL_INVOICE")} options={Object.keys(documentRoleLabels)} labels={documentRoleLabels} onChange={value => setDetailDraft(prev => ({ ...prev, document_role: value }))} />
            <label style={S.checkboxRow}><input type="checkbox" checked={Boolean(detailDraft.include_in_summary)} onChange={e => setDetailDraft(prev => ({ ...prev, include_in_summary: e.target.checked }))} /> 计入本次报销汇总</label>

            <div style={S.sectionTitle}>金额与日期</div>
            <EditSelect label="发票类型" value={String(detailDraft.invoice_type || "UNKNOWN")} options={invoiceTypeOptions} labels={invoiceTypeLabels} onChange={value => setDetailDraft(prev => ({ ...prev, invoice_type: value }))} />
            <EditSelect label="费用类别" value={String(detailDraft.expense_category || "OTHER")} options={expenseCategoryOptions} labels={expenseCategoryLabels} onChange={value => setDetailDraft(prev => ({ ...prev, expense_category: value }))} />
            <EditInput label="发票号码" value={detailDraft.invoice_number ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, invoice_number: value }))} />
            <EditInput label="发票日期" type="date" value={detailDraft.invoice_date ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, invoice_date: value || null }))} />
            <EditInput label="业务日期" type="date" value={detailDraft.business_date ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, business_date: value || null }))} />
            <EditInput label="销售方" value={detailDraft.seller_name ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, seller_name: value }))} />
            <EditInput label="购买方" value={detailDraft.buyer_name ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, buyer_name: value }))} />
            <EditInput label="识别金额" type="number" value={detailDraft.total_amount ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, total_amount: value === "" ? null : Number(value) }))} />
            <EditInput label="确认金额" type="number" value={detailDraft.confirmed_amount ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, confirmed_amount: value === "" ? null : Number(value) }))} />

            <div style={S.sectionTitle}>交通字段</div>
            <EditInput label="出发城市" value={detailDraft.from_city ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, from_city: value }))} />
            <EditInput label="到达城市" value={detailDraft.to_city ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, to_city: value }))} />
            <EditInput label="出发地" value={detailDraft.from_place ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, from_place: value }))} />
            <EditInput label="到达地" value={detailDraft.to_place ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, to_place: value }))} />
            <EditInput label="车次/航班号" value={detailDraft.transport_no ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, transport_no: value }))} />
            <EditInput label="出发时间" value={detailDraft.depart_time_str ?? ""} placeholder="例如 15:10" onChange={value => setDetailDraft(prev => ({ ...prev, depart_time_str: value }))} />
            <EditInput label="席别/舱位" value={detailDraft.seat_class ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, seat_class: value }))} />

            <div style={S.sectionTitle}>住宿字段</div>
            <EditInput label="酒店名称" value={detailDraft.hotel_name ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, hotel_name: value }))} />
            <EditInput label="入住日期" type="date" value={detailDraft.checkin_date ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, checkin_date: value || null }))} />
            <EditInput label="离店日期" type="date" value={detailDraft.checkout_date ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, checkout_date: value || null }))} />
            <EditInput label="住宿晚数" type="number" value={detailDraft.nights ?? ""} onChange={value => setDetailDraft(prev => ({ ...prev, nights: value === "" ? null : Number(value) }))} />

            <div style={S.sectionTitle}>备注与 OCR</div>
            <label style={S.editRow}>
              <span style={S.editLabel}>备注</span>
              <textarea value={detailDraft.note ?? ""} onChange={e => setDetailDraft(prev => ({ ...prev, note: e.target.value }))} style={S.textarea} />
            </label>
            <div style={S.ocrUnavailable}>OCR 原文当前未在工作台返回；如 OCR 不可用，可直接在此人工录入关键字段。</div>
            <div style={S.drawerActions}>
              <button onClick={handleSaveDetail} disabled={!detailDoc.invoice_id || !!loading} style={S.btnPrimary}>保存并标记人工确认</button>
              <button onClick={() => setDetailDoc(null)} style={S.btn}>取消</button>
            </div>
          </div>
        </div>
      )}

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

function shortName(name: string): string {
  return name.length > 26 ? `${name.slice(0, 18)}...${name.slice(-6)}` : name;
}

function Stat({ label, value, warn, accent }: { label: string; value: number | string; warn?: boolean; accent?: boolean }) {
  return (
    <div style={S.stat}>
      <div style={{ fontSize: 11, color: "#888", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: warn ? "#c62828" : accent ? "#1565c0" : "#333" }}>{value}</div>
    </div>
  );
}

function Tag({ color, bg, small, children }: { color: string; bg: string; small?: boolean; children: React.ReactNode }) {
  return <span style={{ padding: small ? "1px 6px" : "2px 8px", borderRadius: 10, fontSize: small ? 10 : 11, fontWeight: 600, background: bg, color, whiteSpace: "nowrap" }}>{children}</span>;
}

function IssueGroup({
  title,
  color,
  issues,
  docs,
  onView,
  onResolve,
}: {
  title: string;
  color: string;
  issues: IssueData[];
  docs: WorkspaceDoc[];
  onView: (d: WorkspaceDoc) => void;
  onResolve: (issue: IssueData, ignored: boolean) => void;
}) {
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ marginBottom: 8, fontWeight: 600, color, fontSize: 13 }}>{title}</div>
      {issues.map(issue => <IssueRow key={issue.id} issue={issue} docs={docs} onView={onView} onResolve={onResolve} />)}
    </div>
  );
}

function IssueRow({
  issue,
  docs,
  onView,
  onResolve,
}: {
  issue: IssueData;
  docs: WorkspaceDoc[];
  onView: (d: WorkspaceDoc) => void;
  onResolve: (issue: IssueData, ignored: boolean) => void;
}) {
  const sevColor = issue.severity === "ERROR" ? "#c62828" : issue.severity === "WARNING" ? "#e65100" : "#2e7d32";
  const sevBg = issue.severity === "ERROR" ? "#ffebee" : issue.severity === "WARNING" ? "#fff3e0" : "#e8f5e9";
  return (
    <div style={S.issueRow}>
      <Tag color={sevColor} bg={sevBg} small>{severityLabels[issue.severity] || issue.severity}</Tag>
      <span style={{ minWidth: 110, color: "#666", fontSize: 12 }}>{issueTypeLabels[issue.issue_type] || issue.issue_type}</span>
      <span style={{ flex: 1 }}>{issue.message}</span>
      {issue.file_name && <span style={S.issueFile}>{issue.file_name}</span>}
      {issue.document_id && <button onClick={() => { const doc = docs.find(x => x.id === issue.document_id); if (doc) onView(doc); }} style={S.linkBtn}>查看票据</button>}
      <button onClick={() => onResolve(issue, false)} style={S.linkBtn}>已解决</button>
      <button onClick={() => onResolve(issue, true)} style={S.linkBtn}>忽略</button>
    </div>
  );
}

function DRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={S.detailRow}>
      <span style={S.detailLabel}>{label}</span>
      <span style={{ flex: 1, wordBreak: "break-all", fontSize: 12 }}>{value || "未识别"}</span>
    </div>
  );
}

function EditInput({
  label,
  value,
  onChange,
  type = "text",
  placeholder,
}: {
  label: string;
  value: string | number;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
}) {
  return (
    <label style={S.editRow}>
      <span style={S.editLabel}>{label}</span>
      <input type={type} value={value} placeholder={placeholder} onChange={e => onChange(e.target.value)} style={S.editInput} />
    </label>
  );
}

function EditSelect({
  label,
  value,
  options,
  labels,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  labels: Record<string, string>;
  onChange: (value: string) => void;
}) {
  return (
    <label style={S.editRow}>
      <span style={S.editLabel}>{label}</span>
      <select value={value} onChange={e => onChange(e.target.value)} style={S.editInput}>
        {options.map(option => <option key={option} value={option}>{labels[option] || option}</option>)}
      </select>
    </label>
  );
}

const S: Record<string, React.CSSProperties> = {
  card: { background: "#fff", borderRadius: 10, boxShadow: "0 1px 4px rgba(0,0,0,0.06)", padding: 20, marginBottom: 14 },
  cardTitle: { fontSize: 15, fontWeight: 600, marginBottom: 12, color: "#333" },
  select: { padding: "6px 12px", border: "1px solid #ddd", borderRadius: 6, fontSize: 14, minWidth: 240, background: "#fff" },
  selectSm: { padding: "2px 6px", borderRadius: 6, fontSize: 11, border: "1px solid #ddd", background: "#fff", cursor: "pointer", minWidth: 96 },
  titleInput: { fontSize: 20, fontWeight: 700, border: "none", borderBottom: "2px solid #eee", outline: "none", padding: "2px 0", width: "100%", background: "transparent" },
  pathText: { fontSize: 11, color: "#aaa", marginTop: 2, maxWidth: 620, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  btn: { padding: "8px 16px", border: "1px solid #ddd", borderRadius: 6, background: "#fff", cursor: "pointer", fontSize: 13, color: "#555" },
  btnSm: { padding: "4px 10px", border: "1px solid #eee", borderRadius: 4, background: "#f8f8f8", cursor: "pointer", fontSize: 11, color: "#666" },
  btnPrimary: { padding: "10px 20px", border: "none", borderRadius: 8, background: "#1565c0", color: "#fff", cursor: "pointer", fontSize: 14, fontWeight: 600 },
  btnSuccess: { padding: "8px 16px", border: "1px solid #b7dfb9", borderRadius: 6, background: "#e8f5e9", cursor: "pointer", fontSize: 13, color: "#2e7d32", fontWeight: 600 },
  toast: { position: "fixed", top: 20, right: 20, background: "#2e7d32", color: "#fff", padding: "10px 20px", borderRadius: 8, zIndex: 2000, fontSize: 14 },
  err: { background: "#ffebee", color: "#c62828", padding: "10px 16px", borderRadius: 8, marginBottom: 14, display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 },
  errClose: { background: "none", border: "none", cursor: "pointer", fontSize: 16, color: "#c62828" },
  loading: { background: "#e3f2fd", color: "#1565c0", padding: "8px 16px", borderRadius: 8, marginBottom: 14, fontSize: 13 },
  progress: { background: "#fff3e0", color: "#e65100", padding: "8px 16px", borderRadius: 8, marginBottom: 14, fontSize: 13 },
  ocrHint: { marginTop: 8, fontSize: 12, color: "#888", lineHeight: 1.6 },
  statGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10, marginBottom: 16 },
  stat: { background: "#fff", borderRadius: 8, boxShadow: "0 1px 3px rgba(0,0,0,0.06)", padding: "14px 16px", textAlign: "center" },
  barLabel: { display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 2 },
  barTrack: { background: "#eee", borderRadius: 2, height: 10, overflow: "hidden" },
  summaryRow: { display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 13, borderBottom: "1px solid #f5f5f5" },
  summaryTotal: { display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: 13, fontWeight: 700, borderTop: "2px solid #e0e0e0", marginTop: 4 },
  summaryGrand: { display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 14, fontWeight: 700, color: "#1565c0" },
  filterBtn: { padding: "2px 8px", border: "none", borderRadius: 10, cursor: "pointer", fontSize: 11 },
  bulkBar: { display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", padding: "8px 10px", background: "#fafafa", borderRadius: 8, marginBottom: 10, fontSize: 12, color: "#666" },
  tableHead: { color: "#888", fontSize: 12, borderBottom: "1px solid #eee", background: "#fafafa" },
  thLeft: { padding: "6px 8px", textAlign: "left" },
  thCenter: { padding: "6px 8px", textAlign: "center" },
  thRight: { padding: "6px 8px", textAlign: "right" },
  tdCenter: { padding: "4px 8px", textAlign: "center" },
  tdRight: { padding: "4px 8px", textAlign: "right", whiteSpace: "nowrap" },
  tdFile: { padding: "4px 8px", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  tableSelect: { width: 110, fontSize: 12, border: "1px solid #ddd", borderRadius: 4, padding: "2px 4px", background: "#fff" },
  linkBtn: { background: "none", border: "none", color: "#1565c0", cursor: "pointer", fontSize: 12, padding: "2px 4px" },
  routeDate: { fontWeight: 600, fontSize: 13, color: "#1565c0", marginBottom: 4, paddingBottom: 2, borderBottom: "1px solid #e3f2fd" },
  routeRow: { display: "flex", alignItems: "center", padding: "4px 0 4px 12px", borderLeft: "2px solid #e8e8e8", marginLeft: 6, fontSize: 13, gap: 10 },
  issueRow: { display: "flex", alignItems: "center", gap: 8, padding: "5px 0", fontSize: 13, borderBottom: "1px solid #f8f8f8" },
  issueFile: { color: "#888", fontSize: 11, maxWidth: 160, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" },
  overlay: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.3)", zIndex: 1000, display: "flex", justifyContent: "flex-end" },
  drawer: { width: 520, maxWidth: "96vw", background: "#fff", height: "100%", overflowY: "auto", boxShadow: "-4px 0 20px rgba(0,0,0,0.1)", padding: 24 },
  drawerHead: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  closeBtn: { background: "none", border: "none", fontSize: 18, cursor: "pointer", color: "#888" },
  sectionTitle: { marginTop: 16, marginBottom: 8, fontSize: 14, fontWeight: 700, color: "#1565c0", borderBottom: "1px solid #e3f2fd", paddingBottom: 4 },
  detailRow: { display: "flex", padding: "5px 0", borderBottom: "1px solid #f5f5f5" },
  detailLabel: { minWidth: 92, color: "#888", fontSize: 12 },
  editRow: { display: "flex", alignItems: "center", gap: 8, padding: "5px 0", fontSize: 13 },
  editLabel: { minWidth: 92, color: "#666", fontSize: 12 },
  editInput: { flex: 1, border: "1px solid #ddd", borderRadius: 6, padding: "6px 8px", fontSize: 13 },
  checkboxRow: { display: "flex", alignItems: "center", gap: 6, padding: "6px 0", fontSize: 13, color: "#555" },
  textarea: { flex: 1, border: "1px solid #ddd", borderRadius: 6, padding: "6px 8px", fontSize: 13, minHeight: 72, resize: "vertical" },
  ocrUnavailable: { background: "#fafafa", color: "#888", borderRadius: 6, padding: 10, fontSize: 12, lineHeight: 1.6, marginTop: 8 },
  drawerActions: { display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 18, paddingBottom: 30 },
};
