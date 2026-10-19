import { useEffect, useState } from "react";
import {
  Circle,
  CircleMarker,
  GeoJSON,
  MapContainer,
  Marker,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import type { FeatureCollection } from "geojson";
import { Compass, MapPin, Maximize2 } from "lucide-react";
import type { Place, Point } from "./types";

type Props = {
  point: Point;
  places: Place[];
  active: string | null;
  onSelect: (id: string) => void;
  picking: boolean;
  onPick: (point: Point) => void;
  radius: number;
};
const CITY: L.LatLngBoundsExpression = [
  [51.02, 71.3],
  [51.23, 71.6],
];
const FIT: L.FitBoundsOptions = {
  paddingTopLeft: [50, 85],
  paddingBottomRight: [60, 170],
  maxZoom: 14,
  animate: false,
};

function MapControls({ point, places, active, picking, onPick }: Props) {
  const map = useMap();
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      if (!map.getContainer().clientWidth) return;
      map.invalidateSize({ pan: false });
      const bounds = L.latLngBounds([
        [point.latitude, point.longitude],
        ...places.map((p) => [p.latitude, p.longitude] as [number, number]),
      ]);
      map.fitBounds(bounds, FIT);
    });
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map, point.latitude, point.longitude, places]);
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
  const [online, setOnline] = useState(false);
  const [tileError, setTileError] = useState(false);
  const [map, setMap] = useState<L.Map | null>(null);
  useEffect(() => {
    fetch("/astana-map.geojson")
      .then((r) => {
        if (!r.ok) throw Error();
        return r.json();
      })
      .then(setBasemap)
      .catch(() => setMapError(true));
  }, []);
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
        zoom={13}
        minZoom={11}
        maxZoom={18}
        maxBounds={CITY}
        maxBoundsViscosity={0.7}
        scrollWheelZoom={false}
        zoomControl={false}
        attributionControl={false}
      >
        {basemap && (
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
            eventHandlers={{ tileerror: () => setTileError(true) }}
          />
        )}
        <Circle
          interactive={false}
          center={[props.point.latitude, props.point.longitude]}
          radius={props.radius}
          pathOptions={{
            color: "#1b6e66",
            weight: 1,
            dashArray: "5 7",
            fillOpacity: 0.025,
          }}
        />
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
            <Tooltip>{place.name}</Tooltip>
          </Marker>
        ))}
        <MapControls {...props} />
      </MapContainer>
      <div className="map-tools">
        <button aria-label="Показать все места" onClick={fit}>
          <Maximize2 size={18} />
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
      {(mapError || tileError) && (
        <div className="map-hint error">
          Карта загружена не полностью. Список мест работает.
        </div>
      )}
      <div className="map-legend">
        <Compass size={17} />
        <div>
          <strong>Места рядом с вами</strong>
          <span>Круг — радиус поиска. Путь между местами не рассчитан.</span>
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
        <span>Обзорная карта</span>
      </div>
      <details className="online-map">
        <summary>Детальная онлайн-карта</summary>
        <p>
          При включении OpenStreetMap получает ваш IP и область карты. Выбор
          сохраняется только до закрытия страницы.
        </p>
        <label>
          <input
            type="checkbox"
            checked={online}
            onChange={(e) => setOnline(e.target.checked)}
          />{" "}
          Загрузить подробную карту
        </label>
      </details>
    </section>
  );
}
