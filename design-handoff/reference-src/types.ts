export type Point = { latitude: number; longitude: number; label: string };
export type Category =
  | "park"
  | "cafe"
  | "museum"
  | "gallery"
  | "attraction"
  | "playground"
  | "viewpoint"
  | "public_space"
  | "computer_club"
  | "restaurant"
  | "cinema"
  | "shopping_mall"
  | "library"
  | "fitness";
export type Source = {
  id: string;
  name: string;
  url: string;
  collected_at: string;
  fields: Record<string, string>;
};
export type Place = {
  poi_id: string;
  name: string;
  category: string;
  category_label: string;
  latitude: number;
  longitude: number;
  coordinate_accuracy: string;
  description: string;
  description_origin: string;
  address: string | null;
  reason: string;
  suggested_activity: string;
  activity_origin: string;
  distance_m: number;
  walk_minutes: number;
  visit_minutes: number;
  total_minutes: number;
  opening_status: "open" | "closed" | "unknown";
  opening_hours_raw: string | null;
  sources: Source[];
  fact_refs: string[];
  collected_at: string;
  warnings: string[];
  wheelchair: boolean | null;
  sockets: boolean | null;
};
export type Result = {
  place_provider?: string;
  data_mode?: "live" | "snapshot";
  checked_at?: string;
  live_objects_count?: number;
  query_understanding?: {
    categories: string[];
    name: string;
    cuisines: string[];
    method: string;
  };
  live_answer?: {
    grounding: "web" | "catalog";
    segments: { text: string; sources: number[] }[];
    sources: { url: string; title: string }[];
    search_suggestions: string;
    checked_at: string;
  };
  request_id: string;
  mode: "demo" | "live";
  generation_mode: "llm" | "template";
  retrieval_mode: string;
  recommendations: Place[];
  warnings: string[];
  empty_reason: string | null;
  candidates_count: number;
  applied_constraints: {
    minutes: number;
    radius_m: number;
    return_to_start: boolean;
    interests: string[];
    open_now: boolean;
    sockets_required: boolean;
    accessible_only: boolean;
    with_child: boolean;
  };
};
export type Dataset = {
  place_provider?: string;
  live_place_search: boolean;
  ai_configured: boolean;
  web_search_enabled: boolean;
  version: string;
  count: number;
  collected_at: string;
  retrieval_mode: string;
  categories: Record<string, number>;
};
