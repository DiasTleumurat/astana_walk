import { useEffect, useState, useRef } from "react";
import { useMotionValueEvent } from "motion/react";
import type { MotionValue } from "motion/react";
import { RadiusValue } from "./RadiusControl";
import {
  Circle,
  CircleMarker,
  GeoJSON,
  MapContainer,
  Marker,
  Popup,
  ScaleControl,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import type { FeatureCollection } from "geojson";
import { Compass, MapPin, Maximize2, LocateFixed } from "lucide-react";
import type { Place, Point } from "./types";

type Props = {
  point: Point;
  places: Place[];
  active: string | null;
  onSelect: (id: string) => void;
  picking: boolean;
  onPick: (point: Point) => void;
  radius: number;
  animatedRadius: MotionValue<number>;
};

function SearchRadius({
  point,
  value,
}: {
  point: Point;
  value: MotionValue<number>;
}) {
  const circle = useRef<L.Circle | null>(null);
  useMotionValueEvent(value, "change", (radius) =>
    circle.current?.setRadius(radius),
  );
  return (
    <Circle
      ref={circle}
      interactive={false}
      center={[point.latitude, point.longitude]}
      radius={value.get()}
      pathOptions={{
        className: "search-radius",
        color: "#38a9ef",
        fillColor: "#38a9ef",
        weight: 2.5,
        opacity: 0.95,
        dashArray: "8 6",
        fillOpacity: 0.1,
      }}
    />
  );
}
const CITY: L.LatLngBoundsExpression = [
  [51.02, 71.3],
  [51.23, 71.6],
];
const FIT: L.FitBoundsOptions = {
  paddingTopLeft: [50, 85],
  paddingBottomRight: [60, 170],
  maxZoom: 16,
  animate: false,
};

function MapControls({ point, places, active, picking, onPick }: Props) {
  const map = useMap();
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      if (!map.getContainer().clientWidth) return;
      map.invalidateSize({ pan: false });
    });
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);
  useMapEvents({
    click(e) {
      if (picking)
        onPick({
          latitude: e.latlng.lat,
          longitude: e.latlng.lng,
          label: "Точка на карте",
        });
    },
  });
  useEffect(() => {
    const bounds = L.latLngBounds([
      [point.latitude, point.longitude],
      ...places.map((p) => [p.latitude, p.longitude] as [number, number]),
    ]);
    map.fitBounds(bounds, FIT);
  }, [point.latitude, point.longitude, places, map]);
  useEffect(() => {
    const place = places.find((p) => p.poi_id === active);
    if (place)
      map.panInside([place.latitude, place.longitude], {
        paddingTopLeft: [50, 85],
        paddingBottomRight: [60, 170],
        animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        duration: 0.25,
      });
  }, [active, map, places]);
  return null;
}

