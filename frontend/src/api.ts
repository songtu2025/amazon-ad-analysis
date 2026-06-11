export type AnomalyStatus = "pending" | "observing" | "handled";

export type Anomaly = {
  id: number;
  product_id: number | null;
  market_id: number | null;
  anomaly_type: string;
  severity: string;
  object_type: string;
  object_id: string | null;
  object_name: string | null;
  period_start: string;
  period_end: string;
  status: AnomalyStatus;
  rule_result_json: string;
  evidence_json: string;
  created_at: string;
  updated_at: string;
};

export type Suggestion = {
  id: number;
  anomaly_event_id: number;
  suggestion_level: SuggestionLevel;
  suggested_action: string;
  title: string | null;
  summary: string | null;
  reasoning: string | null;
  risk_note: string | null;
  evidence_summary: string | null;
  recommended_manual_decision: DecisionInput["decision_type"] | null;
  source_trace_json: string | null;
  ai_model: string | null;
  created_at: string;
  updated_at: string;
};

export type DecisionInput = {
  decision_type: "adopt" | "adopt_with_changes" | "reject" | "observe" | "handled";
  modified_action?: string | null;
  reason?: string | null;
  observe_period?: "7d" | "14d" | null;
  operator_name?: string | null;
};

export type SuggestionLevel = "adoptable" | "small_test" | "observe" | "blocked";
export type AnomalyType =
  | "spend_spike"
  | "acos_worse"
  | "clicks_no_orders"
  | "search_term_clicks_no_orders"
  | "cvr_drop"
  | "impression_low"
  | "impressions_drop"
  | "inventory_goal_conflict";

export type Decision = {
  id: number;
  suggestion_id: number;
  suggestion: {
    title: string | null;
    suggested_action: string;
    suggestion_level: SuggestionLevel;
    anomaly_event_id: number;
    evidence_json: string | null;
  } | null;
  decision_type: DecisionInput["decision_type"];
  modified_action: string | null;
  reason: string | null;
  observe_period: string | null;
  operator_name: string | null;
  decided_at: string;
};

export type DecisionResult = {
  decision: Decision;
  anomaly_event_id: number;
  anomaly_status: AnomalyStatus;
};

export type ReviewResult = "improved" | "unchanged" | "worse";

export type Review = {
  id: number;
  manual_decision_id: number;
  review_period: "7d" | "14d";
  before_metrics_json: string | null;
  after_metrics_json: string | null;
  result: ReviewResult | null;
  note: string | null;
  reviewed_at: string;
};

export type ReviewInput = {
  review_period: "7d" | "14d";
  before_metrics_json?: Record<string, unknown> | null;
  after_metrics_json?: Record<string, unknown> | null;
  result: ReviewResult;
  note?: string | null;
};

export type DashboardSummary = {
  sync: {
    source: string;
    market_id: number;
    period_start: string;
    period_end: string;
    status: string;
    rows_synced: number;
    finished_at: string | null;
  } | null;
  period: {
    start: string;
    end: string;
  };
  market: {
    market_id: number | null;
    market_ids: number[];
    market_name: string | null;
    country_code: string | null;
    raw_name?: string | null;
    identity_status: "matched" | "name_missing" | "multiple" | "unknown";
  };
  data_sources: string[];
  product_binding: {
    status: "none" | "partial" | "complete" | "unknown";
    bound_rows: number;
    total_rows: number;
  };
  overview: {
    metric_rows: number;
    impressions: number;
    clicks: number;
    cost: number;
    orders: number;
    sales: number;
    acos: number;
    cvr: number;
    anomaly_count: number;
    anomaly_product_count: number;
    high_risk_count: number;
    pending_suggestion_count: number;
    waste_cost: number;
  };
  trend: {
    date: string;
    cost: number;
    acos: number;
    cvr: number;
  }[];
  top_campaigns: {
    campaign_id: string | null;
    campaign_name: string | null;
    metric_rows: number;
    ad_group_count: number;
    keyword_count: number;
    impressions: number;
    clicks: number;
    cost: number;
    orders: number;
    sales: number;
    acos: number;
    cvr: number;
  }[];
  anomaly_types: {
    anomaly_type: string;
    count: number;
  }[];
};

export type DashboardHealth = Pick<
  DashboardSummary,
  "sync" | "period" | "market" | "data_sources" | "product_binding" | "overview" | "top_campaigns"
>;
export type DashboardTrends = Pick<DashboardSummary, "period" | "trend">;
export type DashboardAnomalySummary = Pick<DashboardSummary, "period" | "anomaly_types"> & {
  anomaly_count: number;
  anomaly_product_count: number;
  high_risk_count: number;
  pending_suggestion_count: number;
  waste_cost: number;
};

export type SearchTermSemanticCategory = "asin" | "accessory_or_unrelated" | "age_spec" | "core_product" | "generic";
export type SearchTermPerformanceStatus =
  | "high_conversion"
  | "costly_no_order"
  | "high_acos"
  | "data_insufficient"
  | "observe";
