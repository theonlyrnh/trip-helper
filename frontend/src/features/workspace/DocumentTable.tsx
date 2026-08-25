import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, CirclePause, Eye, Filter, Pencil, RotateCcw, Search, Trash2 } from "lucide-react";
import { documentsApi, invoicesApi } from "../../api/resources";
import type { DocumentInvoice, DocumentRecord, InvoiceUpdateInput } from "../../api/types";
import { formatBytes, formatMoney, labelForDocumentType, labelForExpenseCategory, labelForInvoiceType, labelForReimbursementStatus, labelForState } from "../../lib/format";

interface DocumentTableProps {
  tripId: string;
  documents: DocumentRecord[];
  loading: boolean;
  onPreview: (document: DocumentRecord) => void;
  onEdit: (document: DocumentRecord) => void;
  onChanged: () => void;
}

type DocumentFilter = "ALL" | "NEEDS_REVIEW" | "THIS_TRIP" | "PENDING" | "HAS_ISSUE" | "FAILED";
type InvoiceMutation = { invoiceId: string; documentId: string; input: InvoiceUpdateInput };

const auxiliaryDocumentRoles = new Set(["ORDER_SCREENSHOT", "BOOKING_SCREENSHOT", "SUPPORTING_DOC"]);

const filterOptions: Array<{ value: DocumentFilter; label: string }> = [
  { value: "ALL", label: "全部票据" },
  { value: "NEEDS_REVIEW", label: "待人工复核" },
  { value: "THIS_TRIP", label: "本次报销" },
  { value: "PENDING", label: "待确认" },
  { value: "HAS_ISSUE", label: "存在异常" },
  { value: "FAILED", label: "处理失败" },
];

function matchesFilter(document: DocumentRecord, filter: DocumentFilter): boolean {
  if (filter === "ALL") return true;
  if (filter === "HAS_ISSUE") return document.issue_count > 0;
  if (filter === "FAILED") return hasProcessingFailure(document);
  if (!document.invoice) return false;
  if (filter === "NEEDS_REVIEW") return document.invoice.review_status === "NEEDS_REVIEW";
  return document.invoice.reimbursement_status === filter;
}

function hasProcessingFailure(document: DocumentRecord): boolean {
  return document.processing_status === "FAILED" || document.ocr_status === "FAILED";
}

function matchesSearch(document: DocumentRecord, query: string): boolean {
  const normalized = query.trim().toLocaleLowerCase("zh-CN");
  if (!normalized) return true;
  const invoice = document.invoice;
  return [
    document.original_filename,
    document.relative_path,
    document.mime_type,
    document.document_type,
    document.processing_status,
    document.ocr_status,
    invoice?.invoice_type,
    invoice?.expense_category,
    invoice?.seller_name,
    invoice?.transport_no,
    invoice?.hotel_name,
  ].filter((value): value is string => Boolean(value)).some((value) => value.toLocaleLowerCase("zh-CN").includes(normalized));
}

function applyInvoiceUpdate(invoice: DocumentInvoice, input: InvoiceUpdateInput): DocumentInvoice {
  const next = { ...invoice, ...input };
  const reimbursementStatus = next.reimbursement_status;
  if (reimbursementStatus !== "THIS_TRIP" || auxiliaryDocumentRoles.has(next.document_role)) {
    next.include_in_summary = false;
  } else if (input.include_in_summary === undefined && (input.reimbursement_status !== undefined || input.document_role !== undefined)) {
    next.include_in_summary = true;
  }
  return next;
}

function updateDocumentInvoice(documents: DocumentRecord[] | undefined, invoiceId: string, update: (invoice: DocumentInvoice) => DocumentInvoice): DocumentRecord[] | undefined {
  return documents?.map((document) => document.invoice?.id === invoiceId
    ? { ...document, invoice: update(document.invoice) }
    : document);
}

function updateDocumentInvoices(documents: DocumentRecord[] | undefined, updates: Map<string, DocumentInvoice>): DocumentRecord[] | undefined {
  return documents?.map((document) => document.invoice && updates.has(document.invoice.id)
    ? { ...document, invoice: updates.get(document.invoice.id)! }
    : document);
}

