import { useState } from "react";
import type { FormEvent } from "react";
import { X } from "lucide-react";
import type { DocumentInvoice, DocumentRecord, InvoiceUpdateInput } from "../../api/types";
import { labelForExpenseCategory, labelForInvoiceType } from "../../lib/format";

interface InvoiceDrawerProps {
  document: DocumentRecord | null;
  invoice: DocumentInvoice | null;
  loading: boolean;
  loadError: boolean;
  busy: boolean;
  onClose: () => void;
  onSave: (invoiceId: string, update: InvoiceUpdateInput) => void;
}

interface Draft {
  invoice_type: string;
  expense_category: string;
  total_amount: string;
  confirmed_amount: string;
  reimbursement_status: string;
  include_in_summary: boolean;
  review_status: string;
  document_role: string;
  invoice_number: string;
  invoice_date: string;
  business_date: string;
  seller_name: string;
  buyer_name: string;
  from_city: string;
  to_city: string;
  from_place: string;
  to_place: string;
  transport_no: string;
  depart_time_str: string;
  seat_class: string;
  hotel_name: string;
  checkin_date: string;
  checkout_date: string;
  nights: string;
  note: string;
}

const invoiceTypeOptions = [
  "GENERAL_INVOICE", "VAT_INVOICE", "TRAIN_TICKET", "FLIGHT_TICKET", "FLIGHT_ORDER_PROOF",
  "HOTEL_INVOICE", "HOTEL_BOOKING_PROOF", "TAXI_INVOICE", "RIDE_HAILING_INVOICE", "MEAL_INVOICE",
  "BUS_TICKET", "TRAVEL_INSURANCE_INVOICE", "EXPRESS_LOGISTICS", "OFFICE_SUPPLIES", "ELECTRONICS_DIGITAL",
  "SOFTWARE_SERVICE", "COMMUNICATION", "GENERAL_SERVICE", "DAILY_GENERAL", "OTHER", "UNKNOWN",
];

const expenseCategoryOptions = [
  "INTERCITY_TRANSPORT", "LOCAL_TRANSPORT", "LODGING", "MEAL", "REFUND_CHANGE_FEE", "TRAVEL_INSURANCE",
  "EXPRESS_LOGISTICS", "OFFICE_SUPPLIES", "ELECTRONICS_DIGITAL", "SOFTWARE_SERVICE", "COMMUNICATION",
  "GENERAL_SERVICE", "DAILY_GENERAL", "OTHER",
];

function optionsIncluding(value: string, options: string[]): string[] {
  return options.includes(value) ? options : [value, ...options];
}

function draftFor(invoice: DocumentInvoice): Draft {
  return {
    invoice_type: invoice?.invoice_type || "UNKNOWN",
    expense_category: invoice?.expense_category || "OTHER",
    total_amount: invoice?.total_amount?.toString() || "",
    confirmed_amount: invoice?.confirmed_amount?.toString() || "",
    reimbursement_status: invoice?.reimbursement_status || "PENDING",
    include_in_summary: invoice?.include_in_summary || false,
    review_status: invoice?.review_status || "NEEDS_REVIEW",
    document_role: invoice?.document_role || "OFFICIAL_INVOICE",
    invoice_number: invoice?.invoice_number || "",
    invoice_date: invoice?.invoice_date || "",
    business_date: invoice?.business_date || "",
    seller_name: invoice?.seller_name || "",
    buyer_name: invoice?.buyer_name || "",
    from_city: invoice?.from_city || "",
    to_city: invoice?.to_city || "",
    from_place: invoice?.from_place || "",
    to_place: invoice?.to_place || "",
    transport_no: invoice?.transport_no || "",
    depart_time_str: invoice?.depart_time_str || "",
    seat_class: invoice?.seat_class || "",
    hotel_name: invoice?.hotel_name || "",
    checkin_date: invoice?.checkin_date || "",
    checkout_date: invoice?.checkout_date || "",
    nights: invoice?.nights?.toString() || "",
    note: invoice?.note || "",
  };
}

