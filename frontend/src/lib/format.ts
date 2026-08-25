export function formatMoney(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    minimumFractionDigits: 2,
  }).format(value);
}

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "-";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium" }).format(date);
}

export function formatDateRange(start: string | null | undefined, end: string | null | undefined): string {
  if (!start && !end) return "日期待确认";
  if (!start || !end) return formatDate(start || end);
  return `${formatDate(start)} 至 ${formatDate(end)}`;
}

export function labelForProjectType(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    TRAVEL: "出差报销",
    DAILY: "日常票据",
    MIXED: "综合项目",
  };
  return labels[value || ""] || value || "-";
}

export function labelForInvoiceType(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    GENERAL_INVOICE: "通用发票",
    VAT_INVOICE: "增值税发票",
    TRAIN_TICKET: "火车票",
    FLIGHT_TICKET: "机票",
    HOTEL_INVOICE: "酒店发票",
    TAXI_INVOICE: "出租车票",
    RIDE_HAILING_INVOICE: "网约车票",
    MEAL_INVOICE: "餐饮发票",
    UNKNOWN: "待识别",
  };
  return labels[value || ""] || value || "-";
}

export function labelForDocumentType(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    PDF: "PDF 文档",
    IMAGE: "图片",
    INVOICE: "票据",
  };
  return labels[value || ""] || value || "-";
}

export function labelForExpenseCategory(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    INTERCITY_TRANSPORT: "城际交通",
    LOCAL_TRANSPORT: "市内交通",
    LODGING: "住宿",
    MEAL: "餐饮",
    REFUND_CHANGE_FEE: "退改签",
    TRAVEL_INSURANCE: "出行保险",
    DAILY_GENERAL: "日常费用",
    OTHER: "其他",
  };
  return labels[value || ""] || value || "-";
}

export function labelForReimbursementStatus(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    THIS_TRIP: "本次报销",
    ALREADY_REIMBURSED: "已报销",
    PARTIAL_REIMBURSED: "部分已报销",
    NOT_REIMBURSED: "暂不报销",
    PENDING: "待确认",
  };
  return labels[value || ""] || value || "-";
}

export function labelForState(value: string | null | undefined): string {
  const labels: Record<string, string> = {
    PENDING: "待处理",
    QUEUED: "排队中",
    RUNNING: "处理中",
    SUCCEEDED: "已完成",
    FAILED: "失败",
    CANCELLED: "已取消",
    RETRYING: "重试中",
    UPLOADING: "上传中",
    UPLOADED: "已上传",
    CREATED: "待处理",
    NEEDS_REVIEW: "待复核",
    ANALYZED: "可复核",
    READY_FOR_REVIEW: "待复核",
    FINALIZED: "已完成",
    PREPROCESSING: "预处理中",
    PREPROCESSED: "已预处理",
    RECOGNIZED: "已识别",
    PROCESSING: "处理中",
    OCR_PENDING: "等待识别",
    OCR_RUNNING: "识别中",
    OCR_SUCCEEDED: "识别完成",
    OCR_FAILED: "识别失败",
    THIS_TRIP: "本次报销",
    ALREADY_REIMBURSED: "已报销",
    NOT_REIMBURSED: "暂不报销",
    MANUALLY_CONFIRMED: "人工确认",
    REJECTED: "已驳回",
    OPEN: "待处理",
    RESOLVED: "已解决",
    IGNORED: "已忽略",
    AUTO_CLEARED: "自动关闭",
  };
  return labels[value || ""] || value || "-";
}

export function labelForJobKind(value: string): string {
  const labels: Record<string, string> = {
    PROCESS_DOCUMENT: "处理文档",
    REPROCESS_DOCUMENT: "重新处理文档",
    FULL_ANALYSIS: "分析全部文档",
    EXPORT_XLSX: "导出 Excel",
    EXPORT_PDF: "导出 PDF",
  };
  return labels[value] || value.replaceAll("_", " ");
}

export function labelForIssueType(value: string): string {
  const labels: Record<string, string> = {
    LOW_CONFIDENCE: "识别置信度较低",
    MISSING_AMOUNT: "缺少有效金额",
    INVALID_AMOUNT: "识别金额异常",
    CANNOT_INFER_DATES: "无法推断出差日期",
  };
  return labels[value] || value;
}
