export interface ForecastPoint {
  date: string;
  product_id: string;
  predicted_quantity: number;
  predicted_revenue?: number;
}

export interface ForecastResponse {
  product_id: string;
  from_date: string;
  to_date: string;
  points: ForecastPoint[];
  model_version?: string;
}

export interface ScenarioResponse {
  product_id: string;
  from_date: string;
  to_date: string;
  price_delta_pct: number;
  base_forecast_points: ForecastPoint[];
  scenario_forecast_points: ForecastPoint[];
  delta_revenue_pct?: number;
  delta_quantity_pct?: number;
}

export interface BacktestDateRange {
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
}

export interface BacktestResult {
  mae: number | null;
  rmse: number | null;
  mape: number | null;
  n_samples: number;
  date_range?: BacktestDateRange;
  product_id?: string;
  message?: string;
}

export interface TrainResult {
  version: string;
  artifact_id: number;
  mae: number;
  rmse: number;
  mape: number;
  n_eval_samples: number;
  eval_source: "train" | "test";
  date_range?: BacktestDateRange;
}

export interface ChatResponse {
  answer: string;
  used_tools: string[];
  citations: Record<string, unknown>[];
}

export interface KnowledgeResponse {
  answer: string;
  citations: Record<string, unknown>[];
}
