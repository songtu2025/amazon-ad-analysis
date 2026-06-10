import { AuditOutlined, EyeOutlined, PlusOutlined, ReloadOutlined, SaveOutlined } from "@ant-design/icons";
import {
  Alert,
  App as AntApp,
  Button,
  Card,
  Divider,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";
import {
  Anomaly,
  AnomalyStatus,
  AnomalyType,
  DashboardSummary,
  Decision,
  DecisionInput,
  Product,
  ProductGoalType,
  ProductInput,
  ProductRuleInput,
  Review,
  ReviewInput,
  SuggestionLevel,
  Suggestion,
  SyncRun,
  bindCampaignToProduct,
  createDecision,
  createProduct,
  createReview,
  fetchAnomalies,
  fetchDashboardAnomalySummary,
  fetchDashboardHealth,
  fetchDashboardTrends,
  fetchDecisions,
  fetchProducts,
  fetchReviews,
  fetchSuggestions,
  fetchSyncRuns,
  fetchSyncStatus,
  generateAnomalies,
  generateSuggestions,
  syncSpAds,
  syncSpKeywords,
  syncSpSearchTerms,
  updateProduct,
  updateProductGoal,
  updateProductRules
} from "./api";

const { Text, Title } = Typography;

const anomalyLabels: Record<string, string> = {
  acos_worse: "ACOS 异常",
  clicks_no_orders: "点击多无订单",
  spend_spike: "花费异常",
  cvr_drop: "CVR 下滑",
  impression_low: "曝光异常",
  impressions_drop: "曝光异常",
  inventory_goal_conflict: "库存目标冲突"
};

const anomalyOptions = [
  { value: "acos_worse", label: "ACOS 异常" },
  { value: "clicks_no_orders", label: "点击多无订单" },
  { value: "spend_spike", label: "花费异常" },
  { value: "cvr_drop", label: "CVR 下滑" },
  { value: "impressions_drop", label: "曝光异常" },
  { value: "inventory_goal_conflict", label: "库存目标冲突" }
];

const severityColors: Record<string, string> = {
  high: "red",
  medium: "orange",
  low: "blue"
};

const severityLabels: Record<string, string> = {
  high: "高风险",
  medium: "中风险",
  low: "低风险"
};

const statusColors: Record<string, string> = {
  pending: "gold",
  observing: "blue",
  handled: "green"
};

const statusLabels: Record<string, string> = {
  pending: "待处理",
  observing: "观察中",
  handled: "已人工处理"
};

const objectTypeLabels: Record<string, string> = {
  keyword: "关键词",
  search_term: "搜索词",
  product: "产品"
};

const suggestionLevelLabels: Record<string, string> = {
  adoptable: "可采纳",
  small_test: "小步测试",
  observe: "观察",
  blocked: "禁止建议"
};

const suggestionLevelColors: Record<string, string> = {
  adoptable: "green",
  small_test: "blue",
  observe: "gold",
  blocked: "red"
};

const suggestionLevelOptions = Object.entries(suggestionLevelLabels).map(([value, label]) => ({ value, label }));

const decisionLabels: Record<DecisionInput["decision_type"], string> = {
  adopt: "采纳建议",
  adopt_with_changes: "修改后采纳",
  reject: "拒绝并记录原因",
  observe: "加入观察",
  handled: "已人工处理"
};

const reviewResultLabels: Record<string, string> = {
  improved: "改善",
  unchanged: "无明显变化",
  worse: "变差"
};

const targetMatchColors: Record<string, string> = {
  matched: "green",
  mismatch: "red",
  unknown: "default"
};

const targetMatchLabels: Record<string, string> = {
  matched: "匹配",
  mismatch: "不匹配",
  unknown: "未判断"
};

const syncStatusLabels: Record<string, string> = {
  running: "同步中",
  success: "同步成功",
  failed: "同步失败"
};

const syncSourceLabels: Record<string, string> = {
  sp_keywords: "SP 关键词报表",
  sp_search_terms: "SP 搜索词报表"
};

const aiModelLabels: Record<string, string> = {
  "rule-placeholder": "规则解释（占位）"
};

function aiModelLabel(model?: string | null): string {
  return model ? aiModelLabels[model] || model : "未记录模型";
}

function formatDateInput(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function defaultDateRange(): { start: string; end: string } {
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - 13);
  return {
    start: formatDateInput(start),
    end: formatDateInput(end)
  };
}

const goalOptions: { value: ProductGoalType; label: string }[] = [
  { value: "test_keywords", label: "测试词款" },
  { value: "scale", label: "放量款" },
  { value: "profit", label: "利润款" },
  { value: "rank_carryover", label: "排名承接款" },
  { value: "clear_inventory", label: "清库存款" },
  { value: "stop_loss", label: "止损款" }
];

type ProductDraft = {
  goal_type?: ProductGoalType;
  note?: string;
  inventory_quantity?: number | null;
  campaign_id?: string;
  rules: ProductRuleInput;
};

function parseJsonText(value: string): string {
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

function parseJsonObject(value: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function parseNullableJsonObject(value: string | null): Record<string, unknown> {
  return value ? parseJsonObject(value) : {};
}

function parseOptionalJson(value?: string): Record<string, unknown> | undefined {
  if (!value?.trim()) {
    return undefined;
  }
  return JSON.parse(value);
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatMoney(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function numberFrom(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

const metricLabels: Record<string, string> = {
  acos: "ACOS",
  cvr: "CVR",
  cost: "花费",
  orders: "订单",
  sales: "销售额",
  clicks: "点击"
};

function formatMetricValue(key: string, value: number): string {
  if (key === "acos" || key === "cvr" || key.endsWith("_rate")) {
    return formatPercent(value);
  }
  return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2);
}

function reviewMetricChanges(review: Review): string[] {
  const before = parseNullableJsonObject(review.before_metrics_json);
  const after = parseNullableJsonObject(review.after_metrics_json);
  return ["acos", "cvr", "cost", "orders", "sales", "clicks"]
    .map((key) => {
      const beforeValue = numberFrom(before[key]);
      const afterValue = numberFrom(after[key]);
      if (beforeValue === null || afterValue === null) {
        return null;
      }
      const direction = afterValue > beforeValue ? "↑" : afterValue < beforeValue ? "↓" : "→";
      return `${metricLabels[key] || key} ${formatMetricValue(key, beforeValue)} ${direction} ${formatMetricValue(key, afterValue)}`;
    })
    .filter((item): item is string => !!item);
}

function anomalySuggestionLevel(anomaly: Anomaly): string {
  const ruleResult = parseJsonObject(anomaly.rule_result_json);
  const value = ruleResult.suggestion_level;
  return typeof value === "string" && value ? value : "observe";
}

function anomalyEvidence(anomaly: Anomaly): Record<string, unknown> {
  return parseJsonObject(anomaly.evidence_json);
}

function anomalyMatchedRules(anomaly: Anomaly): { rule: string; message: string }[] {
  const ruleResult = parseJsonObject(anomaly.rule_result_json);
  const value = ruleResult.matched_rules;
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((item): item is Record<string, unknown> => !!item && typeof item === "object" && !Array.isArray(item))
    .map((item) => ({
      rule: typeof item.rule === "string" ? item.rule : "-",
      message: typeof item.message === "string" ? item.message : "-"
    }));
}

function productGoalLabel(value: unknown): string {
  if (typeof value !== "string") {
    return "-";
  }
  return goalOptions.find((item) => item.value === value)?.label || value;
}

function detailMetrics(evidence: Record<string, unknown>): { label: string; value: string }[] {
  const metricItems: { key: string; label: string; format?: "percent" | "money"; type?: "number" | "text" }[] = [
    { key: "impressions", label: "曝光" },
    { key: "clicks", label: "点击" },
    { key: "cost", label: "花费", format: "money" },
    { key: "orders", label: "订单" },
    { key: "sales", label: "销售额", format: "money" },
    { key: "acos", label: "ACOS", format: "percent" },
    { key: "roas", label: "ROAS" },
    { key: "target_acos", label: "目标 ACOS", format: "percent" },
    { key: "cvr", label: "CVR", format: "percent" },
    { key: "target_cvr", label: "目标 CVR", format: "percent" },
    { key: "bid", label: "竞价", format: "money" },
    { key: "serving_status", label: "投放状态", type: "text" },
    { key: "cpc", label: "CPC", format: "money" },
    { key: "max_cpc", label: "最大 CPC", format: "money" },
    { key: "min_clicks", label: "点击门槛" },
    { key: "min_spend", label: "花费门槛", format: "money" },
    { key: "min_orders", label: "订单门槛" },
    { key: "min_impressions", label: "曝光门槛" },
    { key: "inventory_quantity", label: "当前库存" },
    { key: "inventory_guard", label: "库存阈值" }
  ];
  return metricItems
    .map((item) => {
      if (item.type === "text") {
        const text = evidence[item.key];
        return typeof text === "string" && text.trim() ? { label: item.label, value: text } : null;
      }
      const value = numberFrom(evidence[item.key]);
      if (value === null) {
        return null;
      }
      const formatted = item.format === "percent" ? formatPercent(value) : item.format === "money" ? formatMoney(value) : String(value);
      return { label: item.label, value: formatted };
    })
    .filter((item): item is { label: string; value: string } => !!item);
}

function trendPoint(
  index: number,
  total: number,
  value: number,
  maxValue: number,
  width = 400,
  height = 160,
  padding = 24
): string {
  const x = total <= 1 ? width / 2 : padding + (index * (width - padding * 2)) / (total - 1);
  const y = padding + (1 - value / Math.max(maxValue, 1)) * (height - padding * 2);
  return `${x.toFixed(1)},${y.toFixed(1)}`;
}

export default function App() {
  const { message, modal } = AntApp.useApp();
  const [form] = Form.useForm();
  const [productForm] = Form.useForm<ProductInput>();
  const [batchForm] = Form.useForm();
  const [reviewForm] = Form.useForm();
  const defaultPeriod = useMemo(() => defaultDateRange(), []);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [anomalyMarketId, setAnomalyMarketId] = useState<number | null>(null);
  const [anomalyGoalType, setAnomalyGoalType] = useState<ProductGoalType>();
  const [anomalyType, setAnomalyType] = useState<AnomalyType>();
  const [suggestionLevel, setSuggestionLevel] = useState<SuggestionLevel>();
  const [anomalyStartDate, setAnomalyStartDate] = useState<string | undefined>(defaultPeriod.start);
  const [anomalyEndDate, setAnomalyEndDate] = useState<string | undefined>(defaultPeriod.end);
  const [status, setStatus] = useState<AnomalyStatus>("pending");
  const [generatingAnomalies, setGeneratingAnomalies] = useState(false);
  const [generatingSuggestions, setGeneratingSuggestions] = useState(false);
  const [selected, setSelected] = useState<Anomaly | null>(null);
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null);
  const [suggestionLoading, setSuggestionLoading] = useState(false);
  const [decisionType, setDecisionType] = useState<DecisionInput["decision_type"] | null>(null);
  const [decisionSubmitting, setDecisionSubmitting] = useState(false);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [syncRuns, setSyncRuns] = useState<SyncRun[]>([]);
  const [dashboardLoading, setDashboardLoading] = useState(false);
  const [syncingKeywords, setSyncingKeywords] = useState(false);
  const [syncingAds, setSyncingAds] = useState(false);
  const [syncingSearchTerms, setSyncingSearchTerms] = useState(false);
  const isSyncing = syncingKeywords || syncingAds || syncingSearchTerms;
  const [dashboardMarketId, setDashboardMarketId] = useState<number | null>(null);
  const [dashboardGoalType, setDashboardGoalType] = useState<ProductGoalType>();
  const [dashboardAnomalyType, setDashboardAnomalyType] = useState<AnomalyType>();
  const [dashboardSuggestionLevel, setDashboardSuggestionLevel] = useState<SuggestionLevel>();
  const [dashboardStartDate, setDashboardStartDate] = useState<string | undefined>(defaultPeriod.start);
  const [dashboardEndDate, setDashboardEndDate] = useState<string | undefined>(defaultPeriod.end);
  const [products, setProducts] = useState<Product[]>([]);
  const [productDrafts, setProductDrafts] = useState<Record<number, ProductDraft>>({});
  const [productLoading, setProductLoading] = useState(false);
  const [productMarketId, setProductMarketId] = useState<number | null>(null);
  const [productGoalType, setProductGoalType] = useState<ProductGoalType>();
  const [productAnomalyType, setProductAnomalyType] = useState<AnomalyType>();
  const [productSuggestionLevel, setProductSuggestionLevel] = useState<SuggestionLevel>();
  const [productStartDate, setProductStartDate] = useState<string | undefined>(defaultPeriod.start);
  const [productEndDate, setProductEndDate] = useState<string | undefined>(defaultPeriod.end);
  const [productSavingId, setProductSavingId] = useState<number | null>(null);
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
  const [batchApplyOpen, setBatchApplyOpen] = useState(false);
  const [batchApplying, setBatchApplying] = useState(false);
  const [createProductOpen, setCreateProductOpen] = useState(false);
  const [creatingProduct, setCreatingProduct] = useState(false);
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [decisionFilter, setDecisionFilter] = useState<DecisionInput["decision_type"]>();
  const [decisionMarketId, setDecisionMarketId] = useState<number | null>(null);
  const [decisionGoalType, setDecisionGoalType] = useState<ProductGoalType>();
  const [decisionAnomalyType, setDecisionAnomalyType] = useState<AnomalyType>();
  const [decisionSuggestionLevel, setDecisionSuggestionLevel] = useState<SuggestionLevel>();
  const [decisionOperatorName, setDecisionOperatorName] = useState<string | undefined>();
  const [decisionStartDate, setDecisionStartDate] = useState<string | undefined>(defaultPeriod.start);
  const [decisionEndDate, setDecisionEndDate] = useState<string | undefined>(defaultPeriod.end);
  const [decisionLoading, setDecisionLoading] = useState(false);
  const [reviewDecision, setReviewDecision] = useState<Decision | null>(null);
  const [reviewSubmitting, setReviewSubmitting] = useState(false);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await fetchAnomalies({
        market_id: anomalyMarketId ?? undefined,
        goal_type: anomalyGoalType,
        anomaly_type: anomalyType,
        suggestion_level: suggestionLevel,
        status,
        start_date: anomalyStartDate,
        end_date: anomalyEndDate
      });
      setAnomalies(rows);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载异常队列失败";
      setError(text);
      message.error(text);
    } finally {
      setLoading(false);
    }
  };

  const submitGenerateAnomalies = async () => {
    setGeneratingAnomalies(true);
    try {
      await generateAnomalies({
        market_id: anomalyMarketId ?? undefined,
        start_date: anomalyStartDate,
        end_date: anomalyEndDate
      });
      message.success("异常事件已生成，已重新加载异常与 AI 建议队列");
      await loadData();
      if (activeTab === "dashboard") {
        await loadDashboard();
      }
    } catch (err) {
      const text = err instanceof Error ? err.message : "生成异常事件失败";
      message.error(text);
    } finally {
      setGeneratingAnomalies(false);
    }
  };

  const submitGenerateSuggestions = async () => {
    setGeneratingSuggestions(true);
    try {
      await generateSuggestions({
        market_id: anomalyMarketId ?? undefined,
        anomaly_type: anomalyType,
        status
      });
      message.success("AI 建议已生成，已重新加载建议详情或队列");
      if (selected) {
        const rows = await fetchSuggestions({ anomaly_event_id: selected.id });
        setSuggestion(rows[0] || null);
      } else {
        await loadData();
      }
    } catch (err) {
      const text = err instanceof Error ? err.message : "生成 AI 建议失败";
      message.error(text);
    } finally {
      setGeneratingSuggestions(false);
    }
  };

const buildProductDraft = (product: Product): ProductDraft => ({
  goal_type: product.goal?.goal_type,
  note: product.goal?.note || "",
  inventory_quantity: product.inventory_quantity ?? null,
  campaign_id: "",
  rules: {
      min_clicks: product.rules?.min_clicks ?? null,
      min_spend: product.rules?.min_spend ?? null,
      min_orders: product.rules?.min_orders ?? null,
      target_acos: product.rules?.target_acos ?? null,
      target_cvr: product.rules?.target_cvr ?? null,
      max_cpc: product.rules?.max_cpc ?? null,
      inventory_guard: product.rules?.inventory_guard ?? null
    }
  });

  const loadProducts = async () => {
    setProductLoading(true);
    try {
      const rows = await fetchProducts({
        market_id: productMarketId ?? undefined,
        goal_type: productGoalType,
        anomaly_type: productAnomalyType,
        suggestion_level: productSuggestionLevel,
        start_date: productStartDate,
        end_date: productEndDate
      });
      setProducts(rows);
      setProductDrafts(Object.fromEntries(rows.map((product) => [product.id, buildProductDraft(product)])));
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载产品列表失败";
      message.error(text);
    } finally {
      setProductLoading(false);
    }
  };

  const loadDashboard = async () => {
    setDashboardLoading(true);
    try {
      const filters = {
        market_id: dashboardMarketId ?? undefined,
        goal_type: dashboardGoalType,
        anomaly_type: dashboardAnomalyType,
        suggestion_level: dashboardSuggestionLevel,
        start_date: dashboardStartDate,
        end_date: dashboardEndDate
      };
      const [health, trends, anomalySummary, syncStatus, runs] = await Promise.all([
        fetchDashboardHealth(filters),
        fetchDashboardTrends(filters),
        fetchDashboardAnomalySummary(filters),
        fetchSyncStatus(),
        fetchSyncRuns(5)
      ]);
      setDashboard({
        ...health,
        sync: syncStatus.latest,
        trend: trends.trend,
        anomaly_types: anomalySummary.anomaly_types,
        overview: {
          ...health.overview,
          anomaly_count: anomalySummary.anomaly_count,
          anomaly_product_count: anomalySummary.anomaly_product_count,
          high_risk_count: anomalySummary.high_risk_count,
          pending_suggestion_count: anomalySummary.pending_suggestion_count,
          waste_cost: anomalySummary.waste_cost
        }
      });
      setSyncRuns(runs);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载驾驶舱失败";
      message.error(text);
    } finally {
      setDashboardLoading(false);
    }
  };

  const confirmSync = (type: "keywords" | "ads" | "search_terms") => {
    const title =
      type === "keywords" ? "同步 SP 关键词报表" : type === "ads" ? "同步 SP 广告报表" : "同步 SP 搜索词报表";
    modal.confirm({
      title,
      content: "该操作会请求积加只读 API。本次前端只同步 count=10、max_pages=1，请勿频繁点击。",
      okText: "确认同步",
      cancelText: "取消",
      onOk: async () => {
        if (type === "keywords") {
          setSyncingKeywords(true);
        } else if (type === "ads") {
          setSyncingAds(true);
        } else {
          setSyncingSearchTerms(true);
        }
        try {
          if (type === "keywords") {
            await syncSpKeywords({ market_id: dashboardMarketId ?? undefined });
          } else if (type === "ads") {
            await syncSpAds({ market_id: dashboardMarketId ?? undefined });
          } else {
            await syncSpSearchTerms({ market_id: dashboardMarketId ?? undefined });
          }
          message.success("同步完成");
          await loadDashboard();
        } catch (err) {
          const text = err instanceof Error ? err.message : "同步失败";
          message.error(text);
        } finally {
          if (type === "keywords") {
            setSyncingKeywords(false);
          } else if (type === "ads") {
            setSyncingAds(false);
          } else {
            setSyncingSearchTerms(false);
          }
        }
      }
    });
  };

  const loadDecisions = async () => {
    setDecisionLoading(true);
    try {
      const decisionRows = await fetchDecisions({
        decision_type: decisionFilter,
        market_id: decisionMarketId ?? undefined,
        goal_type: decisionGoalType,
        anomaly_type: decisionAnomalyType,
        suggestion_level: decisionSuggestionLevel,
        operator_name: decisionOperatorName,
        start_date: decisionStartDate,
        end_date: decisionEndDate
      });
      const decisionIds = decisionRows.map((item) => item.id);
      const reviewRows = decisionIds.length ? await fetchReviews({ decision_ids: decisionIds }) : [];
      setDecisions(decisionRows);
      setReviews(reviewRows);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载处理记录失败";
      message.error(text);
    } finally {
      setDecisionLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, [anomalyMarketId, anomalyGoalType, anomalyType, suggestionLevel, status, anomalyStartDate, anomalyEndDate]);

  useEffect(() => {
    void loadProducts();
  }, []);

  useEffect(() => {
    if (activeTab === "dashboard") {
      void loadDashboard();
    }
  }, [
    activeTab,
    dashboardMarketId,
    dashboardGoalType,
    dashboardAnomalyType,
    dashboardSuggestionLevel,
    dashboardStartDate,
    dashboardEndDate
  ]);

  useEffect(() => {
    if (activeTab === "products") {
      void loadProducts();
    }
  }, [activeTab, productMarketId, productGoalType, productAnomalyType, productSuggestionLevel, productStartDate, productEndDate]);

  useEffect(() => {
    if (activeTab === "decisions") {
      void loadDecisions();
    }
  }, [
    activeTab,
    decisionFilter,
    decisionMarketId,
    decisionGoalType,
    decisionAnomalyType,
    decisionSuggestionLevel,
    decisionOperatorName,
    decisionStartDate,
    decisionEndDate
  ]);

  useEffect(() => {
    if (!selected) {
      setSuggestion(null);
      return;
    }

    const loadSuggestion = async () => {
      setSuggestionLoading(true);
      try {
        const rows = await fetchSuggestions({ anomaly_event_id: selected.id });
        setSuggestion(rows[0] || null);
      } catch (err) {
        const text = err instanceof Error ? err.message : "加载 AI 建议失败";
        message.error(text);
      } finally {
        setSuggestionLoading(false);
      }
    };
    void loadSuggestion();
  }, [selected?.id]);

  const selectedSuggestion = selected && suggestion?.anomaly_event_id === selected.id ? suggestion : null;

  const submitDecision = async (payload: DecisionInput) => {
    if (!selectedSuggestion) {
      message.warning("当前异常还没有 AI 建议");
      return;
    }
    setDecisionSubmitting(true);
    try {
      await createDecision(selectedSuggestion.id, payload);
      message.success("人工处理已记录，可在处理记录与复盘查看");
      setDecisionType(null);
      form.resetFields();
      setSelected(null);
      await loadData();
      if (activeTab === "decisions") {
        await loadDecisions();
      }
    } catch (err) {
      const text = err instanceof Error ? err.message : "提交人工处理失败";
      message.error(text);
    } finally {
      setDecisionSubmitting(false);
    }
  };

  const openDecisionModal = (type: DecisionInput["decision_type"]) => {
    setDecisionType(type);
    form.resetFields();
  };

  const updateProductDraft = (productId: number, patch: Partial<Omit<ProductDraft, "rules">>) => {
    setProductDrafts((drafts) => ({
      ...drafts,
      [productId]: {
        ...drafts[productId],
        ...patch,
        rules: drafts[productId]?.rules || {
          min_clicks: null,
          min_spend: null,
          min_orders: null,
          target_acos: null,
          target_cvr: null,
          max_cpc: null,
          inventory_guard: null
        }
      }
    }));
  };

  const updateProductRuleDraft = (productId: number, key: keyof ProductRuleInput, value: number | null) => {
    setProductDrafts((drafts) => ({
      ...drafts,
      [productId]: {
        ...drafts[productId],
        rules: {
          min_clicks: drafts[productId]?.rules.min_clicks ?? null,
          min_spend: drafts[productId]?.rules.min_spend ?? null,
          min_orders: drafts[productId]?.rules.min_orders ?? null,
          target_acos: drafts[productId]?.rules.target_acos ?? null,
          target_cvr: drafts[productId]?.rules.target_cvr ?? null,
          max_cpc: drafts[productId]?.rules.max_cpc ?? null,
          inventory_guard: drafts[productId]?.rules.inventory_guard ?? null,
          [key]: value
        }
      }
    }));
  };

  const saveProductSettings = async (productId: number) => {
    const draft = productDrafts[productId];
    const product = products.find((item) => item.id === productId);
    if (!draft?.goal_type) {
      message.warning("请选择产品目标");
      return;
    }

    setProductSavingId(productId);
    try {
      if (product && draft.inventory_quantity !== product.inventory_quantity) {
        await updateProduct(productId, { inventory_quantity: draft.inventory_quantity ?? null });
      }
      if (draft.campaign_id?.trim()) {
        const result = await bindCampaignToProduct(productId, {
          campaign_id: draft.campaign_id.trim(),
          market_id: product?.market_id ?? undefined
        });
        message.success(`广告活动已绑定：关键词 ${result.keyword_rows_updated} 行，搜索词 ${result.search_term_rows_updated} 行`);
      }
      await updateProductGoal(productId, {
        goal_type: draft.goal_type,
        note: draft.note
      });
      await updateProductRules(productId, draft.rules);
      message.success("产品设置已保存");
      await loadProducts();
    } catch (err) {
      const text = err instanceof Error ? err.message : "保存产品设置失败";
      message.error(text);
    } finally {
      setProductSavingId(null);
    }
  };

  const submitBatchApply = async () => {
    if (!selectedProductIds.length) {
      message.warning("请先选择产品");
      return;
    }

    const ruleKeys: (keyof ProductRuleInput)[] = [
      "min_clicks",
      "min_spend",
      "min_orders",
      "target_acos",
      "target_cvr",
      "max_cpc",
      "inventory_guard"
    ];

    try {
      const values = await batchForm.validateFields();
      const hasGoal = !!values.goal_type;
      const hasRulePatch = ruleKeys.some((key) => values[key] !== undefined && values[key] !== null);
      if (!hasGoal && !hasRulePatch) {
        message.warning("请至少填写一个要批量应用的字段");
        return;
      }

      setBatchApplying(true);
      for (const productId of selectedProductIds) {
        const draft = productDrafts[productId];
        if (hasGoal) {
          await updateProductGoal(productId, {
            goal_type: values.goal_type,
            note: values.note
          });
        }
        if (hasRulePatch) {
          const mergedRules = { ...(draft?.rules || buildProductDraft({} as Product).rules) };
          for (const key of ruleKeys) {
            if (values[key] !== undefined && values[key] !== null) {
              mergedRules[key] = values[key];
            }
          }
          await updateProductRules(productId, mergedRules);
        }
      }
      message.success("批量应用已保存");
      setBatchApplyOpen(false);
      setSelectedProductIds([]);
      batchForm.resetFields();
      await loadProducts();
    } catch (err) {
      const text = err instanceof Error ? err.message : "批量应用失败";
      message.error(text);
    } finally {
      setBatchApplying(false);
    }
  };

  const discardProductChanges = async () => {
    await loadProducts();
    message.success("已放弃未保存更改");
  };

  const submitCreateProduct = async () => {
    try {
      const values = await productForm.validateFields();
      setCreatingProduct(true);
      await createProduct(values);
      message.success("产品已创建");
      setCreateProductOpen(false);
      productForm.resetFields();
      await loadProducts();
    } catch (err) {
      if (err instanceof Error) {
        message.error(err.message);
      }
    } finally {
      setCreatingProduct(false);
    }
  };

  const submitReview = async () => {
    if (!reviewDecision) {
      return;
    }

    try {
      const values = await reviewForm.validateFields();
      const payload: ReviewInput = {
        review_period: values.review_period,
        result: values.result,
        note: values.note,
        before_metrics_json: parseOptionalJson(values.before_metrics_json),
        after_metrics_json: parseOptionalJson(values.after_metrics_json)
      };
      setReviewSubmitting(true);
      await createReview(reviewDecision.id, payload);
      message.success("复盘已记录");
      setReviewDecision(null);
      reviewForm.resetFields();
      await loadDecisions();
    } catch (err) {
      const text = err instanceof SyntaxError ? "指标快照格式不正确，请按示例填写" : err instanceof Error ? err.message : "提交复盘失败";
      message.error(text);
    } finally {
      setReviewSubmitting(false);
    }
  };

  const modalTitle = {
    adopt_with_changes: "修改后采纳",
    reject: "拒绝并记录原因",
    observe: "加入观察",
    adopt: "采纳建议",
    handled: "标记已人工处理"
  }[decisionType || "handled"];

  const displayedAnomalies = useMemo(
    () => anomalies.filter((anomaly) => !suggestionLevel || anomalySuggestionLevel(anomaly) === suggestionLevel),
    [anomalies, suggestionLevel]
  );

  const columns = useMemo<ColumnsType<Anomaly>>(
    () => [
      {
        title: "异常类型",
        dataIndex: "anomaly_type",
        width: 160,
        render: (value: string) => anomalyLabels[value] || value
      },
      {
        title: "建议等级",
        width: 120,
        render: (_, record) => {
          const level = anomalySuggestionLevel(record);
          return <Tag color={suggestionLevelColors[level] || "default"}>{suggestionLevelLabels[level] || level}</Tag>;
        }
      },
      {
        title: "风险等级",
        dataIndex: "severity",
        width: 110,
        render: (value: string) => <Tag color={severityColors[value] || "default"}>{severityLabels[value] || value}</Tag>
      },
      {
        title: "命中对象",
        dataIndex: "object_name",
        ellipsis: true,
        render: (_value, record) => (
          <Space direction="vertical" size={0}>
            <Text strong>{record.object_name || record.object_id || "-"}</Text>
            <Text type="secondary">{objectTypeLabels[record.object_type] || record.object_type}</Text>
            <Text type="secondary" className="object-meta">
              {[
                anomalyEvidence(record).campaign_name || anomalyEvidence(record).campaign_id
                  ? `广告活动: ${anomalyEvidence(record).campaign_name || anomalyEvidence(record).campaign_id}`
                  : null,
                anomalyEvidence(record).ad_group_name || anomalyEvidence(record).ad_group_id
                  ? `广告组: ${anomalyEvidence(record).ad_group_name || anomalyEvidence(record).ad_group_id}`
                  : null,
                anomalyEvidence(record).keyword_text || anomalyEvidence(record).keyword_id
                  ? `关键词: ${anomalyEvidence(record).keyword_text || anomalyEvidence(record).keyword_id}`
                  : null,
                anomalyEvidence(record).search_term
                  ? `搜索词: ${anomalyEvidence(record).search_term}`
                  : null
              ]
                .filter(Boolean)
                .join(" / ")}
            </Text>
          </Space>
        )
      },
      {
        title: "产品目标",
        width: 130,
        render: (_, record) => {
          const goal = anomalyEvidence(record).product_goal;
          const label = goalOptions.find((item) => item.value === goal)?.label;
          return label || (typeof goal === "string" ? goal : "-");
        }
      },
      {
        title: "关键指标",
        width: 300,
        render: (_, record) => {
          const evidence = anomalyEvidence(record);
          const rawMetrics = [
            { label: "点击", value: evidence.clicks },
            { label: "花费", value: evidence.cost },
            { label: "订单", value: evidence.orders },
            { label: "ACOS", value: numberFrom(evidence.acos) === null ? null : formatPercent(numberFrom(evidence.acos) || 0) },
            { label: "CVR", value: numberFrom(evidence.cvr) === null ? null : formatPercent(numberFrom(evidence.cvr) || 0) },
            { label: "曝光", value: evidence.impressions }
          ];
          const metrics = rawMetrics
            .filter((item) => item.value !== null && item.value !== undefined)
            .map((item) => ({ label: item.label, value: String(item.value) }));
          return (
            <Space wrap size={[4, 4]} className="metric-pills">
              {metrics.map((item) => (
                <Tag key={item.label}>
                  {item.label} {item.value}
                </Tag>
              ))}
            </Space>
          );
        }
      },
      {
        title: "产品",
        dataIndex: "product_id",
        width: 110,
        render: (value: number | null) => value ?? "-"
      },
      {
        title: "店铺 / 站点",
        dataIndex: "market_id",
        width: 100,
        render: (value: number | null) => value ?? "-"
      },
      {
        title: "状态",
        dataIndex: "status",
        width: 120,
        render: (value: string) => <Tag color={statusColors[value] || "default"}>{statusLabels[value] || value}</Tag>
      },
      {
        title: "周期",
        width: 210,
        render: (_, record) => `${record.period_start} 至 ${record.period_end}`
      },
      {
        title: "",
        width: 72,
        align: "right",
        render: (_, record) => (
          <Button
            aria-label="进入详情页"
            icon={<EyeOutlined />}
            onClick={() => setSelected(record)}
            title="进入详情页"
          />
        )
      }
    ],
    []
  );

  const productColumns = useMemo<ColumnsType<Product>>(
    () => [
      {
        title: "ASIN / MSKU / 产品名称",
        dataIndex: "product_name",
        width: 260,
        fixed: "left",
        render: (_value, record) => (
          <Space direction="vertical" size={0}>
            <Text strong>{record.product_name || record.asin || record.msku || `产品 ${record.id}`}</Text>
            <Text type="secondary">
              ASIN {record.asin || "-"} / MSKU {record.msku || "-"}
            </Text>
          </Space>
        )
      },
      {
        title: "店铺 / 站点",
        dataIndex: "market_id",
        width: 90,
        render: (value: number | null) => value ?? "-"
      },
      {
        title: "SP 花费",
        width: 110,
        render: (_, record) => formatMoney(record.sp_metrics.cost)
      },
      {
        title: "订单",
        width: 90,
        render: (_, record) => record.sp_metrics.orders.toLocaleString()
      },
      {
        title: "ACOS",
        width: 100,
        render: (_, record) => formatPercent(record.sp_metrics.acos)
      },
      {
        title: "CVR",
        width: 100,
        render: (_, record) => formatPercent(record.sp_metrics.cvr)
      },
      {
        title: "库存状态",
        width: 100,
        render: (_, record) => <Tag>{record.inventory_status}</Tag>
      },
      {
        title: "当前库存",
        width: 120,
        render: (_, record) => {
          const draft = productDrafts[record.id] || buildProductDraft(record);
          return (
            <InputNumber
              className="table-control"
              min={0}
              precision={0}
              value={draft.inventory_quantity}
              onChange={(value) => updateProductDraft(record.id, { inventory_quantity: value })}
            />
          );
        }
      },
      {
        title: "绑定广告活动",
        width: 170,
        render: (_, record) => {
          const draft = productDrafts[record.id] || buildProductDraft(record);
          return (
            <Input
              value={draft.campaign_id}
              placeholder="广告活动 ID"
              onChange={(event) => updateProductDraft(record.id, { campaign_id: event.target.value })}
            />
          );
        }
      },
      {
        title: "目标与数据表现是否匹配",
        width: 180,
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Tag color={targetMatchColors[record.target_match.status]}>
              {targetMatchLabels[record.target_match.status] || record.target_match.status}
            </Tag>
            <Text type="secondary" className="compact-note">
              {record.target_match.reason}
            </Text>
          </Space>
        )
      },
      {
        title: "产品目标",
        width: 170,
        render: (_, record) => {
          const draft = productDrafts[record.id] || buildProductDraft(record);
          return (
            <Select
              className="table-control"
              placeholder="选择目标"
              value={draft.goal_type}
              options={goalOptions}
              onChange={(value) => updateProductDraft(record.id, { goal_type: value })}
            />
          );
        }
      },
      {
        title: "目标 ACOS",
        width: 130,
        render: (_, record) => {
          const draft = productDrafts[record.id] || buildProductDraft(record);
          return (
            <InputNumber
              className="table-control"
              min={0}
              step={0.05}
              value={draft.rules.target_acos}
              placeholder="0.3"
              onChange={(value) => updateProductRuleDraft(record.id, "target_acos", value)}
            />
          );
        }
      },
      {
        title: "目标 CVR",
        width: 130,
        render: (_, record) => {
          const draft = productDrafts[record.id] || buildProductDraft(record);
          return (
            <InputNumber
              className="table-control"
              min={0}
              step={0.01}
              value={draft.rules.target_cvr}
              placeholder="0.08"
              onChange={(value) => updateProductRuleDraft(record.id, "target_cvr", value)}
            />
          );
        }
      },
      {
        title: "最小点击",
        width: 120,
        render: (_, record) => {
          const draft = productDrafts[record.id] || buildProductDraft(record);
          return (
            <InputNumber
              className="table-control"
              min={0}
              precision={0}
              value={draft.rules.min_clicks}
              onChange={(value) => updateProductRuleDraft(record.id, "min_clicks", value)}
            />
          );
        }
      },
      {
        title: "最小花费",
        width: 120,
        render: (_, record) => {
          const draft = productDrafts[record.id] || buildProductDraft(record);
          return (
            <InputNumber
              className="table-control"
              min={0}
              step={1}
              value={draft.rules.min_spend}
              onChange={(value) => updateProductRuleDraft(record.id, "min_spend", value)}
            />
          );
        }
      },
      {
        title: "最小订单",
        width: 120,
        render: (_, record) => {
          const draft = productDrafts[record.id] || buildProductDraft(record);
          return (
            <InputNumber
              className="table-control"
              min={0}
              precision={0}
              value={draft.rules.min_orders}
              onChange={(value) => updateProductRuleDraft(record.id, "min_orders", value)}
            />
          );
        }
      },
      {
        title: "最大 CPC",
        width: 120,
        render: (_, record) => {
          const draft = productDrafts[record.id] || buildProductDraft(record);
          return (
            <InputNumber
              className="table-control"
              min={0}
              step={0.1}
              value={draft.rules.max_cpc}
              onChange={(value) => updateProductRuleDraft(record.id, "max_cpc", value)}
            />
          );
        }
      },
      {
        title: "库存阈值",
        width: 120,
        render: (_, record) => {
          const draft = productDrafts[record.id] || buildProductDraft(record);
          return (
            <InputNumber
              className="table-control"
              min={0}
              precision={0}
              value={draft.rules.inventory_guard}
              onChange={(value) => updateProductRuleDraft(record.id, "inventory_guard", value)}
            />
          );
        }
      },
      {
        title: "备注",
        width: 220,
        render: (_, record) => {
          const draft = productDrafts[record.id] || buildProductDraft(record);
          return (
            <Input
              value={draft.note}
              placeholder="目标说明"
              onChange={(event) => updateProductDraft(record.id, { note: event.target.value })}
            />
          );
        }
      },
      {
        title: "",
        width: 100,
        align: "right",
        fixed: "right",
        render: (_, record) => (
          <Button
            icon={<SaveOutlined />}
            loading={productSavingId === record.id}
            onClick={() => void saveProductSettings(record.id)}
          >
            保存设置
          </Button>
        )
      }
    ],
    [productDrafts, productSavingId]
  );

  const reviewsByDecision = useMemo(() => {
    const grouped: Record<number, Review[]> = {};
    for (const review of reviews) {
      grouped[review.manual_decision_id] = [...(grouped[review.manual_decision_id] || []), review];
    }
    return grouped;
  }, [reviews]);

  const decisionColumns = useMemo<ColumnsType<Decision>>(
    () => [
      {
        title: "人工处理结果",
        dataIndex: "decision_type",
        width: 140,
        render: (value: DecisionInput["decision_type"]) => <Tag>{decisionLabels[value] || value}</Tag>
      },
      {
        title: "原建议",
        width: 300,
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Text strong>{record.suggestion?.title || `建议 ${record.suggestion_id}`}</Text>
            <Text type="secondary" className="object-meta">
              {record.suggestion?.suggested_action || "-"}
            </Text>
            {record.suggestion?.suggestion_level ? (
              <Tag color={suggestionLevelColors[record.suggestion.suggestion_level] || "default"}>
                {suggestionLevelLabels[record.suggestion.suggestion_level] || record.suggestion.suggestion_level}
              </Tag>
            ) : null}
          </Space>
        )
      },
      {
        title: "处理人",
        width: 180,
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            {record.observe_period ? <Text type="secondary">观察周期：{record.observe_period === "7d" ? "7 天" : "14 天"}</Text> : null}
            <Text type="secondary">处理人：{record.operator_name || "-"}</Text>
          </Space>
        )
      },
      {
        title: "修改内容",
        width: 220,
        ellipsis: true,
        render: (_, record) => record.modified_action || "-"
      },
      {
        title: "拒绝原因",
        width: 220,
        ellipsis: true,
        render: (_, record) => record.reason || "-"
      },
      {
        title: "处理时间",
        dataIndex: "decided_at",
        width: 190,
        render: (value: string) => new Date(value).toLocaleString()
      },
      {
        title: "复盘状态",
        width: 220,
        render: (_, record) => {
          const rowReviews = reviewsByDecision[record.id] || [];
          return (
            <Space wrap>
              {["7d", "14d"].map((period) => {
                const review = rowReviews.find((item) => item.review_period === period);
                return (
                  <Tag key={period} color={review ? "green" : "default"}>
                    {period === "7d" ? "7 天复盘" : "14 天复盘"}{" "}
                    {review ? reviewResultLabels[review.result || ""] || review.result || "已复盘" : "未复盘"}
                  </Tag>
                );
              })}
            </Space>
          );
        }
      },
      {
        title: "复盘指标变化",
        width: 280,
        render: (_, record) => {
          const rowReviews = reviewsByDecision[record.id] || [];
          const latestReview = rowReviews[0];
          const changes = latestReview ? reviewMetricChanges(latestReview) : [];
          return changes.length ? (
            <Space wrap size={[4, 4]} className="metric-pills">
              {changes.map((change) => (
                <Tag key={change}>{change}</Tag>
              ))}
            </Space>
          ) : (
            <Text type="secondary">暂无复盘指标变化</Text>
          );
        }
      },
      {
        title: "",
        width: 100,
        align: "right",
        render: (_, record) => (
          <Button
            icon={<AuditOutlined />}
            onClick={() => {
              const existingReview = (reviewsByDecision[record.id] || [])[0];
              setReviewDecision(record);
              reviewForm.resetFields();
              reviewForm.setFieldsValue({
                review_period: existingReview?.review_period || "7d",
                result: existingReview?.result || "improved",
                note: existingReview?.note || undefined,
                before_metrics_json: existingReview?.before_metrics_json
                  ? parseJsonText(existingReview.before_metrics_json)
                  : record.suggestion?.evidence_json
                    ? parseJsonText(record.suggestion.evidence_json)
                    : undefined,
                after_metrics_json: existingReview?.after_metrics_json ? parseJsonText(existingReview.after_metrics_json) : undefined
              });
            }}
          >
            复盘
          </Button>
        )
      }
    ],
    [reviewForm, reviewsByDecision]
  );

  const trendChart = useMemo(() => {
    const rows = dashboard?.trend || [];
    const costMax = Math.max(...rows.map((item) => item.cost), 1);
    const acosMax = Math.max(...rows.map((item) => item.acos), 1);
    const cvrMax = Math.max(...rows.map((item) => item.cvr), 1);
    const costPoints = rows.map((item, index) => trendPoint(index, rows.length, item.cost, costMax)).join(" ");
    const costArea = rows.length
      ? `24,136 ${costPoints} ${rows.length <= 1 ? "200,136" : "376,136"}`
      : "";
    return {
      costArea,
      costPoints,
      acosPoints: rows.map((item, index) => trendPoint(index, rows.length, item.acos, acosMax)).join(" "),
      cvrPoints: rows.map((item, index) => trendPoint(index, rows.length, item.cvr, cvrMax)).join(" "),
      startDate: rows[0]?.date || "",
      endDate: rows[rows.length - 1]?.date || "",
      costMax,
      acosMax,
      cvrMax
    };
  }, [dashboard]);
  const anomalyMaxCount = Math.max(...(dashboard?.anomaly_types.map((item) => item.count) || [0]), 1);
  const metricTiles = dashboard
    ? [
        { label: "指标行数", value: dashboard.overview.metric_rows.toLocaleString() },
        { label: "曝光", value: dashboard.overview.impressions.toLocaleString() },
        { label: "点击", value: dashboard.overview.clicks.toLocaleString() },
        { label: "花费", value: formatMoney(dashboard.overview.cost) },
        { label: "订单", value: dashboard.overview.orders.toLocaleString() },
        { label: "销售额", value: formatMoney(dashboard.overview.sales) },
        { label: "ACOS", value: formatPercent(dashboard.overview.acos) },
        { label: "CVR", value: formatPercent(dashboard.overview.cvr) },
        { label: "异常产品数量", value: dashboard.overview.anomaly_product_count.toLocaleString() },
        { label: "待处理建议数量", value: dashboard.overview.pending_suggestion_count.toLocaleString() },
        { label: "高风险异常", value: dashboard.overview.high_risk_count.toLocaleString() },
        { label: "浪费花费", value: formatMoney(dashboard.overview.waste_cost) },
        { label: "异常总数", value: dashboard.overview.anomaly_count.toLocaleString() }
      ]
    : [];

  const activeTitle =
    activeTab === "dashboard"
      ? "广告健康驾驶舱"
      : activeTab === "products"
      ? "产品目标与规则设置"
      : activeTab === "decisions"
        ? "处理记录与复盘"
        : "异常与 AI 建议队列";

  const activeDescription =
    activeTab === "dashboard"
      ? "近 14 天 SP 广告健康概览，优先暴露异常和待处理事项。"
      : activeTab === "products"
      ? "人工维护产品经营目标和规则门槛，供规则引擎使用。"
      : activeTab === "decisions"
        ? "记录人工判断，并跟踪 7 天 / 14 天复盘。"
        : "SP 广告异常规则结果，供运营复核和后续处理。";

  const selectedEvidence = selected ? anomalyEvidence(selected) : {};
  const selectedMatchedRules = selected ? anomalyMatchedRules(selected) : [];
  const selectedLevel = selected ? anomalySuggestionLevel(selected) : "observe";
  const selectedDetailMetrics = selected ? detailMetrics(selectedEvidence) : [];
  const selectedDrawerTitle = selected
    ? `建议详情与溯源：${selectedSuggestion?.title || anomalyLabels[selected.anomaly_type] || selected.anomaly_type}`
    : "建议详情与溯源";

  const openAnomalyQueueFromDashboard = () => {
    setAnomalyMarketId(dashboardMarketId);
    setAnomalyGoalType(dashboardGoalType);
    setAnomalyType(dashboardAnomalyType);
    setSuggestionLevel(dashboardSuggestionLevel);
    setAnomalyStartDate(dashboardStartDate);
    setAnomalyEndDate(dashboardEndDate);
    setActiveTab("anomalies");
  };

  return (
    <AntApp>
      <main className="page">
        <section className="toolbar-band">
          <div className="toolbar">
            <div>
              <Title level={3} className="page-title">
                {activeTitle}
              </Title>
              <Text type="secondary">{activeDescription}</Text>
            </div>
            <Space wrap>
              {activeTab === "dashboard" ? (
                <>
                  <InputNumber
                    className="filter"
                    min={1}
                    precision={0}
                    placeholder="店铺 / 站点 ID"
                    value={dashboardMarketId}
                    onChange={setDashboardMarketId}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="产品目标"
                    value={dashboardGoalType}
                    onChange={setDashboardGoalType}
                    options={goalOptions}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="异常类型"
                    value={dashboardAnomalyType}
                    onChange={setDashboardAnomalyType}
                    options={anomalyOptions}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="建议等级"
                    value={dashboardSuggestionLevel}
                    onChange={setDashboardSuggestionLevel}
                    options={suggestionLevelOptions}
                  />
                  <Input
                    className="filter"
                    placeholder="时间周期开始"
                    value={dashboardStartDate}
                    onChange={(event) => setDashboardStartDate(event.target.value || undefined)}
                  />
                  <Input
                    className="filter"
                    placeholder="时间周期结束"
                    value={dashboardEndDate}
                    onChange={(event) => setDashboardEndDate(event.target.value || undefined)}
                  />
                  <Button icon={<ReloadOutlined />} onClick={loadDashboard} loading={dashboardLoading} title="刷新">
                    刷新
                  </Button>
                  <Button onClick={() => confirmSync("keywords")} loading={syncingKeywords} disabled={isSyncing && !syncingKeywords}>
                    同步关键词
                  </Button>
                  <Button onClick={() => confirmSync("ads")} loading={syncingAds} disabled={isSyncing && !syncingAds}>
                    同步广告
                  </Button>
                  <Button onClick={() => confirmSync("search_terms")} loading={syncingSearchTerms} disabled={isSyncing && !syncingSearchTerms}>
                    同步搜索词
                  </Button>
                </>
              ) : activeTab === "products" ? (
                <>
                  <Button icon={<PlusOutlined />} type="primary" onClick={() => setCreateProductOpen(true)}>
                    新增产品
                  </Button>
                  <Button disabled={!selectedProductIds.length} onClick={() => setBatchApplyOpen(true)}>
                    批量应用
                  </Button>
                  <Button onClick={() => void discardProductChanges()}>
                    放弃更改
                  </Button>
                  <InputNumber
                    className="filter"
                    min={1}
                    precision={0}
                    placeholder="店铺 / 站点 ID"
                    value={productMarketId}
                    onChange={setProductMarketId}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="产品目标"
                    value={productGoalType}
                    onChange={setProductGoalType}
                    options={goalOptions}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="异常类型"
                    value={productAnomalyType}
                    onChange={setProductAnomalyType}
                    options={anomalyOptions}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="建议等级"
                    value={productSuggestionLevel}
                    onChange={setProductSuggestionLevel}
                    options={suggestionLevelOptions}
                  />
                  <Input
                    className="filter"
                    placeholder="时间周期开始"
                    value={productStartDate}
                    onChange={(event) => setProductStartDate(event.target.value || undefined)}
                  />
                  <Input
                    className="filter"
                    placeholder="时间周期结束"
                    value={productEndDate}
                    onChange={(event) => setProductEndDate(event.target.value || undefined)}
                  />
                  <Button icon={<ReloadOutlined />} onClick={loadProducts} loading={productLoading} title="刷新">
                    刷新
                  </Button>
                </>
              ) : activeTab === "decisions" ? (
                <>
                  <InputNumber
                    className="filter"
                    min={1}
                    precision={0}
                    placeholder="店铺 / 站点 ID"
                    value={decisionMarketId}
                    onChange={setDecisionMarketId}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="产品目标"
                    value={decisionGoalType}
                    onChange={setDecisionGoalType}
                    options={goalOptions}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="异常类型"
                    value={decisionAnomalyType}
                    onChange={setDecisionAnomalyType}
                    options={anomalyOptions}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="建议等级"
                    value={decisionSuggestionLevel}
                    onChange={setDecisionSuggestionLevel}
                    options={suggestionLevelOptions}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="处理类型"
                    value={decisionFilter}
                    onChange={setDecisionFilter}
                    options={[
                      { value: "adopt", label: "采纳建议" },
                      { value: "adopt_with_changes", label: "修改后采纳" },
                      { value: "reject", label: "拒绝并记录原因" },
                      { value: "observe", label: "加入观察" },
                      { value: "handled", label: "已人工处理" }
                    ]}
                  />
                  <Input
                    className="filter"
                    placeholder="处理人"
                    value={decisionOperatorName}
                    onChange={(event) => setDecisionOperatorName(event.target.value || undefined)}
                  />
                  <Input
                    className="filter"
                    placeholder="时间周期开始"
                    value={decisionStartDate}
                    onChange={(event) => setDecisionStartDate(event.target.value || undefined)}
                  />
                  <Input
                    className="filter"
                    placeholder="时间周期结束"
                    value={decisionEndDate}
                    onChange={(event) => setDecisionEndDate(event.target.value || undefined)}
                  />
                  <Button icon={<ReloadOutlined />} onClick={loadDecisions} loading={decisionLoading} title="刷新">
                    刷新
                  </Button>
                </>
              ) : (
                <>
                  <InputNumber
                    className="filter"
                    min={1}
                    precision={0}
                    placeholder="店铺 / 站点 ID"
                    value={anomalyMarketId}
                    onChange={setAnomalyMarketId}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="产品目标"
                    value={anomalyGoalType}
                    onChange={setAnomalyGoalType}
                    options={goalOptions}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="异常类型"
                    value={anomalyType}
                    onChange={setAnomalyType}
                    options={anomalyOptions}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="建议等级"
                    value={suggestionLevel}
                    onChange={setSuggestionLevel}
                    options={suggestionLevelOptions}
                  />
                  <Select
                    className="filter"
                    placeholder="状态"
                    value={status}
                    onChange={setStatus}
                    options={[
                      { value: "pending", label: "待处理" },
                      { value: "observing", label: "观察中" },
                      { value: "handled", label: "已人工处理" }
                    ]}
                  />
                  <Input
                    className="filter"
                    placeholder="时间周期开始"
                    value={anomalyStartDate}
                    onChange={(event) => setAnomalyStartDate(event.target.value || undefined)}
                  />
                  <Input
                    className="filter"
                    placeholder="时间周期结束"
                    value={anomalyEndDate}
                    onChange={(event) => setAnomalyEndDate(event.target.value || undefined)}
                  />
                  <Button icon={<ReloadOutlined />} onClick={() => void submitGenerateAnomalies()} loading={generatingAnomalies}>
                    生成异常事件
                  </Button>
                  <Button icon={<ReloadOutlined />} onClick={() => void submitGenerateSuggestions()} loading={generatingSuggestions}>
                    生成 AI 建议
                  </Button>
                  <Button icon={<ReloadOutlined />} onClick={loadData} loading={loading} title="刷新">
                    刷新
                  </Button>
                </>
              )}
            </Space>
          </div>
        </section>

        <section className="content">
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={[
              {
                key: "dashboard",
                label: "广告健康驾驶舱",
                children: (
                  <Spin spinning={dashboardLoading}>
                    {dashboard ? (
                      <Space direction="vertical" size={16} className="dashboard">
                        <section className="sync-band">
                          <Space direction="vertical" size={10} className="drawer-body">
                            <Space wrap size={16}>
                              <Text strong>同步状态</Text>
                              {dashboard.sync ? (
                                <>
                                  <Tag color={dashboard.sync.status === "success" ? "green" : "orange"}>
                                    {syncStatusLabels[dashboard.sync.status] || dashboard.sync.status}
                                  </Tag>
                                  <Text type="secondary">店铺 / 站点 {dashboard.sync.market_id}</Text>
                                  <Text type="secondary">
                                    {dashboard.sync.period_start} 至 {dashboard.sync.period_end}
                                  </Text>
                                  <Text type="secondary">写入 {dashboard.sync.rows_synced} 行</Text>
                                </>
                              ) : (
                                <Text type="secondary">暂无同步记录</Text>
                              )}
                              <Text type="secondary">
                                统计周期 {dashboard.period.start} 至 {dashboard.period.end}
                              </Text>
                              <Button size="small" onClick={openAnomalyQueueFromDashboard}>
                                查看异常队列
                              </Button>
                            </Space>
                            {syncRuns.length ? (
                              <div className="sync-history">
                                {syncRuns.map((run) => (
                                  <div className="sync-history-row" key={run.id}>
                                    <Tag color={run.status === "success" ? "green" : run.status === "failed" ? "red" : "orange"}>
                                      {syncStatusLabels[run.status] || run.status}
                                    </Tag>
                                    <Text>{syncSourceLabels[run.source] || run.source}</Text>
                                    <Text type="secondary">店铺 / 站点 {run.market_id}</Text>
                                    <Text type="secondary">{run.period_start} 至 {run.period_end}</Text>
                                    <Text type="secondary">写入 {run.rows_synced} 行</Text>
                                    <Text type="secondary">{run.finished_at || run.started_at}</Text>
                                  </div>
                                ))}
                              </div>
                            ) : null}
                          </Space>
                        </section>
                        <section className="metric-grid">
                          {metricTiles.map((tile) => (
                            <Card key={tile.label} size="small">
                              <Text type="secondary">{tile.label}</Text>
                              <div className="metric-value">{tile.value}</div>
                            </Card>
                          ))}
                        </section>
                        <section className="dashboard-grid">
                          <Card title="ACOS / CVR / 花费趋势" size="small">
                            {dashboard.trend.length ? (
                              <div className="trend-chart">
                                <svg viewBox="0 0 400 160" role="img" aria-label="ACOS、CVR 和花费趋势">
                                  <line x1="24" y1="136" x2="376" y2="136" className="chart-axis" />
                                  <line x1="24" y1="24" x2="24" y2="136" className="chart-axis" />
                                  <polygon points={trendChart.costArea} className="chart-cost-area" />
                                  <polyline points={trendChart.costPoints} className="chart-cost-line" />
                                  <polyline points={trendChart.acosPoints} className="chart-acos-line" />
                                  <polyline points={trendChart.cvrPoints} className="chart-cvr-line" />
                                </svg>
                                <div className="chart-legend">
                                  <span><i className="legend-dot cost" />花费峰值 {formatMoney(trendChart.costMax)}</span>
                                  <span><i className="legend-dot acos" />ACOS 峰值 {formatPercent(trendChart.acosMax)}</span>
                                  <span><i className="legend-dot cvr" />CVR 峰值 {formatPercent(trendChart.cvrMax)}</span>
                                </div>
                                <div className="chart-dates">
                                  <Text type="secondary">{trendChart.startDate}</Text>
                                  <Text type="secondary">{trendChart.endDate}</Text>
                                </div>
                              </div>
                            ) : (
                              <Empty description="暂无趋势数据" />
                            )}
                          </Card>
                          <Card title="异常类型分布" size="small">
                            {dashboard.anomaly_types.length ? (
                              <Space direction="vertical" className="drawer-body" size={10}>
                                {dashboard.anomaly_types.map((item) => (
                                  <div className="anomaly-type-row" key={item.anomaly_type}>
                                    <div className="anomaly-type-label">
                                      <Text>{anomalyLabels[item.anomaly_type] || item.anomaly_type}</Text>
                                      <Tag>{item.count}</Tag>
                                    </div>
                                    <div className="anomaly-type-bar-track">
                                      <div
                                        className="anomaly-type-bar"
                                        style={{ width: `${Math.max((item.count / anomalyMaxCount) * 100, 6)}%` }}
                                      />
                                    </div>
                                  </div>
                                ))}
                              </Space>
                            ) : (
                              <Empty description="暂无异常" />
                            )}
                          </Card>
                        </section>
                      </Space>
                    ) : (
                      <Empty description="暂无驾驶舱数据" />
                    )}
                  </Spin>
                )
              },
              {
                key: "anomalies",
                label: "异常与 AI 建议队列",
                children: (
                  <>
                    {error ? <Alert className="alert" type="error" message={error} showIcon /> : null}
                    <Table
                      rowKey="id"
                      loading={loading}
                      columns={columns}
                      dataSource={displayedAnomalies}
                      pagination={{ pageSize: 10, showSizeChanger: false }}
                      locale={{ emptyText: <Empty description="暂无异常" /> }}
                      scroll={{ x: 1400 }}
                    />
                  </>
                )
              },
              {
                key: "products",
                label: "产品设置",
                children: (
                  <Table
                    rowKey="id"
                    loading={productLoading}
                    columns={productColumns}
                    dataSource={products}
                    rowSelection={{
                      selectedRowKeys: selectedProductIds,
                      onChange: (keys) => setSelectedProductIds(keys.map((key) => Number(key)))
                    }}
                    pagination={{ pageSize: 10, showSizeChanger: false }}
                    locale={{ emptyText: <Empty description="暂无产品，请先新增产品" /> }}
                    scroll={{ x: 2380 }}
                  />
                )
              },
              {
                key: "decisions",
                label: "处理记录与复盘",
                children: (
                  <Table
                    rowKey="id"
                    loading={decisionLoading}
                    columns={decisionColumns}
                    dataSource={decisions}
                    pagination={{ pageSize: 10, showSizeChanger: false }}
                    locale={{ emptyText: <Empty description="暂无处理记录" /> }}
                    scroll={{ x: 1760 }}
                  />
                )
              }
            ]}
          />
        </section>

        <Drawer
          title={selectedDrawerTitle}
          open={!!selected}
          onClose={() => setSelected(null)}
          width={720}
        >
          {selected ? (
            <Space direction="vertical" size={16} className="drawer-body">
              <Space wrap>
                <Tag color={severityColors[selected.severity] || "default"}>
                  风险等级 {severityLabels[selected.severity] || selected.severity}
                </Tag>
                <Tag color={statusColors[selected.status] || "default"}>{statusLabels[selected.status] || selected.status}</Tag>
                <Tag color={suggestionLevelColors[selectedLevel] || "default"}>
                  建议等级 {suggestionLevelLabels[selectedLevel] || selectedLevel}
                </Tag>
                <Text type="secondary">异常类型 {anomalyLabels[selected.anomaly_type] || selected.anomaly_type}</Text>
                <Text type="secondary">产品目标 {productGoalLabel(selectedEvidence.product_goal)}</Text>
                <Text type="secondary">产品 {selected.product_id ?? "-"}</Text>
                <Text type="secondary">店铺 / 站点 {selected.market_id ?? "-"}</Text>
              </Space>
              <section>
                <Text strong>命中对象</Text>
                <div className="object-name">{selected.object_name || selected.object_id || "-"}</div>
                <div className="source-line">
                  广告活动: {String(selectedEvidence.campaign_name || selectedEvidence.campaign_id || "-")} / 广告组:{" "}
                  {String(selectedEvidence.ad_group_name || selectedEvidence.ad_group_id || "-")}
                </div>
                <div className="source-line">
                  关键词: {String(selectedEvidence.keyword_text || selectedEvidence.keyword_id || "-")} / 搜索词:{" "}
                  {String(selectedEvidence.search_term || "-")}
                </div>
              </section>
              <section>
                <Text strong>指标快照 / 数据快照</Text>
                {selectedDetailMetrics.length ? (
                  <div className="detail-metric-grid">
                    {selectedDetailMetrics.map((item) => (
                      <div className="detail-metric" key={item.label}>
                        <Text type="secondary">{item.label}</Text>
                        <Text strong>{item.value}</Text>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="source-line">暂无指标快照 / 数据快照</div>
                )}
              </section>
              <Divider className="drawer-divider" />
              <section className="suggestion-panel">
                <div className="section-title">AI 建议</div>
                {suggestionLoading ? (
                  <Spin />
                ) : selectedSuggestion ? (
                  <Space direction="vertical" size={10} className="drawer-body">
                    <Space wrap>
                      <Tag color={suggestionLevelColors[selectedSuggestion.suggestion_level] || "default"}>
                        {suggestionLevelLabels[selectedSuggestion.suggestion_level] || selectedSuggestion.suggestion_level}
                      </Tag>
                      <Text type="secondary">{aiModelLabel(selectedSuggestion.ai_model)}</Text>
                    </Space>
                    <div className="suggestion-block">
                      <Text strong>建议标题</Text>
                      <div>{selectedSuggestion.title || "未命名建议"}</div>
                    </div>
                    <Text>{selectedSuggestion.summary || "暂无摘要"}</Text>
                    <div className="suggestion-block">
                      <Text strong>建议动作</Text>
                      <div>{selectedSuggestion.suggested_action}</div>
                    </div>
                    <div className="suggestion-block">
                      <Text strong>推荐人工动作</Text>
                      <div>
                        {selectedSuggestion.recommended_manual_decision
                          ? decisionLabels[selectedSuggestion.recommended_manual_decision] || selectedSuggestion.recommended_manual_decision
                          : "-"}
                      </div>
                    </div>
                    <div className="suggestion-block">
                      <Text strong>AI 解释</Text>
                      <div>{selectedSuggestion.reasoning || "暂无 AI 解释"}</div>
                    </div>
                    <div className="suggestion-block">
                      <Text strong>风险提示 / 风险说明</Text>
                      <div>{selectedSuggestion.risk_note || "暂无风险提示 / 风险说明"}</div>
                    </div>
                    <div className="suggestion-block">
                      <Text strong>证据摘要</Text>
                      <div>{selectedSuggestion.evidence_summary || "暂无证据摘要"}</div>
                    </div>
                    <Text strong>人工处理按钮 / 人工处理动作</Text>
                    <Space wrap className="decision-actions">
                      <Button
                        type="primary"
                        onClick={() => openDecisionModal("adopt")}
                        loading={decisionSubmitting}
                        disabled={selectedSuggestion.suggestion_level === "blocked"}
                      >
                        采纳建议
                      </Button>
                      <Button
                        onClick={() => openDecisionModal("adopt_with_changes")}
                        disabled={selectedSuggestion.suggestion_level === "blocked"}
                      >
                        修改后采纳
                      </Button>
                      <Button danger onClick={() => openDecisionModal("reject")}>
                        拒绝并记录原因
                      </Button>
                      <Button onClick={() => openDecisionModal("observe")}>加入观察</Button>
                      <Button onClick={() => openDecisionModal("handled")}>
                        标记已人工处理
                      </Button>
                    </Space>
                  </Space>
                ) : (
                  <Alert type="warning" showIcon message="当前异常还没有生成 AI 建议" />
                )}
              </section>
              <Divider className="drawer-divider" />
              <section>
                <Text strong>命中规则 / 规则判定结果</Text>
                {selectedMatchedRules.length ? (
                  <Space direction="vertical" className="drawer-body">
                    {selectedMatchedRules.map((rule) => (
                      <div className="rule-row" key={rule.rule}>
                        <Tag>{rule.rule}</Tag>
                        <Text>{rule.message}</Text>
                      </div>
                    ))}
                  </Space>
                ) : (
                  <Text type="secondary">暂无规则明细</Text>
                )}
              </section>
              <section>
                <Text strong>原始来源</Text>
                <div className="source-line">
                  产品目标: {productGoalLabel(selectedEvidence.product_goal)} / 时间周期: {selected.period_start} -{" "}
                  {selected.period_end}
                </div>
                <div className="source-line">
                  广告活动: {String(selectedEvidence.campaign_name || selectedEvidence.campaign_id || "-")} / 广告组:{" "}
                  {String(selectedEvidence.ad_group_name || selectedEvidence.ad_group_id || "-")}
                </div>
                <div className="source-line">
                  关键词: {String(selectedEvidence.keyword_text || selectedEvidence.keyword_id || "-")} / 匹配方式:{" "}
                  {String(selectedEvidence.match_type || "-")}
                </div>
                <div className="source-line">搜索词: {String(selectedEvidence.search_term || "-")}</div>
                {selectedSuggestion?.source_trace_json ? <pre>{parseJsonText(selectedSuggestion.source_trace_json)}</pre> : null}
              </section>
              <section>
                <Text strong>规则判定原始结果</Text>
                <pre>{parseJsonText(selected.rule_result_json)}</pre>
              </section>
              <section>
                <Text strong>证据快照原始数据</Text>
                <pre>{parseJsonText(selected.evidence_json)}</pre>
              </section>
            </Space>
          ) : null}
        </Drawer>
        <Modal
          title={modalTitle}
          open={!!decisionType}
          onCancel={() => setDecisionType(null)}
          onOk={() => {
            void form.validateFields().then((values) => {
              if (!decisionType) return;
              void submitDecision({
                decision_type: decisionType,
                modified_action: values.modified_action,
                reason: values.reason,
                observe_period: values.observe_period,
                operator_name: values.operator_name
              });
            });
          }}
          confirmLoading={decisionSubmitting}
          okText="提交"
          cancelText="取消"
        >
          <Form form={form} layout="vertical">
            <Alert
              type="info"
              showIcon
              message="仅记录人工处理决定，不会自动修改广告预算、竞价、否词或暂停广告。"
            />
            {decisionType === "adopt_with_changes" ? (
              <Form.Item name="modified_action" label="修改内容" rules={[{ required: true, message: "请输入修改内容" }]}>
                <Input.TextArea rows={3} placeholder="例如：降低竞价 10%，观察 7 天" />
              </Form.Item>
            ) : null}
            {decisionType === "observe" ? (
              <Form.Item name="observe_period" label="观察周期" rules={[{ required: true, message: "请选择观察周期" }]}>
                <Select
                  placeholder="选择观察周期"
                  options={[
                    { value: "7d", label: "7 天" },
                    { value: "14d", label: "14 天" }
                  ]}
                />
              </Form.Item>
            ) : null}
            <Form.Item
              name="reason"
              label={
                decisionType === "reject"
                  ? "拒绝原因"
                  : decisionType === "adopt_with_changes"
                    ? "修改原因"
                    : "处理说明"
              }
              rules={
                decisionType === "reject"
                  ? [{ required: true, message: "请输入拒绝原因" }]
                  : decisionType === "adopt_with_changes"
                    ? [{ required: true, message: "请输入修改原因" }]
                    : []
              }
            >
              <Input.TextArea rows={3} placeholder="记录人工判断依据" />
            </Form.Item>
            <Form.Item name="operator_name" label="处理人" rules={[{ required: true, message: "请输入处理人" }]}>
              <Input placeholder="请输入处理人姓名" />
            </Form.Item>
          </Form>
        </Modal>
        <Modal
          title="新增产品"
          open={createProductOpen}
          onCancel={() => setCreateProductOpen(false)}
          onOk={() => void submitCreateProduct()}
          confirmLoading={creatingProduct}
          okText="创建"
          cancelText="取消"
        >
          <Form form={productForm} layout="vertical">
            <Form.Item name="product_name" label="产品名称" rules={[{ required: true, message: "请输入产品名称" }]}>
              <Input placeholder="例如：RIVBOS 太阳镜" />
            </Form.Item>
            <Form.Item name="asin" label="ASIN">
              <Input placeholder="Amazon ASIN" />
            </Form.Item>
            <Form.Item name="msku" label="MSKU">
              <Input placeholder="店铺 MSKU" />
            </Form.Item>
            <Form.Item name="sku" label="SKU">
              <Input placeholder="本地 SKU" />
            </Form.Item>
            <Form.Item name="image_url" label="产品图片 URL">
              <Input placeholder="https://..." />
            </Form.Item>
            <Form.Item name="brand" label="品牌">
              <Input placeholder="品牌名称" />
            </Form.Item>
            <Form.Item name="category" label="分类">
              <Input placeholder="产品分类" />
            </Form.Item>
            <Form.Item name="market_id" label="店铺 / 站点 ID">
              <InputNumber className="table-control" min={1} precision={0} placeholder="1" />
            </Form.Item>
            <Form.Item name="inventory_quantity" label="当前库存">
              <InputNumber className="table-control" min={0} precision={0} placeholder="可先手动维护" />
            </Form.Item>
          </Form>
        </Modal>
        <Modal
          title={`批量应用到 ${selectedProductIds.length} 个产品`}
          open={batchApplyOpen}
          onCancel={() => setBatchApplyOpen(false)}
          onOk={() => void submitBatchApply()}
          confirmLoading={batchApplying}
          okText="应用"
          cancelText="取消"
        >
          <Form form={batchForm} layout="vertical">
            <Form.Item name="goal_type" label="产品目标">
              <Select allowClear placeholder="不修改产品目标" options={goalOptions} />
            </Form.Item>
            <Form.Item name="note" label="目标备注">
              <Input placeholder="可选，随产品目标一起保存" />
            </Form.Item>
            <div className="batch-rule-grid">
              <Form.Item name="target_acos" label="目标 ACOS">
                <InputNumber className="table-control" min={0} step={0.05} placeholder="不修改" />
              </Form.Item>
              <Form.Item name="target_cvr" label="目标 CVR">
                <InputNumber className="table-control" min={0} step={0.01} placeholder="不修改" />
              </Form.Item>
              <Form.Item name="min_clicks" label="最小点击">
                <InputNumber className="table-control" min={0} precision={0} placeholder="不修改" />
              </Form.Item>
              <Form.Item name="min_spend" label="最小花费">
                <InputNumber className="table-control" min={0} step={1} placeholder="不修改" />
              </Form.Item>
              <Form.Item name="min_orders" label="最小订单">
                <InputNumber className="table-control" min={0} precision={0} placeholder="不修改" />
              </Form.Item>
              <Form.Item name="max_cpc" label="最大 CPC">
                <InputNumber className="table-control" min={0} step={0.1} placeholder="不修改" />
              </Form.Item>
              <Form.Item name="inventory_guard" label="库存阈值">
                <InputNumber className="table-control" min={0} precision={0} placeholder="不修改" />
              </Form.Item>
            </div>
          </Form>
        </Modal>
        <Modal
          title={reviewDecision ? `复盘处理记录 ${reviewDecision.id}` : "复盘"}
          open={!!reviewDecision}
          onCancel={() => setReviewDecision(null)}
          onOk={() => void submitReview()}
          confirmLoading={reviewSubmitting}
          okText="保存复盘"
          cancelText="取消"
        >
          <Form form={reviewForm} layout="vertical" initialValues={{ review_period: "7d", result: "improved" }}>
            <Form.Item name="review_period" label="复盘周期" rules={[{ required: true, message: "请选择复盘周期" }]}>
              <Select
                options={[
                  { value: "7d", label: "7 天复盘" },
                  { value: "14d", label: "14 天复盘" }
                ]}
              />
            </Form.Item>
            <Form.Item name="result" label="复盘结果" rules={[{ required: true, message: "请选择复盘结果" }]}>
              <Select
                options={[
                  { value: "improved", label: "改善" },
                  { value: "unchanged", label: "无明显变化" },
                  { value: "worse", label: "变差" }
                ]}
              />
            </Form.Item>
            <Form.Item name="note" label="复盘说明">
              <Input.TextArea rows={3} placeholder="记录调整后的表现、是否继续观察或二次处理" />
            </Form.Item>
            <Form.Item name="before_metrics_json" label="处理前指标快照">
              <Input.TextArea rows={3} placeholder='例如：{"acos": 0.32, "orders": 3}' />
            </Form.Item>
            <Form.Item name="after_metrics_json" label="复盘后指标快照">
              <Input.TextArea rows={3} placeholder='例如：{"acos": 0.25, "orders": 5}' />
            </Form.Item>
          </Form>
        </Modal>
      </main>
    </AntApp>
  );
}
