import { describe, expect, it } from "vitest";
import { formatBytes, formatMoney, labelForIssueType, labelForJobKind, labelForReimbursementStatus, labelForState } from "./format";

describe("formatting helpers", () => {
  it("formats known user-facing values without paths or server data", () => {
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatMoney(12.5)).toContain("12.50");
    expect(labelForState("RUNNING")).toBe("处理中");
    expect(labelForState("RECOGNIZED")).toBe("已识别");
    expect(labelForJobKind("PROCESS_DOCUMENT")).toBe("处理文档");
    expect(labelForIssueType("CANNOT_INFER_DATES")).toBe("无法推断出差日期");
    expect(labelForReimbursementStatus("PARTIAL_REIMBURSED")).toBe("部分已报销");
  });
});
