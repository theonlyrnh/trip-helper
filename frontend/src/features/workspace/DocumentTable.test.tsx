import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { invoicesApi } from "../../api/resources";
import type { DocumentInvoice, DocumentRecord } from "../../api/types";
import { DocumentTable } from "./DocumentTable";

const document: DocumentRecord = {
  id: "document-1",
  trip_id: "trip-1",
  original_filename: "train-ticket.pdf",
  relative_path: null,
  size_bytes: 512,
  mime_type: "application/pdf",
  upload_status: "UPLOADED",
  processing_status: "SUCCEEDED",
  ocr_status: "SUCCEEDED",
  document_type: "INVOICE",
  error_code: null,
  error_message: null,
  issue_count: 0,
  created_at: "2026-07-01T00:00:00Z",
  invoice: {
    id: "invoice-1",
    invoice_type: "TRAIN_TICKET",
    expense_category: "INTERCITY_TRANSPORT",
    total_amount: 120,
    confirmed_amount: 120,
    reimbursement_status: "THIS_TRIP",
    include_in_summary: true,
    review_status: "MANUALLY_CONFIRMED",
    document_role: "OFFICIAL_INVOICE",
    invoice_number: null,
    invoice_date: "2026-07-01",
    business_date: "2026-07-01",
    seller_name: null,
    buyer_name: null,
    from_city: "南京",
    to_city: "北京",
    from_place: "南京南",
    to_place: "北京南",
    transport_no: "G123",
    depart_time_str: "08:00",
    seat_class: "二等座",
    hotel_name: null,
    checkin_date: null,
    checkout_date: null,
    nights: null,
    note: null,
  },
};

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((next) => { resolve = next; });
  return { promise, resolve };
}

function TableHarness({ onChanged }: { onChanged: () => void }) {
  const documents = useQuery({
    queryKey: ["trip", "trip-1", "documents"],
    queryFn: async () => [document],
  });
  return <DocumentTable tripId="trip-1" documents={documents.data || []} loading={false} onPreview={vi.fn()} onEdit={vi.fn()} onChanged={onChanged} />;
}

function renderTable(onChanged = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  queryClient.setQueryData(["trip", "trip-1", "documents"], [document]);
  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <TableHarness onChanged={onChanged} />
      </QueryClientProvider>,
    ),
    onChanged,
  };
}

describe("DocumentTable reimbursement updates", () => {
  afterEach(() => vi.restoreAllMocks());

  it("updates the selected reimbursement state before the request returns", async () => {
    const response = deferred<DocumentInvoice>();
    vi.spyOn(invoicesApi, "update").mockReturnValue(response.promise);
    const { onChanged } = renderTable();
    const user = userEvent.setup();

    const status = screen.getByLabelText("train-ticket.pdf 报销状态") as HTMLSelectElement;
    await user.selectOptions(status, "ALREADY_REIMBURSED");

    await waitFor(() => expect(status.value).toBe("ALREADY_REIMBURSED"));
    expect(onChanged).not.toHaveBeenCalled();
    expect(invoicesApi.update).toHaveBeenCalledWith("invoice-1", { reimbursement_status: "ALREADY_REIMBURSED" });

    response.resolve({
      ...document.invoice!,
      reimbursement_status: "ALREADY_REIMBURSED",
      include_in_summary: false,
    });
    await waitFor(() => expect(status.disabled).toBe(false));
  });

  it("keeps processing and OCR status in the file cell for narrow screens", () => {
    const { container } = renderTable();
    const currentTable = within(container);

    expect(currentTable.getByText("处理 已完成")).toBeInTheDocument();
    expect(currentTable.getByText("OCR 已完成")).toBeInTheDocument();
  });

  it("searches file and invoice metadata before applying the table filter", async () => {
    const user = userEvent.setup();
    const hotelDocument: DocumentRecord = {
      ...document,
      id: "document-2",
      original_filename: "hotel-receipt.pdf",
      invoice: { ...document.invoice!, id: "invoice-2", invoice_type: "HOTEL_INVOICE", expense_category: "LODGING", hotel_name: "太原酒店" },
    };
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <DocumentTable tripId="trip-1" documents={[document, hotelDocument]} loading={false} onPreview={vi.fn()} onEdit={vi.fn()} onChanged={vi.fn()} />
      </QueryClientProvider>,
    );

    const currentTable = within(container);
    await user.type(currentTable.getByLabelText("搜索票据"), "hotel");
    expect(currentTable.getByText("hotel-receipt.pdf")).toBeInTheDocument();
    expect(currentTable.queryByText("train-ticket.pdf")).not.toBeInTheDocument();
  });
});