export function DocumentTable({ tripId, documents, loading, onPreview, onEdit, onChanged }: DocumentTableProps) {
  const queryClient = useQueryClient();
  const [actionId, setActionId] = useState<string | null>(null);
  const [busyInvoiceDocumentIds, setBusyInvoiceDocumentIds] = useState<Set<string>>(() => new Set());
  const [selectedInvoiceIds, setSelectedInvoiceIds] = useState<string[]>([]);
  const [filter, setFilter] = useState<DocumentFilter>("ALL");
  const [query, setQuery] = useState("");
  const documentsKey = ["trip", tripId, "documents"] as const;
  const invoicesKey = ["trip", tripId, "invoices"] as const;
  const removeDocument = useMutation({
    mutationFn: (documentId: string) => documentsApi.remove(documentId),
    onSuccess: onChanged,
    onSettled: () => setActionId(null),
  });
  const retryDocument = useMutation({
    mutationFn: (documentId: string) => documentsApi.retry(documentId),
    onSuccess: onChanged,
    onSettled: () => setActionId(null),
  });
  const updateInvoice = useMutation({
    mutationFn: ({ invoiceId, input }: InvoiceMutation) => invoicesApi.update(invoiceId, input),
    onMutate: async ({ invoiceId, documentId, input }) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: documentsKey, exact: true }),
        queryClient.cancelQueries({ queryKey: invoicesKey, exact: true }),
      ]);
      const previousDocuments = queryClient.getQueryData<DocumentRecord[]>(documentsKey);
      const previousInvoices = queryClient.getQueryData<DocumentInvoice[]>(invoicesKey);
      queryClient.setQueryData<DocumentRecord[]>(documentsKey, (current) => updateDocumentInvoice(current, invoiceId, (invoice) => applyInvoiceUpdate(invoice, input)));
      queryClient.setQueryData<DocumentInvoice[]>(invoicesKey, (current) => current?.map((invoice) => invoice.id === invoiceId ? applyInvoiceUpdate(invoice, input) : invoice));
      setBusyInvoiceDocumentIds((previous) => new Set(previous).add(documentId));
      return { previousDocuments, previousInvoices };
    },
    onError: (_error, _variables, context) => {
      if (context?.previousDocuments) queryClient.setQueryData(documentsKey, context.previousDocuments);
      if (context?.previousInvoices) queryClient.setQueryData(invoicesKey, context.previousInvoices);
    },
    onSuccess: (invoice) => {
      queryClient.setQueryData<DocumentRecord[]>(documentsKey, (current) => updateDocumentInvoice(current, invoice.id, () => invoice));
      queryClient.setQueryData<DocumentInvoice[]>(invoicesKey, (current) => current?.map((item) => item.id === invoice.id ? invoice : item));
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["trip", tripId], exact: true }),
        queryClient.invalidateQueries({ queryKey: ["trip", tripId, "summary"], exact: true }),
        queryClient.invalidateQueries({ queryKey: ["trips"], exact: true }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
    onSettled: (_data, _error, variables) => {
      setBusyInvoiceDocumentIds((previous) => {
        const next = new Set(previous);
        next.delete(variables.documentId);
        return next;
      });
    },
  });
  const bulkUpdate = useMutation({
    mutationFn: (reimbursementStatus: string) => invoicesApi.bulkUpdate(tripId, selectedInvoiceIds, { reimbursement_status: reimbursementStatus }),
    onSuccess: (invoices) => {
      setSelectedInvoiceIds([]);
      const updatedById = new Map(invoices.map((invoice) => [invoice.id, invoice]));
      queryClient.setQueryData<DocumentRecord[]>(documentsKey, (current) => updateDocumentInvoices(current, updatedById));
      queryClient.setQueryData<DocumentInvoice[]>(invoicesKey, (current) => current?.map((invoice) => updatedById.get(invoice.id) || invoice));
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["trip", tripId], exact: true }),
        queryClient.invalidateQueries({ queryKey: ["trip", tripId, "summary"], exact: true }),
        queryClient.invalidateQueries({ queryKey: ["trips"], exact: true }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
  });

  function remove(document: DocumentRecord) {
    if (!window.confirm(`删除“${document.original_filename}”？此操作会同时删除相关处理结果。`)) return;
    setActionId(document.id);
    removeDocument.mutate(document.id);
  }

  function retryProcessing(document: DocumentRecord) {
    setActionId(document.id);
    retryDocument.mutate(document.id);
  }

  const visibleDocuments = documents.filter((document) => matchesFilter(document, filter) && matchesSearch(document, query));
  const invoiceIds = visibleDocuments.flatMap((document) => document.invoice ? [document.invoice.id] : []);
  const allSelected = invoiceIds.length > 0 && invoiceIds.every((invoiceId) => selectedInvoiceIds.includes(invoiceId));

  function selectInvoice(invoiceId: string, selected: boolean) {
    setSelectedInvoiceIds((previous) => selected
      ? [...new Set([...previous, invoiceId])]
      : previous.filter((item) => item !== invoiceId));
  }

  function selectAll(selected: boolean) {
    setSelectedInvoiceIds(selected ? invoiceIds : []);
  }

  if (loading) return <section className="workspace-section"><div className="compact-empty">正在加载文档...</div></section>;

  return (
    <section className="workspace-section document-section" aria-labelledby="documents-title">
      <div className="section-heading">
        <div>
          <p className="eyebrow">票据</p>
          <h2 id="documents-title">票据与费用明细</h2>
        </div>
        <div className="document-table-controls">
          <label className="document-search"><Search size={15} aria-hidden="true" /><span className="visually-hidden">搜索票据</span><input aria-label="搜索票据" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索文件或类型..." /></label>
          <label className="table-filter"><Filter size={15} aria-hidden="true" /><span>筛选</span><select aria-label="筛选票据" value={filter} onChange={(event) => setFilter(event.target.value as DocumentFilter)}>{filterOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
          <span className="muted">{visibleDocuments.length}/{documents.length} 个文件</span>
        </div>
      </div>
      {selectedInvoiceIds.length > 0 && (
        <div className="bulk-actions">
          <span>已选 {selectedInvoiceIds.length} 张票据</span>
          <button className="button button-secondary" type="button" disabled={bulkUpdate.isPending} onClick={() => bulkUpdate.mutate("THIS_TRIP")}><Check size={15} /> 批量本次报销</button>
          <button className="button button-secondary" type="button" disabled={bulkUpdate.isPending} onClick={() => bulkUpdate.mutate("ALREADY_REIMBURSED")}><Check size={15} /> 批量已报销</button>
          <button className="button button-secondary" type="button" disabled={bulkUpdate.isPending} onClick={() => bulkUpdate.mutate("PENDING")}><CirclePause size={15} /> 批量待确认</button>
          <button className="button button-secondary" type="button" disabled={bulkUpdate.isPending} onClick={() => bulkUpdate.mutate("NOT_REIMBURSED")}><CirclePause size={15} /> 批量暂不报销</button>
        </div>
      )}
      {documents.length === 0 ? <div className="compact-empty">上传文件后，处理状态和人工复核信息会显示在这里。</div> : visibleDocuments.length === 0 ? <div className="compact-empty">当前筛选条件下没有匹配的票据。</div> : (
        <div className="table-scroll">
          <table className="document-table">
            <thead>
              <tr>
                <th><input type="checkbox" aria-label="选择全部可编辑票据" checked={allSelected} disabled={invoiceIds.length === 0} onChange={(event) => selectAll(event.target.checked)} /></th><th>文件</th><th>目录</th><th>大小</th><th>上传</th><th>处理</th><th>OCR</th><th>类型</th><th>类别</th><th>金额</th><th>确认金额</th><th>报销</th><th>计入</th><th>异常</th><th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {visibleDocuments.map((document) => {
                const invoice = document.invoice;
                const isBusy = actionId === document.id || busyInvoiceDocumentIds.has(document.id);
                const processingFailed = hasProcessingFailure(document);
                return (
                  <tr key={document.id}>
                    <td><input type="checkbox" aria-label={`选择 ${document.original_filename}`} checked={invoice ? selectedInvoiceIds.includes(invoice.id) : false} disabled={!invoice} onChange={(event) => invoice && selectInvoice(invoice.id, event.target.checked)} /></td>
                    <td className="document-name">
                      <span className="document-filename">{document.original_filename}</span>
                      <div className="document-mobile-processing">
                        <div className="document-mobile-statuses"><Status value={document.processing_status} prefix="处理" /><Status value={document.ocr_status} prefix="OCR" /></div>
                        {processingFailed && <button className="button button-secondary document-mobile-retry" type="button" disabled={isBusy} onClick={() => retryProcessing(document)}><RotateCcw size={13} /> 重试处理</button>}
                        {processingFailed && document.error_message && <small className="document-mobile-error" title={document.error_message}>{document.error_message}</small>}
                      </div>
                    </td>
                    <td title={document.relative_path || undefined}>{document.relative_path || "-"}</td>
                    <td>{formatBytes(document.size_bytes)}</td>
                    <td><Status value={document.upload_status} /></td>
                    <td><Status value={document.processing_status} /></td>
                    <td><Status value={document.ocr_status} /></td>
                    <td>{invoice?.invoice_type ? labelForInvoiceType(invoice.invoice_type) : labelForDocumentType(document.document_type)}</td>
                    <td>{labelForExpenseCategory(invoice?.expense_category)}</td>
                    <td>{formatMoney(invoice?.total_amount)}</td>
                    <td>{formatMoney(invoice?.confirmed_amount)}</td>
                    <td>{invoice ? <select className="table-status-select" aria-label={`${document.original_filename} 报销状态`} value={invoice.reimbursement_status} disabled={isBusy} onChange={(event) => updateInvoice.mutate({ invoiceId: invoice.id, documentId: document.id, input: { reimbursement_status: event.target.value } })}><option value="THIS_TRIP">{labelForReimbursementStatus("THIS_TRIP")}</option><option value="ALREADY_REIMBURSED">{labelForReimbursementStatus("ALREADY_REIMBURSED")}</option><option value="NOT_REIMBURSED">{labelForReimbursementStatus("NOT_REIMBURSED")}</option><option value="PENDING">{labelForReimbursementStatus("PENDING")}</option></select> : "-"}</td>
                    <td><input type="checkbox" aria-label={`${document.original_filename} 是否计入汇总`} checked={invoice?.include_in_summary || false} disabled={!invoice || isBusy} onChange={(event) => { if (!invoice) return; updateInvoice.mutate({ invoiceId: invoice.id, documentId: document.id, input: { include_in_summary: event.target.checked } }); }} /></td>
                    <td>{document.issue_count || "-"}</td>
                    <td>
                      <div className="table-actions">
                        <button className="icon-button" type="button" title="预览" aria-label="预览" onClick={() => onPreview(document)}><Eye size={16} /></button>
                        <button className="icon-button" type="button" title="人工复核" aria-label="人工复核" onClick={() => onEdit(document)}><Pencil size={16} /></button>
                        {processingFailed && <button className="icon-button" type="button" title="重试处理" aria-label="重试处理" disabled={isBusy} onClick={() => retryProcessing(document)}><RotateCcw size={16} /></button>}
                        <button className="icon-button danger-button" type="button" title="删除文件" aria-label="删除文件" disabled={isBusy} onClick={() => remove(document)}><Trash2 size={16} /></button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {(removeDocument.error || retryDocument.error || updateInvoice.error || bulkUpdate.error) && <p className="form-error" role="alert">操作未能完成，请刷新后重试。</p>}
    </section>
  );
}

function Status({ value, prefix }: { value: string | null | undefined; prefix?: string }) {
  const normalized = value || "PENDING";
  const stateClass = normalized === "FAILED" ? " error" : ["SUCCEEDED", "UPLOADED", "SUCCESS"].includes(normalized) ? " success" : "";
  return <span className={`status-badge${stateClass}`}>{prefix ? `${prefix} ${labelForState(normalized)}` : labelForState(normalized)}</span>;
}