export type SearchTermCandidateType = "scale_opportunity" | "waste_risk" | "efficiency_risk";

export type SearchTermSummaryBucket = {
  key: string;
  label: string;
  terms: number;
  clicks: number;
  cost: number;
  orders: number;
  sales: number;
  acos: number;
  cvr: number;
};

export type SearchTermGroupSummary = {
  group_key: string;
  group_label: string;
  semantic_category: SearchTermSemanticCategory;
  semantic_label: string;
  performance_status: SearchTermPerformanceStatus;
  performance_label: string;
  terms: number;
  clicks: number;
  cost: number;
  orders: number;
  sales: number;
  acos: number;
  cvr: number;
  representative_terms: string[];
  manual_hint: string;
};

export type SearchTermAnalysisRow = {
  search_term: string;
  semantic_category: SearchTermSemanticCategory;
  semantic_label: string;
  semantic_reasons: string[];
  performance_status: SearchTermPerformanceStatus;
  performance_label: string;
  performance_reasons: string[];
  metric_rows: number;
  campaign_count: number;
  ad_group_count: number;
  keyword_count: number;
  impressions: number;
  clicks: number;
  cost: number;
  orders: number;
  sales: number;
  acos: number;
  cvr: number;
  evidence: {
    campaign_name: string | null;
    ad_group_name: string | null;
    keyword_text: string | null;
  };
  manual_hint: string;
};

export type SearchTermAnalysis = {
  period: {
    start: string;
    end: string;
  };
  filters: {
    market_id: number | null;
    product_id: number | null;
    semantic_category: SearchTermSemanticCategory | null;
    performance_status: SearchTermPerformanceStatus | null;
    min_clicks: number;
    min_spend: number;
    target_acos: number;
    limit: number;
  };
  summary: SearchTermSummaryBucket & {
    distinct_terms: number;
  };
  category_summary: SearchTermSummaryBucket[];
  performance_summary: SearchTermSummaryBucket[];
  group_summary: SearchTermGroupSummary[];
  rows: SearchTermAnalysisRow[];
};

export type SearchTermProductReadinessProduct = {
  product_id: number;
  product_name: string | null;
  asin: string | null;
  msku: string | null;
  search_term_rows: number;
  distinct_terms: number;
  clicks: number;
  cost: number;
  orders: number;
  sales: number;
  acos: number;
  cvr: number;
};

export type SearchTermProductReadiness = {
  period: {
    start: string;
    end: string;
  };
  filters: {
    market_id: number | null;
    product_id: number | null;
  };
  ready: boolean;
  status: "ready" | "needs_attribution";
  manual_hint: string;
  summary: {
    active_binding_count: number;
    bound_search_term_rows: number;
    product_count: number;
    products_with_search_terms: number;
  };
  products: SearchTermProductReadinessProduct[];
};

export type SearchTermCandidate = {
  candidate_id: string;
  candidate_type: SearchTermCandidateType;
  candidate_label: string;
  search_term: string;
  title: string;
  recommended_manual_decision: DecisionInput["decision_type"];
  suggested_manual_action: string;
  reasoning: string;
  risk_note: string;
  semantic_category: SearchTermSemanticCategory;
  semantic_label: string;
  performance_status: SearchTermPerformanceStatus;
  performance_label: string;
  metrics: {
    impressions: number;
    clicks: number;
    cost: number;
    orders: number;
    sales: number;
    acos: number;
    cvr: number;
    metric_rows: number;
  };
  evidence: {
    campaign_name: string | null;
    ad_group_name: string | null;
    keyword_text: string | null;
    campaign_count: number;
    ad_group_count: number;
    keyword_count: number;
  };
  source_trace: {
    source: string;
    search_term: string;
    semantic_reasons: string[];
    performance_reasons: string[];
  };
  manual_hint: string;
};

export type SearchTermCandidateDecisionType = "adopt_with_changes" | "reject" | "observe";

export type SearchTermCandidateDecision = {
  id: number;
  candidate_id: string;
  candidate_type: SearchTermCandidateType;
  search_term: string;
  market_id: number | null;
  product_id: number | null;
  period_start: string;
  period_end: string;
  decision_type: SearchTermCandidateDecisionType;
  modified_action: string | null;
  reason: string | null;
  observe_period: string | null;
  operator_name: string | null;
  candidate_snapshot: SearchTermCandidate | Record<string, unknown>;
  decided_at: string;
};

export type SearchTermGroupDecision = {
  id: number;
  group_key: string;
  group_label: string;
  market_id: number | null;
  product_id: number | null;
  semantic_category: SearchTermSemanticCategory;
  performance_status: SearchTermPerformanceStatus;
  period_start: string;
  period_end: string;
  decision_type: SearchTermCandidateDecisionType;
  modified_action: string | null;
  reason: string | null;
  observe_period: string | null;
  operator_name: string | null;
  group_snapshot: SearchTermGroupSummary | Record<string, unknown>;
  decided_at: string;
};