export function InvoiceDrawer({ document, invoice, loading, loadError, busy, onClose, onSave }: InvoiceDrawerProps) {
  if (!document) return null;
  if (!document.invoice) {
    return <InvoiceDrawerEmpty document={document} onClose={onClose} message="该文件尚未生成可编辑票据。完成处理后可在此人工复核。" />;
  }
  if (loading) {
    return <InvoiceDrawerEmpty document={document} onClose={onClose} message="正在读取完整票据详情..." />;
  }
  if (loadError || !invoice) {
    return <InvoiceDrawerEmpty document={document} onClose={onClose} message="票据详情暂时无法加载，请关闭后重试。" error />;
  }
  return <InvoiceDrawerForm key={invoice.id} document={document} invoice={invoice} busy={busy} onClose={onClose} onSave={onSave} />;
}

function InvoiceDrawerEmpty({ document, message, error = false, onClose }: { document: DocumentRecord; message: string; error?: boolean; onClose: () => void }) {
  return (
    <aside className="drawer" aria-label="票据人工复核">
      <header className="drawer-header">
        <div><p className="eyebrow">人工复核</p><h2>{document.original_filename}</h2></div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="关闭复核面板" title="关闭"><X size={18} /></button>
      </header>
      <div className={`compact-empty${error ? " error-state" : ""}`}>{message}</div>
    </aside>
  );
}

