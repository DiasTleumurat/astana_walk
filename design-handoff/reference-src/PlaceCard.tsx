import { motion } from "motion/react";
import { ArrowUpRight, Clock3, Footprints, MapPin } from "lucide-react";
import type { Place } from "./types";

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
}: {
  place: Place;
  index: number;
  active: boolean;
  onSelect: () => void;
}) {
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
        <ArrowUpRight size={20} />
      </button>
      <div className="place-measures">
        <span>
          <Footprints size={14} /> ≈ {place.walk_minutes} мин в пути
        </span>
        <span>
          <Clock3 size={14} /> {place.visit_minutes} мин на месте
        </span>
      </div>
      <p className="place-reason">{place.reason}</p>
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