export type SearchTermCandidateReview = {
  decision_id: number;
  candidate_id: string;
  search_term: string;
  candidate_type: SearchTermCandidateType;
  decision_type: SearchTermCandidateDecisionType;
  review_period: "7d" | "14d";
  before_period: {
    start: string;
    end: string;
  };
  after_period: {
    start: string;
    end: string;
  };
  before_metrics: SearchTermCandidate["metrics"];
  after_metrics: SearchTermCandidate["metrics"];
  delta: {
    clicks_delta: number;
    cost_delta: number;
    orders_delta: number;
    sales_delta: number;
    acos_delta: number;
    cvr_delta: number;
  };
  result: "improved" | "unchanged" | "worse" | "data_pending";
  result_label: string;
  manual_hint: string;
};

export type SearchTermGroupDecisionReview = {
  decision_id: number;
  group_key: string;
  group_label: string;
  semantic_category: SearchTermSemanticCategory;
  performance_status: SearchTermPerformanceStatus;
  decision_type: SearchTermCandidateDecisionType;
  review_period: "7d" | "14d";
  before_period: {
    start: string;
    end: string;
  };
  after_period: {
    start: string;
    end: string;
  };
  before_metrics: SearchTermCandidate["metrics"];
  after_metrics: SearchTermCandidate["metrics"];
  delta_metrics: {
    clicks_delta: number;
    cost_delta: number;
    orders_delta: number;
    sales_delta: number;
    acos_delta: number;
    cvr_delta: number;
  };
  result: "improved" | "unchanged" | "worse" | "data_pending";
  result_label: string;
  manual_hint: string;
};

export type SearchTermCandidateDecisionInput = {
  candidate_id: string;
  decision_type: SearchTermCandidateDecisionType;
  modified_action?: string | null;
  reason?: string | null;
  observe_period?: "7d" | "14d" | null;
  operator_name?: string | null;
  market_id?: number;
  product_id?: number;
  semantic_category?: SearchTermSemanticCategory;
  performance_status?: SearchTermPerformanceStatus;
  start_date?: string;
  end_date?: string;
  min_clicks?: number;
  min_spend?: number;
  target_acos?: number;
  limit?: number;
};

export type SearchTermGroupDecisionInput = {
  group_key: string;
  decision_type: SearchTermCandidateDecisionType;
  modified_action?: string | null;
  reason?: string | null;
  observe_period?: "7d" | "14d" | null;
  operator_name?: string | null;
  market_id?: number;
  product_id?: number;
  semantic_category?: SearchTermSemanticCategory;
  performance_status?: SearchTermPerformanceStatus;
  start_date?: string;
  end_date?: string;
  min_clicks?: number;
  min_spend?: number;
  target_acos?: number;
  limit?: number;
};

export type SearchTermCandidates = {
  period: {
    start: string;
    end: string;
  };
  filters: SearchTermAnalysis["filters"] & {
    candidate_type: SearchTermCandidateType | null;
  };
  summary: {
    total_candidates: number;
    scale_opportunity_count: number;
    waste_risk_count: number;
    efficiency_risk_count: number;
  };
  type_summary: {
    key: SearchTermCandidateType;
    label: string;
    count: number;
  }[];
  rows: SearchTermCandidate[];
};

export type SyncRun = {
  id: number;
  source: string;
  market_id: number;
  period_start: string;
  period_end: string;
  status: string;
  rows_synced: number;
  raw_path: string | null;
  message: string | null;
  started_at: string;
  finished_at: string | null;
};

export type SyncStatus = {
  latest: SyncRun | null;
};

export type ProductGoalType =
  | "test_keywords"
  | "scale"
  | "profit"
  | "rank_carryover"
  | "clear_inventory"
  | "stop_loss";

export type Product = {
  id: number;
  asin: string | null;
  msku: string | null;
  sku: string | null;
  product_name: string | null;
  image_url: string | null;
  brand: string | null;
  category: string | null;
  market_id: number | null;
  market: {
    market_id: number | null;
    market_name: string | null;
    country_code: string | null;
    raw_name?: string | null;
  } | null;
  ad_coverage_status: "attributed" | "sp_unattributed" | "not_advertised";
  is_ad_tuning_eligible: boolean;
  inventory_quantity: number | null;
  goal: {
    goal_type: ProductGoalType;
    note: string | null;
  } | null;
  rules: {
    min_clicks: number | null;
    min_spend: number | null;
    min_orders: number | null;
    target_acos: number | null;
    target_cvr: number | null;
    max_cpc: number | null;
    inventory_guard: number | null;
  } | null;
  sp_metrics: {
    impressions: number;
    clicks: number;
    cost: number;
    orders: number;
    sales: number;
    acos: number;
    cvr: number;
  };
  sp_metrics_period: {
    start: string | null;
    end: string | null;
  };
  sales_snapshot: {
    period_start: string;
    period_end: string;
    units_ordered: number;
    orders: number;
    sales: number;
    sessions: number;
    order_cvr: number;
    ads_spend: number;
    ads_sales: number;
    acos: number;
    gross_profit: number;
    net_profit: number;
  } | null;
  inventory_status: string;
  target_match: {
    status: "matched" | "mismatch" | "unknown";
    reason: string;
  };
  created_at: string;
  updated_at: string;
};

