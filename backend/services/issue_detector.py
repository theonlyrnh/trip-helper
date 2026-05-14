"""Issue detector – finds anomalies in invoices and trip data."""

from sqlalchemy.orm import Session

from models.trip import Trip
from models.invoice import Invoice
from models.review_issue import ReviewIssue
from models.app_setting import AppSetting
from enums import IssueSeverity


class IssueDetector:

    @staticmethod
    def detect_all(db: Session, trip: Trip) -> list[ReviewIssue]:
        """Run all detection rules and return created issues."""
        issues: list[ReviewIssue] = []

        # Clear previous auto-generated issues
        db.query(ReviewIssue).filter(
            ReviewIssue.trip_id == trip.id,
            ReviewIssue.auto_generated == True,
        ).delete()
        db.commit()

        # Get settings for company name matching
        setting = db.query(AppSetting).first()

        invoices = (
            db.query(Invoice)
            .filter(Invoice.trip_id == trip.id)
            .all()
        )

        for inv in invoices:
            issues.extend(IssueDetector._check_invoice(inv, trip, setting, db))

        issues.extend(IssueDetector._check_trip(trip, db))

        # Save all issues
        for issue in issues:
            db.add(issue)
        db.commit()

        # Update trip issue count
        trip.issue_count = len(issues)
        db.commit()

        return issues

    @staticmethod
    def _check_invoice(
        inv: Invoice, trip: Trip, setting: AppSetting | None, db: Session
    ) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []

        # Low confidence
        if inv.confidence < 0.7:
            issues.append(
                ReviewIssue(
                    trip_id=trip.id,
                    invoice_id=inv.id,
                    document_id=inv.document_id,
                    issue_type="LOW_CONFIDENCE",
                    severity=IssueSeverity.WARNING,
                    message=f"识别置信度较低 ({inv.confidence:.0%})，请人工复核",
                    suggestion="请手动检查并修正识别结果",
                    auto_generated=True,
                )
            )

        # Missing amount
        amount = inv.confirmed_amount or inv.total_amount
        if amount is None or amount <= 0:
            issues.append(
                ReviewIssue(
                    trip_id=trip.id,
                    invoice_id=inv.id,
                    document_id=inv.document_id,
                    issue_type="MISSING_AMOUNT",
                    severity=IssueSeverity.ERROR,
                    message="未识别到有效金额",
                    suggestion="请手动填写发票金额",
                    auto_generated=True,
                )
            )

        # Invalid amount (too large, likely picked up invoice code)
        if amount is not None and amount > 100000:
            issues.append(
                ReviewIssue(
                    trip_id=trip.id,
                    invoice_id=inv.id,
                    document_id=inv.document_id,
                    issue_type="INVALID_AMOUNT",
                    severity=IssueSeverity.ERROR,
                    message=f"识别金额异常 ({float(amount):.2f})，疑似误识别为发票代码",
                    suggestion="请人工核对并填写正确金额，确认后将不计入汇总",
                    auto_generated=True,
                )
            )

        # Buyer name mismatch
        if (
            setting
            and setting.default_company_name
            and inv.buyer_name
            and setting.default_company_name not in inv.buyer_name
        ):
            issues.append(
                ReviewIssue(
                    trip_id=trip.id,
                    invoice_id=inv.id,
                    document_id=inv.document_id,
                    issue_type="BUYER_NAME_MISMATCH",
                    severity=IssueSeverity.ERROR,
                    message=f"购买方名称与配置公司名称不一致",
                    suggestion=f"期望: {setting.default_company_name}, 实际: {inv.buyer_name}",
                    auto_generated=True,
                )
            )

        # Date out of trip range – skip for refund/change fees (they have different dates)
        if inv.expense_category != "REFUND_CHANGE_FEE":
            trip_start = trip.confirmed_start_date or trip.folder_date_start or trip.inferred_start_date
            trip_end = trip.confirmed_end_date or trip.folder_date_end or trip.inferred_end_date
            if trip_start and trip_end and inv.business_date:
                if inv.business_date < trip_start or inv.business_date > trip_end:
                    issues.append(
                        ReviewIssue(
                            trip_id=trip.id,
                            invoice_id=inv.id,
                            document_id=inv.document_id,
                            issue_type="DATE_OUT_OF_TRIP_RANGE",
                            severity=IssueSeverity.WARNING,
                            message=f"票据日期 ({inv.business_date}) 不在出差日期范围 ({trip_start} ~ {trip_end}) 内",
                            suggestion="请确认该票据是否属于本次出差，或手动调整出差日期",
                            auto_generated=True,
                        )
                    )

        # Missing travel date for transport tickets
        if inv.invoice_type in ("TRAIN_TICKET", "FLIGHT_TICKET") and not inv.business_date:
            issues.append(
                ReviewIssue(
                    trip_id=trip.id,
                    invoice_id=inv.id,
                    document_id=inv.document_id,
                    issue_type="MISSING_TRAVEL_DATE",
                    severity=IssueSeverity.WARNING,
                    message="交通票据缺少日期，无法用于路线和日期推断",
                    suggestion="请手动补充乘车/航班日期",
                    auto_generated=True,
                )
            )

        return issues

    @staticmethod
    def _check_trip(trip: Trip, db: Session) -> list[ReviewIssue]:
        issues: list[ReviewIssue] = []

        # Cannot infer dates
        if not trip.inferred_start_date or not trip.inferred_end_date:
            issues.append(
                ReviewIssue(
                    trip_id=trip.id,
                    issue_type="CANNOT_INFER_DATES",
                    severity=IssueSeverity.WARNING,
                    message="无法自动推断出差日期",
                    suggestion="请手动设置出差起止日期",
                    auto_generated=True,
                )
            )

        return issues