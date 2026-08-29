import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight,
  BriefcaseBusiness,
  CalendarRange,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  FileText,
  LayoutGrid,
  List,
  Plus,
  Search,
  Trash2,
  WalletCards,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { tripsApi } from "../../api/resources";
import type { CreateTripInput, Trip } from "../../api/types";
import { formatDate, formatDateRange, formatMoney, labelForProjectType, labelForReimbursementStatus, labelForState } from "../../lib/format";
import { DeleteTripDialog } from "./DeleteTripDialog";
import { TripFormDialog } from "./TripFormDialog";

const tripListKey = ["trips"] as const;
const PAGE_SIZE = 6;

type ProjectFilter = "ALL" | "ACTIVE" | "COMPLETED";
type ProjectView = "GRID" | "LIST";
type ProjectStatusTone = "active" | "review" | "success" | "danger" | "neutral";

const activeProjectStates = new Set(["PENDING", "QUEUED", "RUNNING", "RETRYING", "PROCESSING", "PREPROCESSING"]);
const reviewProjectStates = new Set(["ANALYZED", "READY_FOR_REVIEW", "NEEDS_REVIEW"]);
const successfulProjectStates = new Set(["FINALIZED", "COMPLETED", "SUCCEEDED"]);
const failedProjectStates = new Set(["FAILED", "CANCELLED"]);

function projectStatusTone(status: string): ProjectStatusTone {
  if (successfulProjectStates.has(status)) return "success";
  if (reviewProjectStates.has(status)) return "review";
  if (failedProjectStates.has(status)) return "danger";
  if (activeProjectStates.has(status)) return "active";
  return "neutral";
}

function isCompletedProject(trip: Trip): boolean {
  return ["FINALIZED", "COMPLETED", "CANCELLED"].includes(trip.status);
}

function matchesProjectFilter(trip: Trip, filter: ProjectFilter): boolean {
  if (filter === "ALL") return true;
  return filter === "COMPLETED" ? isCompletedProject(trip) : !isCompletedProject(trip);
}

function matchesSearch(trip: Trip, query: string): boolean {
  const normalized = query.trim().toLocaleLowerCase("zh-CN");
  if (!normalized) return true;
  return [trip.title, trip.source_label, trip.route_text, trip.traveler_name, trip.company_name]
    .filter((value): value is string => Boolean(value))
    .some((value) => value.toLocaleLowerCase("zh-CN").includes(normalized));
}