export type ProductInput = {
  asin?: string | null;
  msku?: string | null;
  sku?: string | null;
  product_name?: string | null;
  image_url?: string | null;
  brand?: string | null;
  category?: string | null;
  market_id?: number | null;
  inventory_quantity?: number | null;
};

export type ProductGoalInput = {
  goal_type: ProductGoalType;
  note?: string | null;
};

export type ProductRuleInput = NonNullable<Product["rules"]>;

export type CampaignBindingInput = {
  campaign_id: string;
  market_id?: number | null;
};

export type AttributionScopeType = "campaign" | "ad_group";

export type UnboundAdSource = {
  scope_type: AttributionScopeType;
  scope_id: string | null;
  scope_name: string | null;
  market_id: number | null;
  campaign_id: string | null;
  campaign_name: string | null;
  ad_group_id: string | null;
  ad_group_name: string | null;
  metric_rows: number;
  keyword_count: number;
  ad_group_count: number;
  search_term_rows: number;
  impressions: number;
  clicks: number;
  cost: number;
  orders: number;
  sales: number;
  acos: number;
  cvr: number;
};

export type ProductAdBinding = {
  id: number;
  market_id: number | null;
  product_id: number;
  scope_type: AttributionScopeType;
  scope_id: string;
  scope_name: string | null;
  status: string;
  created_by: string | null;
  evidence_json: string | null;
  created_at: string;
  updated_at: string;
};

export type AdBindingInput = {
  scope_type: AttributionScopeType;
  scope_id: string;
  scope_name?: string | null;
  market_id?: number | null;
  created_by?: string | null;
  period_start?: string;
  period_end?: string;
  evidence_note?: string | null;
};

export type AttributionMetricRow = {
  clicks: number;
  cost: number;
  orders: number;
  sales: number;
  acos: number;
  cvr: number;
};

export type ProductAttributionSource = UnboundAdSource;

export type ProductAttributionCandidate = {
  product_id: number;
  product_name: string | null;
  asin: string | null;
  msku: string | null;
  sku: string | null;
  market_id: number | null;
  goal_type: ProductGoalType | null;
  inventory_quantity: number | null;
  target_acos: number | null;
  confidence_score: number;
  confidence_level: "high" | "medium" | "low" | string;
  reasons: string[];
};

export type ProductAttributionEvidence = {
  period: {
    start: string;
    end: string;
  };
  source: ProductAttributionSource;
  top_keywords: (AttributionMetricRow & {
    keyword_id: string | null;
    keyword_text: string | null;
  })[];
  top_search_terms: (AttributionMetricRow & {
    search_term: string | null;
    keyword_text: string | null;
  })[];
  candidate_products: ProductAttributionCandidate[];
  selected_product: ProductAttributionCandidate | null;
  conflicts: {
    binding_id: number;
    product_id: number;
    scope_type: AttributionScopeType;
    scope_id: string;
    scope_name: string | null;
    created_by: string | null;
    updated_at: string;
    message: string;
  }[];
};

export type ProductAttributionCandidateRow = {
  candidate_id: string;
  source: UnboundAdSource;
  candidate_product: ProductAttributionCandidate;
  priority_rank: number;
  priority_label: string;
  confidence_score: number;
  confidence_level: "high" | "medium" | "low" | string;
  confidence_reasons: string[];
  metrics: AttributionMetricRow & {
    metric_rows: number;
    search_term_rows: number;
  };
  unlock_impact: {
    search_term_rows: number;
    cost: number;
    sales: number;
    orders: number;
    acos: number;
    cvr: number;
  };
  evidence_preview: {
    top_keyword?: (AttributionMetricRow & {
      keyword_id?: string | null;
      keyword_text?: string | null;
    }) | Record<string, never>;
    top_search_term?: (AttributionMetricRow & {
      search_term?: string | null;
      keyword_text?: string | null;
    }) | Record<string, never>;
    conflict_count: number;
  };
  manual_hint: string;
};

export type ProductAttributionCandidates = {
  period: {
    start: string;
    end: string;
  };
  filters: {
    market_id: number | null;
    scope_type: AttributionScopeType;
    min_confidence: number;
    limit: number;
  };
  summary: {
    total_candidates: number;
    high_confidence_count: number;
    medium_confidence_count: number;
  };
  rows: ProductAttributionCandidateRow[];
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function errorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (detail?.message) {
      return detail.wait_seconds ? `${detail.message}，约 ${detail.wait_seconds} 秒后重试` : detail.message;
    }
  } catch {
    return fallback;
  }
  return fallback;
}

