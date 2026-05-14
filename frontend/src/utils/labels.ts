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
  PLATFORM_SELLER_WITH_BOOKING_PROOF: "平台代开发票，已有订单凭证佐证",
  PLATFORM_SELLER_NEEDS_PROOF: "平台代开发票，建议补充订单截图",
  FLIGHT_ORDER_MATCHED_INVOICE: "机票订单已关联正式发票",
  FLIGHT_CLOSED_WITH_ANCILLARY: "机票已闭环，订单含保险/附加服务",
  FLIGHT_ORDER_ONLY: "只有机票订单截图，缺少正式发票",
  FLIGHT_INVOICE_ONLY: "只有机票发票，缺少订单截图",
  AMOUNT_RECONCILIATION_NEEDED: "订单金额与发票金额差异需核对",
  FLIGHT_DATE_CONFLICT: "航班日期冲突",
  FLIGHT_NO_CONFLICT: "航班号冲突",
  SUPPORTING_DOC_ONLY: "只有订单截图，缺少正式发票",
  LODGING_AMOUNT_CONFLICT: "订单金额与发票金额不一致",
  LODGING_DATE_CONFLICT: "住宿日期冲突",
  LODGING_NIGHTS_INSUFFICIENT: "住宿晚数可能不足",
  LODGING_NIGHTS_EXCEEDED: "住宿晚数超过出差晚数",
  LODGING_NIGHTS_MISSING: "住宿晚数未识别",
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
  FLIGHT_ORDER_PROOF: "机票订单凭证",
  PLATFORM_FLIGHT_INVOICE: "平台代订机票发票",
  HOTEL_INVOICE: "酒店发票",
  PLATFORM_HOTEL_INVOICE: "平台代订住宿发票",
  HOTEL_BOOKING_PROOF: "酒店订单凭证",
  TAXI_INVOICE: "出租车发票",
  RIDE_HAILING_INVOICE: "网约车发票",
  MEAL_INVOICE: "餐饮发票",
  VAT_INVOICE: "增值税发票",
  QUOTA_INVOICE: "定额发票",
  BUS_TICKET: "汽车票",
  OTHER: "其他",
  UNKNOWN: "未知类型",
};

export const documentRoleLabels: Record<string, string> = {
  OFFICIAL_INVOICE: "正式发票",
  ORDER_SCREENSHOT: "订单截图",
  BOOKING_SCREENSHOT: "预订截图",
  PAYMENT_PROOF: "付款凭证",
  SUPPORTING_DOC: "辅助凭证",
  UNKNOWN: "未知",
};

export const lodgingStatusLabels: Record<string, string> = {
  CLOSED: "已闭环",
  CLOSED_WITH_INSURANCE: "已闭环，含出行保险",
  CLOSED_WITH_ANCILLARY: "已闭环，含附加服务",
  SUPPORTING_ONLY: "仅有辅助凭证",
  INVOICE_ONLY: "仅有正式发票",
  AMOUNT_CONFLICT: "金额不一致",
  DATE_CONFLICT: "日期冲突",
  NEEDS_REVIEW: "需复核",
  ORDER_ONLY: "仅有订单截图",
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