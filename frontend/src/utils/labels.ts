/** Unified Chinese label mappings for all enums used in the UI. */

export const severityLabels: Record<string, string> = {
  INFO: "信息",
  WARNING: "警告",
  ERROR: "错误",
};

export const issueTypeLabels: Record<string, string> = {
  LOW_CONFIDENCE: "识别置信度低",
  MISSING_AMOUNT: "缺少金额",
  INVALID_AMOUNT: "金额异常",
  BUYER_NAME_MISMATCH: "购买方不匹配",
  DATE_OUT_OF_TRIP_RANGE: "日期超出范围",
  CANNOT_INFER_DATES: "无法推断日期",
  MISSING_TRAVEL_DATE: "缺少出行日期",
};

export const scanStatusLabels: Record<string, string> = {
  PENDING: "待处理",
  SCANNED: "已扫描",
  TEXT_EXTRACTED: "已提取文本",
  PREPROCESSED: "已预处理",
  RENDER_FAILED: "渲染失败",
  PREPROCESS_FAILED: "预处理失败",
};

export const ocrStatusLabels: Record<string, string> = {
  PENDING: "待识别",
  PROCESSING: "识别中",
  SUCCESS: "识别成功",
  FAILED: "识别失败",
  SKIPPED: "已跳过",
};

export const invoiceTypeLabels: Record<string, string> = {
  TRAIN_TICKET: "火车票",
  FLIGHT_TICKET: "机票",
  HOTEL_INVOICE: "酒店发票",
  TAXI_INVOICE: "出租车发票",
  RIDE_HAILING_INVOICE: "网约车发票",
  MEAL_INVOICE: "餐饮发票",
  VAT_INVOICE: "增值税发票",
  QUOTA_INVOICE: "定额发票",
  BUS_TICKET: "汽车票",
  OTHER: "其他",
  UNKNOWN: "未知类型",
};

export const expenseCategoryLabels: Record<string, string> = {
  INTERCITY_TRANSPORT: "城际交通",
  LOCAL_TRANSPORT: "市内交通",
  LODGING: "住宿费",
  MEAL: "餐饮费",
  REFUND_CHANGE_FEE: "退票/改签费",
  OTHER: "其他",
};

export const reviewStatusLabels: Record<string, string> = {
  AUTO_CONFIRMED: "自动确认",
  NEEDS_REVIEW: "待复核",
  MANUALLY_CONFIRMED: "人工确认",
  REJECTED: "已驳回",
};

export const tripStatusLabels: Record<string, string> = {
  CREATED: "已创建",
  SCANNED: "已扫描",
  RECOGNIZING: "识别中",
  RECOGNIZED: "已识别",
  ANALYZED: "已分析",
  NEEDS_REVIEW: "需复核",
  FINALIZED: "已确认",
  EXPORTED: "已导出",
};

export const reimbursementLabels: Record<string, string> = {
  NOT_REIMBURSED: "未报销",
  REIMBURSED: "已报销",
  PARTIAL_REIMBURSED: "部分报销",
  NOT_REQUIRED: "无需报销",
};

/** Format a number as currency: ¥1,234.56 */
export function formatMoney(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return "待确认";
  if (!isFinite(value) || Math.abs(value) > 1e10) return "金额异常";
  return "¥" + value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/** Format file size */
export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Truncate text with ellipsis */
export function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, max) + "...";
}