export async function fetchAnomalies(filters: {
  market_id?: number;
  product_id?: number;
  goal_type?: ProductGoalType;
  anomaly_type?: AnomalyType;
  suggestion_level?: SuggestionLevel;
  status?: AnomalyStatus;
  start_date?: string;
  end_date?: string;
}): Promise<Anomaly[]> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.product_id !== undefined) params.set("product_id", String(filters.product_id));
  if (filters.goal_type) params.set("goal_type", filters.goal_type);
  if (filters.anomaly_type) params.set("anomaly_type", filters.anomaly_type);
  if (filters.suggestion_level) params.set("suggestion_level", filters.suggestion_level);
  if (filters.status) params.set("status", filters.status);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/anomalies${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载异常队列失败：${response.status}`));
  }
  return response.json();
}

export async function fetchAnomaly(anomalyId: number): Promise<Anomaly> {
  const response = await fetch(`${API_BASE_URL}/api/anomalies/${anomalyId}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载异常详情失败：${response.status}`));
  }
  return response.json();
}

export async function generateAnomalies(filters: {
  market_id?: number;
  start_date?: string;
  end_date?: string;
  min_clicks?: number;
  min_spend?: number;
}): Promise<unknown> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);
  if (filters.min_clicks !== undefined) params.set("min_clicks", String(filters.min_clicks));
  if (filters.min_spend !== undefined) params.set("min_spend", String(filters.min_spend));

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/anomalies/generate${query ? `?${query}` : ""}`, {
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `生成异常失败：${response.status}`));
  }
  return response.json();
}

export async function fetchDashboardSummary(filters: {
  market_id?: number;
  goal_type?: ProductGoalType;
  anomaly_type?: AnomalyType;
  suggestion_level?: SuggestionLevel;
  start_date?: string;
  end_date?: string;
} = {}): Promise<DashboardSummary> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.goal_type) params.set("goal_type", filters.goal_type);
  if (filters.anomaly_type) params.set("anomaly_type", filters.anomaly_type);
  if (filters.suggestion_level) params.set("suggestion_level", filters.suggestion_level);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/dashboard/summary${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载驾驶舱失败：${response.status}`));
  }
  return response.json();
}

export async function fetchDashboardHealth(filters: {
  market_id?: number;
  goal_type?: ProductGoalType;
  anomaly_type?: AnomalyType;
  suggestion_level?: SuggestionLevel;
  start_date?: string;
  end_date?: string;
} = {}): Promise<DashboardHealth> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.goal_type) params.set("goal_type", filters.goal_type);
  if (filters.anomaly_type) params.set("anomaly_type", filters.anomaly_type);
  if (filters.suggestion_level) params.set("suggestion_level", filters.suggestion_level);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/dashboard/health${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载健康概览失败：${response.status}`));
  }
  return response.json();
}

export async function fetchDashboardTrends(filters: {
  market_id?: number;
  goal_type?: ProductGoalType;
  anomaly_type?: AnomalyType;
  suggestion_level?: SuggestionLevel;
  start_date?: string;
  end_date?: string;
} = {}): Promise<DashboardTrends> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.goal_type) params.set("goal_type", filters.goal_type);
  if (filters.anomaly_type) params.set("anomaly_type", filters.anomaly_type);
  if (filters.suggestion_level) params.set("suggestion_level", filters.suggestion_level);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/dashboard/trends${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载趋势数据失败：${response.status}`));
  }
  return response.json();
}

export async function fetchDashboardAnomalySummary(filters: {
  market_id?: number;
  goal_type?: ProductGoalType;
  anomaly_type?: AnomalyType;
  suggestion_level?: SuggestionLevel;
  start_date?: string;
  end_date?: string;
} = {}): Promise<DashboardAnomalySummary> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.goal_type) params.set("goal_type", filters.goal_type);
  if (filters.anomaly_type) params.set("anomaly_type", filters.anomaly_type);
  if (filters.suggestion_level) params.set("suggestion_level", filters.suggestion_level);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/dashboard/anomaly-summary${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载异常概览失败：${response.status}`));
  }
  return response.json();
}

export async function fetchSearchTermAnalysis(filters: {
  market_id?: number;
  product_id?: number;
  semantic_category?: SearchTermSemanticCategory;
  performance_status?: SearchTermPerformanceStatus;
  start_date?: string;
  end_date?: string;
  min_clicks?: number;
  min_spend?: number;
  target_acos?: number;
  limit?: number;
} = {}): Promise<SearchTermAnalysis> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.product_id !== undefined) params.set("product_id", String(filters.product_id));
  if (filters.semantic_category) params.set("semantic_category", filters.semantic_category);
  if (filters.performance_status) params.set("performance_status", filters.performance_status);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);
  if (filters.min_clicks !== undefined) params.set("min_clicks", String(filters.min_clicks));
  if (filters.min_spend !== undefined) params.set("min_spend", String(filters.min_spend));
  if (filters.target_acos !== undefined) params.set("target_acos", String(filters.target_acos));
  if (filters.limit !== undefined) params.set("limit", String(filters.limit));

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/search-terms/analysis${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载搜索词分析失败：${response.status}`));
  }
  return response.json();
}

export async function fetchSearchTermProductReadiness(filters: {
  market_id?: number;
  product_id?: number;
  start_date?: string;
  end_date?: string;
} = {}): Promise<SearchTermProductReadiness> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.product_id !== undefined) params.set("product_id", String(filters.product_id));
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/search-terms/product-readiness${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载产品维度搜索词就绪状态失败：${response.status}`));
  }
  return response.json();
}

