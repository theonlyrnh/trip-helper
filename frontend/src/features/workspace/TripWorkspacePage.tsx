import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BadgeCheck, CircleAlert, RefreshCw, Trash2 } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { documentsApi, exportsApi, invoicesApi, issuesApi, jobsApi, tripsApi } from "../../api/resources";
import type { DocumentRecord, InvoiceUpdateInput, Trip } from "../../api/types";
import { DeleteTripDialog } from "../trips/DeleteTripDialog";
import { DocumentPreviewDialog } from "./DocumentPreviewDialog";
import { DocumentTable } from "./DocumentTable";
import { ExpenseBreakdown } from "./ExpenseBreakdown";
import { InvoiceDrawer } from "./InvoiceDrawer";
import { IssuePanel } from "./IssuePanel";
import { PixelAssistant } from "./PixelAssistant";
import { ProjectReimbursementDialog } from "./ProjectReimbursementDialog";
import { RouteTimeline } from "./RouteTimeline";
import { TripHeader } from "./TripHeader";
import { UploadPanel } from "./UploadPanel";
import { WorkspaceActions } from "./WorkspaceActions";

function isActive(state: string): boolean {
  return ["PENDING", "QUEUED", "RUNNING", "RETRYING"].includes(state);
}

function adaptivePoll(baseMilliseconds: number, active: boolean, failures: number): number | false {
  if (!active || (typeof document !== "undefined" && document.visibilityState !== "visible")) return false;
  return Math.min(baseMilliseconds * 2 ** Math.min(failures, 4), 30_000);
}

const auxiliaryDocumentRoles = new Set(["ORDER_SCREENSHOT", "BOOKING_SCREENSHOT", "SUPPORTING_DOC"]);

function markDocumentsReimbursed(documents: DocumentRecord[] | undefined): DocumentRecord[] | undefined {
  return documents?.map((document) => {
    if (!document.invoice || auxiliaryDocumentRoles.has(document.invoice.document_role)) return document;
    return {
      ...document,
      invoice: {
        ...document.invoice,
        reimbursement_status: "ALREADY_REIMBURSED",
        include_in_summary: false,
      },
    };
  });
}

