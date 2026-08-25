"""Native administration commands that do not expose an unauthenticated UI flow."""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import func, select

from app.core.security import MIN_PASSWORD_LENGTH, hash_password
from app.infrastructure.db.models import Document, OcrRun, Trip, User
from app.infrastructure.db.session import get_session_factory, init_database
from app.services.recognition import extract_invoice_from_ocr
from app.services.trips import default_settings_for_user, rebuild_trip_projections


def create_account(identifier: str, password: str, *, is_admin: bool) -> int:
    init_database()
    db = get_session_factory()()
    try:
        normalized = identifier.strip().lower()
        if db.scalar(select(User).where(User.email == normalized)):
            print("An account with that identifier already exists.", file=sys.stderr)
            return 1
        user = User(email=normalized, password_hash=hash_password(password), is_admin=is_admin)
        db.add(user)
        db.flush()
        default_settings_for_user(db, user.id)
        db.commit()
        role = "administrator" if is_admin else "user"
        print(f"Created {role}: {normalized}")
        return 0
    finally:
        db.close()


def create_admin(email: str, password: str) -> int:
    return create_account(email, password, is_admin=True)


def create_user(username: str, password: str) -> int:
    return create_account(username, password, is_admin=False)


def reparse_document(document_id: str) -> int:
    """Rebuild one editable invoice projection from its latest durable OCR run."""
    init_database()
    db = get_session_factory()()
    try:
        document = db.get(Document, document_id)
        if not document:
            print("Document not found.", file=sys.stderr)
            return 1
        runs = list(
            db.scalars(
                select(OcrRun)
                .where(OcrRun.document_id == document.id, OcrRun.status == "SUCCEEDED")
                .order_by(OcrRun.created_at.desc())
            )
        )
        ocr_run = next((item for item in runs if item.page_index is None), None) or (runs[0] if runs else None)
        if not ocr_run:
            print("No successful OCR run is available for this document.", file=sys.stderr)
            return 1
        invoice = extract_invoice_from_ocr(db, document, ocr_run)
        if invoice is None:
            print("OCR run contains no parseable text.", file=sys.stderr)
            return 1
        trip = db.get(Trip, invoice.trip_id)
        if trip is None:
            print("Trip not found.", file=sys.stderr)
            return 1
        rebuild_trip_projections(db, trip)
        db.commit()
        print(f"Reparsed document: {document.id}")
        return 0
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Trip Helper native administration")
    subcommands = parser.add_subparsers(dest="command", required=True)
    command = subcommands.add_parser("create-admin", help="create an administrator")
    command.add_argument("--email", "--username", dest="identifier", required=True)
    command.add_argument("--password", help="omit to enter the password without echoing it")
    command = subcommands.add_parser("create-user", help="create a regular isolated user")
    command.add_argument("--username", "--email", dest="identifier", required=True)
    command.add_argument("--password", help="omit to enter the password without echoing it")
    command = subcommands.add_parser("reparse-document", help="rebuild one invoice from its latest OCR run")
    command.add_argument("--document-id", required=True)
    args = parser.parse_args()
    if args.command in {"create-admin", "create-user"}:
        password = args.password or getpass.getpass("Password: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            parser.error(f"password must contain at least {MIN_PASSWORD_LENGTH} characters")
        if args.command == "create-admin":
            return create_admin(args.identifier, password)
        return create_user(args.identifier, password)
    if args.command == "reparse-document":
        return reparse_document(args.document_id)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