export async function fetchSearchTermCandidates(filters: {
  market_id?: number;
  product_id?: number;
  semantic_category?: SearchTermSemanticCategory;
  performance_status?: SearchTermPerformanceStatus;
  candidate_type?: SearchTermCandidateType;
  start_date?: string;
  end_date?: string;
  min_clicks?: number;
  min_spend?: number;
  target_acos?: number;
  limit?: number;
} = {}): Promise<SearchTermCandidates> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.product_id !== undefined) params.set("product_id", String(filters.product_id));
  if (filters.semantic_category) params.set("semantic_category", filters.semantic_category);
  if (filters.performance_status) params.set("performance_status", filters.performance_status);
  if (filters.candidate_type) params.set("candidate_type", filters.candidate_type);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);
  if (filters.min_clicks !== undefined) params.set("min_clicks", String(filters.min_clicks));
  if (filters.min_spend !== undefined) params.set("min_spend", String(filters.min_spend));
  if (filters.target_acos !== undefined) params.set("target_acos", String(filters.target_acos));
  if (filters.limit !== undefined) params.set("limit", String(filters.limit));

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/search-terms/candidates${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载搜索词候选池失败：${response.status}`));
  }
  return response.json();
}

export async function createSearchTermCandidateDecision(
  payload: SearchTermCandidateDecisionInput
): Promise<{ decision: SearchTermCandidateDecision }> {
  const response = await fetch(`${API_BASE_URL}/api/search-terms/candidate-decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `提交搜索词人工判断失败：${response.status}`));
  }
  return response.json();
}

export async function fetchSearchTermCandidateDecisions(filters: {
  candidate_id?: string;
  decision_type?: SearchTermCandidateDecisionType;
  operator_name?: string;
  market_id?: number;
  product_id?: number;
  start_date?: string;
  end_date?: string;
} = {}): Promise<SearchTermCandidateDecision[]> {
  const params = new URLSearchParams();
  if (filters.candidate_id) params.set("candidate_id", filters.candidate_id);
  if (filters.decision_type) params.set("decision_type", filters.decision_type);
  if (filters.operator_name) params.set("operator_name", filters.operator_name);
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.product_id !== undefined) params.set("product_id", String(filters.product_id));
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/search-terms/candidate-decisions${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载搜索词候选处理记录失败：${response.status}`));
  }
  return response.json();
}

export async function createSearchTermGroupDecision(
  payload: SearchTermGroupDecisionInput
): Promise<{ decision: SearchTermGroupDecision }> {
  const response = await fetch(`${API_BASE_URL}/api/search-terms/group-decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `提交搜索词归类组人工判断失败：${response.status}`));
  }
  return response.json();
}

export async function fetchSearchTermGroupDecisions(filters: {
  group_key?: string;
  decision_type?: SearchTermCandidateDecisionType;
  operator_name?: string;
  market_id?: number;
  product_id?: number;
  semantic_category?: SearchTermSemanticCategory;
  performance_status?: SearchTermPerformanceStatus;
  start_date?: string;
  end_date?: string;
} = {}): Promise<SearchTermGroupDecision[]> {
  const params = new URLSearchParams();
  if (filters.group_key) params.set("group_key", filters.group_key);
  if (filters.decision_type) params.set("decision_type", filters.decision_type);
  if (filters.operator_name) params.set("operator_name", filters.operator_name);
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.product_id !== undefined) params.set("product_id", String(filters.product_id));
  if (filters.semantic_category) params.set("semantic_category", filters.semantic_category);
  if (filters.performance_status) params.set("performance_status", filters.performance_status);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/search-terms/group-decisions${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载搜索词归类组人工记录失败：${response.status}`));
  }
  return response.json();
}

export async function fetchSearchTermCandidateReview(
  decisionId: number,
  reviewPeriod: "7d" | "14d" = "7d"
): Promise<SearchTermCandidateReview> {
  const params = new URLSearchParams();
  params.set("review_period", reviewPeriod);
  const response = await fetch(`${API_BASE_URL}/api/search-terms/candidate-decisions/${decisionId}/review?${params.toString()}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载搜索词处理复盘失败：${response.status}`));
  }
  return response.json();
}

export async function fetchSearchTermGroupDecisionReview(
  decisionId: number,
  reviewPeriod: "7d" | "14d" = "7d"
): Promise<SearchTermGroupDecisionReview> {
  const params = new URLSearchParams();
  params.set("review_period", reviewPeriod);
  const response = await fetch(`${API_BASE_URL}/api/search-terms/group-decisions/${decisionId}/review?${params.toString()}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载搜索词归类组复盘失败：${response.status}`));
  }
  return response.json();
}

export async function syncSpKeywords(filters: { market_id?: number } = {}): Promise<unknown> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  params.set("count", "10");
  params.set("max_pages", "1");

  const response = await fetch(`${API_BASE_URL}/api/sync/sp-keywords?${params.toString()}`, {
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `同步 SP 关键词失败：${response.status}`));
  }
  return response.json();
}

export async function syncSpAds(filters: { market_id?: number } = {}): Promise<unknown> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  params.set("count", "10");
  params.set("max_pages", "1");

  const response = await fetch(`${API_BASE_URL}/api/sync/sp-ads?${params.toString()}`, {
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `同步 SP 广告失败：${response.status}`));
  }
  return response.json();
}

export async function syncSpSearchTerms(filters: { market_id?: number } = {}): Promise<unknown> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  params.set("count", "10");
  params.set("max_pages", "1");

  const response = await fetch(`${API_BASE_URL}/api/sync/sp-search-terms?${params.toString()}`, {
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `同步 SP 搜索词失败：${response.status}`));
  }
  return response.json();
}

export async function fetchSyncRuns(limit = 5): Promise<SyncRun[]> {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  const response = await fetch(`${API_BASE_URL}/api/sync/runs?${params.toString()}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载同步记录失败：${response.status}`));
  }
  return response.json();
}

export async function fetchSyncStatus(): Promise<SyncStatus> {
  const response = await fetch(`${API_BASE_URL}/api/sync/status`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载同步状态失败：${response.status}`));
  }
  return response.json();
}