export function TripWorkspacePage() {
  const { tripId } = useParams<{ tripId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [previewDocument, setPreviewDocument] = useState<DocumentRecord | null>(null);
  const [editingDocument, setEditingDocument] = useState<DocumentRecord | null>(null);
  const [showDelete, setShowDelete] = useState(false);
  const [showMarkReimbursed, setShowMarkReimbursed] = useState(false);
  const [markReimbursedInvoiceCount, setMarkReimbursedInvoiceCount] = useState(0);
  const validTripId = tripId || "";

  const trip = useQuery({ queryKey: ["trip", validTripId], queryFn: () => tripsApi.get(validTripId), enabled: Boolean(validTripId) });
  const jobs = useQuery({
    queryKey: ["trip", validTripId, "jobs"],
    queryFn: ({ signal }) => jobsApi.list(validTripId, signal),
    enabled: Boolean(validTripId),
    refetchInterval: (query) => adaptivePoll(1_500, Boolean(query.state.data?.some((job) => isActive(job.state))), query.state.fetchFailureCount),
  });
  const hasActiveJobs = jobs.data?.some((job) => isActive(job.state)) || false;
  const documents = useQuery({
    queryKey: ["trip", validTripId, "documents"],
    queryFn: ({ signal }) => documentsApi.list(validTripId, signal),
    enabled: Boolean(validTripId),
    refetchInterval: (query) => adaptivePoll(3_000, hasActiveJobs, query.state.fetchFailureCount),
  });
  const issues = useQuery({
    queryKey: ["trip", validTripId, "issues"],
    queryFn: ({ signal }) => issuesApi.list(validTripId, signal),
    enabled: Boolean(validTripId),
    refetchInterval: (query) => adaptivePoll(3_000, hasActiveJobs, query.state.fetchFailureCount),
  });
  const exports = useQuery({
    queryKey: ["trip", validTripId, "exports"],
    queryFn: ({ signal }) => exportsApi.list(validTripId, signal),
    enabled: Boolean(validTripId),
    refetchInterval: (query) => adaptivePoll(1_500, Boolean(query.state.data?.some((record) => isActive(record.status))), query.state.fetchFailureCount),
  });
  const summary = useQuery({
    queryKey: ["trip", validTripId, "summary"],
    queryFn: ({ signal }) => tripsApi.summary(validTripId, signal),
    enabled: Boolean(validTripId),
    refetchInterval: (query) => adaptivePoll(3_000, hasActiveJobs, query.state.fetchFailureCount),
  });
  const routeSegments = useQuery({
    queryKey: ["trip", validTripId, "route-segments"],
    queryFn: ({ signal }) => tripsApi.routeSegments(validTripId, signal),
    enabled: Boolean(validTripId),
    refetchInterval: (query) => adaptivePoll(3_000, hasActiveJobs, query.state.fetchFailureCount),
  });
  const invoices = useQuery({
    queryKey: ["trip", validTripId, "invoices"],
    queryFn: () => invoicesApi.list(validTripId),
    enabled: Boolean(validTripId && editingDocument?.invoice),
  });

  const refreshWorkspace = useCallback(() => {
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: ["trip", validTripId], exact: true }),
      queryClient.invalidateQueries({ queryKey: ["trip", validTripId, "documents"], exact: true }),
      queryClient.invalidateQueries({ queryKey: ["trip", validTripId, "jobs"], exact: true }),
      queryClient.invalidateQueries({ queryKey: ["trip", validTripId, "issues"], exact: true }),
      queryClient.invalidateQueries({ queryKey: ["trip", validTripId, "exports"], exact: true }),
      queryClient.invalidateQueries({ queryKey: ["trip", validTripId, "summary"], exact: true }),
      queryClient.invalidateQueries({ queryKey: ["trip", validTripId, "route-segments"], exact: true }),
      queryClient.invalidateQueries({ queryKey: ["trip", validTripId, "invoices"], exact: true }),
      queryClient.invalidateQueries({ queryKey: ["trips"], exact: true }),
    ]);
  }, [queryClient, validTripId]);

  const updateInvoice = useMutation({
    mutationFn: ({ invoiceId, input }: { invoiceId: string; input: InvoiceUpdateInput }) => invoicesApi.update(invoiceId, input),
    onSuccess: () => {
      setEditingDocument(null);
      refreshWorkspace();
    },
  });
  const deleteTrip = useMutation({
    mutationFn: () => tripsApi.remove(validTripId),
    onSuccess: () => {
      queryClient.setQueryData<Trip[]>(["trips"], (current) => current?.filter((item) => item.id !== validTripId) ?? []);
      queryClient.removeQueries({ queryKey: ["trip", validTripId] });
      void queryClient.invalidateQueries({ queryKey: ["trips"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      navigate("/trips", { replace: true });
    },
  });
  const markTripReimbursed = useMutation({
    mutationFn: () => tripsApi.markReimbursed(validTripId),
    onMutate: async () => {
      const tripKey = ["trip", validTripId] as const;
      const documentsKey = ["trip", validTripId, "documents"] as const;
      await Promise.all([
        queryClient.cancelQueries({ queryKey: tripKey, exact: true }),
        queryClient.cancelQueries({ queryKey: documentsKey, exact: true }),
      ]);
      const previousTrip = queryClient.getQueryData<Trip>(tripKey);
      const previousDocuments = queryClient.getQueryData<DocumentRecord[]>(documentsKey);
      queryClient.setQueryData<Trip>(tripKey, (current) => current ? { ...current, reimbursement_status: "ALREADY_REIMBURSED" } : current);
      queryClient.setQueryData<DocumentRecord[]>(documentsKey, (current) => markDocumentsReimbursed(current));
      return { previousTrip, previousDocuments };
    },
    onError: (_error, _variables, context) => {
      const tripKey = ["trip", validTripId] as const;
      const documentsKey = ["trip", validTripId, "documents"] as const;
      if (context?.previousTrip) queryClient.setQueryData(tripKey, context.previousTrip);
      if (context?.previousDocuments) queryClient.setQueryData(documentsKey, context.previousDocuments);
    },
    onSuccess: (updatedTrip) => {
      queryClient.setQueryData<Trip>(["trip", validTripId], updatedTrip);
      queryClient.setQueryData<Trip[]>(["trips"], (current) => current?.map((item) => item.id === updatedTrip.id ? updatedTrip : item) ?? []);
      setShowMarkReimbursed(false);
    },
    onSettled: () => {
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ["trip", validTripId], exact: true }),
        queryClient.invalidateQueries({ queryKey: ["trip", validTripId, "documents"], exact: true }),
        queryClient.invalidateQueries({ queryKey: ["trip", validTripId, "summary"], exact: true }),
        queryClient.invalidateQueries({ queryKey: ["trips"], exact: true }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
  });
  const editingInvoice = editingDocument?.invoice
    ? invoices.data?.find((invoice) => invoice.id === editingDocument.invoice?.id) || null
    : null;
  const invoiceLoading = Boolean(editingDocument?.invoice) && (invoices.isPending || (invoices.isFetching && !editingInvoice));
  const reimbursableInvoiceCount = documents.data?.filter((document) => document.invoice
    && !auxiliaryDocumentRoles.has(document.invoice.document_role)
    && document.invoice.reimbursement_status !== "ALREADY_REIMBURSED").length || 0;

  if (!tripId) {
    return <section className="page"><div className="empty-state error-state">项目标识无效。</div></section>;
  }
  if (trip.isPending) return <section className="page"><div className="empty-state">正在加载项目...</div></section>;
  if (trip.error || !trip.data) {
    return (
      <section className="page">
        <Link className="back-link" to="/trips"><ArrowLeft size={16} /> 返回项目列表</Link>
        <div className="empty-state error-state"><CircleAlert size={20} /> 项目无法加载。<button className="button button-secondary" type="button" onClick={() => void trip.refetch()}>重试</button></div>
      </section>
    );
  }

  return (
    <section className="page workspace-page">
      <div className="workspace-toolbar">
        <Link className="back-link" to="/trips"><ArrowLeft size={16} /> 项目列表</Link>
        <div className="workspace-toolbar-actions">
          {trip.data.reimbursement_status !== "ALREADY_REIMBURSED" && <button className="button button-primary workspace-reimburse-button" type="button" disabled={documents.isPending || reimbursableInvoiceCount === 0 || markTripReimbursed.isPending} onClick={() => { markTripReimbursed.reset(); setMarkReimbursedInvoiceCount(reimbursableInvoiceCount); setShowMarkReimbursed(true); }}><BadgeCheck size={16} /> 标记项目已报销</button>}
          <button className="icon-button" type="button" title="刷新项目数据" aria-label="刷新项目数据" onClick={refreshWorkspace}><RefreshCw size={17} /></button>
          <button className="icon-button danger-button" type="button" title="删除项目" aria-label={`删除项目：${trip.data.title}`} onClick={() => { deleteTrip.reset(); setShowDelete(true); }}><Trash2 size={16} /></button>
        </div>
      </div>
      <TripHeader trip={trip.data} expenseSummary={summary.data} summaryLoading={summary.isPending} onChanged={refreshWorkspace} />
      {(documents.error || jobs.error || issues.error || exports.error || summary.error || routeSegments.error) && <p className="form-error" role="alert">部分项目数据暂时无法加载，刷新后可重试。</p>}
      <div className="workspace-content-grid">
        <div className="workspace-main-column">
          <RouteTimeline trip={trip.data} segments={routeSegments.data || []} loading={routeSegments.isPending} />
        </div>
        <aside className="workspace-side-rail" aria-label="项目操作与费用概览">
          <ExpenseBreakdown summary={summary.data} loading={summary.isPending} />
          <PixelAssistant
            activeProcessing={hasActiveJobs}
            issueCount={issues.data?.filter((issue) => !issue.resolved).length || 0}
            documentCount={documents.data?.length || 0}
            segmentCount={routeSegments.data?.length || 0}
            onReviewIssues={() => document.getElementById("issues-title")?.scrollIntoView({ behavior: "smooth", block: "start" })}
          />
        </aside>
        <div className="workspace-action-band">
          <UploadPanel tripId={tripId} onUploaded={refreshWorkspace} />
          <WorkspaceActions tripId={tripId} exports={exports.data || []} documentCount={documents.data?.length || 0} loading={exports.isPending} onChanged={refreshWorkspace} />
        </div>
      </div>
      <DocumentTable tripId={tripId} documents={documents.data || []} loading={documents.isPending} onPreview={setPreviewDocument} onEdit={setEditingDocument} onChanged={refreshWorkspace} />
      <IssuePanel issues={issues.data || []} loading={issues.isPending} onChanged={refreshWorkspace} />
      <DocumentPreviewDialog document={previewDocument} onClose={() => setPreviewDocument(null)} />
      {editingDocument && <div className="drawer-backdrop" role="presentation" onMouseDown={() => setEditingDocument(null)}><div onMouseDown={(event) => event.stopPropagation()}><InvoiceDrawer document={editingDocument} invoice={editingInvoice} loading={invoiceLoading} loadError={Boolean(invoices.error)} busy={updateInvoice.isPending} onClose={() => setEditingDocument(null)} onSave={(invoiceId, input) => updateInvoice.mutate({ invoiceId, input })} /></div></div>}
      <ProjectReimbursementDialog trip={showMarkReimbursed ? trip.data : null} invoiceCount={markReimbursedInvoiceCount} busy={markTripReimbursed.isPending} error={Boolean(markTripReimbursed.error)} onClose={() => { if (!markTripReimbursed.isPending) { markTripReimbursed.reset(); setShowMarkReimbursed(false); } }} onConfirm={() => markTripReimbursed.mutate()} />
      <DeleteTripDialog trip={showDelete ? trip.data : null} busy={deleteTrip.isPending} error={Boolean(deleteTrip.error)} onClose={() => { if (!deleteTrip.isPending) { deleteTrip.reset(); setShowDelete(false); } }} onConfirm={() => deleteTrip.mutate()} />
      {updateInvoice.error && <p className="form-error" role="alert">人工复核结果未能保存，请重试。</p>}
    </section>
  );
}
