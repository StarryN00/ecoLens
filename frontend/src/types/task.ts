export interface Task {
  id: string;
  task_name: string;
  area_name: string;
  operator: string;
  region_id?: string | null;
  region_path?: string | null;
  plot_area_mu?: number | null;
  forestry_sub_compartment?: string | null;
  status: string;
  total_images: number;
  processed_images: number;
  created_at: string;
  completed_at: string | null;
}

export interface Nest {
  id: string;
  nest_code: string;
  latitude: number;
  longitude: number;
  severity: string;
  confidence: number;
  detection_count: number;
  source_images: string[];
  created_at: string;
}

export interface TaskResults {
  task_id: string;
  image_stats: {
    total_processed: number;
    with_camphor_tree: number;
    with_nests: number;
    total_candidate_detections?: number;
    total_nest_detections: number;
  };
  nest_stats: {
    total_unique: number;
    severe: number;
    medium: number;
    light: number;
  };
}

export interface TaskImage {
  id: string;
  filename: string;
  has_gps: boolean;
  latitude?: number;
  longitude?: number;
  altitude?: number;
  capture_time?: string | null;
  created_at?: string | null;
  detection?: {
    has_nest: boolean;
    nest_count?: number;
    max_severity: string | null;
  } | null;
}