export async function fetchSuggestions(filters: {
  anomaly_event_id?: number;
  market_id?: number;
  product_id?: number;
  goal_type?: ProductGoalType;
  anomaly_type?: AnomalyType;
  status?: AnomalyStatus;
  suggestion_level?: SuggestionLevel;
  start_date?: string;
  end_date?: string;
}): Promise<Suggestion[]> {
  const params = new URLSearchParams();
  if (filters.anomaly_event_id !== undefined) params.set("anomaly_event_id", String(filters.anomaly_event_id));
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.product_id !== undefined) params.set("product_id", String(filters.product_id));
  if (filters.goal_type) params.set("goal_type", filters.goal_type);
  if (filters.anomaly_type) params.set("anomaly_type", filters.anomaly_type);
  if (filters.status) params.set("status", filters.status);
  if (filters.suggestion_level) params.set("suggestion_level", filters.suggestion_level);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/suggestions${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载 AI 建议失败：${response.status}`));
  }
  return response.json();
}

export async function fetchSuggestion(suggestionId: number): Promise<Suggestion> {
  const response = await fetch(`${API_BASE_URL}/api/suggestions/${suggestionId}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载 AI 建议详情失败：${response.status}`));
  }
  return response.json();
}

export async function generateSuggestions(filters: {
  market_id?: number;
  product_id?: number;
  anomaly_type?: AnomalyType;
  status?: AnomalyStatus;
}): Promise<unknown> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.product_id !== undefined) params.set("product_id", String(filters.product_id));
  if (filters.anomaly_type) params.set("anomaly_type", filters.anomaly_type);
  if (filters.status) params.set("status", filters.status);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/suggestions/generate${query ? `?${query}` : ""}`, {
    method: "POST"
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `生成 AI 建议失败：${response.status}`));
  }
  return response.json();
}

export async function createDecision(suggestionId: number, payload: DecisionInput): Promise<DecisionResult> {
  const response = await fetch(`${API_BASE_URL}/api/suggestions/${suggestionId}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `提交人工处理失败：${response.status}`));
  }
  return response.json();
}

export async function fetchProducts(filters: {
  market_id?: number;
  goal_type?: ProductGoalType;
  anomaly_type?: AnomalyType;
  suggestion_level?: SuggestionLevel;
  start_date?: string;
  end_date?: string;
} = {}): Promise<Product[]> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.goal_type) params.set("goal_type", filters.goal_type);
  if (filters.anomaly_type) params.set("anomaly_type", filters.anomaly_type);
  if (filters.suggestion_level) params.set("suggestion_level", filters.suggestion_level);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/products${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载产品列表失败：${response.status}`));
  }
  return response.json();
}

export async function fetchProduct(
  productId: number,
  filters: {
    start_date?: string;
    end_date?: string;
  } = {}
): Promise<Product> {
  const params = new URLSearchParams();
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/products/${productId}${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载产品详情失败：${response.status}`));
  }
  return response.json();
}

export async function createProduct(payload: ProductInput): Promise<Product> {
  const response = await fetch(`${API_BASE_URL}/api/products`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `创建产品失败：${response.status}`));
  }
  return response.json();
}

export async function updateProduct(productId: number, payload: ProductInput): Promise<Product> {
  const response = await fetch(`${API_BASE_URL}/api/products/${productId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `保存产品信息失败：${response.status}`));
  }
  return response.json();
}

export async function updateProductGoal(productId: number, payload: ProductGoalInput): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}/api/products/${productId}/goal`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `保存产品目标失败：${response.status}`));
  }
  return response.json();
}

export async function updateProductRules(productId: number, payload: ProductRuleInput): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}/api/products/${productId}/rules`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `保存产品规则失败：${response.status}`));
  }
  return response.json();
}

