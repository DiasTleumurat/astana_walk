import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  AnimatePresence,
  motion,
  MotionConfig,
  useSpring,
  useReducedMotion,
} from "motion/react";
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
  Moon,
  Sun,
} from "lucide-react";
import WalkMap from "./WalkMap";
import RadiusControl from "./RadiusControl";
import PlaceCard, { dateLabel } from "./PlaceCard";
import type { Category, Dataset, Point, Result } from "./types";

const PRESETS: Point[] = [
  { label: "Ботанический сад", latitude: 51.1061652, longitude: 71.4165705 },
  { label: "Левый берег · центр", latitude: 51.1282, longitude: 71.4304 },
  { label: "Район EXPO", latitude: 51.0895, longitude: 71.4115 },
  { label: "Национальный музей", latitude: 51.1182297, longitude: 71.4693823 },
  {
    label: "Правый берег · Дворец Жастар",
    latitude: 51.1703258,
    longitude: 71.4269441,
  },
  {
    label: "Правый берег · Пушкинский парк",
    latitude: 51.1594839,
    longitude: 71.46914,
  },
  {
    label: "Правый берег · парк Жеруйык",
    latitude: 51.1455747,
    longitude: 71.4899608,
  },
  {
    label: "Правый берег · парк Журналистов",
    latitude: 51.1673074,
    longitude: 71.4525488,
  },
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
  const [dark, setDark] = useState(() => {
    try {
      const saved = localStorage.getItem("astana-walk-theme");
      if (saved === "dark" || saved === "light") return saved === "dark";
    } catch {
      /* Theme remains available when storage is blocked. */
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });
  useLayoutEffect(() => {
    const theme = dark ? "dark" : "light";
    document.documentElement.dataset.theme = theme;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", dark ? "#181c14" : "#eeeeee");
    try {
      localStorage.setItem("astana-walk-theme", theme);
    } catch {
      /* Optional preference only. */
    }
  }, [dark]);
  const [point, setPoint] = useState<Point>(PRESETS[0]);
  const [query, setQuery] = useState(INITIAL_QUERY);
  const [minutes, setMinutes] = useState(60);
  const [timeEnabled, setTimeEnabled] = useState(true);
  const [radius, setRadius] = useState(2500);
  const animatedRadius = useSpring(2500, {
    stiffness: 260,
    damping: 34,
    mass: 0.6,
  });
  const reducedMotion = useReducedMotion();
  useLayoutEffect(() => {
    if (reducedMotion) animatedRadius.jump(radius);
    else animatedRadius.set(radius);
  }, [radius, animatedRadius, reducedMotion]);
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
  const [locating, setLocating] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
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
    const timer = setTimeout(() => abort.abort("timeout"), 80000);
    try {
      const response = await fetch("/api/recommendations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abort.signal,
        body: JSON.stringify({
          use_ai: !initial,
          limit: initial ? 3 : 12,
          query,
          latitude: point.latitude,
          longitude: point.longitude,
          minutes,
          time_enabled: timeEnabled,
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
    if (locating) return;
    if (!window.isSecureContext) {
      setGeoStatus("Для геолокации откройте сайт по HTTPS или на localhost.");
      return;
    }
    if (!navigator.geolocation) {
      setGeoStatus("Геолокация недоступна. Выберите точку на карте.");
      return;
    }
    setGeoStatus("Определяем местоположение…");
    setLocating(true);
    const locationRevision = revision.current;
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        if (revision.current !== locationRevision) {
          setGeoStatus(
            "Старт уже изменён. Нажмите геолокацию ещё раз при необходимости.",
          );
          return;
        }
        const { latitude, longitude } = position.coords;
        if (
          latitude < 51.02 ||
          latitude > 51.23 ||
          longitude < 71.3 ||
          longitude > 71.6
        ) {
          setGeoStatus(
            "Вы сейчас за пределами поддерживаемой области Астаны. Выберите старт в городе на карте.",
          );
          return;
        }
        choosePoint({
          label: "Моё местоположение",
          latitude,
          longitude,
        });
        setGeoStatus("");
      },
      (error) => {
        setLocating(false);
        if (revision.current !== locationRevision) return;
        setGeoStatus(
          error.code === 1
            ? "Доступ к геолокации запрещён. Разрешите его в настройках сайта и устройства, затем повторите. Можно выбрать точку на карте."
            : error.code === 3
              ? "Определение местоположения заняло слишком много времени. Проверьте GPS и повторите или выберите точку на карте."
              : "Устройство не смогло определить местоположение. Включите службы геолокации или выберите точку на карте.",
        );
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 30000 },
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
            <span className="brand-mark" aria-hidden="true" />
            <span>
              Astana<span className="brand-light">Walk</span>
            </span>
          </a>
          <div className="header-right">
            <span className="city-label">Город ближе, чем кажется</span>
            <button
              className="theme-toggle"
              type="button"
              aria-label={
                dark ? "Включить светлую тему" : "Включить тёмную тему"
              }
              title={dark ? "Светлая тема" : "Тёмная тема"}
              aria-pressed={dark}
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
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
                  Находим места в {dataset?.place_provider || "OpenStreetMap"},
                  учитываем ваши условия и объясняем выбор. Время в пути —
                  оценка по расстоянию, а не проверенный пешеходный маршрут.
                </p>
                <p>
                  Точные координаты и тексты запросов не сохраняются. Подробная
                  карта загружается из OpenStreetMap. Часы работы, доступность и
                  удобства показываем только при наличии данных.
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
                    disabled={locating}
                    aria-busy={locating}
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
                <div className="wish-input">
                  <textarea
                    id="wish"
                    value={query}
                    maxLength={600}
                    rows={2}
                    onChange={(e) => {
                      setQuery(e.target.value);
                      setInterests([]);
                      changed();
                    }}
                    placeholder="Например, кофе и немного архитектуры"
                  />
                  <button
                    type="submit"
                    className="wish-send"
                    aria-label="Отправить запрос"
                    title="Отправить запрос"
                    disabled={loading}
                  >
                    {loading ? (
                      <span className="loading-dot" />
                    ) : (
                      <span className="send-icon" aria-hidden="true" />
                    )}
                  </button>
                </div>
                <RadiusControl
                  radius={radius}
                  animated={animatedRadius}
                  onChange={(next) => {
                    setRadius(next);
                    changed();
                  }}
                />
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
                      <div className="interest-options">
                        {(
                          [
                            ["park", "Парки"],
                            ["cafe", "Кафе"],
                            ["museum", "Музеи"],
                            ["attraction", "Архитектура"],
                            ["computer_club", "Компьютерные клубы"],
                            ["restaurant", "Рестораны"],
                            ["cinema", "Кинотеатры"],
                            ["shopping_mall", "Торговые центры"],
                            ["library", "Библиотеки"],
                            ["fitness", "Спорт"],
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
                <fieldset
                  className={`time-field ${timeEnabled ? "" : "time-disabled"}`}
                >
                  <legend>
                    <span>Сколько у вас времени?</span>
                    <button
                      type="button"
                      role="switch"
                      className="time-toggle"
                      aria-label="Учитывать ограничение по времени"
                      aria-checked={timeEnabled}
                      aria-controls="time-options"
                      onClick={() => {
                        setTimeEnabled(!timeEnabled);
                        changed();
                      }}
                    >
                      <span className="time-toggle-status">
                        {timeEnabled ? "Вкл" : "Выкл"}
                      </span>
                      <span className="time-toggle-track" aria-hidden="true">
                        <span />
                      </span>
                    </button>
                  </legend>
                  <div className="time-options" id="time-options">
                    {[30, 60, 90, 120].map((t) => (
                      <button
                        type="button"
                        key={t}
                        disabled={!timeEnabled}
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
                  {!timeEnabled && (
                    <p className="time-filter-note">
                      Без ограничения по времени. Оценка длительности останется
                      в карточках.
                    </p>
                  )}
                </fieldset>
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
                    <span className="send-icon" aria-hidden="true" />
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
            </div>
            <div
              className={`right-column ${mobileView === "list" && !result?.empty_reason ? "mobile-hidden" : ""}`}
            >
              <div className="map-sticky">
                <WalkMap
                  point={point}
                  places={dirty ? EMPTY_PLACES : places}
                  active={active}
                  onSelect={setActive}
                  picking={picking}
                  onPick={choosePoint}
                  radius={radius}
                  animatedRadius={animatedRadius}
                />
                {result?.checked_at && (
                  <p className="status-text" role="status">
                    Онлайн-поиск выполнен{" "}
                    {new Date(result.checked_at).toLocaleTimeString("ru-RU", {
                      timeZone: "Asia/Almaty",
                    })}{" "}
                    · {result.place_provider || "OpenStreetMap"}
                  </p>
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
              {result?.query_understanding &&
                (result.query_understanding.categories.length > 0 ||
                  result.query_understanding.name) && (
                  <p className="results-caption">
                    По вашему запросу:{" "}
                    {[
                      ...result.query_understanding.categories,
                      result.query_understanding.name,
                      ...result.query_understanding.cuisines,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                    .
                  </p>
                )}
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
              {result?.live_answer && !error && (
                <article
                  className={`live-answer ${loading || dirty ? "stale" : ""}`}
                  aria-label="Ответ Gemini с источниками"
                >
                  <h3>
                    <Sparkles size={17} /> Gemini ·{" "}
                    {result.live_answer.grounding === "web"
                      ? "актуальные предложения"
                      : "идеи для вашей прогулки"}
                  </h3>
                  <p className="live-answer-time">
                    {result.live_answer.grounding === "web"
                      ? "Проверено"
                      : "Ответ получен"}{" "}
                    {new Date(result.live_answer.checked_at).toLocaleString(
                      "ru-RU",
                      { timeZone: "Asia/Almaty" },
                    )}{" "}
                    · время Астаны
                  </p>
                  <div className="live-answer-text">
                    {result.live_answer.segments.map((segment, i) => (
                      <span key={i}>
                        {segment.text}
                        {segment.sources.map((id) => {
                          const source = result.live_answer!.sources[id - 1];
                          return source ? (
                            <sup key={id}>
                              <a
                                href={source.url}
                                target="_blank"
                                rel="noreferrer"
                                aria-label={`Источник ${id}: ${source.title}`}
                              >
                                [{id}]
                              </a>
                            </sup>
                          ) : null;
                        })}
                      </span>
                    ))}
                  </div>
                  <div className="live-sources">
                    {result.live_answer.sources.map((source, i) => (
                      <a
                        key={`${source.url}-${i}`}
                        href={source.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        [{i + 1}] {source.title}
                      </a>
                    ))}
                  </div>
                  {result.live_answer.search_suggestions && (
                    <iframe
                      title="Поисковые подсказки Google"
                      className="google-suggestions"
                      sandbox="allow-popups allow-popups-to-escape-sandbox"
                      referrerPolicy="no-referrer"
                      srcDoc={result.live_answer.search_suggestions}
                    />
                  )}
                  <p className="live-answer-time">
                    {result.live_answer.grounding === "web"
                      ? "Предложения из интернета могут отличаться от каталога на карте."
                      : "Ответ по локальному каталогу. События, цены и часы работы сейчас не проверяются через интернет."}{" "}
                    Перед посещением уточните детали у площадки.
                  </p>
                </article>
              )}
              {loading && !result && (
                <div className="skeleton" aria-label="Загрузка рекомендаций">
                  <div />
                  <div />
                  <div />
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
                    {result.data_mode === "live"
                      ? `Места получены онлайн из ${result.place_provider || "OpenStreetMap"}`
                      : result.live_answer
                        ? "Карточки и карта — из каталога OpenStreetMap"
                        : result.generation_mode === "llm"
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
        </main>
        <footer>
          <span>
            astanawalk <span className="footer-dot">·</span> Сделано для
            прогулок
          </span>
          <span>
            {dataset?.place_provider === "2ГИС"
              ? "Места: 2ГИС · Карта: OpenStreetMap"
              : dataset
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
          <p className="footer-search-note">
            При поиске запрашиваем места в{" "}
            {dataset?.place_provider || "OpenStreetMap"}. Gemini помогает понять
            пожелание. Текст запроса передаётся Google, если Gemini подключён.
            {["OSRMRoute", "2ГИС"].includes(dataset?.place_provider || "") &&
              ` Координата и радиус поиска передаются ${dataset?.place_provider}.`}
          </p>
        </footer>
      </div>
    </MotionConfig>
  );
}
