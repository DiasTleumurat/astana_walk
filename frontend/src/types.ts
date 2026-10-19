export type Point = { latitude: number; longitude: number; label: string };
export type Category =
  | "park"
  | "cafe"
  | "museum"
  | "gallery"
  | "attraction"
  | "playground"
  | "viewpoint"
  | "public_space";
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
  category: Category;
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
  version: string;
  count: number;
  collected_at: string;
  retrieval_mode: string;
  categories: Record<string, number>;
};
