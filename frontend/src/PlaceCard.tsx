import { motion } from "motion/react";
import {
  ArrowUpRight,
  Clock3,
  Footprints,
  MapPin,
  Navigation,
  ShoppingBag,
  Star,
} from "lucide-react";
import type { Place, Point, Rating } from "./types";

const TWOGIS = "https://2gis.kz/astana";
const coord = (lon: number, lat: number) =>
  `${lon.toFixed(6)},${lat.toFixed(6)}`;

type Target = Pick<Place, "poi_id" | "latitude" | "longitude" | "distance_m">;

/** 2GIS web links; on phones they open the 2GIS app when it is installed. */
export function twoGisLinks(place: Target, start?: Point | null) {
  const firm = place.poi_id.match(/^2gis:(\d+)$/)?.[1];
  const dest = coord(place.longitude, place.latitude);
  return {
    open: firm ? `${TWOGIS}/firm/${firm}` : `${TWOGIS}/geo/${dest}`,
    route:
      start && place.distance_m >= 30
        ? `${TWOGIS}/directions/tab/pedestrian/points/${coord(start.longitude, start.latitude)}%7C${dest}`
        : null,
  };
}

const reviewsWord = (n: number) => {
  const tens = n % 100,
    ones = n % 10;
  if (tens >= 11 && tens <= 14) return "отзывов";
  return ones === 1 ? "отзыв" : ones >= 2 && ones <= 4 ? "отзыва" : "отзывов";
};

function RatingBadge({ rating }: { rating: Rating }) {
  const text = (
    <>
      <Star size={13} aria-hidden="true" />
      <b>{rating.value.toFixed(1)}</b>
      {rating.count ? (
        <span>
          · {rating.count} {reviewsWord(rating.count)}
        </span>
      ) : null}
      {rating.source && <span>в {rating.source}</span>}
    </>
  );
  return rating.url ? (
    <a
      className="rating"
      href={rating.url}
      target="_blank"
      rel="noreferrer"
      data-testid="place-rating"
      aria-label={`Рейтинг ${rating.value.toFixed(1)}, читать отзывы в ${rating.source || "источнике"}`}
    >
      {text}
    </a>
  ) : (
    <span className="rating" data-testid="place-rating">
      {text}
    </span>
  );
}

export const dateLabel = (date: string) =>
  new Intl.DateTimeFormat("ru", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "Asia/Almaty",
  }).format(new Date(date));
export default function PlaceCard({
  place,
  index,
  active,
  onSelect,
  start,
}: {
  place: Place;
  index: number;
  active: boolean;
  onSelect: () => void;
  start?: Point | null;
}) {
  const links = twoGisLinks(place, start);
  const stop = place.stop;
  const stopLinks = stop && twoGisLinks(stop, start);
  return (
    <motion.article
      layout="position"
      transition={{ duration: 0.2 }}
      className={`place-card ${active ? "active" : ""}`}
      id={`place-${index}`}
      data-testid="place-card"
    >
      <button
        className="place-heading"
        onClick={onSelect}
        aria-pressed={active}
        aria-label={`Показать на карте: ${place.name}`}
      >
        <span className="place-number">{index + 1}</span>
        <span>
          <h3>{place.name}</h3>
          <span className="place-category">{place.category_label}</span>
        </span>
      </button>
      {place.rating && <RatingBadge rating={place.rating} />}
      <div className="place-measures">
        <span>
          <Footprints size={14} /> ≈ {place.walk_minutes} мин в пути
        </span>
        <span>
          <Clock3 size={14} /> {place.visit_minutes} мин на месте
        </span>
      </div>
      <p className="place-reason">{place.reason}</p>
      {stop && stopLinks && (
        <div className="stop" data-testid="place-stop">
          <span className="stop-title">
            <ShoppingBag size={14} /> По пути · +{stop.extra_minutes} мин
          </span>
          <strong>{stop.name}</strong>
          <span className="stop-meta">
            {stop.category_label}
            {stop.address ? ` · ${stop.address}` : ""}
          </span>
          {stop.rating && <RatingBadge rating={stop.rating} />}
          <div className="place-links">
            <a href={stopLinks.open} target="_blank" rel="noreferrer">
              <MapPin size={14} /> Открыть в 2ГИС
            </a>
            {stopLinks.route && (
              <a href={stopLinks.route} target="_blank" rel="noreferrer">
                <Navigation size={14} /> Маршрут до остановки
              </a>
            )}
          </div>
        </div>
      )}
      <div className="activity">
        <span>Идея для прогулки</span>
        <p>{place.suggested_activity}</p>
      </div>
      <div className="place-bottom">
        <span
          className={`hours ${place.opening_status === "open" ? "open" : ""}`}
        >
          {place.opening_status === "open"
            ? "Открыто по расписанию"
            : "Часы работы не подтверждены"}
        </span>
        <span className="time-total">≈ {place.total_minutes} мин всего</span>
      </div>
      <div className="place-links">
        <a
          href={links.open}
          target="_blank"
          rel="noreferrer"
          data-testid="open-2gis"
        >
          <MapPin size={14} /> Открыть в 2ГИС
        </a>
        {links.route && (
          <a
            href={links.route}
            target="_blank"
            rel="noreferrer"
            data-testid="route-2gis"
          >
            <Navigation size={14} /> Маршрут пешком
          </a>
        )}
      </div>
      <details className="evidence">
        <summary>Данные и источники</summary>
        <div className="evidence-body">
          <p>
            <MapPin size={14} />{" "}
            {place.address || `${place.distance_m} м по прямой от старта`}
          </p>
          <p>{place.description}</p>
          <p>
            Расписание: {place.opening_hours_raw || "нет данных"}. Доступность
            для коляски:{" "}
            {place.wheelchair === true
              ? "да, по данным OSM"
              : place.wheelchair === false
                ? "нет, по данным OSM"
                : "неизвестна"}
            . Розетки:{" "}
            {place.sockets === true ? "есть в источнике" : "не подтверждены"}.
          </p>
          {place.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
          <p>
            Время — оценка приложения. Идея занятия{" "}
            {place.activity_origin === "llm_selected_idea"
              ? "выбрана ИИ"
              : "подготовлена по шаблону"}
            .
          </p>
          {place.sources.map((source) => (
            <a
              key={source.id}
              href={source.url}
              target="_blank"
              rel="noreferrer"
            >
              {source.name} <ArrowUpRight size={13} />
            </a>
          ))}
          <span className="source-date">
            Данные получены {dateLabel(place.collected_at)}
          </span>
        </div>
      </details>
    </motion.article>
  );
}
