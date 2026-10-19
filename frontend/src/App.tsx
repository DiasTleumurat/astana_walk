import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, MotionConfig } from "motion/react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  Coffee,
  Footprints,
  Info,
  LocateFixed,
  MapPin,
  Navigation,
  SlidersHorizontal,
  Sparkles,
  Trees,
  Users,
  X,
} from "lucide-react";
import WalkMap from "./WalkMap";
import PlaceCard, { dateLabel } from "./PlaceCard";
import type { Category, Dataset, Point, Result } from "./types";

const PRESETS: Point[] = [
  { label: "Ботанический сад", latitude: 51.1061652, longitude: 71.4165705 },
  { label: "Левый берег · центр", latitude: 51.1282, longitude: 71.4304 },
  { label: "Район EXPO", latitude: 51.0895, longitude: 71.4115 },
  { label: "Национальный музей", latitude: 51.1182297, longitude: 71.4693823 },
];
const SCENARIOS = [
  {
    label: "Прогуляться",
    icon: Trees,
    query: "Хочу неспешно погулять в парке и посмотреть город",
    interests: [] as Category[],
    child: false,
  },
  {
    label: "Кофе рядом",
    icon: Coffee,
    query: "Хочу выпить кофе недалеко от меня",
    interests: ["cafe"] as Category[],
    child: false,
  },
  {
    label: "С ребёнком",
    icon: Users,
    query: "Ищу парк или детскую площадку для прогулки с ребёнком",
    interests: [] as Category[],
    child: true,
  },
];
const INITIAL_QUERY = SCENARIOS[0].query;
const EMPTY_PLACES: Result["recommendations"] = [];