function InvoiceDrawerForm({ document, invoice, busy, onClose, onSave }: Omit<InvoiceDrawerProps, "document" | "invoice" | "loading" | "loadError"> & { document: DocumentRecord; invoice: DocumentInvoice }) {
  const [draft, setDraft] = useState<Draft>(() => draftFor(invoice));

  function update<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((previous) => ({ ...previous, [key]: value }));
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSave(invoice.id, {
      invoice_type: draft.invoice_type,
      expense_category: draft.expense_category,
      total_amount: draft.total_amount === "" ? null : Number(draft.total_amount),
      confirmed_amount: draft.confirmed_amount === "" ? null : Number(draft.confirmed_amount),
      reimbursement_status: draft.reimbursement_status,
      include_in_summary: draft.include_in_summary,
      review_status: draft.review_status,
      document_role: draft.document_role,
      invoice_number: draft.invoice_number || null,
      invoice_date: draft.invoice_date || null,
      business_date: draft.business_date || null,
      seller_name: draft.seller_name || null,
      buyer_name: draft.buyer_name || null,
      from_city: draft.from_city || null,
      to_city: draft.to_city || null,
      from_place: draft.from_place || null,
      to_place: draft.to_place || null,
      transport_no: draft.transport_no || null,
      depart_time_str: draft.depart_time_str || null,
      seat_class: draft.seat_class || null,
      hotel_name: draft.hotel_name || null,
      checkin_date: draft.checkin_date || null,
      checkout_date: draft.checkout_date || null,
      nights: draft.nights === "" ? null : Number(draft.nights),
      note: draft.note || null,
    });
  }

  return (
    <aside className="drawer" aria-label="票据人工复核">
      <header className="drawer-header">
        <div><p className="eyebrow">人工复核</p><h2>{document.original_filename}</h2></div>
        <button className="icon-button" type="button" onClick={onClose} aria-label="关闭复核面板" title="关闭"><X size={18} /></button>
      </header>
      <form className="drawer-form" onSubmit={submit}>
          <div className="form-grid">
            <label className="field"><span>票据类型</span><select value={draft.invoice_type} onChange={(event) => update("invoice_type", event.target.value)}>{optionsIncluding(draft.invoice_type, invoiceTypeOptions).map((value) => <option key={value} value={value}>{labelForInvoiceType(value)}</option>)}</select></label>
            <label className="field"><span>费用类别</span><select value={draft.expense_category} onChange={(event) => update("expense_category", event.target.value)}>{optionsIncluding(draft.expense_category, expenseCategoryOptions).map((value) => <option key={value} value={value}>{labelForExpenseCategory(value)}</option>)}</select></label>
            <label className="field"><span>识别金额</span><input type="number" min="0" step="0.01" value={draft.total_amount} onChange={(event) => update("total_amount", event.target.value)} /></label>
            <label className="field"><span>确认金额</span><input type="number" min="0" step="0.01" value={draft.confirmed_amount} onChange={(event) => update("confirmed_amount", event.target.value)} /></label>
            <label className="field"><span>报销状态</span><select value={draft.reimbursement_status} onChange={(event) => update("reimbursement_status", event.target.value)}><option value="THIS_TRIP">本次报销</option><option value="ALREADY_REIMBURSED">已报销</option><option value="NOT_REIMBURSED">暂不报销</option><option value="PENDING">待确认</option></select></label>
            <label className="field"><span>凭证角色</span><select value={draft.document_role} onChange={(event) => update("document_role", event.target.value)}><option value="OFFICIAL_INVOICE">正式发票</option><option value="ORDER_SCREENSHOT">订单截图</option><option value="BOOKING_SCREENSHOT">预订截图</option><option value="SUPPORTING_DOC">辅助凭证</option></select></label>
            <label className="field"><span>发票号码</span><input value={draft.invoice_number} onChange={(event) => update("invoice_number", event.target.value)} /></label>
            <label className="field"><span>发票日期</span><input type="date" value={draft.invoice_date} onChange={(event) => update("invoice_date", event.target.value)} /></label>
            <label className="field"><span>业务日期</span><input type="date" value={draft.business_date} onChange={(event) => update("business_date", event.target.value)} /></label>
            <label className="field"><span>销售方</span><input value={draft.seller_name} onChange={(event) => update("seller_name", event.target.value)} /></label>
            <label className="field"><span>购买方</span><input value={draft.buyer_name} onChange={(event) => update("buyer_name", event.target.value)} /></label>
            <label className="field"><span>复核状态</span><select value={draft.review_status} onChange={(event) => update("review_status", event.target.value)}><option value="NEEDS_REVIEW">待复核</option><option value="MANUALLY_CONFIRMED">人工确认</option><option value="REJECTED">已驳回</option></select></label>
            <h3 className="drawer-subheading field-full">交通信息</h3>
            <label className="field"><span>出发城市</span><input value={draft.from_city} onChange={(event) => update("from_city", event.target.value)} /></label>
            <label className="field"><span>到达城市</span><input value={draft.to_city} onChange={(event) => update("to_city", event.target.value)} /></label>
            <label className="field"><span>出发地</span><input value={draft.from_place} onChange={(event) => update("from_place", event.target.value)} /></label>
            <label className="field"><span>到达地</span><input value={draft.to_place} onChange={(event) => update("to_place", event.target.value)} /></label>
            <label className="field"><span>车次或航班号</span><input value={draft.transport_no} onChange={(event) => update("transport_no", event.target.value)} /></label>
            <label className="field"><span>出发时间</span><input value={draft.depart_time_str} onChange={(event) => update("depart_time_str", event.target.value)} placeholder="例如 15:10" /></label>
            <label className="field"><span>席别或舱位</span><input value={draft.seat_class} onChange={(event) => update("seat_class", event.target.value)} /></label>
            <h3 className="drawer-subheading field-full">住宿信息</h3>
            <label className="field"><span>酒店名称</span><input value={draft.hotel_name} onChange={(event) => update("hotel_name", event.target.value)} /></label>
            <label className="field"><span>入住日期</span><input type="date" value={draft.checkin_date} onChange={(event) => update("checkin_date", event.target.value)} /></label>
            <label className="field"><span>离店日期</span><input type="date" value={draft.checkout_date} onChange={(event) => update("checkout_date", event.target.value)} /></label>
            <label className="field"><span>住宿晚数</span><input type="number" min="0" max="366" value={draft.nights} onChange={(event) => update("nights", event.target.value)} /></label>
            <label className="check-field field-full"><input type="checkbox" checked={draft.include_in_summary} onChange={(event) => update("include_in_summary", event.target.checked)} /> 计入本次报销汇总</label>
            <label className="field field-full"><span>备注</span><textarea value={draft.note} onChange={(event) => update("note", event.target.value)} rows={4} /></label>
          </div>
          <footer className="drawer-actions"><button className="button button-secondary" type="button" onClick={onClose}>取消</button><button className="button button-primary" type="submit" disabled={busy}>{busy ? "正在保存" : "保存复核结果"}</button></footer>
      </form>
    </aside>
  );
}