export default function WalkMap(props: Props) {
  const [basemap, setBasemap] = useState<FeatureCollection | null>(null);
  const [mapError, setMapError] = useState(false);
  const [online, setOnline] = useState(true);
  const [tileError, setTileError] = useState(false);
  const [map, setMap] = useState<L.Map | null>(null);
  useEffect(() => {
    if (online) return;
    const controller = new AbortController();
    fetch("/astana-map.geojson", { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then((data) => {
        if (!controller.signal.aborted) setBasemap(data);
      })
      .catch(() => {
        if (!controller.signal.aborted) setMapError(true);
      });
    return () => controller.abort();
  }, [online]);
  const fit = () =>
    map?.fitBounds(
      L.latLngBounds([
        [props.point.latitude, props.point.longitude],
        ...props.places.map(
          (p) => [p.latitude, p.longitude] as [number, number],
        ),
      ]),
      FIT,
    );
  return (
    <section
      className={`map-panel ${props.picking ? "picking" : ""}`}
      aria-label="Карта мест"
    >
      <div className="map-title">
        <span>
          <MapPin size={16} /> Астана
        </span>
        <span>Пешком по городу</span>
      </div>
      <MapContainer
        ref={setMap}
        center={[props.point.latitude, props.point.longitude]}
        zoom={16}
        minZoom={10}
        maxZoom={19}
        maxBounds={CITY}
        maxBoundsViscosity={0.7}
        scrollWheelZoom={true}
        touchZoom={true}
        doubleClickZoom={true}
        zoomControl={false}
        attributionControl={false}
      >
        {!online && basemap && (
          <GeoJSON
            data={basemap}
            interactive={false}
            style={(feature) => {
              const kind = feature?.properties?.kind;
              return kind === "water"
                ? {
                    color: "#a4c7c9",
                    weight: 4,
                    fillColor: "#c2dedf",
                    fillOpacity: 1,
                  }
                : kind === "park"
                  ? {
                      color: "#c7d9c0",
                      weight: 1,
                      fillColor: "#dce7d4",
                      fillOpacity: 0.9,
                    }
                  : { color: "#fff", weight: 3, opacity: 1 };
            }}
          />
        )}
        {online && (
          <TileLayer
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            maxZoom={19}
            referrerPolicy="strict-origin-when-cross-origin"
            eventHandlers={{ tileerror: () => setTileError(true) }}
          />
        )}
        <ScaleControl position="topleft" imperial={false} />
        <SearchRadius point={props.point} value={props.animatedRadius} />
        <CircleMarker
          interactive={false}
          center={[props.point.latitude, props.point.longitude]}
          radius={8}
          pathOptions={{
            color: "#ffffff",
            weight: 3,
            fillColor: "#1b6e66",
            fillOpacity: 1,
          }}
        >
          <Tooltip direction="bottom" offset={[0, 8]} permanent>
            Ваш старт
          </Tooltip>
        </CircleMarker>
        {props.places.map((place, i) => (
          <Marker
            key={place.poi_id}
            position={[place.latitude, place.longitude]}
            icon={L.divIcon({
              className: "place-pin-wrap",
              html: `<span class="place-pin ${props.active === place.poi_id ? "selected" : ""}"><b>${i + 1}</b></span>`,
              iconSize: [36, 42],
              iconAnchor: [18, 39],
            })}
            eventHandlers={{
              click: () =>
                props.picking
                  ? props.onPick({
                      latitude: place.latitude,
                      longitude: place.longitude,
                      label: place.name,
                    })
                  : props.onSelect(place.poi_id),
            }}
            title={place.name}
            alt={`Место ${i + 1}: ${place.name}`}
          >
            <Tooltip
              key={props.active === place.poi_id ? "selected" : "idle"}
              permanent={props.active === place.poi_id}
              direction="top"
              offset={[0, -38]}
            >
              {place.name}
            </Tooltip>
            <Popup>
              <div className="map-place-popup">
                <strong>{place.name}</strong>
                <span>{place.category_label}</span>
                {place.address && <span>{place.address}</span>}
                <span>
                  {place.distance_m} м по прямой · ≈ {place.walk_minutes} мин
                  пешком
                </span>
                {place.sources[0] && (
                  <a
                    href={place.sources[0].url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Открыть в {place.sources[0].name}
                  </a>
                )}
              </div>
            </Popup>
          </Marker>
        ))}
        <MapControls {...props} />
      </MapContainer>
      <div className="map-tools">
        <button aria-label="Показать все места" onClick={fit}>
          <Maximize2 size={18} />
        </button>
        <button
          aria-label="Вернуться к старту"
          onClick={() =>
            map?.setView([props.point.latitude, props.point.longitude], 16)
          }
        >
          <LocateFixed size={18} />
        </button>
        <button aria-label="Приблизить карту" onClick={() => map?.zoomIn()}>
          +
        </button>
        <button aria-label="Отдалить карту" onClick={() => map?.zoomOut()}>
          −
        </button>
      </div>
      {props.picking && (
        <div className="map-hint" role="status">
          <MapPin size={16} /> Нажмите на карту, чтобы выбрать старт
        </div>
      )}
      {((!online && mapError) || (online && tileError)) && (
        <div className="map-hint error">
          Карта загружена не полностью. Список мест работает.
          {online && (
            <button onClick={() => setOnline(false)}>Обзорная карта</button>
          )}
        </div>
      )}
      <div className="map-legend">
        <Compass size={17} />
        <div>
          <strong>
            Радиус <RadiusValue value={props.animatedRadius} />
          </strong>
          <span>Нажмите на метку, чтобы увидеть адрес места.</span>
        </div>
      </div>
      <div className="map-attribution">
        <a
          href="https://www.openstreetmap.org/copyright"
          target="_blank"
          rel="noreferrer"
        >
          © OpenStreetMap contributors
        </a>
        <span>{online ? "Подробная карта" : "Обзорная карта"}</span>
      </div>
      <details className="online-map">
        <summary>Слой карты</summary>
        <p>
          Подробная карта показывает улицы, здания и подписи. OpenStreetMap
          получает IP и область просмотра.
        </p>
        <label>
          <input
            type="checkbox"
            checked={online}
            onChange={(e) => {
              setTileError(false);
              setOnline(e.target.checked);
            }}
          />{" "}
          Подробная карта
        </label>
      </details>
    </section>
  );
}