export async function bindCampaignToProduct(productId: number, payload: CampaignBindingInput): Promise<{
  product_id: number;
  campaign_id: string;
  market_id: number | null;
  rows_updated: number;
  keyword_rows_updated: number;
  search_term_rows_updated: number;
}> {
  const response = await fetch(`${API_BASE_URL}/api/products/${productId}/campaign-binding`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `绑定 Campaign 失败：${response.status}`));
  }
  return response.json();
}

export async function fetchUnboundAdSources(filters: {
  market_id?: number;
  scope_type?: AttributionScopeType;
  start_date?: string;
  end_date?: string;
} = {}): Promise<UnboundAdSource[]> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.scope_type) params.set("scope_type", filters.scope_type);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/products/unbound-ad-sources${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载未归因广告数据池失败：${response.status}`));
  }
  return response.json();
}

export async function fetchProductAdBindings(filters: {
  market_id?: number;
  product_id?: number;
} = {}): Promise<ProductAdBinding[]> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.product_id !== undefined) params.set("product_id", String(filters.product_id));

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/products/ad-bindings${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载产品归因规则失败：${response.status}`));
  }
  return response.json();
}

export async function fetchProductAttributionEvidence(filters: {
  market_id?: number;
  scope_type: AttributionScopeType;
  scope_id: string;
  start_date?: string;
  end_date?: string;
}): Promise<ProductAttributionEvidence> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  params.set("scope_type", filters.scope_type);
  params.set("scope_id", filters.scope_id);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const response = await fetch(`${API_BASE_URL}/api/products/ad-attribution-evidence?${params.toString()}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载产品归因证据失败：${response.status}`));
  }
  return response.json();
}

export async function fetchProductAttributionCandidates(filters: {
  market_id?: number;
  scope_type?: AttributionScopeType;
  start_date?: string;
  end_date?: string;
  min_confidence?: number;
  limit?: number;
} = {}): Promise<ProductAttributionCandidates> {
  const params = new URLSearchParams();
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.scope_type) params.set("scope_type", filters.scope_type);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);
  if (filters.min_confidence !== undefined) params.set("min_confidence", String(filters.min_confidence));
  if (filters.limit !== undefined) params.set("limit", String(filters.limit));

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/products/attribution-candidates${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载产品归因候选失败：${response.status}`));
  }
  return response.json();
}

export async function bindAdSourceToProduct(productId: number, payload: AdBindingInput): Promise<{
  id: number;
  product_id: number;
  market_id: number | null;
  scope_type: AttributionScopeType;
  scope_id: string;
  scope_name: string | null;
  evidence_json: string | null;
  rows_updated: number;
  keyword_rows_updated: number;
  search_term_rows_updated: number;
}> {
  const response = await fetch(`${API_BASE_URL}/api/products/${productId}/ad-binding`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `确认产品归因失败：${response.status}`));
  }
  return response.json();
}

export async function fetchDecisions(filters: {
  suggestion_id?: number;
  decision_type?: DecisionInput["decision_type"];
  operator_name?: string;
  market_id?: number;
  goal_type?: ProductGoalType;
  anomaly_type?: AnomalyType;
  suggestion_level?: SuggestionLevel;
  start_date?: string;
  end_date?: string;
} = {}): Promise<Decision[]> {
  const params = new URLSearchParams();
  if (filters.suggestion_id !== undefined) params.set("suggestion_id", String(filters.suggestion_id));
  if (filters.decision_type) params.set("decision_type", filters.decision_type);
  if (filters.operator_name) params.set("operator_name", filters.operator_name);
  if (filters.market_id !== undefined) params.set("market_id", String(filters.market_id));
  if (filters.goal_type) params.set("goal_type", filters.goal_type);
  if (filters.anomaly_type) params.set("anomaly_type", filters.anomaly_type);
  if (filters.suggestion_level) params.set("suggestion_level", filters.suggestion_level);
  if (filters.start_date) params.set("start_date", filters.start_date);
  if (filters.end_date) params.set("end_date", filters.end_date);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/decisions${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载处理记录失败：${response.status}`));
  }
  return response.json();
}

export async function fetchReviews(filters: {
  decision_id?: number;
  decision_ids?: number[];
  review_period?: "7d" | "14d";
  result?: ReviewResult;
} = {}): Promise<Review[]> {
  const params = new URLSearchParams();
  if (filters.decision_id !== undefined) params.set("decision_id", String(filters.decision_id));
  if (filters.decision_ids?.length) params.set("decision_ids", filters.decision_ids.join(","));
  if (filters.review_period) params.set("review_period", filters.review_period);
  if (filters.result) params.set("result", filters.result);

  const query = params.toString();
  const response = await fetch(`${API_BASE_URL}/api/reviews${query ? `?${query}` : ""}`);
  if (!response.ok) {
    throw new Error(await errorMessage(response, `加载复盘记录失败：${response.status}`));
  }
  return response.json();
}

export async function createReview(decisionId: number, payload: ReviewInput): Promise<Review> {
  const response = await fetch(`${API_BASE_URL}/api/reviews/${decisionId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `提交复盘失败：${response.status}`));
  }
  return response.json();
}
