import {
  ArrowRight,
  BadgeCheck,
  BusFront,
  CalendarDays,
  CarTaxiFront,
  MapPin,
  MapPinned,
  PlaneTakeoff,
  Sparkles,
  TrainFront,
} from "lucide-react";
import type { RouteSegment, Trip } from "../../api/types";
import { formatDate, formatMoney } from "../../lib/format";

interface RouteTimelineProps {
  trip: Trip;
  segments: RouteSegment[];
  loading: boolean;
}

const transportLabels: Record<string, string> = {
  TRAIN: "铁路",
  FLIGHT: "航班",
  BUS: "客运",
  TAXI: "出租车",
  RIDE_HAILING: "网约车",
};

function placeFor(segment: RouteSegment, side: "from" | "to"): string {
  const place = side === "from" ? segment.from_place : segment.to_place;
  const city = side === "from" ? segment.from_city : segment.to_city;
  return place || city || "待确认";
}

function cityFor(segment: RouteSegment, side: "from" | "to"): string {
  const city = side === "from" ? segment.from_city : segment.to_city;
  return city || placeFor(segment, side);
}

function dateSortValue(value: string | null): string {
  return /^\d{4}-\d{2}-\d{2}$/.test(value || "") ? value! : "9999-12-31";
}

function timeSortValue(value: string | null): number {
  const match = /^(\d{1,2}):(\d{2})$/.exec(value || "");
  if (!match) return Number.POSITIVE_INFINITY;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  return hours < 24 && minutes < 60 ? (hours * 60) + minutes : Number.POSITIVE_INFINITY;
}

function compareSegments(left: RouteSegment, right: RouteSegment): number {
  const dateOrder = dateSortValue(left.depart_date).localeCompare(dateSortValue(right.depart_date));
  if (dateOrder !== 0) return dateOrder;
  const leftTime = timeSortValue(left.depart_time);
  const rightTime = timeSortValue(right.depart_time);
  if (leftTime !== rightTime) return leftTime - rightTime;
  return left.id.localeCompare(right.id);
}

function TransportGlyph({ type }: { type: string }) {
  if (type === "TRAIN") return <TrainFront size={16} aria-hidden="true" />;
  if (type === "FLIGHT") return <PlaneTakeoff size={16} aria-hidden="true" />;
  if (type === "BUS") return <BusFront size={16} aria-hidden="true" />;
  return <CarTaxiFront size={16} aria-hidden="true" />;
}

function routeStops(segments: RouteSegment[]): string[] {
  const stops: string[] = [];
  for (const segment of segments) {
    for (const location of [cityFor(segment, "from"), cityFor(segment, "to")]) {
      if (!stops.length || stops[stops.length - 1] !== location) stops.push(location);
    }
  }
  return stops;
}

export function RouteTimeline({ trip, segments, loading }: RouteTimelineProps) {
  const manuallyConfirmed = Boolean(trip.confirmed_start_date || trip.confirmed_end_date);
  const orderedSegments = [...segments].sort(compareSegments);
  const stops = routeStops(orderedSegments);
  const firstSegment = orderedSegments[0];
  const lastSegment = orderedSegments.at(-1);
  const groupedSegments = new Map<string, RouteSegment[]>();
  for (const segment of orderedSegments) {
    const key = segment.depart_date || "日期待确认";
    groupedSegments.set(key, [...(groupedSegments.get(key) || []), segment]);
  }

  return (
    <section className="workspace-section route-timeline" aria-labelledby="route-title">
      <div className="section-heading route-heading">
        <div>
          <p className="eyebrow">行程</p>
          <h2 id="route-title">交通路线</h2>
        </div>
        {!loading && orderedSegments.length > 0 && <span className="route-ticket-count">{orderedSegments.length} 段交通</span>}
      </div>

      <div className="route-scroll-area">
        {loading && <div className="route-loading">正在整理交通明细...</div>}

        {!loading && orderedSegments.length === 0 && (
          <div className="route-empty">
            <MapPinned size={19} aria-hidden="true" />
            <div><strong>{trip.route_text || "路线待确认"}</strong><span>识别到交通票据后会显示具体起止站点和时间。</span></div>
          </div>
        )}

        {!loading && firstSegment && lastSegment && (
          <>
          <div className="route-journey" aria-label={`交通路线：${stops.join("至")}`}>
            <div className="route-terminal route-terminal-start">
              <span>出发城市</span>
              <strong>{cityFor(firstSegment, "from")}</strong>
              <small><MapPin size={12} aria-hidden="true" /> {placeFor(firstSegment, "from")}</small>
            </div>
            <div className="route-connector" aria-hidden="true">
              <span className="route-connector-line" />
              <span className="route-connector-count">{orderedSegments.length} 段</span>
              <ArrowRight size={18} />
            </div>
            <div className="route-terminal route-terminal-end">
              <span>抵达城市</span>
              <strong>{cityFor(lastSegment, "to")}</strong>
              <small><MapPin size={12} aria-hidden="true" /> {placeFor(lastSegment, "to")}</small>
            </div>
          </div>

          {stops.length > 2 && (
            <ol className="route-stop-list" aria-label="途经城市">
              {stops.map((stop, index) => <li key={`${index}-${stop}`}>{stop}</li>)}
            </ol>
          )}

          <div className="route-detail-row">
            <span className={`date-source ${manuallyConfirmed ? "confirmed" : "inferred"}`}>{manuallyConfirmed ? <BadgeCheck size={14} /> : <Sparkles size={14} />}{manuallyConfirmed ? "日期已确认" : `推断置信度 ${Math.round(trip.date_confidence * 100)}%`}</span>
            <span className="route-evidence"><CalendarDays size={14} aria-hidden="true" /> {formatDate(firstSegment.depart_date)} 至 {formatDate(lastSegment.depart_date)}</span>
            {trip.date_evidence[0] && <span className="route-evidence route-evidence-muted">{trip.date_evidence[0]}</span>}
          </div>

          <ol className="route-day-list" aria-label="交通明细">
            {Array.from(groupedSegments.entries()).map(([date, daySegments]) => (
              <li key={date} className="route-day">
                <div className="route-day-heading">
                  <time dateTime={date === "日期待确认" ? undefined : date}>{formatDate(date === "日期待确认" ? null : date)}</time>
                  <span>{daySegments.length} 段交通</span>
                </div>
                <ol className="route-ticket-list">
                  {daySegments.map((segment) => (
                    <li key={segment.id} className="route-ticket">
                      <time className="route-ticket-time" dateTime={segment.depart_date || undefined}>
                        <strong>{segment.depart_time || "--:--"}</strong>
                        <span>{transportLabels[segment.transport_type] || segment.transport_type}</span>
                      </time>
                      <span className={`route-ticket-icon route-ticket-icon-${segment.transport_type.toLowerCase()}`}><TransportGlyph type={segment.transport_type} /></span>
                      <div className="route-ticket-main">
                        <div className="route-ticket-topline"><strong>{segment.transport_no || "交通编号待确认"}</strong>{segment.seat_class && <span>{segment.seat_class}</span>}</div>
                        <div className="route-place-pair"><strong>{placeFor(segment, "from")}</strong><ArrowRight size={15} aria-hidden="true" /><strong>{placeFor(segment, "to")}</strong></div>
                        <span className="route-city-pair">{cityFor(segment, "from")} 至 {cityFor(segment, "to")}</span>
                      </div>
                      <strong className="route-segment-amount">{formatMoney(segment.amount)}</strong>
                    </li>
                  ))}
                </ol>
              </li>
            ))}
          </ol>
          </>
        )}
      </div>
    </section>
  );
}