export function TripsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [deletingTrip, setDeletingTrip] = useState<Trip | null>(null);
  const [filter, setFilter] = useState<ProjectFilter>("ALL");
  const [query, setQuery] = useState("");
  const [view, setView] = useState<ProjectView>("GRID");
  const [page, setPage] = useState(1);
  const trips = useQuery({ queryKey: tripListKey, queryFn: tripsApi.list });
  const createTrip = useMutation({
    mutationFn: (input: CreateTripInput) => tripsApi.create(input),
    onSuccess: (trip) => {
      queryClient.invalidateQueries({ queryKey: tripListKey });
      setShowCreate(false);
      navigate(`/trips/${trip.id}`);
    },
  });
  const deleteTrip = useMutation({
    mutationFn: (trip: Trip) => tripsApi.remove(trip.id),
    onSuccess: (_, removedTrip) => {
      queryClient.setQueryData<Trip[]>(tripListKey, (current) => current?.filter((trip) => trip.id !== removedTrip.id) ?? []);
      queryClient.removeQueries({ queryKey: ["trip", removedTrip.id] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: tripListKey });
      setDeletingTrip(null);
    },
  });

  function requestDelete(trip: Trip) {
    deleteTrip.reset();
    setDeletingTrip(trip);
  }

  function closeDeleteDialog() {
    if (deleteTrip.isPending) return;
    deleteTrip.reset();
    setDeletingTrip(null);
  }

  const orderedTrips = useMemo(
    () => [...(trips.data || [])].sort((left, right) => right.updated_at.localeCompare(left.updated_at)),
    [trips.data],
  );
  const visibleTrips = useMemo(
    () => orderedTrips.filter((trip) => matchesProjectFilter(trip, filter) && matchesSearch(trip, query)),
    [filter, orderedTrips, query],
  );
  const pageCount = Math.max(1, Math.ceil(visibleTrips.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const paginatedTrips = visibleTrips.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const completedCount = orderedTrips.filter(isCompletedProject).length;
  const activeCount = orderedTrips.length - completedCount;
  const reviewCount = orderedTrips.reduce((total, trip) => total + (trip.summary?.review_count || 0) + (trip.summary?.issue_count || 0), 0);
  const projectTotal = orderedTrips.reduce((total, trip) => total + (trip.summary?.grand_total_amount || 0), 0);

  return (
    <section className="page projects-page">
      <header className="projects-hero">
        <div className="projects-hero-copy">
          <p className="projects-breadcrumb"><span>工作台</span><span aria-hidden="true">/</span><strong>报销项目管理</strong></p>
          <h1>报销项目</h1>
          <p>票据、处理任务与导出结果均按当前账号隔离保存。</p>
        </div>
        <div className="projects-hero-actions">
          <div className="project-kpi-strip" aria-label="项目概览">
            <div><span className="project-kpi-icon"><BriefcaseBusiness size={16} aria-hidden="true" /></span><p>累计项目<strong>{orderedTrips.length} 个</strong></p></div>
            <div><span className="project-kpi-icon project-kpi-icon-money"><WalletCards size={16} aria-hidden="true" /></span><p>项目合计<strong>{formatMoney(projectTotal)}</strong></p></div>
            <div><span className="project-kpi-icon project-kpi-icon-review"><CircleAlert size={16} aria-hidden="true" /></span><p>待处理<strong>{reviewCount} 项</strong></p></div>
          </div>
          <button className="button button-primary project-create-button" type="button" onClick={() => setShowCreate(true)}>
          <Plus size={17} /> 新建项目
          </button>
        </div>
      </header>

      {trips.isPending && (
        <div className="project-skeleton-grid" role="status" aria-label="正在加载项目">
          <span className="visually-hidden">正在加载项目...</span>
          {Array.from({ length: PAGE_SIZE }, (_, index) => (
            <div className="project-skeleton-card" aria-hidden="true" key={index}>
              <span className="project-skeleton-line project-skeleton-badge" />
              <span className="project-skeleton-line project-skeleton-title" />
              <span className="project-skeleton-line project-skeleton-copy" />
              <span className="project-skeleton-metrics" />
              <span className="project-skeleton-line project-skeleton-footer" />
            </div>
          ))}
        </div>
      )}
      {trips.error && (
        <div className="empty-state error-state">
          <CircleAlert size={20} />
          <span>项目列表加载失败。</span>
          <button className="button button-secondary" type="button" onClick={() => void trips.refetch()}>重试</button>
        </div>
      )}
      {trips.data && trips.data.length === 0 && (
        <div className="empty-state empty-projects">
          <FileText size={28} />
          <h2>还没有项目</h2>
          <p>创建项目后，可直接选择或拖入 PDF、JPG、PNG 文件。</p>
          <button className="button button-primary" type="button" onClick={() => setShowCreate(true)}><Plus size={17} /> 新建项目</button>
        </div>
      )}
      {trips.data && trips.data.length > 0 && (
        <>
          <section className="projects-toolbar" aria-label="项目筛选与视图">
            <div className="project-filter-tabs" role="tablist" aria-label="项目状态">
              <button className={filter === "ALL" ? "active" : ""} type="button" role="tab" aria-selected={filter === "ALL"} onClick={() => { setFilter("ALL"); setPage(1); }}>全部 <span>{orderedTrips.length}</span></button>
              <button className={filter === "ACTIVE" ? "active" : ""} type="button" role="tab" aria-selected={filter === "ACTIVE"} onClick={() => { setFilter("ACTIVE"); setPage(1); }}>进行中 <span>{activeCount}</span></button>
              <button className={filter === "COMPLETED" ? "active" : ""} type="button" role="tab" aria-selected={filter === "COMPLETED"} onClick={() => { setFilter("COMPLETED"); setPage(1); }}>已完结 <span>{completedCount}</span></button>
            </div>
            <div className="projects-toolbar-tools">
              <label className="project-search"><Search size={15} aria-hidden="true" /><span className="visually-hidden">搜索项目</span><input aria-label="搜索项目" value={query} onChange={(event) => { setQuery(event.target.value); setPage(1); }} placeholder="搜索项目名称或地点..." /></label>
              <div className="project-view-switch" role="group" aria-label="项目展示方式">
                <button className={view === "GRID" ? "active" : ""} type="button" onClick={() => setView("GRID")} aria-label="网格视图" aria-pressed={view === "GRID"} title="网格视图"><LayoutGrid size={16} /></button>
                <button className={view === "LIST" ? "active" : ""} type="button" onClick={() => setView("LIST")} aria-label="列表视图" aria-pressed={view === "LIST"} title="列表视图"><List size={16} /></button>
              </div>
            </div>
          </section>

          {visibleTrips.length === 0 ? <div className="empty-state project-search-empty"><Search size={21} /><div><strong>没有匹配的项目</strong><span>调整搜索词或切换项目状态后重试。</span></div></div> : (
            <div className={`trip-grid projects-results projects-results-${view.toLowerCase()}`}>
              {paginatedTrips.map((trip) => <TripCard key={trip.id} trip={trip} view={view} onOpen={() => navigate(`/trips/${trip.id}`)} onDelete={() => requestDelete(trip)} />)}
            </div>
          )}

          <footer className="projects-pagination" aria-label="项目分页">
            <span>显示第 {visibleTrips.length === 0 ? 0 : ((currentPage - 1) * PAGE_SIZE) + 1} 至 {Math.min(currentPage * PAGE_SIZE, visibleTrips.length)} 条，共 {visibleTrips.length} 个项目</span>
            <div>
              <button className="icon-button" type="button" aria-label="上一页" title="上一页" disabled={currentPage === 1} onClick={() => setPage((previous) => Math.max(1, previous - 1))}><ChevronLeft size={16} /></button>
              <span className="projects-page-indicator">{currentPage} / {pageCount}</span>
              <button className="icon-button" type="button" aria-label="下一页" title="下一页" disabled={currentPage === pageCount} onClick={() => setPage((previous) => Math.min(pageCount, previous + 1))}><ChevronRight size={16} /></button>
            </div>
          </footer>
        </>
      )}

      {createTrip.error && <p className="form-error" role="alert">项目未能创建，请重试。</p>}
      <TripFormDialog open={showCreate} busy={createTrip.isPending} onClose={() => setShowCreate(false)} onSubmit={(input) => createTrip.mutate(input)} />
      <DeleteTripDialog trip={deletingTrip} busy={deleteTrip.isPending} error={Boolean(deleteTrip.error)} onClose={closeDeleteDialog} onConfirm={() => { if (deletingTrip) deleteTrip.mutate(deletingTrip); }} />
    </section>
  );
}

function TripCard({ trip, view, onOpen, onDelete }: { trip: Trip; view: ProjectView; onOpen: () => void; onDelete: () => void }) {
  const summary = trip.summary;
  const statusTone = projectStatusTone(trip.status);
  return (
    <article className={`trip-card project-card project-card-${view.toLowerCase()}`}>
      <div className="trip-card-topline">
        <div className="trip-card-badges"><span className={`status-badge project-status project-status-${statusTone}`}>{labelForState(trip.status)}</span><span className="status-badge neutral-badge">{labelForProjectType(trip.project_type)}</span><span className={`project-reimbursement-state project-reimbursement-${trip.reimbursement_status.toLowerCase()}`}>{labelForReimbursementStatus(trip.reimbursement_status)}</span></div>
        <div className="trip-card-meta-actions">
          <time dateTime={trip.updated_at}>更新于 {formatDate(trip.updated_at)}</time>
          <button className="icon-button danger-button trip-delete-button" type="button" onClick={onDelete} aria-label={`删除项目：${trip.title}`} title="删除项目"><Trash2 size={15} /></button>
        </div>
      </div>
      <h2>{trip.title}</h2>
      <p className="trip-source">{trip.route_text || trip.source_label || "路线与来源待补充"}</p>
      <dl className="trip-metrics">
        <div><dt>文件</dt><dd>{summary?.document_count ?? 0}</dd></div>
        <div><dt>待复核</dt><dd>{summary?.review_count ?? 0}</dd></div>
        <div><dt>异常</dt><dd className={(summary?.issue_count ?? 0) > 0 ? "metric-warning" : undefined}>{summary?.issue_count ?? 0}</dd></div>
        <div><dt>合计</dt><dd>{formatMoney(summary?.grand_total_amount)}</dd></div>
      </dl>
      <div className="trip-card-footer">
        <span className="trip-card-date"><CalendarRange size={14} aria-hidden="true" /> {formatDateRange(trip.start_date, trip.end_date)}{trip.trip_days != null ? ` · ${trip.trip_days} 天` : ""}</span>
        <button className="inline-action" type="button" onClick={onOpen}>打开 <ArrowRight size={16} /></button>
      </div>
    </article>
  );
}