export default function App() {
  const [point, setPoint] = useState<Point>(PRESETS[0]);
  const [query, setQuery] = useState(INITIAL_QUERY);
  const [minutes, setMinutes] = useState(60);
  const [radius, setRadius] = useState(2500);
  const [interests, setInterests] = useState<Category[]>([]);
  const [child, setChild] = useState(false);
  const [accessible, setAccessible] = useState(false);
  const [openNow, setOpenNow] = useState(false);
  const [sockets, setSockets] = useState(false);
  const [roundTrip, setRoundTrip] = useState(false);
  const [filters, setFilters] = useState(false);
  const [about, setAbout] = useState(false);
  const [picking, setPicking] = useState(false);
  const [geoStatus, setGeoStatus] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [resultPoint, setResultPoint] = useState<Point>(PRESETS[0]);
  const [active, setActive] = useState<string | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dirty, setDirty] = useState(false);
  const [mobileView, setMobileView] = useState<"list" | "map">("list");
  const [customLat, setCustomLat] = useState("51.1061652");
  const [customLon, setCustomLon] = useState("71.4165705");
  const controller = useRef<AbortController | null>(null);
  const revision = useRef(0);
  const resultHeading = useRef<HTMLHeadingElement>(null);

  function changed() {
    revision.current++;
    setDirty(true);
  }
  function choosePoint(p: Point) {
    changed();
    setPoint(p);
    setCustomLat(String(p.latitude));
    setCustomLon(String(p.longitude));
    setPicking(false);
  }
  async function findPlaces(initial = false) {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    const requestRevision = revision.current;
    setLoading(true);
    setError("");
    const timer = setTimeout(() => abort.abort("timeout"), 23000);
    try {
      const response = await fetch("/api/recommendations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abort.signal,
        body: JSON.stringify({
          query,
          latitude: point.latitude,
          longitude: point.longitude,
          minutes,
          radius_m: radius,
          interests,
          with_child: child,
          accessible_only: accessible,
          open_now: openNow,
          sockets_required: sockets,
          return_to_start: roundTrip,
        }),
      });
      if (!response.ok)
        throw new Error(
          response.status === 429
            ? "Слишком много запросов. Подождите минуту и попробуйте снова."
            : "Не удалось подобрать места. Проверьте соединение и попробуйте снова.",
        );
      const data: Result = await response.json();
      if (controller.current !== abort) return;
      setResult(data);
      setResultPoint(point);
      setActive(data.recommendations[0]?.poi_id || null);
      setDirty(revision.current !== requestRevision);
      if (!initial) {
        setMobileView("list");
        setTimeout(
          () => resultHeading.current?.focus({ preventScroll: true }),
          50,
        );
      }
    } catch (err) {
      if (controller.current !== abort) return;
      if (!abort.signal.aborted || abort.signal.reason === "timeout")
        setError(
          err instanceof Error && !abort.signal.aborted
            ? err.message
            : "Подбор занял слишком много времени. Попробуйте ещё раз.",
        );
    } finally {
      clearTimeout(timer);
      if (controller.current === abort) setLoading(false);
    }
  }
  useEffect(() => {
    fetch("/api/dataset/status")
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then(setDataset)
      .catch(() => {});
    void findPlaces(true);
    return () => controller.current?.abort();
    // Initial example runs once; subsequent changes are submitted explicitly.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function locate() {
    if (!navigator.geolocation) {
      setGeoStatus("Геолокация недоступна. Выберите точку на карте.");
      return;
    }
    setGeoStatus("Определяем местоположение…");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        choosePoint({
          label: "Моё местоположение",
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
        setGeoStatus("Точка выбрана. Координаты не сохраняются.");
      },
      () =>
        setGeoStatus(
          "Не удалось получить геолокацию. Выберите район или точку на карте.",
        ),
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 0 },
    );
  }
  function applyScenario(index: number) {
    const scenario = SCENARIOS[index];
    setQuery(scenario.query);
    setInterests(scenario.interests);
    setChild(scenario.child);
    setSockets(false);
    changed();
  }
  const places = result?.recommendations || EMPTY_PLACES;
  const selected = places.find((p) => p.poi_id === active);
  const filterCount =
    Number(child) +
    Number(accessible) +
    Number(openNow) +
    Number(sockets) +
    Number(roundTrip) +
    interests.length;
  return (
    <MotionConfig reducedMotion="user">
      <div className="app">
        <header className="header">
          <a className="brand" href="/" aria-label="Astana Walk — главная">
            <img src="/mark.svg" alt="" />
            <span>
              astana<span className="brand-light">walk</span>
            </span>
          </a>
          <div className="header-right">
            <span className="city-label">Город ближе, чем кажется</span>
            <button
              className="about-button"
              aria-expanded={about}
              onClick={() => setAbout(!about)}
            >
              <Info size={17} />
              <span>О проекте</span>
            </button>
          </div>
        </header>
        <AnimatePresence>
          {about && (
            <motion.section
              className="about-panel"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.2 }}
            >
              <div>
                <div className="section-title">
                  <h2>Прогулка с опорой на данные</h2>
                  <button
                    className="icon-button"
                    aria-label="Закрыть описание проекта"
                    onClick={() => setAbout(false)}
                  >
                    <X size={18} />
                  </button>
                </div>
                <p>
                  Находим места в OpenStreetMap, учитываем ваши условия и
                  объясняем выбор. Время в пути — оценка по расстоянию, а не
                  проверенный пешеходный маршрут.
                </p>
                <p>
                  Точные координаты и тексты запросов не сохраняются. Карта по
                  умолчанию загружается с этого приложения. Часы работы,
                  доступность и удобства показываем только при наличии данных.
                </p>
                <p>
                  {dataset
                    ? `${dataset.count} мест · снимок от ${dateLabel(dataset.collected_at)}.`
                    : "Информация о датасете появится после подключения к серверу."}{" "}
                  {dataset?.retrieval_mode === "hybrid"
                    ? "Используется мультиязычный семантический поиск."
                    : "Используется резервный поиск по словам."}{" "}
                  Без ключа Gemini объяснения составляются из проверенных
                  шаблонов.
                </p>
              </div>
            </motion.section>
          )}
        </AnimatePresence>
        <main>
          <div className="intro">
            <div>
              <h1>Куда пойдём в Астане?</h1>
              <p>Найдите время для города. Мы подберём места рядом.</p>
            </div>
            <div className="intro-mark">
              <Footprints size={22} />
              <span>
                Ваш темп.
                <br />
                Ваша прогулка.
              </span>
            </div>
          </div>
          <div className="workspace">
            <div className="left-column">
              <form
                className="planner"
                onSubmit={(e) => {
                  e.preventDefault();
                  void findPlaces();
                }}
              >
                <div className="section-title">
                  <h2>Ваша прогулка</h2>
                  <span className="small-label">Пешком</span>
                </div>
                <div className="location-row">
                  <MapPin size={18} />
                  <label className="sr-only" htmlFor="start">
                    Откуда начнём
                  </label>
                  <select
                    id="start"
                    value={
                      PRESETS.some((p) => p.label === point.label)
                        ? point.label
                        : "custom"
                    }
                    onChange={(e) => {
                      const p = PRESETS.find((p) => p.label === e.target.value);
                      if (p) choosePoint(p);
                    }}
                  >
                    {PRESETS.map((p) => (
                      <option key={p.label}>{p.label}</option>
                    ))}
                    {!PRESETS.some((p) => p.label === point.label) && (
                      <option value="custom">{point.label}</option>
                    )}
                  </select>
                  <button
                    type="button"
                    className="icon-button"
                    title="Моё местоположение"
                    aria-label="Моё местоположение"
                    onClick={locate}
                  >
                    <LocateFixed size={18} />
                  </button>
                </div>
                <div className="location-actions">
                  <button
                    type="button"
                    className="text-button"
                    aria-pressed={picking}
                    onClick={() => {
                      setPicking(!picking);
                      setMobileView("map");
                    }}
                  >
                    {picking ? "Отменить выбор точки" : "Выбрать на карте"}
                    <ArrowRight size={13} />
                  </button>
                  <details className="coordinates">
                    <summary>Координаты</summary>
                    <div>
                      <label>
                        Широта
                        <input
                          type="number"
                          step="any"
                          min="-90"
                          max="90"
                          value={customLat}
                          onChange={(e) => setCustomLat(e.target.value)}
                        />
                      </label>
                      <label>
                        Долгота
                        <input
                          type="number"
                          step="any"
                          min="-180"
                          max="180"
                          value={customLon}
                          onChange={(e) => setCustomLon(e.target.value)}
                        />
                      </label>
                      <button
                        type="button"
                        onClick={() => {
                          const lat = Number(customLat),
                            lon = Number(customLon);
                          if (
                            customLat.trim() &&
                            customLon.trim() &&
                            Number.isFinite(lat) &&
                            Number.isFinite(lon) &&
                            Math.abs(lat) <= 90 &&
                            Math.abs(lon) <= 180
                          ) {
                            choosePoint({
                              label: "Моя точка",
                              latitude: lat,
                              longitude: lon,
                            });
                            setGeoStatus("Координаты применены.");
                          } else setGeoStatus("Введите корректные координаты.");
                        }}
                      >
                        Применить
                      </button>
                    </div>
                  </details>
                </div>
                {geoStatus && (
                  <p className="status-text" role="status">
                    {geoStatus}
                  </p>
                )}
                <label className="field-label" htmlFor="wish">
                  Что вам сейчас хочется?
                </label>
                <textarea
                  id="wish"
                  value={query}
                  maxLength={600}
                  rows={2}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    changed();
                  }}
                  placeholder="Например, кофе и немного архитектуры"
                />
                <div className="scenario-row">
                  {SCENARIOS.map((s, i) => (
                    <button
                      key={s.label}
                      type="button"
                      className={
                        query === s.query ? "scenario selected" : "scenario"
                      }
                      aria-pressed={query === s.query}
                      onClick={() => applyScenario(i)}
                    >
                      <s.icon size={15} />
                      {s.label}
                    </button>
                  ))}
                </div>
                <fieldset className="time-field">
                  <legend>Сколько у вас времени?</legend>
                  <div className="time-options">
                    {[30, 60, 90, 120].map((t) => (
                      <button
                        type="button"
                        key={t}
                        aria-pressed={minutes === t}
                        className={minutes === t ? "selected" : ""}
                        onClick={() => {
                          setMinutes(t);
                          changed();
                        }}
                      >
                        {t === 120 ? "2 часа" : `${t} мин`}
                      </button>
                    ))}
                  </div>
                </fieldset>
                <button
                  type="button"
                  className="filter-toggle"
                  aria-expanded={filters}
                  onClick={() => setFilters(!filters)}
                >
                  <span>
                    <SlidersHorizontal size={16} />
                    Ещё пожелания
                    {filterCount > 0 && (
                      <span className="filter-count">{filterCount}</span>
                    )}
                  </span>
                  <ChevronDown size={16} className={filters ? "rotated" : ""} />
                </button>
                <AnimatePresence>
                  {filters && (
                    <motion.div
                      className="filters"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <div className="radius-label">
                        <label htmlFor="radius">Радиус поиска</label>
                        <output>
                          {(radius / 1000).toLocaleString("ru")} км
                        </output>
                      </div>
                      <input
                        id="radius"
                        type="range"
                        min="500"
                        max="5000"
                        step="500"
                        value={radius}
                        onChange={(e) => {
                          setRadius(Number(e.target.value));
                          changed();
                        }}
                      />
                      <div className="interest-options">
                        {(
                          [
                            ["park", "Парки"],
                            ["cafe", "Кафе"],
                            ["museum", "Музеи"],
                            ["attraction", "Архитектура"],
                          ] as [Category, string][]
                        ).map(([id, label]) => (
                          <button
                            type="button"
                            key={id}
                            aria-pressed={interests.includes(id)}
                            onClick={() => {
                              setInterests(
                                interests.includes(id)
                                  ? interests.filter((x) => x !== id)
                                  : [...interests, id],
                              );
                              changed();
                            }}
                          >
                            {interests.includes(id) && <Check size={13} />}
                            {label}
                          </button>
                        ))}
                      </div>
                      {(
                        [
                          [child, setChild, "С ребёнком"],
                          [
                            openNow,
                            setOpenNow,
                            "Только открытые по расписанию",
                          ],
                          [
                            accessible,
                            setAccessible,
                            "Подтверждённый доступ для коляски",
                          ],
                          [sockets, setSockets, "Подтверждённые розетки"],
                          [
                            roundTrip,
                            setRoundTrip,
                            "Учесть возвращение к старту",
                          ],
                        ] as [boolean, (value: boolean) => void, string][]
                      ).map(([value, setter, label]) => (
                        <label className="check-row" key={label}>
                          <input
                            type="checkbox"
                            checked={value}
                            onChange={(e) => {
                              setter(e.target.checked);
                              changed();
                            }}
                          />
                          {label}
                        </label>
                      ))}
                      <p className="filter-note">
                        Строгие фильтры исключают места без подтверждающих
                        данных.
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
                <motion.button
                  type="submit"
                  className="find-button"
                  whileTap={{ scale: 0.985 }}
                  disabled={loading}
                >
                  <span>
                    {loading ? "Ищем подходящие места…" : "Найти мою прогулку"}
                  </span>
                  {loading ? (
                    <span className="loading-dot" />
                  ) : (
                    <ArrowRight size={19} />
                  )}
                </motion.button>
                <p className="privacy-note">
                  <Check size={12} />
                  Без регистрации. Геолокация не сохраняется.
                </p>
              </form>
              <div
                className="mobile-view"
                role="group"
                aria-label="Вид результатов"
              >
                <button
                  aria-pressed={mobileView === "list"}
                  onClick={() => setMobileView("list")}
                >
                  Места
                </button>
                <button
                  aria-pressed={mobileView === "map"}
                  onClick={() => setMobileView("map")}
                >
                  Карта
                </button>
              </div>
              <section
                className={`results ${mobileView === "map" ? "mobile-hidden" : ""}`}
                aria-busy={loading}
              >
                <div className="results-heading">
                  <h2 ref={resultHeading} tabIndex={-1}>
                    {result?.empty_reason
                      ? "Изменим условия?"
                      : "Места для вашей прогулки"}
                  </h2>
                  <span>
                    {places.length > 0 ? `${places.length} варианта` : ""}
                  </span>
                </div>
                <p className="results-caption">
                  Каждое место — отдельный вариант прогулки.
                </p>
                {dirty && result && (
                  <p className="dirty-note" role="status">
                    Условия изменились. Нажмите «Найти мою прогулку», чтобы
                    обновить места.
                  </p>
                )}
                {error && (
                  <div className="empty-state" role="alert">
                    <h3>Не удалось завершить подбор</h3>
                    <p>{error}</p>
                    <button onClick={() => void findPlaces()}>
                      Попробовать снова <ArrowRight size={15} />
                    </button>
                  </div>
                )}
                {loading && !result && (
                  <div className="skeleton" aria-label="Загрузка рекомендаций">
                    <div />
                    <div />
                    <div />
                  </div>
                )}
                {result?.empty_reason && !error && (
                  <div className="empty-state">
                    <Navigation size={26} />
                    <h3>Не нашлось подходящих мест</h3>
                    <p>{result.empty_reason}</p>
                    <button
                      onClick={() => {
                        setFilters(true);
                        setOpenNow(false);
                        setSockets(false);
                        setAccessible(false);
                        setQuery("Хочу прогуляться рядом");
                        setInterests([]);
                        changed();
                      }}
                    >
                      Упростить пожелания <ArrowRight size={15} />
                    </button>
                  </div>
                )}
                <div className={loading || dirty ? "places stale" : "places"}>
                  {places.map((place, i) => (
                    <PlaceCard
                      key={place.poi_id}
                      place={place}
                      index={i}
                      active={active === place.poi_id}
                      onSelect={() => {
                        setActive(place.poi_id);
                        setMobileView("map");
                      }}
                    />
                  ))}
                </div>
                {result && (
                  <div className="result-notes">
                    <p>
                      <Sparkles size={14} />
                      {result.generation_mode === "llm"
                        ? "Идеи подобраны Gemini по найденным местам"
                        : "Деморежим · объяснения по данным и шаблонам"}
                    </p>
                    {result.warnings.map((w) => (
                      <p key={w}>{w}</p>
                    ))}
                  </div>
                )}
              </section>
            </div>
            <div
              className={`right-column ${mobileView === "list" ? "mobile-hidden" : ""}`}
            >
              <div className="map-sticky">
                <WalkMap
                  point={picking || !result ? point : resultPoint}
                  places={places}
                  active={active}
                  onSelect={setActive}
                  picking={picking}
                  onPick={choosePoint}
                  radius={result?.applied_constraints.radius_m || radius}
                />
                {selected && (
                  <div className="selected-summary">
                    <span className="summary-pin">
                      <MapPin size={17} />
                    </span>
                    <div>
                      <strong>{selected.name}</strong>
                      <span>
                        {selected.distance_m} м по прямой · ≈{" "}
                        {selected.total_minutes} мин с посещением
                      </span>
                    </div>
                    <button
                      className="text-button"
                      onClick={() => {
                        setMobileView("list");
                        const index = places.findIndex(
                          (p) => p.poi_id === active,
                        );
                        setTimeout(
                          () =>
                            document
                              .getElementById(`place-${index}`)
                              ?.scrollIntoView({
                                behavior: window.matchMedia(
                                  "(prefers-reduced-motion: reduce)",
                                ).matches
                                  ? "auto"
                                  : "smooth",
                                block: "center",
                              }),
                          30,
                        );
                      }}
                    >
                      Подробнее
                      <ArrowRight size={14} />
                    </button>
                  </div>
                )}
                <div className="map-footnote">
                  <Footprints size={16} />
                  <p>
                    Расстояния указаны по прямой. Реальный путь может быть
                    длиннее: учитывайте переходы, ограждения и входы.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </main>
        <footer>
          <span>
            astanawalk <span className="footer-dot">·</span> Сделано для
            прогулок
          </span>
          <span>
            {dataset
              ? `${dataset.count} мест из OpenStreetMap`
              : "OpenStreetMap"}
            <span className="footer-dot">·</span>
            <a
              href="https://www.openstreetmap.org/copyright"
              target="_blank"
              rel="noreferrer"
            >
              ODbL
            </a>
          </span>
        </footer>
      </div>
    </MotionConfig>
  );
}
