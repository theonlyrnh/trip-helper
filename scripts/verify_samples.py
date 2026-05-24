"""Read-only sample verifier for local invoice examples.

This script intentionally does not call PaddleOCR or any remote OCR service.
It only reads a local sample folder and the hand-written 标准.txt baseline,
then prints conservative fields that can be used for manual comparison.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


DEFAULT_SAMPLE_DIR = Path(r"D:\发票")
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


@dataclass
class BaselineRecord:
    line_no: int
    invoice_number: str | None = None
    amount: float | None = None
    travel_date: str | None = None
    depart_time: str | None = None
    from_place: str | None = None
    to_place: str | None = None
    transport_no: str | None = None
    raw_line: str = ""


def parse_baseline_line(line: str, line_no: int) -> BaselineRecord:
    record = BaselineRecord(line_no=line_no, raw_line=line.strip())

    invoice_match = re.search(r"发票号码为\s*([0-9A-Za-z]+)", line)
    if invoice_match:
        record.invoice_number = invoice_match.group(1)

    amount_match = re.search(r"总金额为\s*([0-9]+(?:\.[0-9]{1,2})?)\s*元", line)
    if amount_match:
        record.amount = float(amount_match.group(1))

    datetime_match = re.search(
        r"出发时间为\s*(\d{4})年(\d{1,2})月(\d{1,2})日\s*(\d{1,2}:\d{2})开",
        line,
    )
    if datetime_match:
        year, month, day, depart_time = datetime_match.groups()
        record.travel_date = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        record.depart_time = depart_time

    route_match = re.search(r"，([^，；;]+?)开往([^，；;\s]+)", line)
    if route_match:
        record.from_place = route_match.group(1).strip()
        record.to_place = route_match.group(2).strip()

    transport_match = re.search(r"车次[:：]\s*([A-Z0-9]+)", line)
    if transport_match:
        record.transport_no = transport_match.group(1)

    return record


def read_baseline(path: Path) -> list[BaselineRecord]:
    if not path.exists():
        raise FileNotFoundError(f"未找到基准文件：{path}")

    records: list[BaselineRecord] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        records.append(parse_baseline_line(line, idx))
    return records


def list_sample_files(sample_dir: Path) -> list[dict[str, object]]:
    if not sample_dir.exists():
        raise FileNotFoundError(f"未找到样例目录：{sample_dir}")

    files = []
    for path in sorted(sample_dir.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.name == "标准.txt":
            continue
        files.append({
            "name": path.name,
            "extension": path.suffix.lower(),
            "supported_by_scanner": path.suffix.lower() in SUPPORTED_EXTENSIONS,
            "size_bytes": path.stat().st_size,
        })
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="只读校验 D:\\发票 与 标准.txt 的保守字段。")
    parser.add_argument("--sample-dir", default=str(DEFAULT_SAMPLE_DIR), help="本地发票样例目录，默认 D:\\发票")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出解析结果")
    args = parser.parse_args()

    sample_dir = Path(args.sample_dir)
    baseline_path = sample_dir / "标准.txt"

    files = list_sample_files(sample_dir)
    records = read_baseline(baseline_path)

    payload = {
        "sample_dir": str(sample_dir),
        "baseline_file": str(baseline_path),
        "paddleocr_required": False,
        "sample_files": files,
        "baseline_records": [asdict(record) for record in records],
        "notes": [
            "本脚本只读取样例目录和标准.txt，不删除、不移动、不覆盖原始文件。",
            "本脚本不调用 PaddleOCR，也不要求 PaddleOCR 本地可用。",
            "图片或扫描件如无法通过电子 PDF 文本提取自动识别，应在工作台中人工录入/确认。",
        ],
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"样例目录: {sample_dir}")
    print(f"基准文件: {baseline_path}")
    print("PaddleOCR: 本脚本不要求、不调用")
    print()
    print(f"样例文件数: {len(files)}")
    for file in files:
        supported = "可扫描" if file["supported_by_scanner"] else "不支持"
        print(f"- {file['name']} ({file['extension']}, {file['size_bytes']} bytes, {supported})")
    print()
    print(f"标准.txt 基准记录数: {len(records)}")
    for record in records:
        parts = [f"line={record.line_no}"]
        if record.invoice_number:
            parts.append(f"发票号={record.invoice_number}")
        if record.amount is not None:
            parts.append(f"金额={record.amount:.2f}")
        if record.travel_date:
            parts.append(f"日期={record.travel_date}")
        if record.depart_time:
            parts.append(f"时间={record.depart_time}")
        if record.from_place or record.to_place:
            parts.append(f"路线={record.from_place or '?'}->{record.to_place or '?'}")
        if record.transport_no:
            parts.append(f"车次={record.transport_no}")
        print("- " + " | ".join(parts))
    print()
    print("提示: 对无法自动识别的图片/扫描件，当前无 OCR 环境时需在工作台人工录入或确认。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
