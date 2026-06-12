import {
  AuditOutlined,
  CheckCircleOutlined,
  EyeOutlined,
  PlusOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  SaveOutlined,
  SearchOutlined
} from "@ant-design/icons";
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
  Segmented,
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
  AttributionScopeType,
  DashboardSummary,
  Decision,
  DecisionInput,
  Product,
  ProductAdBinding,
  ProductAttributionCandidateRow,
  ProductAttributionCandidates,
  ProductAttributionEvidence,
  ProductGoalType,
  ProductInput,
  ProductRuleInput,
  Review,
  ReviewInput,
  SearchTermAnalysis,
  SearchTermCandidate,
  SearchTermCandidateDecision,
  SearchTermCandidateDecisionType,
  SearchTermCandidateReview,
  SearchTermCandidateType,
  SearchTermCandidates,
  SearchTermGroupDecision,
  SearchTermGroupDecisionReview,
  SearchTermGroupSummary,
  SearchTermAnalysisRow,
  SearchTermPerformanceStatus,
  SearchTermProductReadiness,
  SearchTermSemanticCategory,
  SuggestionLevel,
  Suggestion,
  SyncRun,
  UnboundAdSource,
  bindAdSourceToProduct,
  bindCampaignToProduct,
  createDecision,
  createProduct,
  createReview,
  createSearchTermCandidateDecision,
  createSearchTermGroupDecision,
  fetchAnomalies,
  fetchDashboardAnomalySummary,
  fetchDashboardHealth,
  fetchDashboardTrends,
  fetchDecisions,
  fetchProductAdBindings,
  fetchProductAttributionCandidates,
  fetchProductAttributionEvidence,
  fetchProducts,
  fetchReviews,
  fetchSearchTermAnalysis,
  fetchSearchTermCandidateDecisions,
  fetchSearchTermCandidateReview,
  fetchSearchTermCandidates,
  fetchSearchTermGroupDecisions,
  fetchSearchTermGroupDecisionReview,
  fetchSearchTermProductReadiness,
  fetchSuggestions,
  fetchSyncRuns,
  fetchSyncStatus,
  fetchUnboundAdSources,
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

type AnomalyStatusFilter = AnomalyStatus | "all";

const anomalyStatusFilterOptions: { value: AnomalyStatusFilter; label: string }[] = [
  { value: "all", label: "全部状态" },
  { value: "pending", label: "待处理" },
  { value: "observing", label: "观察中" },
  { value: "handled", label: "已人工处理" }
];

function anomalyStatusParam(value: AnomalyStatusFilter): AnomalyStatus | undefined {
  return value === "all" ? undefined : value;
}

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

const productBindingLabels: Record<string, string> = {
  none: "未绑定产品",
  partial: "部分已绑定",
  complete: "已绑定产品",
  unknown: "未统计"
};

const productBindingColors: Record<string, string> = {
  none: "red",
  partial: "gold",
  complete: "green",
  unknown: "default"
};

const attributionScopeLabels: Record<AttributionScopeType, string> = {
  campaign: "Campaign",
  ad_group: "Ad Group"
};

const searchTermSemanticLabels: Record<SearchTermSemanticCategory, string> = {
  age_spec: "年龄 / 人群规格词",
  core_product: "核心产品词",
  asin: "ASIN / 商品编号词",
  accessory_or_unrelated: "疑似配件或无关词",
  generic: "泛搜索词"
};

const searchTermSemanticColors: Record<SearchTermSemanticCategory, string> = {
  age_spec: "blue",
  core_product: "green",
  asin: "purple",
  accessory_or_unrelated: "orange",
  generic: "default"
};

const searchTermPerformanceLabels: Record<SearchTermPerformanceStatus, string> = {
  high_conversion: "高转化词",
  costly_no_order: "高花费无单词",
  high_acos: "有单但 ACOS 高",
  data_insufficient: "数据不足",
  observe: "继续观察"
};

const searchTermPerformanceColors: Record<SearchTermPerformanceStatus, string> = {
  high_conversion: "green",
  costly_no_order: "red",
  high_acos: "orange",
  data_insufficient: "default",
  observe: "blue"
};

const searchTermCandidateLabels: Record<SearchTermCandidateType, string> = {
  scale_opportunity: "高转化放量候选",
  waste_risk: "高花费无单处理候选",
  efficiency_risk: "高 ACOS 处理候选"
};

const searchTermCandidateColors: Record<SearchTermCandidateType, string> = {
  scale_opportunity: "green",
  waste_risk: "red",
  efficiency_risk: "orange"
};

const searchTermReviewColors: Record<SearchTermCandidateReview["result"], string> = {
  improved: "green",
  unchanged: "blue",
  worse: "red",
  data_pending: "default"
};

const searchTermSemanticOptions = Object.entries(searchTermSemanticLabels).map(([value, label]) => ({ value, label }));
const searchTermPerformanceOptions = Object.entries(searchTermPerformanceLabels).map(([value, label]) => ({ value, label }));
const searchTermCandidateOptions = Object.entries(searchTermCandidateLabels).map(([value, label]) => ({ value, label }));

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
  start.setDate(start.getDate() - 29);
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

const AD_DRAFT_PRODUCT_CATEGORY = "SP广告来源草稿";

const hasProductSpMetrics = (product: Product) =>
  (product.sp_metrics?.clicks || 0) > 0 ||
  (product.sp_metrics?.cost || 0) > 0 ||
  (product.sp_metrics?.orders || 0) > 0 ||
  (product.sp_metrics?.sales || 0) > 0;

const getProductGoalRuleMissingItems = (product: Product): string[] => {
  const missingItems: string[] = [];
  if (!product.goal) {
    missingItems.push("缺少产品目标");
  }
  if (!product.rules || product.rules.target_acos === null || typeof product.rules.target_acos === "undefined") {
    missingItems.push("缺少目标 ACOS");
  }
  return missingItems;
};

const needsProductGoalRuleSetup = (product: Product, productBindingCount = 0) =>
  isProductAdTuningEligible(product, productBindingCount) && hasProductSpMetrics(product) && getProductGoalRuleMissingItems(product).length > 0;

const isConfiguredNoAnomalyTargetMatch = (product: Product) =>
  product.target_match.status === "matched" &&
  !!product.goal &&
  !!product.rules &&
  typeof product.rules.target_acos === "number" &&
  hasProductSpMetrics(product);

type ProductAdCoverageStatus = "attributed" | "sp_unattributed" | "not_advertised";
type ProductAdCoverageFilter = ProductAdCoverageStatus | "all";
type ProductCenterView = "ad_tuning" | "sales_profile" | "all";

const productAdCoverageMeta: Record<ProductAdCoverageStatus, { label: string; color: string; description: string }> = {
  attributed: {
    label: "有广告覆盖",
    color: "green",
    description: "已有人工确认归因规则，可进入产品维度广告分析"
  },
  sp_unattributed: {
    label: "有 SP 数据待归因",
    color: "gold",
    description: "已有 SP 指标，但还需要人工确认广告来源归属"
  },
  not_advertised: {
    label: "本系统暂无 SP 覆盖证据",
    color: "default",
    description: "只作为销售产品档案，不进入广告调优待办"
  }
};

const productAdCoverageFilterOptions: { value: ProductAdCoverageFilter; label: string }[] = [
  { value: "all", label: "全部覆盖状态" },
  { value: "attributed", label: productAdCoverageMeta.attributed.label },
  { value: "sp_unattributed", label: productAdCoverageMeta.sp_unattributed.label },
  { value: "not_advertised", label: productAdCoverageMeta.not_advertised.label }
];

const productCenterViewOptions: { value: ProductCenterView; label: string }[] = [
  { value: "ad_tuning", label: "广告调优对象" },
  { value: "sales_profile", label: "销售档案" },
  { value: "all", label: "全部产品" }
];

const productSalesProfileHiddenColumnTitles = new Set([
  "目标与数据表现是否匹配",
  "产品目标",
  "目标 ACOS",
  "目标 CVR",
  "最小点击",
  "最小花费",
  "最小订单",
  "最大 CPC",
  "库存阈值",
  "备注",
  "操作"
]);

function productMatchesProductCenterView(productCenterView: ProductCenterView, adCoverageStatus: ProductAdCoverageStatus): boolean {
  if (productCenterView === "ad_tuning") {
    return adCoverageStatus !== "not_advertised";
  }
  if (productCenterView === "sales_profile") {
    return adCoverageStatus === "not_advertised";
  }
  return true;
}

function getProductAdCoverageStatus(product: Product, productBindingCount: number): ProductAdCoverageStatus {
  if (product.ad_coverage_status) {
    return product.ad_coverage_status;
  }
  if (productBindingCount > 0) {
    return "attributed";
  }
  if (hasProductSpMetrics(product)) {
    return "sp_unattributed";
  }
  return "not_advertised";
}

function isProductAdTuningEligible(product: Product, productBindingCount: number): boolean {
  if (typeof product.is_ad_tuning_eligible === "boolean") {
    return product.is_ad_tuning_eligible;
  }
  return getProductAdCoverageStatus(product, productBindingCount) !== "not_advertised";
}

function getProductAdCoveragePriority(product: Product, productBindingCount: number): number {
  const status = getProductAdCoverageStatus(product, productBindingCount);
  if (status === "attributed") {
    return 2;
  }
  if (status === "sp_unattributed") {
    return 1;
  }
  return 0;
}

function isProductAdRuleEditable(product: Product, productBindingCount: number): boolean {
  return isProductAdTuningEligible(product, productBindingCount);
}

function renderNoSpCoverageAdRuleReadonly() {
  return (
    <Space direction="vertical" size={0} className="product-ad-rule-readonly">
      <Tag>只读销售档案</Tag>
      <Text type="secondary" className="compact-note">
        本系统暂无 SP 覆盖证据，不配置广告目标 / 规则
      </Text>
    </Space>
  );
}

const isAdDraftProduct = (product: Product) => product.category === AD_DRAFT_PRODUCT_CATEGORY;

const needsAdDraftIdentityReview = (product: Product) => isAdDraftProduct(product) && (!product.asin || !product.sales_snapshot);

function productSourceLabel(product: Product): string {
  return isAdDraftProduct(product) ? "广告草稿" : "销售表现";
}

function normalizeProductIdentityText(value: string | null | undefined): string {
  return (value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function productIdentityTokens(product: Product): string[] {
  const tokens = [product.asin, product.msku, product.sku, product.product_name]
    .flatMap((value) => normalizeProductIdentityText(value).split(/\s+/))
    .filter((token) => token.length >= 4);
  return Array.from(new Set(tokens));
}

function productIdentityText(product: Product): string {
  return normalizeProductIdentityText([product.asin, product.msku, product.sku, product.product_name].filter(Boolean).join(" "));
}

function findAdDraftIdentityCandidates(adDraftProduct: Product, products: Product[]): Product[] {
  if (!needsAdDraftIdentityReview(adDraftProduct)) {
    return [];
  }
  const tokens = productIdentityTokens(adDraftProduct);
  if (!tokens.length) {
    return [];
  }
  return products
    .map((candidate) => {
      if (candidate.id === adDraftProduct.id || isAdDraftProduct(candidate) || !candidate.sales_snapshot) {
        return null;
      }
      if (adDraftProduct.market_id !== null && candidate.market_id !== adDraftProduct.market_id) {
        return null;
      }
      const candidateText = productIdentityText(candidate);
      const score = tokens.reduce((total, token) => total + (candidateText.includes(token) ? 1 : 0), 0);
      return score > 0 ? { candidate, score } : null;
    })
    .filter((item): item is { candidate: Product; score: number } => !!item)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
    .map((item) => item.candidate);
}

function extractProductFamilyToken(product: Product): string | null {
  const text = [product.product_name, product.msku, product.sku].filter(Boolean).join(" ");
  const familyToken = text.match(/[A-Za-z]{2,}\d{3,}[A-Za-z0-9]*/)?.[0];
  return familyToken ? familyToken.toUpperCase() : null;
}

function findProductFamilyCandidates(adDraftProduct: Product, products: Product[]): Product[] {
  const familyToken = extractProductFamilyToken(adDraftProduct);
  if (!familyToken) {
    return [];
  }
  const normalizedFamilyToken = familyToken.toLowerCase();
  return products.filter((candidate) => {
    if (candidate.id === adDraftProduct.id || isAdDraftProduct(candidate) || !candidate.sales_snapshot) {
      return false;
    }
    if (adDraftProduct.market_id !== null && candidate.market_id !== adDraftProduct.market_id) {
      return false;
    }
    return productIdentityText(candidate).includes(normalizedFamilyToken);
  });
}

type ProductFamilyAdObjectHint = {
  candidateCount: number;
  topSalesShare: number;
  searchTermCount: number;
  specificSearchHitCount: number;
};

function productSpecificTokens(products: Product[], familyToken: string | null): string[] {
  const family = (familyToken || "").toLowerCase();
  const tokens = products
    .flatMap((product) => [product.asin, product.msku, product.sku])
    .map((value) => normalizeProductIdentityText(value))
    .filter((token) => token.length >= 6 && token !== family);
  return Array.from(new Set(tokens));
}

function bindingSearchTermTexts(binding: ProductAdBinding | undefined): string[] {
  const evidence = parseNullableJsonObject(binding?.evidence_json || null);
  const topSearchTerms = evidence.top_search_terms;
  if (!Array.isArray(topSearchTerms)) {
    return [];
  }
  return topSearchTerms
    .filter((item): item is Record<string, unknown> => !!item && typeof item === "object" && !Array.isArray(item))
    .map((item) => `${item.keyword_text || ""} ${item.search_term || ""}`.trim())
    .filter(Boolean);
}

function getAdObjectGranularityHint(adDraftProduct: Product, products: Product[], bindings: ProductAdBinding[]): ProductFamilyAdObjectHint | null {
  if (!needsAdDraftIdentityReview(adDraftProduct)) {
    return null;
  }
  const candidates = findProductFamilyCandidates(adDraftProduct, products);
  if (candidates.length < 3) {
    return null;
  }
  const totalSales = candidates.reduce((sum, product) => sum + (product.sales_snapshot?.sales || 0), 0);
  const topSales = Math.max(...candidates.map((product) => product.sales_snapshot?.sales || 0));
  const topSalesShare = totalSales > 0 ? topSales / totalSales : 0;
  const activeBinding = bindings.find((binding) => binding.product_id === adDraftProduct.id && binding.status === "active");
  const searchTexts = bindingSearchTermTexts(activeBinding);
  const productTokens = productSpecificTokens(candidates, extractProductFamilyToken(adDraftProduct));
  const specificSearchHitCount = searchTexts.filter((text) => {
    const normalized = normalizeProductIdentityText(text);
    return productTokens.some((token) => normalized.includes(token));
  }).length;
  if (topSalesShare >= 0.6 || specificSearchHitCount > 0) {
    return null;
  }
  return {
    candidateCount: candidates.length,
    topSalesShare,
    searchTermCount: searchTexts.length,
    specificSearchHitCount
  };
}

function adSourceIdentityText(source: UnboundAdSource): string {
  return normalizeProductIdentityText(
    [
      source.scope_id,
      source.scope_name,
      source.campaign_id,
      source.campaign_name,
      source.ad_group_id,
      source.ad_group_name
    ]
      .filter(Boolean)
      .join(" ")
  );
}

function sourceMatchesProductIdentity(source: UnboundAdSource, product: Product | null): boolean {
  if (!product) {
    return false;
  }
  const tokens = productIdentityTokens(product);
  if (!tokens.length) {
    return false;
  }
  const sourceText = adSourceIdentityText(source);
  return tokens.some((token) => sourceText.includes(token));
}

type ProductAttributionFilters = {
  market_id?: number;
  start_date?: string;
  end_date?: string;
};

type DashboardWorkflowFilters = {
  market_id?: number;
  goal_type?: ProductGoalType;
  anomaly_type?: AnomalyType;
  suggestion_level?: SuggestionLevel;
  start_date?: string;
  end_date?: string;
};

type SearchTermWorkflowFilters = {
  market_id?: number;
  product_id?: number;
  start_date?: string;
  end_date?: string;
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

type StoreIdentityLike = {
  market_name?: string | null;
  country_code?: string | null;
  identity_status?: string | null;
} | null | undefined;

function formatStoreIdentityLabel(market: StoreIdentityLike): string {
  if (market?.market_name && market.country_code) {
    return `${market.market_name} / ${market.country_code}`;
  }
  if (market?.market_name) {
    return market.market_name;
  }
  if (market?.identity_status === "multiple") {
    return "多店铺汇总";
  }
  return "店铺未识别";
}

function formatProductMarketLabel(product: Product): string {
  return formatStoreIdentityLabel(product.market);
}

function formatMoney(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function adSourceKey(source: UnboundAdSource): string {
  return `${source.scope_type}:${source.market_id ?? "all"}:${source.scope_id || "-"}`;
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

type ProductSalesSnapshotView = {
  period_start?: string;
  period_end?: string;
  sales?: number;
  orders?: number;
  sessions?: number;
  net_profit?: number;
  ads_spend?: number;
  ads_sales?: number;
  acos?: number;
};

function textFrom(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function productSalesSnapshotFromUnknown(value: unknown): ProductSalesSnapshotView | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const source = value as Record<string, unknown>;
  return {
    period_start: textFrom(source.period_start),
    period_end: textFrom(source.period_end),
    sales: numberFrom(source.sales) ?? undefined,
    orders: numberFrom(source.orders) ?? undefined,
    sessions: numberFrom(source.sessions) ?? undefined,
    net_profit: numberFrom(source.net_profit) ?? undefined,
    ads_spend: numberFrom(source.ads_spend) ?? undefined,
    ads_sales: numberFrom(source.ads_sales) ?? undefined,
    acos: numberFrom(source.acos) ?? undefined
  };
}

function productSalesSnapshotFromSourceTrace(
  sourceTraceJson: string | null,
  snapshotKey = "product_sales_snapshot"
): ProductSalesSnapshotView | null {
  const trace = parseNullableJsonObject(sourceTraceJson);
  const context = trace.source_context;
  if (!context || typeof context !== "object" || Array.isArray(context)) {
    return null;
  }
  return productSalesSnapshotFromUnknown((context as Record<string, unknown>)[snapshotKey]);
}

function businessSnapshotMetrics(snapshot: ProductSalesSnapshotView): { label: string; value: string }[] {
  const metricItems: { key: keyof ProductSalesSnapshotView; label: string; format?: "money" | "percent" }[] = [
    { key: "sales", label: "销售额", format: "money" },
    { key: "orders", label: "订单" },
    { key: "sessions", label: "Sessions" },
    { key: "net_profit", label: "净利", format: "money" },
    { key: "ads_spend", label: "广告花费", format: "money" },
    { key: "ads_sales", label: "广告销售", format: "money" },
    { key: "acos", label: "产品 ACOS", format: "percent" }
  ];
  return metricItems
    .map((item) => {
      const value = snapshot[item.key];
      if (typeof value !== "number") {
        return null;
      }
      const formatted = item.format === "percent" ? formatPercent(value) : item.format === "money" ? formatMoney(value) : String(value);
      return { label: item.label, value: formatted };
    })
    .filter((item): item is { label: string; value: string } => !!item);
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

function confidenceColor(level: string | undefined): string {
  if (level === "high") return "green";
  if (level === "medium") return "gold";
  return "red";
}

function confidenceLabel(level: string | undefined): string {
  if (level === "high") return "高";
  if (level === "medium") return "中";
  return "低";
}

function bindingEvidenceSummary(value: string | null): string {
  const evidence = parseNullableJsonObject(value);
  const confidence = evidence.confidence && typeof evidence.confidence === "object" ? (evidence.confidence as Record<string, unknown>) : {};
  const period = evidence.period && typeof evidence.period === "object" ? (evidence.period as Record<string, unknown>) : {};
  const score = typeof confidence.score === "number" ? confidence.score : null;
  const start = typeof period.start === "string" ? period.start : "";
  const end = typeof period.end === "string" ? period.end : "";
  const periodText = start || end ? `${start || "-"} 至 ${end || "-"}` : "未记录周期";
  return `证据快照：${periodText}${score === null ? "" : ` / 可信度 ${score}`}`;
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
  const { message: appMessage, modal } = AntApp.useApp();
  const message = useMemo(
    () => ({
      error: (text: string) => {
        if (typeof appMessage?.error === "function") {
          appMessage.error(text);
          return;
        }
        console.error(text);
      },
      success: (text: string) => {
        if (typeof appMessage?.success === "function") {
          appMessage.success(text);
          return;
        }
        console.info(text);
      },
      warning: (text: string) => {
        if (typeof appMessage?.warning === "function") {
          appMessage.warning(text);
          return;
        }
        console.warn(text);
      }
    }),
    [appMessage]
  );
  const [form] = Form.useForm();
  const [productForm] = Form.useForm<ProductInput>();
  const [batchForm] = Form.useForm();
  const [reviewForm] = Form.useForm();
  const [searchTermDecisionForm] = Form.useForm();
  const [searchTermGroupDecisionForm] = Form.useForm();
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
  const [status, setStatus] = useState<AnomalyStatusFilter>("all");
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
  const [searchTermAnalysis, setSearchTermAnalysis] = useState<SearchTermAnalysis | null>(null);
  const [searchTermCandidates, setSearchTermCandidates] = useState<SearchTermCandidates | null>(null);
  const [searchTermProductReadiness, setSearchTermProductReadiness] = useState<SearchTermProductReadiness | null>(null);
  const [searchTermCandidateDecisions, setSearchTermCandidateDecisions] = useState<SearchTermCandidateDecision[]>([]);
  const [searchTermGroupDecisions, setSearchTermGroupDecisions] = useState<SearchTermGroupDecision[]>([]);
  const [searchTermLoading, setSearchTermLoading] = useState(false);
  const [searchTermProductReadinessLoading, setSearchTermProductReadinessLoading] = useState(false);
  const [searchTermCandidateLoading, setSearchTermCandidateLoading] = useState(false);
  const [searchTermDecisionLoading, setSearchTermDecisionLoading] = useState(false);
  const [searchTermDecisionSubmitting, setSearchTermDecisionSubmitting] = useState(false);
  const [searchTermDecisionCandidate, setSearchTermDecisionCandidate] = useState<SearchTermCandidate | null>(null);
  const [searchTermGroupDecisionLoading, setSearchTermGroupDecisionLoading] = useState(false);
  const [searchTermGroupDecisionSubmitting, setSearchTermGroupDecisionSubmitting] = useState(false);
  const [searchTermGroupDecisionGroup, setSearchTermGroupDecisionGroup] = useState<SearchTermGroupSummary | null>(null);
  const [searchTermReviewDecision, setSearchTermReviewDecision] = useState<SearchTermCandidateDecision | null>(null);
  const [searchTermCandidateReview, setSearchTermCandidateReview] = useState<SearchTermCandidateReview | null>(null);
  const [searchTermGroupReviewDecision, setSearchTermGroupReviewDecision] = useState<SearchTermGroupDecision | null>(null);
  const [searchTermGroupDecisionReview, setSearchTermGroupDecisionReview] = useState<SearchTermGroupDecisionReview | null>(null);
  const [searchTermGroupReviewLoading, setSearchTermGroupReviewLoading] = useState(false);
  const [searchTermReviewLoading, setSearchTermReviewLoading] = useState(false);
  const [searchTermMarketId, setSearchTermMarketId] = useState<number | null>(null);
  const [searchTermProductId, setSearchTermProductId] = useState<number | null>(null);
  const [searchTermSemanticCategory, setSearchTermSemanticCategory] = useState<SearchTermSemanticCategory>();
  const [searchTermPerformanceStatus, setSearchTermPerformanceStatus] = useState<SearchTermPerformanceStatus>();
  const [searchTermCandidateType, setSearchTermCandidateType] = useState<SearchTermCandidateType>();
  const [searchTermStartDate, setSearchTermStartDate] = useState<string | undefined>(defaultPeriod.start);
  const [searchTermEndDate, setSearchTermEndDate] = useState<string | undefined>(defaultPeriod.end);
  const [searchTermMinClicks, setSearchTermMinClicks] = useState<number | null>(10);
  const [searchTermMinSpend, setSearchTermMinSpend] = useState<number | null>(10);
  const [searchTermTargetAcos, setSearchTermTargetAcos] = useState<number | null>(0.35);
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
  const [selectedGoalRuleProduct, setSelectedGoalRuleProduct] = useState<Product | null>(null);
  const [productCenterView, setProductCenterView] = useState<ProductCenterView>("ad_tuning");
  const [productAdCoverageFilter, setProductAdCoverageFilter] = useState<ProductAdCoverageFilter>("all");
  const [adDraftAttributionReviewProduct, setAdDraftAttributionReviewProduct] = useState<Product | null>(null);
  const [adDraftAttributionReviewSourceProduct, setAdDraftAttributionReviewSourceProduct] = useState<Product | null>(null);
  const [unboundAdSources, setUnboundAdSources] = useState<UnboundAdSource[]>([]);
  const [productAdBindings, setProductAdBindings] = useState<ProductAdBinding[]>([]);
  const [productAttributionCandidates, setProductAttributionCandidates] = useState<ProductAttributionCandidates | null>(null);
  const [productAttributionCandidateLoading, setProductAttributionCandidateLoading] = useState(false);
  const [attributionScope, setAttributionScope] = useState<AttributionScopeType>("ad_group");
  const [attributionProductId, setAttributionProductId] = useState<number | null>(null);
  const [attributionLoading, setAttributionLoading] = useState(false);
  const [attributionSavingKey, setAttributionSavingKey] = useState<string | null>(null);
  const [attributionEvidence, setAttributionEvidence] = useState<ProductAttributionEvidence | null>(null);
  const [attributionEvidenceOpen, setAttributionEvidenceOpen] = useState(false);
  const [attributionEvidenceLoading, setAttributionEvidenceLoading] = useState(false);
  const [attributionEvidenceNote, setAttributionEvidenceNote] = useState("");
  const [batchApplyOpen, setBatchApplyOpen] = useState(false);
  const [batchApplying, setBatchApplying] = useState(false);
  const [createProductOpen, setCreateProductOpen] = useState(false);
  const [productSeedSource, setProductSeedSource] = useState<UnboundAdSource | null>(null);
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
        status: anomalyStatusParam(status),
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
        status: anomalyStatusParam(status)
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

  const resolveProductAttributionFilters = async (): Promise<ProductAttributionFilters> => {
    const filters: ProductAttributionFilters = {
      market_id: productMarketId ?? undefined,
      start_date: productStartDate,
      end_date: productEndDate
    };
    const usesDefaultPeriod = productStartDate === defaultPeriod.start && productEndDate === defaultPeriod.end;
    if (!usesDefaultPeriod) {
      return filters;
    }

    try {
      const runs = await fetchSyncRuns(20);
      const latest = runs.find(
        (run) => run.status === "success" && run.period_start && run.period_end && (productMarketId === null || run.market_id === productMarketId)
      );
      if (!latest) {
        return filters;
      }
      setSyncRuns(runs.slice(0, 5));
      if (productMarketId === null) {
        setProductMarketId(latest.market_id);
      }
      if (productStartDate !== latest.period_start) {
        setProductStartDate(latest.period_start);
      }
      if (productEndDate !== latest.period_end) {
        setProductEndDate(latest.period_end);
      }
      return {
        market_id: productMarketId ?? latest.market_id,
        start_date: latest.period_start,
        end_date: latest.period_end
      };
    } catch {
      return filters;
    }
  };

  const loadProductAttributionCandidates = async (filtersOverride?: ProductAttributionFilters) => {
    setProductAttributionCandidateLoading(true);
    try {
      const filters = filtersOverride || (await resolveProductAttributionFilters());
      const payload = await fetchProductAttributionCandidates({
        market_id: filters.market_id,
        scope_type: attributionScope,
        start_date: filters.start_date,
        end_date: filters.end_date,
        min_confidence: 50,
        limit: 30
      });
      setProductAttributionCandidates(payload);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载产品归因候选失败";
      message.error(text);
    } finally {
      setProductAttributionCandidateLoading(false);
    }
  };

  const loadProductAttribution = async (filtersOverride?: ProductAttributionFilters) => {
    setAttributionLoading(true);
    try {
      const filters = filtersOverride || (await resolveProductAttributionFilters());
      const [sources, bindings] = await Promise.all([
        fetchUnboundAdSources({
          ...filters,
          scope_type: attributionScope
        }),
        fetchProductAdBindings({
          market_id: productMarketId ?? undefined
        })
      ]);
      setUnboundAdSources(sources.filter((item) => !!item.scope_id));
      setProductAdBindings(bindings);
      await loadProductAttributionCandidates(filters);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载产品归因数据失败";
      message.error(text);
    } finally {
      setAttributionLoading(false);
    }
  };

  const loadProducts = async () => {
    setProductLoading(true);
    try {
      const filters = await resolveProductAttributionFilters();
      const rows = await fetchProducts({
        market_id: filters.market_id,
        goal_type: productGoalType,
        anomaly_type: productAnomalyType,
        suggestion_level: productSuggestionLevel,
        start_date: filters.start_date,
        end_date: filters.end_date
      });
      setProducts(rows);
      setProductDrafts(Object.fromEntries(rows.map((product) => [product.id, buildProductDraft(product)])));
      await loadProductAttribution(filters);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载产品列表失败";
      message.error(text);
    } finally {
      setProductLoading(false);
    }
  };

  const productAdCoverageSummary = useMemo(
    () =>
      products.reduce<Record<ProductAdCoverageStatus, number>>(
        (summary, product) => {
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === product.id).length;
          const status = getProductAdCoverageStatus(product, productBindingCount);
          summary[status] += 1;
          return summary;
        },
        { attributed: 0, sp_unattributed: 0, not_advertised: 0 }
      ),
    [productAdBindings, products]
  );

  const productCenterProducts = useMemo(
    () =>
      products
        .filter((product) => {
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === product.id).length;
          const adCoverageStatus = getProductAdCoverageStatus(product, productBindingCount);
          if (!productMatchesProductCenterView(productCenterView, adCoverageStatus)) {
            return false;
          }
          return productAdCoverageFilter === "all" || getProductAdCoverageStatus(product, productBindingCount) === productAdCoverageFilter;
        })
        .map((product, index) => ({ product, index }))
        .sort((a, b) => {
          const aBindingCount = productAdBindings.filter((binding) => binding.product_id === a.product.id).length;
          const bBindingCount = productAdBindings.filter((binding) => binding.product_id === b.product.id).length;
          const setupPriority =
            Number(needsProductGoalRuleSetup(b.product, bBindingCount)) - Number(needsProductGoalRuleSetup(a.product, aBindingCount));
          const adCoveragePriority = getProductAdCoveragePriority(b.product, bBindingCount) - getProductAdCoveragePriority(a.product, aBindingCount);
          return setupPriority || adCoveragePriority || a.index - b.index;
        })
        .map(({ product }) => product),
    [productAdBindings, productAdCoverageFilter, productCenterView, products]
  );

  const productsNeedingGoalRuleSetup = useMemo(() => {
    if (productCenterView !== "ad_tuning") {
      return [];
    }
    return productCenterProducts.filter((product) => {
      const productBindingCount = productAdBindings.filter((binding) => binding.product_id === product.id).length;
      return needsProductGoalRuleSetup(product, productBindingCount);
    });
  }, [productAdBindings, productCenterProducts, productCenterView]);

  const configuredNoAnomalyProducts = useMemo(
    () =>
      products.filter((product) => {
        const productBindingCount = productAdBindings.filter((binding) => binding.product_id === product.id).length;
        return isProductAdTuningEligible(product, productBindingCount) && isConfiguredNoAnomalyTargetMatch(product);
      }),
    [productAdBindings, products]
  );

  const selectedGoalRuleProductDraft = selectedGoalRuleProduct
    ? productDrafts[selectedGoalRuleProduct.id] || buildProductDraft(selectedGoalRuleProduct)
    : null;
  const selectedGoalRuleIdentityCandidates = selectedGoalRuleProduct ? findAdDraftIdentityCandidates(selectedGoalRuleProduct, products) : [];

  const resolveDashboardFilters = async (): Promise<DashboardWorkflowFilters> => {
    const filters: DashboardWorkflowFilters = {
      market_id: dashboardMarketId ?? undefined,
      goal_type: dashboardGoalType,
      anomaly_type: dashboardAnomalyType,
      suggestion_level: dashboardSuggestionLevel,
      start_date: dashboardStartDate,
      end_date: dashboardEndDate
    };
    const usesDefaultPeriod = dashboardStartDate === defaultPeriod.start && dashboardEndDate === defaultPeriod.end;
    if (!usesDefaultPeriod) {
      return filters;
    }

    try {
      const runs = await fetchSyncRuns(20);
      const latest = runs.find(
        (run) => run.status === "success" && run.period_start && run.period_end && (dashboardMarketId === null || run.market_id === dashboardMarketId)
      );
      if (!latest) {
        return filters;
      }
      setSyncRuns(runs.slice(0, 5));
      if (dashboardMarketId === null) {
        setDashboardMarketId(latest.market_id);
      }
      if (dashboardStartDate !== latest.period_start) {
        setDashboardStartDate(latest.period_start);
      }
      if (dashboardEndDate !== latest.period_end) {
        setDashboardEndDate(latest.period_end);
      }
      return {
        ...filters,
        market_id: dashboardMarketId ?? latest.market_id,
        start_date: latest.period_start,
        end_date: latest.period_end
      };
    } catch {
      return filters;
    }
  };

  const loadDashboard = async () => {
    setDashboardLoading(true);
    try {
      const filters = await resolveDashboardFilters();
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

  const resolveSearchTermFilters = async (): Promise<SearchTermWorkflowFilters> => {
    const filters: SearchTermWorkflowFilters = {
      market_id: searchTermMarketId ?? undefined,
      product_id: searchTermProductId ?? undefined,
      start_date: searchTermStartDate,
      end_date: searchTermEndDate
    };
    const usesDefaultPeriod = searchTermStartDate === defaultPeriod.start && searchTermEndDate === defaultPeriod.end;
    if (!usesDefaultPeriod) {
      return filters;
    }

    try {
      const runs = await fetchSyncRuns(20);
      const latest = runs.find(
        (run) => run.status === "success" && run.period_start && run.period_end && (searchTermMarketId === null || run.market_id === searchTermMarketId)
      );
      if (!latest) {
        return filters;
      }
      setSyncRuns(runs.slice(0, 5));
      if (searchTermMarketId === null) {
        setSearchTermMarketId(latest.market_id);
      }
      if (searchTermStartDate !== latest.period_start) {
        setSearchTermStartDate(latest.period_start);
      }
      if (searchTermEndDate !== latest.period_end) {
        setSearchTermEndDate(latest.period_end);
      }
      return {
        market_id: searchTermMarketId ?? latest.market_id,
        product_id: searchTermProductId ?? undefined,
        start_date: latest.period_start,
        end_date: latest.period_end
      };
    } catch {
      return filters;
    }
  };

  const loadSearchTermAnalysis = async (filtersOverride?: SearchTermWorkflowFilters) => {
    setSearchTermLoading(true);
    try {
      const filters = filtersOverride || (await resolveSearchTermFilters());
      const payload = await fetchSearchTermAnalysis({
        market_id: filters.market_id,
        product_id: filters.product_id,
        semantic_category: searchTermSemanticCategory,
        performance_status: searchTermPerformanceStatus,
        start_date: filters.start_date,
        end_date: filters.end_date,
        min_clicks: searchTermMinClicks ?? undefined,
        min_spend: searchTermMinSpend ?? undefined,
        target_acos: searchTermTargetAcos ?? undefined,
        limit: 200
      });
      setSearchTermAnalysis(payload);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载搜索词分析失败";
      message.error(text);
    } finally {
      setSearchTermLoading(false);
    }
  };

  const loadSearchTermProductReadiness = async (filtersOverride?: SearchTermWorkflowFilters) => {
    setSearchTermProductReadinessLoading(true);
    try {
      const filters = filtersOverride || (await resolveSearchTermFilters());
      const payload = await fetchSearchTermProductReadiness({
        market_id: filters.market_id,
        product_id: filters.product_id,
        start_date: filters.start_date,
        end_date: filters.end_date
      });
      setSearchTermProductReadiness(payload);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载产品维度搜索词就绪状态失败";
      message.error(text);
    } finally {
      setSearchTermProductReadinessLoading(false);
    }
  };

  const loadSearchTermCandidates = async (filtersOverride?: SearchTermWorkflowFilters) => {
    setSearchTermCandidateLoading(true);
    try {
      const filters = filtersOverride || (await resolveSearchTermFilters());
      const payload = await fetchSearchTermCandidates({
        market_id: filters.market_id,
        product_id: filters.product_id,
        semantic_category: searchTermSemanticCategory,
        performance_status: searchTermPerformanceStatus,
        candidate_type: searchTermCandidateType,
        start_date: filters.start_date,
        end_date: filters.end_date,
        min_clicks: searchTermMinClicks ?? undefined,
        min_spend: searchTermMinSpend ?? undefined,
        target_acos: searchTermTargetAcos ?? undefined,
        limit: 100
      });
      setSearchTermCandidates(payload);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载搜索词候选池失败";
      message.error(text);
    } finally {
      setSearchTermCandidateLoading(false);
    }
  };

  const loadSearchTermCandidateDecisions = async (filtersOverride?: SearchTermWorkflowFilters) => {
    setSearchTermDecisionLoading(true);
    try {
      const filters = filtersOverride || (await resolveSearchTermFilters());
      const rows = await fetchSearchTermCandidateDecisions({
        market_id: filters.market_id,
        product_id: filters.product_id,
        start_date: filters.start_date,
        end_date: filters.end_date
      });
      setSearchTermCandidateDecisions(rows);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载搜索词候选处理记录失败";
      message.error(text);
    } finally {
      setSearchTermDecisionLoading(false);
    }
  };

  const loadSearchTermGroupDecisions = async (filtersOverride?: SearchTermWorkflowFilters) => {
    setSearchTermGroupDecisionLoading(true);
    try {
      const filters = filtersOverride || (await resolveSearchTermFilters());
      const rows = await fetchSearchTermGroupDecisions({
        market_id: filters.market_id,
        product_id: filters.product_id,
        semantic_category: searchTermSemanticCategory,
        performance_status: searchTermPerformanceStatus,
        start_date: filters.start_date,
        end_date: filters.end_date
      });
      setSearchTermGroupDecisions(rows);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载搜索词归类组人工记录失败";
      message.error(text);
    } finally {
      setSearchTermGroupDecisionLoading(false);
    }
  };

  const refreshSearchTermWorkflow = async () => {
    const filters = await resolveSearchTermFilters();
    await Promise.all([
      loadSearchTermProductReadiness(filters),
      loadSearchTermAnalysis(filters),
      loadSearchTermCandidates(filters),
      loadSearchTermCandidateDecisions(filters),
      loadSearchTermGroupDecisions(filters)
    ]);
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
    if (activeTab === "search_terms") {
      void refreshSearchTermWorkflow();
    }
  }, [
    activeTab,
    searchTermMarketId,
    searchTermProductId,
    searchTermSemanticCategory,
    searchTermPerformanceStatus,
    searchTermCandidateType,
    searchTermStartDate,
    searchTermEndDate,
    searchTermMinClicks,
    searchTermMinSpend,
    searchTermTargetAcos
  ]);

  useEffect(() => {
    if (activeTab === "products") {
      void loadProducts();
    }
  }, [
    activeTab,
    productMarketId,
    productGoalType,
    productAnomalyType,
    productSuggestionLevel,
    productStartDate,
    productEndDate,
    attributionScope
  ]);

  useEffect(() => {
    if (activeTab === "attribution") {
      void loadProductAttribution();
    }
  }, [
    activeTab,
    productMarketId,
    productStartDate,
    productEndDate,
    attributionScope
  ]);

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

  const openSearchTermDecisionModal = (candidate: SearchTermCandidate) => {
    const recommended = candidate.recommended_manual_decision;
    const decisionType: SearchTermCandidateDecisionType =
      recommended === "adopt_with_changes" || recommended === "reject" || recommended === "observe"
        ? recommended
        : "observe";
    setSearchTermDecisionCandidate(candidate);
    searchTermDecisionForm.resetFields();
    searchTermDecisionForm.setFieldsValue({
      decision_type: decisionType,
      modified_action: candidate.suggested_manual_action,
      reason: candidate.reasoning,
      observe_period: "7d"
    });
  };

  const submitSearchTermCandidateDecision = async () => {
    if (!searchTermDecisionCandidate) {
      message.warning("请先选择搜索词候选");
      return;
    }
    const values = await searchTermDecisionForm.validateFields();
    setSearchTermDecisionSubmitting(true);
    try {
      await createSearchTermCandidateDecision({
        candidate_id: searchTermDecisionCandidate.candidate_id,
        decision_type: values.decision_type,
        modified_action: values.modified_action,
        reason: values.reason,
        observe_period: values.observe_period,
        operator_name: values.operator_name,
        market_id: searchTermMarketId ?? undefined,
        product_id: searchTermProductId ?? undefined,
        semantic_category: searchTermSemanticCategory,
        performance_status: searchTermPerformanceStatus,
        start_date: searchTermStartDate,
        end_date: searchTermEndDate,
        min_clicks: searchTermMinClicks ?? undefined,
        min_spend: searchTermMinSpend ?? undefined,
        target_acos: searchTermTargetAcos ?? undefined,
        limit: 200
      });
      message.success("搜索词人工判断已记录");
      setSearchTermDecisionCandidate(null);
      await loadSearchTermCandidateDecisions();
    } catch (err) {
      const text = err instanceof Error ? err.message : "提交搜索词人工判断失败";
      message.error(text);
    } finally {
      setSearchTermDecisionSubmitting(false);
    }
  };

  const drillDownSearchTermGroup = (group: SearchTermGroupSummary) => {
    setSearchTermSemanticCategory(group.semantic_category);
    setSearchTermPerformanceStatus(group.performance_status);
    setSearchTermCandidateType(undefined);
    void refreshSearchTermWorkflow();
  };

  const openSearchTermGroupDecisionModal = (group: SearchTermGroupSummary) => {
    setSearchTermGroupDecisionGroup(group);
    searchTermGroupDecisionForm.resetFields();
    searchTermGroupDecisionForm.setFieldsValue({
      decision_type: "observe",
      observe_period: "7d",
      reason: group.manual_hint
    });
  };

  const submitSearchTermGroupDecision = async () => {
    if (!searchTermGroupDecisionGroup) {
      message.warning("请先选择搜索词归类组");
      return;
    }
    const values = await searchTermGroupDecisionForm.validateFields();
    setSearchTermGroupDecisionSubmitting(true);
    try {
      await createSearchTermGroupDecision({
        group_key: searchTermGroupDecisionGroup.group_key,
        decision_type: values.decision_type,
        modified_action: values.modified_action,
        reason: values.reason,
        observe_period: values.observe_period,
        operator_name: values.operator_name,
        market_id: searchTermMarketId ?? undefined,
        product_id: searchTermProductId ?? undefined,
        semantic_category: searchTermGroupDecisionGroup.semantic_category,
        performance_status: searchTermGroupDecisionGroup.performance_status,
        start_date: searchTermStartDate,
        end_date: searchTermEndDate,
        min_clicks: searchTermMinClicks ?? undefined,
        min_spend: searchTermMinSpend ?? undefined,
        target_acos: searchTermTargetAcos ?? undefined,
        limit: 500
      });
      message.success("搜索词归类组人工判断已记录");
      setSearchTermGroupDecisionGroup(null);
      await loadSearchTermGroupDecisions();
    } catch (err) {
      const text = err instanceof Error ? err.message : "提交搜索词归类组人工判断失败";
      message.error(text);
    } finally {
      setSearchTermGroupDecisionSubmitting(false);
    }
  };

  const loadSearchTermCandidateReview = async (
    decision: SearchTermCandidateDecision,
    reviewPeriod: "7d" | "14d"
  ) => {
    setSearchTermReviewDecision(decision);
    setSearchTermCandidateReview(null);
    setSearchTermReviewLoading(true);
    try {
      const payload = await fetchSearchTermCandidateReview(decision.id, reviewPeriod);
      setSearchTermCandidateReview(payload);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载搜索词处理复盘失败";
      message.error(text);
    } finally {
      setSearchTermReviewLoading(false);
    }
  };

  const loadSearchTermGroupDecisionReview = async (
    decision: SearchTermGroupDecision,
    reviewPeriod: "7d" | "14d"
  ) => {
    setSearchTermGroupReviewDecision(decision);
    setSearchTermGroupDecisionReview(null);
    setSearchTermGroupReviewLoading(true);
    try {
      const payload = await fetchSearchTermGroupDecisionReview(decision.id, reviewPeriod);
      setSearchTermGroupDecisionReview(payload);
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载搜索词归类组复盘失败";
      message.error(text);
    } finally {
      setSearchTermGroupReviewLoading(false);
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

  const openGoalRuleDrawer = (product: Product) => {
    setProductDrafts((drafts) => ({
      ...drafts,
      [product.id]: drafts[product.id] || buildProductDraft(product)
    }));
    setSelectedGoalRuleProduct(product);
  };

  const openAdDraftAttributionReview = (candidateProductId?: number) => {
    const candidateProduct = selectedGoalRuleIdentityCandidates.find((candidate) => candidate.id === candidateProductId) || null;
    setAdDraftAttributionReviewProduct(candidateProduct);
    setAdDraftAttributionReviewSourceProduct(selectedGoalRuleProduct);
    setAttributionProductId(candidateProductId ?? null);
    setProductMarketId(selectedGoalRuleProduct?.market_id ?? null);
    setSelectedGoalRuleProduct(null);
    setActiveTab("attribution");
  };

  const openAdDraftRealProductRebind = (adDraftProduct: Product, candidateProductId?: number) => {
    const binding = productAdBindings.find((binding) => binding.product_id === adDraftProduct.id && binding.status === "active");
    const candidateProduct = products.find((product) => product.id === candidateProductId) || null;
    setAdDraftAttributionReviewProduct(candidateProduct);
    setAdDraftAttributionReviewSourceProduct(adDraftProduct);
    setAttributionProductId(candidateProductId ?? null);
    setProductMarketId(adDraftProduct.market_id ?? null);

    if (!binding) {
      setActiveTab("attribution");
      message.warning("未找到该草稿对象已确认的广告来源，请在广告归因页人工选择广告来源后确认。");
      return;
    }

    const source: UnboundAdSource = {
      scope_type: binding.scope_type,
      scope_id: binding.scope_id,
      scope_name: binding.scope_name,
      market_id: binding.market_id,
      campaign_id: binding.scope_type === "campaign" ? binding.scope_id : null,
      campaign_name: binding.scope_type === "campaign" ? binding.scope_name : null,
      ad_group_id: binding.scope_type === "ad_group" ? binding.scope_id : null,
      ad_group_name: binding.scope_type === "ad_group" ? binding.scope_name : null,
      metric_rows: 0,
      keyword_count: 0,
      ad_group_count: binding.scope_type === "ad_group" ? 1 : 0,
      search_term_rows: 0,
      impressions: 0,
      clicks: 0,
      cost: 0,
      orders: 0,
      sales: 0,
      acos: 0,
      cvr: 0
    };
    void openAttributionEvidence(source, candidateProductId);
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

  const openAttributionEvidence = async (source: UnboundAdSource, selectedProductId?: number) => {
    if (!source.scope_id) {
      message.warning("缺少归因对象 ID");
      return;
    }
    setAttributionEvidenceOpen(true);
    setAttributionEvidenceLoading(true);
    setAttributionEvidence(null);
    setAttributionEvidenceNote("");
    try {
      const evidence = await fetchProductAttributionEvidence({
        market_id: source.market_id ?? undefined,
        scope_type: source.scope_type,
        scope_id: source.scope_id,
        start_date: productStartDate,
        end_date: productEndDate
      });
      setAttributionEvidence(evidence);
      if (selectedProductId) {
        setAttributionProductId(selectedProductId);
      } else if (!attributionProductId && evidence.candidate_products[0]?.product_id) {
        setAttributionProductId(evidence.candidate_products[0].product_id);
      }
    } catch (err) {
      const text = err instanceof Error ? err.message : "加载产品归因证据失败";
      message.error(text);
    } finally {
      setAttributionEvidenceLoading(false);
    }
  };

  const prefillProductFromAdSource = (source: UnboundAdSource) => {
    setProductSeedSource(source);
    productForm.resetFields();
    productForm.setFieldsValue({
      product_name: source.scope_name || source.ad_group_name || source.campaign_name || undefined,
      market_id: source.market_id ?? productMarketId ?? undefined,
    });
    setCreateProductOpen(true);
  };

  const confirmAdSourceAttribution = async (source: UnboundAdSource, evidenceNote?: string | null) => {
    if (!source.scope_id) {
      message.warning("缺少归因对象 ID");
      return;
    }
    if (!attributionProductId) {
      message.warning("请先选择归因产品");
      return;
    }

    const key = adSourceKey(source);
    setAttributionSavingKey(key);
    try {
      const result = await bindAdSourceToProduct(attributionProductId, {
        scope_type: source.scope_type,
        scope_id: source.scope_id,
        scope_name: source.scope_name,
        market_id: source.market_id,
        created_by: "运营人工确认",
        period_start: productStartDate,
        period_end: productEndDate,
        evidence_note: evidenceNote
      });
      message.success(`确认归因完成：关键词 ${result.keyword_rows_updated} 行，搜索词 ${result.search_term_rows_updated} 行`);
      setAttributionEvidenceOpen(false);
      setAttributionEvidence(null);
      await loadProducts();
    } catch (err) {
      const text = err instanceof Error ? err.message : "确认产品归因失败";
      message.error(text);
    } finally {
      setAttributionSavingKey(null);
    }
  };

  const openProductSearchTermAnalysis = (record: ProductAdBinding) => {
    setSearchTermProductId(record.product_id);
    setSearchTermMarketId(record.market_id ?? productMarketId);
    setSearchTermStartDate(productStartDate);
    setSearchTermEndDate(productEndDate);
    setSearchTermSemanticCategory(undefined);
    setSearchTermPerformanceStatus(undefined);
    setSearchTermCandidateType(undefined);
    setActiveTab("search_terms");
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
      const createdProduct = await createProduct(values);
      message.success("产品已创建");
      setCreateProductOpen(false);
      productForm.resetFields();
      await loadProducts();
      if (productSeedSource?.scope_id) {
        setAttributionProductId(createdProduct.id);
        const refreshedEvidence = await fetchProductAttributionEvidence({
          market_id: productSeedSource.market_id ?? undefined,
          scope_type: productSeedSource.scope_type,
          scope_id: productSeedSource.scope_id,
          start_date: productStartDate,
          end_date: productEndDate
        });
        setAttributionEvidence(refreshedEvidence);
        setAttributionEvidenceOpen(true);
      }
      setProductSeedSource(null);
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

  const renderAnomalyQueueEmptyState = () => {
    if (displayedAnomalies.length === 0 && anomalies.length > 0) {
      return <Empty description="当前筛选条件下暂无异常" />;
    }
    if (anomalies.length === 0 && configuredNoAnomalyProducts.length > 0) {
      return (
        <div className="anomaly-empty-reason">
          <Empty
            description={
              <Space direction="vertical" size={4}>
                <Text strong>当前已配置对象均未越线</Text>
                <Text type="secondary">不是系统无数据或异常生成失败；当前人工目标规则下没有需要进入队列的异常。</Text>
                <Text type="secondary">已配置且未触发异常对象：{configuredNoAnomalyProducts.length} 个</Text>
              </Space>
            }
          />
          <Button
            onClick={() => {
              setProductCenterView("ad_tuning");
              setActiveTab("products");
            }}
          >
            查看产品中心目标
          </Button>
        </div>
      );
    }
    return <Empty description="暂无异常" />;
  };

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

  const searchTermColumns = useMemo<ColumnsType<SearchTermAnalysisRow>>(
    () => [
      {
        title: "搜索词",
        dataIndex: "search_term",
        width: 260,
        fixed: "left",
        render: (value: string, record) => (
          <Space direction="vertical" size={2}>
            <Text strong>{value}</Text>
            <Text type="secondary" className="search-term-row-meta">
              {record.manual_hint || "仅供人工判断"}
            </Text>
          </Space>
        )
      },
      {
        title: "语义分类",
        dataIndex: "semantic_category",
        width: 170,
        render: (value: SearchTermSemanticCategory, record) => (
          <Space direction="vertical" size={2}>
            <Tag color={searchTermSemanticColors[value] || "default"}>
              {searchTermSemanticLabels[value] || record.semantic_label || value}
            </Tag>
            <Text type="secondary" className="search-term-row-meta">
              {record.semantic_reasons[0] || "-"}
            </Text>
          </Space>
        )
      },
      {
        title: "表现分类",
        dataIndex: "performance_status",
        width: 180,
        render: (value: SearchTermPerformanceStatus, record) => (
          <Space direction="vertical" size={2}>
            <Tag color={searchTermPerformanceColors[value] || "default"}>
              {searchTermPerformanceLabels[value] || record.performance_label || value}
            </Tag>
            <Text type="secondary" className="search-term-row-meta">
              {record.performance_reasons[0] || "-"}
            </Text>
          </Space>
        )
      },
      {
        title: "核心指标",
        width: 270,
        render: (_, record) => (
          <Space wrap size={[4, 4]} className="metric-pills">
            <Tag>点击 {record.clicks.toLocaleString()}</Tag>
            <Tag>花费 {formatMoney(record.cost)}</Tag>
            <Tag>订单 {record.orders.toLocaleString()}</Tag>
            <Tag>销售 {formatMoney(record.sales)}</Tag>
            <Tag color={record.acos > (searchTermTargetAcos ?? 0.35) ? "orange" : "green"}>ACOS {formatPercent(record.acos)}</Tag>
            <Tag>CVR {formatPercent(record.cvr)}</Tag>
          </Space>
        )
      },
      {
        title: "来源证据",
        width: 300,
        render: (_, record) => (
          <Space direction="vertical" size={2}>
            <Text type="secondary">Campaign / Ad Group / 关键词</Text>
            <Text className="search-term-row-meta">
              {record.evidence.campaign_name || "-"} / {record.evidence.ad_group_name || "-"} /{" "}
              {record.evidence.keyword_text || "-"}
            </Text>
            <Text type="secondary">
              来源数：{record.campaign_count} 个 Campaign，{record.ad_group_count} 个 Ad Group，{record.keyword_count} 个关键词
            </Text>
          </Space>
        )
      },
      {
        title: "指标行",
        dataIndex: "metric_rows",
        width: 90,
        render: (value: number) => value.toLocaleString()
      }
    ],
    [searchTermTargetAcos]
  );

  const searchTermCandidateColumns = useMemo<ColumnsType<SearchTermCandidate>>(
    () => [
      {
        title: "候选搜索词",
        dataIndex: "search_term",
        width: 260,
        fixed: "left",
        render: (value: string, record) => (
          <Space direction="vertical" size={2}>
            <Text strong>{value}</Text>
            <Tag color={searchTermCandidateColors[record.candidate_type] || "default"}>
              {searchTermCandidateLabels[record.candidate_type] || record.candidate_label}
            </Tag>
          </Space>
        )
      },
      {
        title: "推荐人工判断",
        dataIndex: "recommended_manual_decision",
        width: 150,
        render: (value: DecisionInput["decision_type"]) => <Tag>{decisionLabels[value] || value}</Tag>
      },
      {
        title: "建议人工处理说明",
        dataIndex: "suggested_manual_action",
        width: 340,
        render: (value: string, record) => (
          <Space direction="vertical" size={4}>
            <Text>{value}</Text>
            <Text type="secondary" className="search-term-candidate-reason">
              {record.reasoning}
            </Text>
            <Text type="secondary" className="search-term-candidate-reason">
              {record.risk_note}
            </Text>
          </Space>
        )
      },
      {
        title: "指标",
        width: 250,
        render: (_, record) => (
          <Space wrap size={[4, 4]} className="metric-pills">
            <Tag>点击 {record.metrics.clicks.toLocaleString()}</Tag>
            <Tag>花费 {formatMoney(record.metrics.cost)}</Tag>
            <Tag>订单 {record.metrics.orders.toLocaleString()}</Tag>
            <Tag>销售 {formatMoney(record.metrics.sales)}</Tag>
            <Tag color={record.metrics.acos > (searchTermTargetAcos ?? 0.35) ? "orange" : "green"}>
              ACOS {formatPercent(record.metrics.acos)}
            </Tag>
          </Space>
        )
      },
      {
        title: "来源证据",
        width: 280,
        render: (_, record) => (
          <Space direction="vertical" size={2}>
            <Text type="secondary">Campaign / Ad Group / 关键词</Text>
            <Text className="search-term-row-meta">
              {record.evidence.campaign_name || "-"} / {record.evidence.ad_group_name || "-"} /{" "}
              {record.evidence.keyword_text || "-"}
            </Text>
            <Text type="secondary">{record.manual_hint}</Text>
          </Space>
        )
      },
      {
        title: "人工记录",
        width: 150,
        render: (_, record) => (
          <Button size="small" icon={<AuditOutlined />} onClick={() => openSearchTermDecisionModal(record)}>
            记录人工判断
          </Button>
        )
      }
    ],
    [searchTermTargetAcos]
  );

  const searchTermCandidateDecisionColumns = useMemo<ColumnsType<SearchTermCandidateDecision>>(
    () => [
      {
        title: "搜索词",
        dataIndex: "search_term",
        width: 240,
        render: (value: string, record) => (
          <Space direction="vertical" size={2}>
            <Text strong>{value}</Text>
            <Tag color={searchTermCandidateColors[record.candidate_type] || "default"}>
              {searchTermCandidateLabels[record.candidate_type] || record.candidate_type}
            </Tag>
          </Space>
        )
      },
      {
        title: "人工判断",
        dataIndex: "decision_type",
        width: 150,
        render: (value: SearchTermCandidateDecisionType, record) => (
          <Space direction="vertical" size={2}>
            <Tag>{decisionLabels[value] || value}</Tag>
            {record.observe_period ? <Text type="secondary">观察 {record.observe_period === "7d" ? "7 天" : "14 天"}</Text> : null}
          </Space>
        )
      },
      {
        title: "处理说明",
        width: 360,
        render: (_, record) => (
          <Space direction="vertical" size={2}>
            <Text>{record.modified_action || record.reason || "-"}</Text>
            {record.modified_action && record.reason ? <Text type="secondary">{record.reason}</Text> : null}
          </Space>
        )
      },
      {
        title: "记录信息",
        width: 220,
        render: (_, record) => (
          <Space direction="vertical" size={0} className="search-term-decision-meta">
            <Text type="secondary">处理人：{record.operator_name || "-"}</Text>
            <Text type="secondary">{new Date(record.decided_at).toLocaleString()}</Text>
          </Space>
        )
      },
      {
        title: "查看复盘",
        width: 180,
        render: (_, record) => (
          <Space wrap size={[4, 4]}>
            <Button size="small" onClick={() => void loadSearchTermCandidateReview(record, "7d")}>
              7 天复盘
            </Button>
            <Button size="small" onClick={() => void loadSearchTermCandidateReview(record, "14d")}>
              14 天复盘
            </Button>
          </Space>
        )
      }
    ],
    []
  );

  const searchTermGroupDecisionColumns = useMemo<ColumnsType<SearchTermGroupDecision>>(
    () => [
      {
        title: "归类组",
        dataIndex: "group_label",
        width: 260,
        render: (value: string, record) => (
          <Space direction="vertical" size={2}>
            <Text strong>{value}</Text>
            <Space wrap size={[4, 4]}>
              <Tag color={searchTermSemanticColors[record.semantic_category] || "default"}>
                {searchTermSemanticLabels[record.semantic_category] || record.semantic_category}
              </Tag>
              <Tag color={searchTermPerformanceColors[record.performance_status] || "default"}>
                {searchTermPerformanceLabels[record.performance_status] || record.performance_status}
              </Tag>
            </Space>
          </Space>
        )
      },
      {
        title: "人工判断",
        dataIndex: "decision_type",
        width: 150,
        render: (value: SearchTermCandidateDecisionType, record) => (
          <Space direction="vertical" size={2}>
            <Tag>{decisionLabels[value] || value}</Tag>
            {record.observe_period ? <Text type="secondary">观察 {record.observe_period === "7d" ? "7 天" : "14 天"}</Text> : null}
          </Space>
        )
      },
      {
        title: "组快照",
        width: 260,
        render: (_, record) => {
          const snapshot = record.group_snapshot as Partial<SearchTermGroupSummary>;
          return (
            <Space wrap size={[4, 4]} className="metric-pills">
              <Tag>词 {snapshot.terms?.toLocaleString?.() || "-"}</Tag>
              <Tag>点击 {snapshot.clicks?.toLocaleString?.() || "-"}</Tag>
              <Tag>花费 {typeof snapshot.cost === "number" ? formatMoney(snapshot.cost) : "-"}</Tag>
              <Tag>订单 {snapshot.orders?.toLocaleString?.() || "-"}</Tag>
              <Tag>ACOS {typeof snapshot.acos === "number" ? formatPercent(snapshot.acos) : "-"}</Tag>
            </Space>
          );
        }
      },
      {
        title: "记录口径",
        width: 150,
        render: (_, record) => <Tag color={record.product_id ? "blue" : "default"}>{record.product_id ? "产品级组判断" : "全局组判断"}</Tag>
      },
      {
        title: "处理说明",
        width: 340,
        render: (_, record) => (
          <Space direction="vertical" size={2}>
            <Text>{record.modified_action || record.reason || "-"}</Text>
            {record.modified_action && record.reason ? <Text type="secondary">{record.reason}</Text> : null}
          </Space>
        )
      },
      {
        title: "记录信息",
        width: 220,
        render: (_, record) => (
          <Space direction="vertical" size={0} className="search-term-decision-meta">
            <Text type="secondary">处理人：{record.operator_name || "-"}</Text>
            <Text type="secondary">{record.period_start} 至 {record.period_end}</Text>
            <Text type="secondary">{new Date(record.decided_at).toLocaleString()}</Text>
          </Space>
        )
      },
      {
        title: "复盘",
        width: 180,
        fixed: "right",
        render: (_, record) => (
          <Space wrap>
            <Button size="small" onClick={() => void loadSearchTermGroupDecisionReview(record, "7d")}>
              查看复盘
            </Button>
            <Button size="small" onClick={() => void loadSearchTermGroupDecisionReview(record, "14d")}>
              14 天
            </Button>
          </Space>
        )
      }
    ],
    []
  );

  const attributionProductOptions = useMemo(
    () =>
      products
        .filter((product) => !isAdDraftProduct(product))
        .map((product) => ({
          value: product.id,
          label: product.product_name || product.asin || product.msku || `产品 ${product.id}`
        })),
    [products]
  );
  const selectedAttributionCandidate = useMemo(
    () => attributionEvidence?.candidate_products.find((candidate) => candidate.product_id === attributionProductId) || null,
    [attributionEvidence, attributionProductId]
  );
  const selectedAttributionProduct = useMemo(
    () => products.find((product) => product.id === attributionProductId) || null,
    [attributionProductId, products]
  );

  const isProductSearchTermMode = Boolean(searchTermProductId);
  const selectedSearchTermProduct = useMemo(
    () => products.find((product) => product.id === searchTermProductId) || null,
    [products, searchTermProductId]
  );
  const selectedReadinessProduct = useMemo(
    () => searchTermProductReadiness?.products.find((product) => product.product_id === searchTermProductId) || null,
    [searchTermProductReadiness, searchTermProductId]
  );
  const searchTermGroupDecisionScopeLabel = isProductSearchTermMode ? "产品级组判断" : "全局组判断";
  const searchTermGroupDecisionScopeDetail = isProductSearchTermMode
    ? "当前记录口径：当前产品级记录，会随 product_id 一起保存。"
    : "当前记录口径：全局组判断，不归属到某个具体产品。";
  const searchTermGroupDecisionListDetail = isProductSearchTermMode
    ? "当前列表口径：当前产品级记录，只展示当前产品下的组级人工判断。"
    : "当前列表口径：全局组判断，未选择产品时不代表任何单一产品。";
  const productGroupDecisionTodo =
    isProductSearchTermMode &&
    (searchTermAnalysis?.group_summary.length ?? 0) > 0 &&
    searchTermGroupDecisions.length === 0;
  const productReviewChecklist = useMemo(() => {
    const activeBindingCount = searchTermProductReadiness?.summary.active_binding_count ?? 0;
    const attributedSearchTermRows = selectedReadinessProduct?.search_term_rows ?? 0;
    const productGroupCount = searchTermProductId ? searchTermAnalysis?.group_summary.length ?? 0 : 0;
    const groupDecisionCount = searchTermGroupDecisions.length;

    return [
      {
        key: "confirmed-binding",
        label: "已确认归因规则",
        ready: activeBindingCount > 0,
        detail: activeBindingCount > 0 ? `已确认归因规则 ${activeBindingCount} 条` : "待人工确认归因"
      },
      {
        key: "attributed-search-terms",
        label: "已归因搜索词",
        ready: attributedSearchTermRows > 0,
        detail: attributedSearchTermRows > 0 ? `已归因搜索词 ${attributedSearchTermRows} 行` : "等待产品归因后回填搜索词"
      },
      {
        key: "product-groups",
        label: "产品维度归类组",
        ready: productGroupCount > 0,
        detail: productGroupCount > 0 ? `已形成产品维度归类组 ${productGroupCount} 组` : "等待产品维度归类结果"
      },
      {
        key: "group-decisions",
        label: isProductSearchTermMode ? "产品级组判断记录" : "组级人工记录",
        ready: groupDecisionCount > 0,
        detail: groupDecisionCount > 0
          ? `当前产品级记录 ${groupDecisionCount} 条`
          : isProductSearchTermMode
            ? "尚未记录当前产品的产品级组判断"
            : "尚未记录组级人工判断"
      }
    ];
  }, [
    searchTermProductReadiness,
    selectedReadinessProduct,
    searchTermProductId,
    isProductSearchTermMode,
    searchTermAnalysis?.group_summary.length,
    searchTermGroupDecisions.length
  ]);
  const groupPriorityReviewItems = useMemo(() => {
    if (!searchTermAnalysis) {
      return [];
    }

    const rankedItems = searchTermAnalysis.group_summary
      .map((group) => {
        if (group.performance_status === "high_acos" || group.performance_status === "costly_no_order") {
          return {
            group,
            rank: 1,
            badge: "高风险优先",
            reason: "先看高风险组：有单高 ACOS 或高花费无单，适合优先人工复核。",
            color: "red"
          };
        }
        if (group.performance_status === "high_conversion") {
          return {
            group,
            rank: 2,
            badge: "机会复核",
            reason: "高转化机会：有订单且 ACOS 未超目标，适合检查是否值得继续观察。",
            color: "green"
          };
        }
        if (group.performance_status === "data_insufficient" && (group.cost >= 50 || group.terms >= 50)) {
          return {
            group,
            rank: 3,
            badge: "低信号大池",
            reason: "数据不足大池：花费或词量集中，但信号不足，适合先下钻看代表词。",
            color: "gold"
          };
        }
        return {
          group,
          rank: 4,
          badge: "低优先级",
          reason: "低优先级观察：当前不需要放在首批复核。",
          color: "default"
        };
      })
      .filter((item) => item.rank <= 3)
      .sort((a, b) => a.rank - b.rank || b.group.cost - a.group.cost || b.group.terms - a.group.terms);
    const requiredRanks = [1, 2, 3];
    const categorySamples = requiredRanks
      .map((rank) => rankedItems.find((item) => item.rank === rank))
      .filter((item): item is (typeof rankedItems)[number] => Boolean(item));
    const sampleKeys = new Set(categorySamples.map((item) => item.group.group_key));
    const remainingItems = rankedItems.filter((item) => !sampleKeys.has(item.group.group_key));
    return [...categorySamples, ...remainingItems].slice(0, 5);
  }, [searchTermAnalysis]);

  const firstAttributionCandidate = productAttributionCandidates?.rows?.[0] || null;
  const adDraftAttributionSourceCandidates = useMemo(
    () =>
      adDraftAttributionReviewSourceProduct
        ? unboundAdSources.filter((source) => sourceMatchesProductIdentity(source, adDraftAttributionReviewSourceProduct))
        : [],
    [adDraftAttributionReviewSourceProduct, unboundAdSources]
  );
  const firstAdDraftAttributionSourceCandidate = adDraftAttributionSourceCandidates[0] || null;
  const productWorkflowGroupDecisionCount = isProductSearchTermMode ? searchTermGroupDecisions.length : 0;
  const openFirstBoundProductSearchTermAnalysis = () => {
    if (productAdBindings[0]) {
      openProductSearchTermAnalysis(productAdBindings[0]);
    }
  };
  const realWorkflowRehearsalSteps = useMemo(
    () => [
      {
        key: "manual-attribution",
        title: "确认产品归因",
        status: productAdBindings.length > 0 ? "已完成" : "待人工确认",
        detail:
          productAdBindings.length > 0
            ? `已有 ${productAdBindings.length} 条人工确认归因规则`
            : firstAttributionCandidate
              ? `建议先确认 ${firstAttributionCandidate.source.scope_name || firstAttributionCandidate.source.scope_id || "首条高可信广告来源"}`
              : "等待高可信归因候选",
        actionLabel: productAdBindings.length > 0 ? "已确认" : "查看证据并确认归因",
        disabled: productAdBindings.length > 0 || !firstAttributionCandidate,
        onClick: () =>
          firstAttributionCandidate
            ? openAttributionEvidence(firstAttributionCandidate.source, firstAttributionCandidate.candidate_product.product_id)
            : undefined
      },
      {
        key: "product-search-terms",
        title: "查看产品维度搜索词",
        status: productAdBindings.length > 0 ? "可查看" : "等待归因",
        detail: productAdBindings.length > 0 ? "进入已归因产品的搜索词归类聚合" : "先人工确认产品归因规则",
        actionLabel: "查看产品维度搜索词",
        disabled: productAdBindings.length === 0,
        onClick: () => {
          if (productAdBindings[0]) {
            openProductSearchTermAnalysis(productAdBindings[0]);
          }
        }
      },
      {
        key: "group-decision",
        title: "记录产品级组判断",
        status: productWorkflowGroupDecisionCount > 0 ? "已记录产品级" : "待记录产品级",
        detail:
          productWorkflowGroupDecisionCount > 0
            ? `当前产品级记录 ${productWorkflowGroupDecisionCount} 条`
            : "进入已归因产品的搜索词分析，使用待办入口记录产品级组判断",
        actionLabel: "记录产品级组判断",
        disabled: productAdBindings.length === 0,
        onClick: openFirstBoundProductSearchTermAnalysis
      },
      {
        key: "group-review",
        title: "复盘组级判断",
        status: productWorkflowGroupDecisionCount > 0 ? "可复盘" : "等待产品级记录",
        detail: productWorkflowGroupDecisionCount > 0 ? "在产品级组记录中查看 7 天 / 14 天复盘" : "先记录产品级组判断，后续有数据再复盘",
        actionLabel: "查看产品级组记录",
        disabled: productAdBindings.length === 0,
        onClick: openFirstBoundProductSearchTermAnalysis
      }
    ],
    [firstAttributionCandidate, productAdBindings, productWorkflowGroupDecisionCount]
  );

  const productAttributionCandidateColumns = useMemo<ColumnsType<ProductAttributionCandidateRow>>(
    () => [
      {
        title: "归因对象",
        width: 300,
        render: (_, record) => (
          <Space direction="vertical" size={2}>
            <Text strong>{record.source.scope_name || record.source.scope_id || "-"}</Text>
            <Text type="secondary">
              Campaign {record.source.campaign_name || record.source.campaign_id || "-"}
              {record.source.ad_group_id ? ` / Ad Group ${record.source.ad_group_name || record.source.ad_group_id}` : ""}
            </Text>
          </Space>
        )
      },
      {
        title: "推荐产品",
        width: 230,
        render: (_, record) => (
          <Space direction="vertical" size={2}>
            {record.priority_rank === 1 ? (
              <Tag color="blue" className="attribution-priority-badge">
                建议优先确认 #{record.priority_rank}
              </Tag>
            ) : (
              <Tag className="attribution-priority-badge">
                {record.priority_label} #{record.priority_rank}
              </Tag>
            )}
            <Text strong>
              {record.candidate_product.product_name || record.candidate_product.msku || `产品 ${record.candidate_product.product_id}`}
            </Text>
            <Text type="secondary">
              MSKU {record.candidate_product.msku || "-"} / ASIN {record.candidate_product.asin || "-"}
            </Text>
          </Space>
        )
      },
      {
        title: "可信度",
        width: 180,
        render: (_, record) => (
          <Space direction="vertical" size={2}>
            <Tag color={confidenceColor(record.confidence_level)}>
              {confidenceLabel(record.confidence_level)} {record.confidence_score}
            </Tag>
            <Text type="secondary" className="attribution-candidate-reason">
              {record.confidence_reasons.join("；")}
            </Text>
          </Space>
        )
      },
      {
        title: "确认后影响",
        width: 210,
        render: (_, record) => (
          <Space wrap size={[4, 4]} className="attribution-unlock-impact">
            <Tag>{record.unlock_impact.search_term_rows} 行搜索词</Tag>
            <Tag>花费 {formatMoney(record.unlock_impact.cost)}</Tag>
            <Tag>销售 {formatMoney(record.unlock_impact.sales)}</Tag>
            <Tag>订单 {record.unlock_impact.orders}</Tag>
            <Tag color="orange">ACOS {formatPercent(record.unlock_impact.acos)}</Tag>
          </Space>
        )
      },
      {
        title: "人工确认",
        width: 240,
        render: (_, record) => (
          <Space direction="vertical" size={6}>
            <Text type="secondary">{record.manual_hint || "必须查看证据并由人工确认后才会保存归因规则"}</Text>
            <Button size="small" icon={<EyeOutlined />} onClick={() => void openAttributionEvidence(record.source, record.candidate_product.product_id)}>
              查看证据
            </Button>
          </Space>
        )
      }
    ],
    [productEndDate, productStartDate]
  );

  const attributionColumns = useMemo<ColumnsType<UnboundAdSource>>(
    () => [
      {
        title: "归因颗粒度",
        dataIndex: "scope_type",
        width: 110,
        render: (value: AttributionScopeType) => <Tag>{attributionScopeLabels[value] || value}</Tag>
      },
      {
        title: "广告来源",
        width: 320,
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Text strong>{record.scope_name || record.scope_id || "-"}</Text>
            <Text type="secondary">
              Campaign {record.campaign_name || record.campaign_id || "-"}
              {record.ad_group_id ? ` / Ad Group ${record.ad_group_name || record.ad_group_id}` : ""}
            </Text>
          </Space>
        )
      },
      {
        title: "数据量",
        width: 170,
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Text>{record.metric_rows} 行关键词指标</Text>
            <Text type="secondary">{record.search_term_rows} 行搜索词</Text>
          </Space>
        )
      },
      {
        title: "花费 / 销售",
        width: 150,
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Text>${formatMoney(record.cost)}</Text>
            <Text type="secondary">${formatMoney(record.sales)}</Text>
          </Space>
        )
      },
      {
        title: "订单",
        dataIndex: "orders",
        width: 80
      },
      {
        title: "ACOS",
        width: 90,
        render: (_, record) => formatPercent(record.acos)
      },
      {
        title: "",
        width: 260,
        align: "right",
        render: (_, record) => (
          <Space wrap size={[4, 4]}>
            <Button
              icon={<EyeOutlined />}
              size="small"
              disabled={!record.scope_id}
              loading={attributionEvidenceLoading && attributionEvidence?.source.scope_id === record.scope_id}
              onClick={() => void openAttributionEvidence(record)}
            >
              查看证据
            </Button>
            <Button size="small" disabled={!record.scope_id} onClick={() => prefillProductFromAdSource(record)}>
              从广告来源创建产品草稿
            </Button>
          </Space>
        )
      }
    ],
    [attributionEvidence, attributionEvidenceLoading, attributionProductId, productEndDate, productMarketId, productStartDate]
  );

  const bindingColumns = useMemo<ColumnsType<ProductAdBinding>>(
    () => [
      {
        title: "产品",
        dataIndex: "product_id",
        width: 180,
        render: (value: number) => products.find((product) => product.id === value)?.product_name || `产品 ${value}`
      },
      {
        title: "归因颗粒度",
        dataIndex: "scope_type",
        width: 110,
        render: (value: AttributionScopeType) => <Tag>{attributionScopeLabels[value] || value}</Tag>
      },
      {
        title: "归因对象",
        width: 260,
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Text>{record.scope_name || record.scope_id}</Text>
            <Text type="secondary">{record.scope_id}</Text>
          </Space>
        )
      },
      {
        title: "状态",
        dataIndex: "status",
        width: 90,
        render: (value: string) => <Tag color={value === "active" ? "green" : "default"}>{value === "active" ? "生效" : value}</Tag>
      },
      {
        title: "证据快照",
        dataIndex: "evidence_json",
        width: 260,
        render: (value: string | null) => <Text type="secondary">{bindingEvidenceSummary(value)}</Text>
      },
      {
        title: "更新时间",
        dataIndex: "updated_at",
        width: 180
      },
      {
        title: "",
        width: 150,
        align: "right",
        render: (_, record) => (
          <Button
            size="small"
            icon={<SearchOutlined />}
            className="binding-search-term-action"
            onClick={() => openProductSearchTermAnalysis(record)}
          >
            查看搜索词分析
          </Button>
        )
      }
    ],
    [productEndDate, productMarketId, productStartDate, products]
  );

  const productColumns = useMemo<ColumnsType<Product>>(
    () => [
      {
        title: "产品 / 广告对象身份",
        dataIndex: "product_name",
        width: 340,
        fixed: "left",
        render: (_value, record) => {
          const familyHint = getAdObjectGranularityHint(record, products, productAdBindings);
          return (
          <div className="product-identity-cell">
            {needsAdDraftIdentityReview(record) ? (
              <div className="product-center-ad-draft-identity">
                <Tag color="orange">广告对象待关联真实商品</Tag>
                <Text type="secondary" className="compact-note">
                  来自 SP 广告来源草稿，不是销售表现商品档案
                </Text>
                {familyHint ? (
                  <div className="product-family-ad-object-hint">
                    <Tag color="blue">疑似商品族广告对象</Tag>
                    <div className="product-family-evidence-list">
                      <span>同系列候选 {familyHint.candidateCount} 个</span>
                      <span>Top 销售占比 {formatPercent(familyHint.topSalesShare)}</span>
                      <span>
                        {familyHint.specificSearchHitCount === 0
                          ? "搜索词未命中明确 ASIN / MSKU / SKU"
                          : `搜索词命中明确 SKU 线索 ${familyHint.specificSearchHitCount} 条`}
                      </span>
                    </div>
                    <Text type="secondary" className="compact-note">
                      建议先选择 / 创建商品族；如能确认单品，再细分到具体 SKU
                    </Text>
                  </div>
                ) : null}
                <Button
                  size="small"
                  icon={<AuditOutlined />}
                  onClick={() => void openAdDraftRealProductRebind(record, findAdDraftIdentityCandidates(record, products)[0]?.id)}
                >
                  关联真实商品
                </Button>
              </div>
            ) : null}
            <Text strong className="product-identity-name">
              {record.product_name || record.asin || record.msku || `产品 ${record.id}`}
            </Text>
            <div className="product-identity-meta">
              <span>
                <Text type="secondary">ASIN</Text> {record.asin || "-"}
              </span>
              <span>
                <Text type="secondary">MSKU</Text> {record.msku || "-"}
              </span>
            </div>
            <div className="product-identity-meta">
              <Tag className="product-identity-tag">类目 {record.category || "-"}</Tag>
            </div>
          </div>
          );
        }
      },
      {
        title: "店铺 / 数据来源",
        width: 150,
        render: (_, record) => (
          <Space direction="vertical" size={2}>
            <Text>{formatProductMarketLabel(record)}</Text>
            <Tag className="product-identity-tag">{productSourceLabel(record)}</Tag>
          </Space>
        )
      },
      {
        title: "归因状态",
        width: 150,
        render: (_, record) => {
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          const adCoverageStatus = getProductAdCoverageStatus(record, productBindingCount);
          const coverageMeta = productAdCoverageMeta[adCoverageStatus];
          const isAdTuningEligible = isProductAdTuningEligible(record, productBindingCount);
          return (
            <Space direction="vertical" size={4}>
              <Tag color={coverageMeta.color}>
                {adCoverageStatus === "attributed" ? `已归因 ${productBindingCount}` : coverageMeta.label}
              </Tag>
              <Text type="secondary" className="compact-note">
                {coverageMeta.description}
              </Text>
              {isAdTuningEligible ? (
                <Button
                  size="small"
                  onClick={() => {
                    setAttributionProductId(record.id);
                    setActiveTab("attribution");
                  }}
                >
                  管理归因
                </Button>
              ) : (
                <Button size="small" disabled>
                  无需归因
                </Button>
              )}
            </Space>
          );
        }
      },
      {
        title: "销售表现快照",
        width: 260,
        render: (_, record) => {
          const snapshot = record.sales_snapshot;
          if (!snapshot) {
            return <Text type="secondary">暂无销售表现快照</Text>;
          }
          return (
            <div className="product-sales-snapshot-cell">
              <div className="product-sales-snapshot-grid">
                <span>
                  <Text type="secondary">销售额</Text>
                  <Text strong>{formatMoney(snapshot.sales)}</Text>
                </span>
                <span>
                  <Text type="secondary">订单</Text>
                  <Text strong>{snapshot.orders.toLocaleString()}</Text>
                </span>
                <span>
                  <Text type="secondary">Sessions</Text>
                  <Text strong>{snapshot.sessions.toLocaleString()}</Text>
                </span>
                <span>
                  <Text type="secondary">净利</Text>
                  <Text strong>{formatMoney(snapshot.net_profit)}</Text>
                </span>
              </div>
              <div className="product-identity-meta">
                <Tag className="product-identity-tag">广告辅助 {formatMoney(snapshot.ads_spend)} / ACOS {formatPercent(snapshot.acos)}</Tag>
                <Text type="secondary">
                  {snapshot.period_start} 至 {snapshot.period_end}
                </Text>
              </div>
            </div>
          );
        }
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
        title: "目标与数据表现是否匹配",
        width: 180,
        render: (_, record) => {
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          const adDraftRuleScopeWarning = needsAdDraftIdentityReview(record) ? (
            <Text type="secondary" className="compact-note ad-draft-rule-scope-warning">
              当前规则挂在广告草稿对象上，关联真实商品后再作为产品级规则使用
            </Text>
          ) : null;
          if (!isProductAdTuningEligible(record, productBindingCount)) {
            return (
              <Space direction="vertical" size={0}>
                <Tag>{productAdCoverageMeta.not_advertised.label}</Tag>
                <Text type="secondary" className="compact-note">
                  {productAdCoverageMeta.not_advertised.description}
                </Text>
                {adDraftRuleScopeWarning}
              </Space>
            );
          }
          if (needsProductGoalRuleSetup(record, productBindingCount)) {
            return (
              <Space direction="vertical" size={0}>
                <Tag color="orange">目标 / 规则待设置</Tag>
                <Text type="secondary" className="compact-note">
                  有 SP 指标，需人工设置产品目标和规则后再参与异常判断
                </Text>
                {adDraftRuleScopeWarning}
              </Space>
            );
          }
          if (isConfiguredNoAnomalyTargetMatch(record)) {
            const targetAcos = record.rules?.target_acos;
            return (
              <Space direction="vertical" size={0} className="target-match-ready-state">
                <Tag color="green">目标已配置</Tag>
                <Text strong>当前未触发异常</Text>
                <Text type="secondary" className="compact-note">
                  ACOS {formatPercent(record.sp_metrics.acos)} 未高于目标 ACOS {formatPercent(typeof targetAcos === "number" ? targetAcos : 0)}
                </Text>
                {adDraftRuleScopeWarning}
              </Space>
            );
          }
          return (
            <Space direction="vertical" size={0}>
              <Tag color={targetMatchColors[record.target_match.status]}>
                {targetMatchLabels[record.target_match.status] || record.target_match.status}
              </Tag>
              <Text type="secondary" className="compact-note">
                {record.target_match.reason}
              </Text>
              {adDraftRuleScopeWarning}
            </Space>
          );
        }
      },
      {
        title: "产品目标",
        width: 170,
        render: (_, record) => {
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          if (!isProductAdRuleEditable(record, productBindingCount)) {
            return renderNoSpCoverageAdRuleReadonly();
          }
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
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          if (!isProductAdRuleEditable(record, productBindingCount)) {
            return renderNoSpCoverageAdRuleReadonly();
          }
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
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          if (!isProductAdRuleEditable(record, productBindingCount)) {
            return renderNoSpCoverageAdRuleReadonly();
          }
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
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          if (!isProductAdRuleEditable(record, productBindingCount)) {
            return renderNoSpCoverageAdRuleReadonly();
          }
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
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          if (!isProductAdRuleEditable(record, productBindingCount)) {
            return renderNoSpCoverageAdRuleReadonly();
          }
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
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          if (!isProductAdRuleEditable(record, productBindingCount)) {
            return renderNoSpCoverageAdRuleReadonly();
          }
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
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          if (!isProductAdRuleEditable(record, productBindingCount)) {
            return renderNoSpCoverageAdRuleReadonly();
          }
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
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          if (!isProductAdRuleEditable(record, productBindingCount)) {
            return renderNoSpCoverageAdRuleReadonly();
          }
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
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          if (!isProductAdRuleEditable(record, productBindingCount)) {
            return renderNoSpCoverageAdRuleReadonly();
          }
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
        title: "操作",
        width: 150,
        align: "right",
        fixed: "right",
        render: (_, record) => {
          const productBindingCount = productAdBindings.filter((binding) => binding.product_id === record.id).length;
          if (!isProductAdTuningEligible(record, productBindingCount)) {
            return (
              <Space direction="vertical" size={6} align="end">
                <Button size="small" disabled>
                  仅销售档案
                </Button>
                <Text type="secondary" className="compact-note">
                  不进入广告调优待办
                </Text>
              </Space>
            );
          }
          return (
            <Space direction="vertical" size={6} align="end">
              <Button size="small" icon={<AuditOutlined />} onClick={() => openGoalRuleDrawer(record)}>
                设置目标 / 规则
              </Button>
              <Button
                size="small"
                icon={<SaveOutlined />}
                loading={productSavingId === record.id}
                onClick={() => void saveProductSettings(record.id)}
              >
                保存设置
              </Button>
            </Space>
          );
        }
      }
    ],
    [productAdBindings, productDrafts, productSavingId, products]
  );

  const productCenterTableColumns = useMemo<ColumnsType<Product>>(
    () =>
      productCenterView === "sales_profile"
        ? productColumns.filter((column) => !productSalesProfileHiddenColumnTitles.has(String(column.title)))
        : productColumns,
    [productCenterView, productColumns]
  );

  const productCenterTableScrollX = productCenterView === "sales_profile" ? 1320 : 2200;
  const shouldShowProductAdCoverageFilter = productCenterView === "all";

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
  const hasDailyTrend = (dashboard?.trend.length || 0) > 1;
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
  const dashboardFocusCards = dashboard
    ? [
        {
          label: "待人工确认",
          value: dashboard.overview.pending_suggestion_count.toLocaleString(),
          note: "AI 建议需要运营判断",
          tone: "danger"
        },
        {
          label: "高风险异常",
          value: dashboard.overview.high_risk_count.toLocaleString(),
          note: `${dashboard.overview.anomaly_product_count.toLocaleString()} 个产品受影响`,
          tone: "warning"
        },
        {
          label: "整体 ACOS",
          value: formatPercent(dashboard.overview.acos),
          note: `花费 ${formatMoney(dashboard.overview.cost)}`,
          tone: "blue"
        },
        {
          label: "销售 / 订单",
          value: formatMoney(dashboard.overview.sales),
          note: `${dashboard.overview.orders.toLocaleString()} 单，CVR ${formatPercent(dashboard.overview.cvr)}`,
          tone: "green"
        }
      ]
    : [];

  const activeTitle =
    activeTab === "dashboard"
      ? "广告健康驾驶舱"
      : activeTab === "search_terms"
      ? "用户搜索词归类聚合"
      : activeTab === "attribution"
      ? "广告归因"
      : activeTab === "products"
      ? "产品中心"
      : activeTab === "decisions"
        ? "处理记录与复盘"
        : "异常与 AI 建议队列";

  const activeDescription =
    activeTab === "dashboard"
      ? "近 30 天 SP 广告健康概览，优先暴露异常和待处理事项。"
      : activeTab === "search_terms"
      ? "按真实用户搜索词聚合表现和来源证据，辅助运营判断词价值。"
      : activeTab === "attribution"
      ? "人工确认广告来源属于哪个产品，只保存本地归因规则和证据快照。"
      : activeTab === "products"
      ? "人工维护产品经营目标和规则门槛，供规则引擎使用。"
      : activeTab === "decisions"
        ? "记录人工判断，并跟踪 7 天 / 14 天复盘。"
        : "SP 广告异常规则结果，供运营复核和后续处理。";

  const selectedEvidence = selected ? anomalyEvidence(selected) : {};
  const suggestionBusinessSnapshot = selectedSuggestion?.source_trace_json
    ? productSalesSnapshotFromSourceTrace(selectedSuggestion.source_trace_json, "product_sales_snapshot")
    : null;
  const evidenceBusinessSnapshot = selectedEvidence.product_sales_snapshot
    ? productSalesSnapshotFromUnknown(selectedEvidence.product_sales_snapshot)
    : null;
  const selectedBusinessSnapshot = suggestionBusinessSnapshot || evidenceBusinessSnapshot;
  const selectedBusinessSnapshotMetrics = selectedBusinessSnapshot ? businessSnapshotMetrics(selectedBusinessSnapshot) : [];
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
    setStatus("all");
    setAnomalyStartDate(dashboardStartDate);
    setAnomalyEndDate(dashboardEndDate);
    setActiveTab("anomalies");
  };

  return (
    <AntApp>
      <main className="page">
        <section className="toolbar-band">
          <div className="toolbar">
            <div className="toolbar-copy">
              <div className="ops-eyebrow">
                <SafetyCertificateOutlined />
                SP 广告健康监控 / 人工决策辅助
              </div>
              <Title level={3} className="page-title">
                {activeTitle}
              </Title>
              <Text type="secondary">{activeDescription}</Text>
              <div className="toolbar-meta">
                <Tag icon={<CheckCircleOutlined />} color="green">
                  只读建议
                </Tag>
                <Tag color="blue">近 30 天</Tag>
                <Tag color="gold">人工确认后记录</Tag>
              </div>
            </div>
            <Space wrap className="toolbar-actions">
              {activeTab === "dashboard" ? (
                <>
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
              ) : activeTab === "search_terms" ? (
                <>
                  <Select
                    allowClear
                    showSearch
                    className="filter"
                    placeholder="产品筛选"
                    value={searchTermProductId}
                    onChange={(value: number | null) => setSearchTermProductId(value ?? null)}
                    options={attributionProductOptions}
                    optionFilterProp="label"
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="语义分类"
                    value={searchTermSemanticCategory}
                    onChange={setSearchTermSemanticCategory}
                    options={searchTermSemanticOptions}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="表现分类"
                    value={searchTermPerformanceStatus}
                    onChange={setSearchTermPerformanceStatus}
                    options={searchTermPerformanceOptions}
                  />
                  <Select
                    allowClear
                    className="filter"
                    placeholder="候选类型"
                    value={searchTermCandidateType}
                    onChange={setSearchTermCandidateType}
                    options={searchTermCandidateOptions}
                  />
                  <Input
                    className="filter"
                    placeholder="时间周期开始"
                    value={searchTermStartDate}
                    onChange={(event) => setSearchTermStartDate(event.target.value || undefined)}
                  />
                  <Input
                    className="filter"
                    placeholder="时间周期结束"
                    value={searchTermEndDate}
                    onChange={(event) => setSearchTermEndDate(event.target.value || undefined)}
                  />
                  <InputNumber
                    className="filter"
                    min={0}
                    precision={0}
                    placeholder="最小点击"
                    value={searchTermMinClicks}
                    onChange={setSearchTermMinClicks}
                  />
                  <InputNumber
                    className="filter"
                    min={0}
                    step={1}
                    placeholder="最小花费"
                    value={searchTermMinSpend}
                    onChange={setSearchTermMinSpend}
                  />
                  <InputNumber
                    className="filter"
                    min={0}
                    step={0.05}
                    placeholder="目标 ACOS"
                    value={searchTermTargetAcos}
                    onChange={setSearchTermTargetAcos}
                  />
                  <Button
                    icon={<SearchOutlined />}
                    onClick={() => void refreshSearchTermWorkflow()}
                    loading={searchTermLoading || searchTermCandidateLoading}
                  >
                    查看搜索词
                  </Button>
                </>
              ) : activeTab === "products" ? (
                <>
                  <Button
                    icon={<PlusOutlined />}
                    type="primary"
                    onClick={() => {
                      setProductSeedSource(null);
                      productForm.resetFields();
                      setCreateProductOpen(true);
                    }}
                  >
                    新增产品
                  </Button>
                  <Button disabled={!selectedProductIds.length} onClick={() => setBatchApplyOpen(true)}>
                    批量应用
                  </Button>
                  <Button onClick={() => void discardProductChanges()}>
                    放弃更改
                  </Button>
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
              ) : activeTab === "attribution" ? (
                <>
                  <Select
                    className="filter"
                    value={attributionScope}
                    onChange={(value: AttributionScopeType) => setAttributionScope(value)}
                    options={[
                      { value: "ad_group", label: "Ad Group" },
                      { value: "campaign", label: "Campaign" }
                    ]}
                    placeholder="归因颗粒度"
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
                  <Button icon={<ReloadOutlined />} onClick={() => void loadProductAttribution()} loading={attributionLoading} title="刷新">
                    刷新归因
                  </Button>
                </>
              ) : activeTab === "decisions" ? (
                <>
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
                    onChange={(value: AnomalyStatusFilter) => setStatus(value)}
                    options={anomalyStatusFilterOptions}
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
            className="ops-tabs"
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
                        <section className="dashboard-identity-strip">
                          <div className="identity-compact-main">
                            <Text type="secondary">当前数据身份</Text>
                            <div className="identity-line">
                              <Text strong className="identity-name">
                                {formatStoreIdentityLabel(dashboard.market)}
                              </Text>
                              <Tag color="blue">站点 {dashboard.market.country_code || "未返回"}</Tag>
                              <Tag color={productBindingColors[dashboard.product_binding.status] || "default"}>
                                产品绑定状态 {productBindingLabels[dashboard.product_binding.status] || dashboard.product_binding.status}
                              </Tag>
                            </div>
                          </div>
                          <div className="identity-compact-meta">
                            <span>
                              <Text type="secondary">周期</Text>
                              <strong>{dashboard.period.start} 至 {dashboard.period.end}</strong>
                            </span>
                            <span>
                              <Text type="secondary">来源</Text>
                              <strong>{dashboard.data_sources.join(" / ")}</strong>
                            </span>
                            <span>
                              <Text type="secondary">产品绑定</Text>
                              <strong>
                                {dashboard.product_binding.bound_rows} / {dashboard.product_binding.total_rows} 行
                              </strong>
                            </span>
                          </div>
                        </section>

                        <section className="dashboard-hero-grid">
                          <section className="manual-task-panel">
                            <Text type="secondary">当前主任务</Text>
                            <div className="manual-task-title">
                              {dashboard.overview.pending_suggestion_count.toLocaleString()} 条 AI 建议待人工确认
                            </div>
                            <Text type="secondary">
                              先复核高风险异常和待处理建议。AI 只整理证据和建议，最终动作必须由运营人工判断。
                            </Text>
                            <Space wrap className="manual-task-tags">
                              <Tag color="red">高风险 {dashboard.overview.high_risk_count.toLocaleString()}</Tag>
                              <Tag color="gold">异常产品 {dashboard.overview.anomaly_product_count.toLocaleString()}</Tag>
                              <Tag color="blue">异常总数 {dashboard.overview.anomaly_count.toLocaleString()}</Tag>
                              <Tag>浪费花费 {formatMoney(dashboard.overview.waste_cost)}</Tag>
                            </Space>
                            <div className="manual-task-actions">
                              <Button type="primary" onClick={openAnomalyQueueFromDashboard}>
                                查看异常队列
                              </Button>
                              <Text type="secondary">人工确认后才记录处理结果</Text>
                            </div>
                          </section>

                          <section className="dashboard-focus-grid compact-focus-grid">
                            {dashboardFocusCards.map((card) => (
                              <Card key={card.label} size="small" className={`focus-card focus-${card.tone}`}>
                                <Text type="secondary">{card.label}</Text>
                                <div className="focus-value">{card.value}</div>
                                <Text className="focus-note">{card.note}</Text>
                              </Card>
                            ))}
                          </section>
                        </section>

                        <section className="sync-compact-line compact-sync-band">
                          <div>
                            <Text strong>数据同步</Text>
                            {dashboard.sync ? (
                              <>
                                <Tag color={dashboard.sync.status === "success" ? "green" : "orange"}>
                                  {syncStatusLabels[dashboard.sync.status] || dashboard.sync.status}
                                </Tag>
                                <Text type="secondary">最近写入 {dashboard.sync.rows_synced} 行</Text>
                                <Text type="secondary">{dashboard.sync.period_start} 至 {dashboard.sync.period_end}</Text>
                              </>
                            ) : (
                              <Text type="secondary">暂无同步记录</Text>
                            )}
                          </div>
                          {syncRuns.length ? <Text type="secondary">最近 {syncRuns.length} 次同步记录</Text> : null}
                        </section>

                        <section className="dashboard-secondary-grid">
                          <Card
                            title="经营指标明细"
                            size="small"
                            className="metric-detail-card"
                            extra={<Text type="secondary">用于人工复核和追溯</Text>}
                          >
                            <section className="metric-grid compact-metric-grid">
                              {metricTiles.map((tile) => (
                                <div className="metric-tile" key={tile.label}>
                                  <Text type="secondary">{tile.label}</Text>
                                  <div className="metric-value">{tile.value}</div>
                                </div>
                              ))}
                            </section>
                          </Card>

                          <Card title="广告活动来源 Top" size="small" className="campaign-source-card">
                            {dashboard.top_campaigns.length ? (
                              <div className="campaign-source-list compact-campaign-source-list">
                                {dashboard.top_campaigns.map((item) => (
                                  <div className="campaign-source-row" key={item.campaign_id || item.campaign_name || "unknown"}>
                                    <div>
                                      <Text strong>{item.campaign_name || item.campaign_id || "未命名 Campaign"}</Text>
                                      <div className="campaign-source-meta">
                                        {item.ad_group_count} 个广告组 / {item.keyword_count} 个关键词 / {item.metric_rows} 行指标
                                      </div>
                                    </div>
                                    <Space wrap className="campaign-source-metrics">
                                      <Tag color="blue">花费 {formatMoney(item.cost)}</Tag>
                                      <Tag color="green">销售 {formatMoney(item.sales)}</Tag>
                                      <Tag color="red">ACOS {formatPercent(item.acos)}</Tag>
                                      <Tag>订单 {item.orders.toLocaleString()}</Tag>
                                    </Space>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <Empty description="暂无广告活动来源" />
                            )}
                          </Card>
                        </section>

                        <section className="dashboard-grid dashboard-lower-grid">
                          <Card title="周期表现说明" size="small">
                            {hasDailyTrend ? (
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
                            ) : dashboard.trend.length ? (
                              <div className="aggregate-note-panel">
                                <Text strong>当前为周期聚合数据</Text>
                                <Text type="secondary">
                                  积加本次按 {dashboard.period.start} 至 {dashboard.period.end} 聚合返回，不能解读为逐日趋势。
                                </Text>
                                <div className="aggregate-metric-row">
                                  <Tag color="blue">花费 {formatMoney(dashboard.overview.cost)}</Tag>
                                  <Tag color="red">ACOS {formatPercent(dashboard.overview.acos)}</Tag>
                                  <Tag color="green">CVR {formatPercent(dashboard.overview.cvr)}</Tag>
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
                key: "search_terms",
                label: "搜索词分析",
                children: (
                  <Spin spinning={searchTermLoading}>
                    {searchTermAnalysis ? (
                      <Space direction="vertical" size={16} className="tab-stack search-term-analysis">
                        <section className="search-term-product-readiness">
                          <Alert
                            showIcon
                            type={searchTermProductReadiness?.ready ? "success" : "warning"}
                            message={searchTermProductReadiness?.ready ? "产品维度分析已就绪" : "产品维度分析未就绪"}
                            description={
                              searchTermProductReadiness?.ready
                                ? `已确认归因规则 ${searchTermProductReadiness.summary.active_binding_count} 条，已归因搜索词行 ${searchTermProductReadiness.summary.bound_search_term_rows} 行。`
                                : searchTermProductReadiness?.manual_hint?.replace("产品设置页", "广告归因页") ||
                                  "请先在广告归因页人工确认产品归因规则"
                            }
                          />
                          <Space wrap className="search-term-candidate-summary">
                            <Tag>归因规则 {searchTermProductReadiness?.summary.active_binding_count ?? 0}</Tag>
                            <Tag>已归因搜索词行 {searchTermProductReadiness?.summary.bound_search_term_rows ?? 0}</Tag>
                            <Tag>有搜索词产品 {searchTermProductReadiness?.summary.products_with_search_terms ?? 0}</Tag>
                            <Button
                              size="small"
                              icon={<ReloadOutlined />}
                              onClick={() => void loadSearchTermProductReadiness()}
                              loading={searchTermProductReadinessLoading}
                            >
                              刷新就绪状态
                            </Button>
                          </Space>
                        </section>
                        {isProductSearchTermMode ? (
                          <section className="product-search-term-context">
                            <div className="product-search-term-context-header">
                              <div>
                                <Text strong>产品维度搜索词归类聚合</Text>
                                <div className="source-line">
                                  基于人工确认归因后的产品筛选，先看产品内搜索词分组，再做人工判断。
                                </div>
                              </div>
                              <Button size="small" onClick={() => setActiveTab("attribution")}>
                                前往广告归因确认归因
                              </Button>
                            </div>
                            <div>
                              <Text type="secondary">当前产品</Text>
                              <div>
                                <Text strong>
                                  {selectedReadinessProduct?.product_name ||
                                    selectedSearchTermProduct?.product_name ||
                                    selectedSearchTermProduct?.msku ||
                                    `产品 ${searchTermProductId}`}
                                </Text>
                              </div>
                            </div>
                            <Space wrap size={[6, 6]} className="product-search-term-context-metrics">
                              <Tag>已归因搜索词行 {selectedReadinessProduct?.search_term_rows ?? 0}</Tag>
                              <Tag>去重搜索词 {selectedReadinessProduct?.distinct_terms ?? 0}</Tag>
                              <Tag>花费 {formatMoney(selectedReadinessProduct?.cost ?? 0)}</Tag>
                              <Tag>销售 {formatMoney(selectedReadinessProduct?.sales ?? 0)}</Tag>
                              <Tag color="orange">ACOS {formatPercent(selectedReadinessProduct?.acos ?? 0)}</Tag>
                            </Space>
                            <div className="product-review-checklist">
                              <div className="product-review-checklist-header">
                                <Text strong>产品维度复核清单</Text>
                                <Text type="secondary">只读检查，用于确认当前产品维度分析是否具备人工复核条件。</Text>
                              </div>
                              <div className="product-review-checklist-grid">
                                {productReviewChecklist.map((item) => (
                                  <div
                                    className={`product-review-checklist-item ${item.ready ? "is-ready" : "is-pending"}`}
                                    key={item.key}
                                  >
                                    <Tag color={item.ready ? "green" : "gold"}>{item.ready ? "可复核" : "待处理"}</Tag>
                                    <Text strong>{item.label}</Text>
                                    <Text type="secondary">{item.detail}</Text>
                                  </div>
                                ))}
                              </div>
                              {productGroupDecisionTodo ? (
                                <Alert
                                  type="warning"
                                  showIcon
                                  message="待记录产品级组判断"
                                  description="当前产品已有归类组，但还没有当前产品级组判断。请进入人工判断弹窗确认，不会自动保存判断或修改广告。"
                                  action={
                                    <Button
                                      size="small"
                                      icon={<AuditOutlined />}
                                      onClick={() => {
                                        if (searchTermAnalysis?.group_summary.length) {
                                          openSearchTermGroupDecisionModal(searchTermAnalysis.group_summary[0]);
                                        }
                                      }}
                                    >
                                      记录产品级组判断
                                    </Button>
                                  }
                                />
                              ) : null}
                            </div>
                            <Text type="secondary">
                              {searchTermProductReadiness?.ready
                                ? "当前产品已具备产品维度搜索词分析前提，后续记录会作为产品级组判断。"
                                : "当前产品尚未形成已归因搜索词，请先在广告归因页人工确认产品归因规则。"}
                            </Text>
                          </section>
                        ) : null}
                        <section className="search-term-summary-grid">
                          <Card size="small" className="search-term-summary-card">
                            <Text type="secondary">周期</Text>
                            <div className="focus-value">
                              {searchTermAnalysis.period.start} 至 {searchTermAnalysis.period.end}
                            </div>
                            <Text type="secondary">仅供人工判断，不会自动修改广告</Text>
                          </Card>
                          <Card size="small" className="search-term-summary-card">
                            <Text type="secondary">去重搜索词</Text>
                            <div className="focus-value">{searchTermAnalysis.summary.distinct_terms.toLocaleString()}</div>
                            <Text type="secondary">{searchTermAnalysis.summary.terms.toLocaleString()} 个聚合词条</Text>
                          </Card>
                          <Card size="small" className="search-term-summary-card">
                            <Text type="secondary">花费 / 销售</Text>
                            <div className="focus-value">
                              {formatMoney(searchTermAnalysis.summary.cost)} / {formatMoney(searchTermAnalysis.summary.sales)}
                            </div>
                            <Text type="secondary">
                              订单 {searchTermAnalysis.summary.orders.toLocaleString()}，点击{" "}
                              {searchTermAnalysis.summary.clicks.toLocaleString()}
                            </Text>
                          </Card>
                          <Card size="small" className="search-term-summary-card">
                            <Text type="secondary">ACOS / CVR</Text>
                            <div className="focus-value">
                              {formatPercent(searchTermAnalysis.summary.acos)} / {formatPercent(searchTermAnalysis.summary.cvr)}
                            </div>
                            <Text type="secondary">
                              判断门槛：点击 {searchTermAnalysis.filters.min_clicks}，花费{" "}
                              {formatMoney(searchTermAnalysis.filters.min_spend)}
                            </Text>
                          </Card>
                        </section>

                        {groupPriorityReviewItems.length ? (
                          <section className="search-term-priority-review">
                            <div className="attribution-header">
                              <div>
                                <Text strong>归类组优先复核顺序</Text>
                                <div className="source-line">
                                  从现有归类聚合组里挑出首批人工复核对象；只改变查看顺序，不自动修改广告。
                                </div>
                              </div>
                              <Tag>优先 {groupPriorityReviewItems.length} 组</Tag>
                            </div>
                            <div className="search-term-priority-review-list">
                              {groupPriorityReviewItems.map((item, index) => (
                                <Card size="small" className="search-term-priority-review-card" key={item.group.group_key}>
                                  <Space direction="vertical" size={8}>
                                    <Space wrap size={[6, 6]}>
                                      <Tag color={item.color}>#{index + 1} {item.badge}</Tag>
                                      <Tag>{item.group.performance_label}</Tag>
                                      <Tag>{item.group.semantic_label}</Tag>
                                    </Space>
                                    <div>
                                      <Text strong>{item.group.group_label}</Text>
                                      <div className="source-line">{item.reason}</div>
                                    </div>
                                    <Space wrap size={[4, 4]}>
                                      <Tag>花费 {formatMoney(item.group.cost)}</Tag>
                                      <Tag>销售 {formatMoney(item.group.sales)}</Tag>
                                      <Tag>订单 {item.group.orders.toLocaleString()}</Tag>
                                      <Tag color="orange">ACOS {formatPercent(item.group.acos)}</Tag>
                                      <Tag>{item.group.terms.toLocaleString()} 个词</Tag>
                                    </Space>
                                    <div className="search-term-priority-review-terms">
                                      <Text type="secondary">代表搜索词</Text>
                                      <Space wrap size={[4, 4]}>
                                        {item.group.representative_terms.slice(0, 4).map((term) => (
                                          <Tag key={term}>{term}</Tag>
                                        ))}
                                      </Space>
                                    </div>
                                    <Space wrap className="search-term-group-actions">
                                      <Button size="small" icon={<EyeOutlined />} onClick={() => drillDownSearchTermGroup(item.group)}>
                                        查看同组明细
                                      </Button>
                                      <Button size="small" icon={<AuditOutlined />} onClick={() => openSearchTermGroupDecisionModal(item.group)}>
                                        记录组判断
                                      </Button>
                                    </Space>
                                  </Space>
                                </Card>
                              ))}
                            </div>
                          </section>
                        ) : null}

                        <section className="search-term-group-grid">
                          <div className="attribution-header">
                            <div>
                              <Text strong>{isProductSearchTermMode ? "产品维度归类聚合组" : "归类聚合组"}</Text>
                              <div className="source-line">
                                {isProductSearchTermMode
                                  ? "基于人工确认归因后的产品筛选，按语义分类 + 表现分类组合聚合；仅供人工判断，不自动修改广告。"
                                  : "语义分类 + 表现分类组合聚合；仅供人工判断，不自动修改广告。"}
                              </div>
                            </div>
                            <Tag>合计 {searchTermAnalysis.group_summary.length} 组</Tag>
                          </div>
                          {searchTermAnalysis.group_summary.length ? (
                            <div className="search-term-group-list">
                              {searchTermAnalysis.group_summary.slice(0, 8).map((group) => (
                                <Card size="small" className="search-term-group-card" key={group.group_key}>
                                  <Space direction="vertical" size={8}>
                                    <Space wrap size={[6, 6]}>
                                      <Tag color={searchTermSemanticColors[group.semantic_category] || "default"}>
                                        {group.semantic_label}
                                      </Tag>
                                      <Tag color={searchTermPerformanceColors[group.performance_status] || "default"}>
                                        {group.performance_label}
                                      </Tag>
                                    </Space>
                                    <div>
                                      <Text strong>{group.group_label}</Text>
                                      <div className="search-term-row-meta">
                                        {group.terms.toLocaleString()} 个词 / 点击 {group.clicks.toLocaleString()} / 订单{" "}
                                        {group.orders.toLocaleString()}
                                      </div>
                                    </div>
                                    <Space wrap size={[4, 4]}>
                                      <Tag>花费 {formatMoney(group.cost)}</Tag>
                                      <Tag>销售 {formatMoney(group.sales)}</Tag>
                                      <Tag color="orange">ACOS {formatPercent(group.acos)}</Tag>
                                      <Tag>CVR {formatPercent(group.cvr)}</Tag>
                                    </Space>
                                    <div className="search-term-group-terms">
                                      <Text type="secondary">代表搜索词</Text>
                                      <Space wrap size={[4, 4]}>
                                        {group.representative_terms.map((term) => (
                                          <Tag key={term}>{term}</Tag>
                                        ))}
                                      </Space>
                                    </div>
                                    <Space wrap className="search-term-group-actions">
                                      <Button size="small" icon={<EyeOutlined />} onClick={() => drillDownSearchTermGroup(group)}>
                                        查看同组明细
                                      </Button>
                                      <Button size="small" icon={<AuditOutlined />} onClick={() => openSearchTermGroupDecisionModal(group)}>
                                        记录组判断
                                      </Button>
                                    </Space>
                                  </Space>
                                </Card>
                              ))}
                            </div>
                          ) : (
                            <Empty description="暂无归类聚合组" />
                          )}
                        </section>

                        <section className="search-term-group-decision-list">
                          <div className="attribution-header">
                            <div>
                              <Text strong>组级人工记录</Text>
                              <div className="source-line">
                                {searchTermGroupDecisionListDetail} 只记录人工判断，不代表广告已自动修改。
                              </div>
                            </div>
                            <Button
                              size="small"
                              icon={<ReloadOutlined />}
                              onClick={() => void loadSearchTermGroupDecisions()}
                              loading={searchTermGroupDecisionLoading}
                            >
                              刷新记录
                            </Button>
                          </div>
                          <Table
                            rowKey="id"
                            size="small"
                            loading={searchTermGroupDecisionLoading}
                            columns={searchTermGroupDecisionColumns}
                            dataSource={searchTermGroupDecisions}
                            pagination={{ pageSize: 5, showSizeChanger: false }}
                            locale={{ emptyText: <Empty description="暂无组级人工记录" /> }}
                            scroll={{ x: 1180 }}
                          />
                        </section>

                        <section className="search-term-candidate-panel">
                          <div className="attribution-header">
                            <div>
                              <Text strong>人工处理候选池</Text>
                              <div className="source-line">
                                从高转化词、高花费无单词和高 ACOS 词派生候选；只做人工判断线索，不自动修改广告。
                              </div>
                            </div>
                            {searchTermCandidates ? (
                              <Space wrap className="search-term-candidate-summary">
                                <Tag color="green">高转化 {searchTermCandidates.summary.scale_opportunity_count}</Tag>
                                <Tag color="red">高花费无单 {searchTermCandidates.summary.waste_risk_count}</Tag>
                                <Tag color="orange">高 ACOS {searchTermCandidates.summary.efficiency_risk_count}</Tag>
                                <Tag>合计 {searchTermCandidates.summary.total_candidates}</Tag>
                              </Space>
                            ) : null}
                          </div>
                          <Table
                            rowKey="candidate_id"
                            size="small"
                            loading={searchTermCandidateLoading}
                            columns={searchTermCandidateColumns}
                            dataSource={searchTermCandidates?.rows || []}
                            pagination={{ pageSize: 6, showSizeChanger: false }}
                            locale={{ emptyText: <Empty description="暂无人工处理候选" /> }}
                            scroll={{ x: 1280 }}
                          />
                          <div className="search-term-decision-list">
                            <div className="attribution-header">
                              <div>
                                <Text strong>候选处理记录</Text>
                                <div className="source-line">只展示本地人工判断记录，不代表广告已被系统自动修改。</div>
                              </div>
                              <Button
                                size="small"
                                icon={<ReloadOutlined />}
                                onClick={() => void loadSearchTermCandidateDecisions()}
                                loading={searchTermDecisionLoading}
                              >
                                刷新记录
                              </Button>
                            </div>
                            <Table
                              rowKey="id"
                              size="small"
                              loading={searchTermDecisionLoading}
                              columns={searchTermCandidateDecisionColumns}
                              dataSource={searchTermCandidateDecisions}
                              pagination={{ pageSize: 5, showSizeChanger: false }}
                              locale={{ emptyText: <Empty description="暂无候选处理记录" /> }}
                              scroll={{ x: 980 }}
                            />
                          </div>
                        </section>

                        <section className="search-term-category-grid">
                          <Card title="语义分类汇总" size="small">
                            {searchTermAnalysis.category_summary.length ? (
                              <div className="search-term-category-list">
                                {searchTermAnalysis.category_summary.map((item) => (
                                  <div className="search-term-category-card" key={item.key}>
                                    <div>
                                      <Text strong>{item.label}</Text>
                                      <div className="search-term-row-meta">
                                        {item.terms.toLocaleString()} 个词 / 点击 {item.clicks.toLocaleString()} / 订单{" "}
                                        {item.orders.toLocaleString()}
                                      </div>
                                    </div>
                                    <Space wrap size={[4, 4]}>
                                      <Tag>花费 {formatMoney(item.cost)}</Tag>
                                      <Tag>销售 {formatMoney(item.sales)}</Tag>
                                      <Tag color="orange">ACOS {formatPercent(item.acos)}</Tag>
                                    </Space>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <Empty description="暂无语义分类" />
                            )}
                          </Card>

                          <Card title="表现分类汇总" size="small">
                            {searchTermAnalysis.performance_summary.length ? (
                              <div className="search-term-category-list">
                                {searchTermAnalysis.performance_summary.map((item) => (
                                  <div className="search-term-category-card" key={item.key}>
                                    <div>
                                      <Text strong>{item.label}</Text>
                                      <div className="search-term-row-meta">
                                        {item.terms.toLocaleString()} 个词 / 点击 {item.clicks.toLocaleString()} / 订单{" "}
                                        {item.orders.toLocaleString()}
                                      </div>
                                    </div>
                                    <Space wrap size={[4, 4]}>
                                      <Tag>花费 {formatMoney(item.cost)}</Tag>
                                      <Tag>销售 {formatMoney(item.sales)}</Tag>
                                      <Tag color="orange">ACOS {formatPercent(item.acos)}</Tag>
                                    </Space>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <Empty description="暂无表现分类" />
                            )}
                          </Card>
                        </section>

                        <Table
                          rowKey={(record) => record.search_term}
                          columns={searchTermColumns}
                          dataSource={searchTermAnalysis.rows}
                          pagination={{ pageSize: 12, showSizeChanger: false }}
                          locale={{ emptyText: <Empty description="暂无搜索词分析结果" /> }}
                          scroll={{ x: 1280 }}
                        />
                      </Space>
                    ) : (
                      <Empty description="暂无搜索词分析结果，请点击查看搜索词" />
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
                      locale={{ emptyText: renderAnomalyQueueEmptyState() }}
                      scroll={{ x: 1400 }}
                    />
                  </>
                )
              },
              {
                key: "attribution",
                label: "广告归因",
                children: (
                  <Space direction="vertical" size={16} className="tab-stack">
                    {adDraftAttributionReviewProduct ? (
                      <Alert
                        className="ad-draft-attribution-review-banner"
                        type="warning"
                        showIcon
                        message="从草稿产品身份核查进入"
                        description={
                          <Space direction="vertical" size={2}>
                            <Text>
                              当前候选销售表现产品：
                              {adDraftAttributionReviewProduct.product_name ||
                                adDraftAttributionReviewProduct.asin ||
                                adDraftAttributionReviewProduct.msku ||
                                `产品 ${adDraftAttributionReviewProduct.id}`}
                            </Text>
                            <Text type="secondary">
                              ASIN {adDraftAttributionReviewProduct.asin || "-"} / MSKU {adDraftAttributionReviewProduct.msku || "-"}。只用于人工核查归因，不会自动保存归因规则，也不会改广告。
                            </Text>
                          </Space>
                        }
                      />
                    ) : null}
                    {adDraftAttributionReviewProduct ? (
                      <section className="ad-draft-attribution-source-focus">
                        <div>
                          <Text strong>建议优先核查的广告来源</Text>
                          <div className="source-line">已按草稿广告来源线索自动定位可能相关的广告来源，并保留候选销售表现产品作为人工确认目标。</div>
                        </div>
                        {firstAdDraftAttributionSourceCandidate ? (
                          <>
                            <div className="ad-draft-focused-source">
                              <div>
                                <Text type="secondary">候选销售表现产品</Text>
                                <div>
                                  <Text strong>
                                    {adDraftAttributionReviewProduct.product_name ||
                                      adDraftAttributionReviewProduct.msku ||
                                      `产品 ${adDraftAttributionReviewProduct.id}`}
                                  </Text>
                                </div>
                                <Text type="secondary">
                                  MSKU {adDraftAttributionReviewProduct.msku || "-"} / ASIN {adDraftAttributionReviewProduct.asin || "-"}
                                </Text>
                              </div>
                              <div>
                                <Text type="secondary">广告来源证据行</Text>
                                <div>
                                  <Text strong>
                                    {firstAdDraftAttributionSourceCandidate.scope_name || firstAdDraftAttributionSourceCandidate.scope_id || "-"}
                                  </Text>
                                </div>
                                <Text type="secondary">
                                  花费 {formatMoney(firstAdDraftAttributionSourceCandidate.cost)} / 订单 {firstAdDraftAttributionSourceCandidate.orders} /
                                  ACOS {formatPercent(firstAdDraftAttributionSourceCandidate.acos)}
                                </Text>
                              </div>
                            </div>
                            <div className="ad-draft-attribution-source-footer">
                              <Text type="secondary">只做证据定位和人工核查，不会自动保存归因规则，也不会改广告。</Text>
                              <Button
                                type="primary"
                                icon={<EyeOutlined />}
                                onClick={() =>
                                  void openAttributionEvidence(firstAdDraftAttributionSourceCandidate, adDraftAttributionReviewProduct.id)
                                }
                              >
                                查看该广告来源证据
                              </Button>
                            </div>
                          </>
                        ) : (
                          <Alert
                            type="info"
                            showIcon
                            message="暂未找到对应候选广告来源"
                            description="当前仍可在下方高可信归因候选和未归因广告数据池中人工核查；系统不会自动保存归因规则。"
                          />
                        )}
                      </section>
                    ) : null}
                    <section className="real-workflow-rehearsal">
                      <div className="real-workflow-rehearsal-header">
                        <div>
                          <Text strong>真实闭环演练</Text>
                          <div className="source-line">按真实数据完成第一轮人工闭环；系统只做引导和记录，不会自动修改广告。</div>
                        </div>
                        <Tag color={productAdBindings.length > 0 ? "green" : "gold"}>
                          {productAdBindings.length > 0 ? "归因已开始" : "待人工归因"}
                        </Tag>
                      </div>
                      <div className="real-workflow-rehearsal-steps">
                        {realWorkflowRehearsalSteps.map((step, index) => (
                          <div className="real-workflow-rehearsal-step" key={step.key}>
                            <div className="real-workflow-rehearsal-step-index">{index + 1}</div>
                            <div className="real-workflow-rehearsal-step-body">
                              <Space wrap size={[6, 6]}>
                                <Text strong>{step.title}</Text>
                                <Tag color={step.disabled ? "default" : "blue"}>{step.status}</Tag>
                              </Space>
                              <div className="source-line">{step.detail}</div>
                              <Button size="small" disabled={step.disabled} onClick={() => void step.onClick()}>
                                {step.actionLabel}
                              </Button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                    <section className="attribution-panel attribution-candidate-panel">
                      <div className="attribution-header">
                        <div>
                          <Text strong>高可信归因候选</Text>
                          <div className="source-line">当前对象：广告来源。人工确认前请查看证据；候选只整理证据，不会自动保存归因规则。</div>
                        </div>
                        <Space wrap>
                          <Tag>合计 {productAttributionCandidates?.summary.total_candidates ?? 0}</Tag>
                          <Tag color="green">高可信 {productAttributionCandidates?.summary.high_confidence_count ?? 0}</Tag>
                          <Tag color="gold">中可信 {productAttributionCandidates?.summary.medium_confidence_count ?? 0}</Tag>
                          <Button
                            icon={<ReloadOutlined />}
                            onClick={() => void loadProductAttributionCandidates()}
                            loading={productAttributionCandidateLoading}
                          >
                            刷新候选
                          </Button>
                        </Space>
                      </div>
                      {productAdBindings.length === 0 && firstAttributionCandidate ? (
                        <section className="first-attribution-guide">
                          <div className="first-attribution-guide-header">
                            <div>
                              <Text strong>首条真实归因引导</Text>
                              <div className="source-line">
                                先确认最可信的一条归因，产品维度搜索词分析才有真实归属；查看证据不会自动保存归因规则。
                              </div>
                            </div>
                            <Tag color={confidenceColor(firstAttributionCandidate.confidence_level)}>
                              {confidenceLabel(firstAttributionCandidate.confidence_level)} {firstAttributionCandidate.confidence_score}
                            </Tag>
                          </div>
                          <div className="first-attribution-guide-main">
                            <div>
                              <Text type="secondary">广告来源</Text>
                              <div>
                                <Text strong>{firstAttributionCandidate.source.scope_name || firstAttributionCandidate.source.scope_id || "-"}</Text>
                              </div>
                            </div>
                            <div>
                              <Text type="secondary">推荐产品</Text>
                              <div>
                                <Text strong>
                                  {firstAttributionCandidate.candidate_product.product_name ||
                                    firstAttributionCandidate.candidate_product.msku ||
                                    `产品 ${firstAttributionCandidate.candidate_product.product_id}`}
                                </Text>
                              </div>
                            </div>
                          </div>
                          <Space wrap size={[6, 6]} className="first-attribution-guide-metrics">
                            <Tag color="blue">可解锁搜索词 {firstAttributionCandidate.unlock_impact.search_term_rows} 行</Tag>
                            <Tag>花费 {formatMoney(firstAttributionCandidate.unlock_impact.cost)}</Tag>
                            <Tag>销售 {formatMoney(firstAttributionCandidate.unlock_impact.sales)}</Tag>
                            <Tag>订单 {firstAttributionCandidate.unlock_impact.orders}</Tag>
                            <Tag color="orange">ACOS {formatPercent(firstAttributionCandidate.unlock_impact.acos)}</Tag>
                          </Space>
                          <div className="first-attribution-guide-footer">
                            <Text type="secondary">人工确认后才会写入本地规则，不会自动保存归因规则，也不会执行任何广告动作。</Text>
                            <Button
                              type="primary"
                              icon={<EyeOutlined />}
                              onClick={() => void openAttributionEvidence(firstAttributionCandidate.source, firstAttributionCandidate.candidate_product.product_id)}
                            >
                              查看证据并确认归因
                            </Button>
                          </div>
                        </section>
                      ) : null}
                      <Table
                        rowKey="candidate_id"
                        size="small"
                        loading={productAttributionCandidateLoading}
                        columns={productAttributionCandidateColumns}
                        dataSource={productAttributionCandidates?.rows || []}
                        rowClassName={(candidate) =>
                          adDraftAttributionReviewSourceProduct &&
                          sourceMatchesProductIdentity(candidate.source, adDraftAttributionReviewSourceProduct)
                            ? "ad-draft-focused-candidate-row"
                            : ""
                        }
                        pagination={{ pageSize: 5, showSizeChanger: false }}
                        locale={{ emptyText: <Empty description="暂无高可信归因候选" /> }}
                        scroll={{ x: 1140 }}
                      />
                    </section>
                    <section className="attribution-panel">
                      <div className="attribution-header">
                        <div>
                          <Text strong>未归因广告数据池</Text>
                          <div className="source-line">当前对象：广告来源。人工确认 Campaign / Ad Group 属于哪个产品，仅写入本地归因规则。</div>
                        </div>
                        <Space wrap>
                          <Select
                            className="filter"
                            value={attributionScope}
                            onChange={(value: AttributionScopeType) => setAttributionScope(value)}
                            options={[
                              { value: "ad_group", label: "Ad Group" },
                              { value: "campaign", label: "Campaign" }
                            ]}
                            placeholder="归因颗粒度"
                          />
                          <Select
                            allowClear
                            showSearch
                            className="filter attribution-product-select"
                            value={attributionProductId}
                            onChange={(value: number | null) => setAttributionProductId(value ?? null)}
                            options={attributionProductOptions}
                            placeholder="选择归因产品"
                            optionFilterProp="label"
                          />
                          <Button icon={<ReloadOutlined />} onClick={() => void loadProductAttribution()} loading={attributionLoading}>
                            刷新归因池
                          </Button>
                        </Space>
                      </div>
                      <Table
                        rowKey={adSourceKey}
                        size="small"
                        loading={attributionLoading}
                        columns={attributionColumns}
                        dataSource={unboundAdSources}
                        rowClassName={(source) =>
                          sourceMatchesProductIdentity(source, adDraftAttributionReviewSourceProduct) ? "ad-draft-focused-candidate-row" : ""
                        }
                        pagination={{ pageSize: 5, showSizeChanger: false }}
                        locale={{ emptyText: <Empty description="暂无未归因广告数据" /> }}
                        scroll={{ x: 1040 }}
                      />
                      <div className="binding-rule-list">
                        <Text strong>已确认归因规则</Text>
                        <div className="source-line">当前对象：归因规则。人工确认归因后，可查看该产品搜索词归类组。</div>
                        <Table
                          rowKey="id"
                          size="small"
                          columns={bindingColumns}
                          dataSource={productAdBindings}
                          pagination={{ pageSize: 5, showSizeChanger: false }}
                          locale={{ emptyText: <Empty description="暂无已确认归因规则" /> }}
                          scroll={{ x: 820 }}
                        />
                      </div>
                    </section>
                  </Space>
                )
              },
              {
                key: "products",
                label: "产品中心",
                children: (
                  <Space direction="vertical" size={16} className="tab-stack">
                    <section className="attribution-panel">
                      <div className="attribution-header">
                        <div>
                          <Text strong>产品基础设置</Text>
                          <div className="source-line">当前对象：产品。维护产品目标、规则门槛和基础信息，不代表广告来源本身。</div>
                        </div>
                      </div>
                      <div className="product-ad-coverage-summary">
                        <div>
                          <Text strong>产品广告覆盖状态</Text>
                          <div className="source-line">
                            销售表现产品不等于广告投放产品；这里仅按人工归因规则和已同步 SP 指标判断广告覆盖，不自动判断产品是否应该投广告。
                          </div>
                        </div>
                        <div className="product-center-view-controls">
                          <Text type="secondary">产品中心视图</Text>
                          <Segmented
                            value={productCenterView}
                            options={productCenterViewOptions}
                            onChange={(value) => {
                              setProductCenterView(value as ProductCenterView);
                              setProductAdCoverageFilter("all");
                            }}
                          />
                        </div>
                        {shouldShowProductAdCoverageFilter ? (
                          <div className="product-ad-coverage-controls">
                            <Text type="secondary">广告覆盖状态</Text>
                            <Select
                              className="table-control"
                              value={productAdCoverageFilter}
                              options={productAdCoverageFilterOptions}
                              onChange={(value) => setProductAdCoverageFilter(value)}
                            />
                          </div>
                        ) : null}
                        <div className="product-ad-coverage-cards">
                          {(["attributed", "sp_unattributed", "not_advertised"] as ProductAdCoverageStatus[]).map((status) => {
                            const meta = productAdCoverageMeta[status];
                            return (
                              <div className="product-ad-coverage-card" key={status}>
                                <Tag color={meta.color}>{meta.label}</Tag>
                                <Text strong>{productAdCoverageSummary[status].toLocaleString()} 个</Text>
                                <Text type="secondary">{meta.description}</Text>
                              </div>
                            );
                          })}
                        </div>
                        <div className="source-line">本系统暂无 SP 覆盖证据的产品只作为销售产品档案，不进入广告调优待办。</div>
                      </div>
                      {productsNeedingGoalRuleSetup.length > 0 ? (
                        <div className="product-goal-rule-guidance">
                          <div>
                            <Space size={8} wrap>
                              <Text strong>需要人工设置产品目标 / 规则</Text>
                              <Tag color="orange">待设置目标 / 规则</Tag>
                            </Space>
                            <div className="source-line">
                              {productsNeedingGoalRuleSetup.length} 个广告调优对象已有 SP 指标，但缺少人工目标或规则门槛。需要运营人工设置产品目标和规则门槛。
                              这里只引导运营人工设置，不会自动保存目标 / 规则，也不会自动修改广告；系统不会自动生成目标或修改广告。
                            </div>
                          </div>
                          <div className="goal-rule-guidance-grid">
                            {productsNeedingGoalRuleSetup.slice(0, 3).map((product) => (
                              <div className="goal-rule-guidance-item" key={product.id}>
                                <Text strong>{product.product_name || product.msku || product.asin || `产品 ${product.id}`}</Text>
                                <div className="goal-rule-guidance-missing">
                                  {getProductGoalRuleMissingItems(product).map((item) => (
                                    <Tag color="orange" key={item}>
                                      {item}
                                    </Tag>
                                  ))}
                                </div>
                                <Text type="secondary" className="goal-rule-guidance-metrics">
                                  当前 SP 指标：花费 {formatMoney(product.sp_metrics.cost)} / 订单 {product.sp_metrics.orders} / ACOS{" "}
                                  {formatPercent(product.sp_metrics.acos)}
                                </Text>
                                <Button size="small" icon={<AuditOutlined />} onClick={() => openGoalRuleDrawer(product)}>
                                  设置目标 / 规则
                                </Button>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : null}
                      <Table
                        rowKey="id"
                        loading={productLoading}
                        columns={productCenterTableColumns}
                        dataSource={productCenterProducts}
                        rowSelection={{
                          selectedRowKeys: selectedProductIds,
                          onChange: (keys) => setSelectedProductIds(keys.map((key) => Number(key)))
                        }}
                        pagination={{ pageSize: 10, showSizeChanger: false }}
                        locale={{ emptyText: <Empty description="暂无产品，请先新增产品" /> }}
                        scroll={{ x: productCenterTableScrollX }}
                      />
                    </section>
                  </Space>
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
          title="产品目标 / 规则设置"
          className="product-goal-rule-drawer"
          open={!!selectedGoalRuleProduct}
          onClose={() => setSelectedGoalRuleProduct(null)}
          width={560}
        >
          {selectedGoalRuleProduct && selectedGoalRuleProductDraft ? (
            <Space direction="vertical" size={16} className="drawer-body">
              <Alert
                className="section-alert"
                type="info"
                showIcon
                message="人工设置边界"
                description="只保存运营人工设置的产品目标和规则门槛，不会自动生成目标，也不会自动修改广告。"
              />
              <div className="goal-rule-product-identity">
                <Text strong>{selectedGoalRuleProduct.product_name || selectedGoalRuleProduct.msku || selectedGoalRuleProduct.asin || `产品 ${selectedGoalRuleProduct.id}`}</Text>
                <Text type="secondary">
                  ASIN {selectedGoalRuleProduct.asin || "-"} / MSKU {selectedGoalRuleProduct.msku || "-"} / {formatProductMarketLabel(selectedGoalRuleProduct)}
                </Text>
                <Tag className="product-identity-tag">{selectedGoalRuleProduct.category || "未记录类目"}</Tag>
              </div>
              {needsAdDraftIdentityReview(selectedGoalRuleProduct) ? (
                <div className="ad-draft-identity-candidates">
                  <Alert
                    className="ad-draft-identity-alert"
                    type="warning"
                    showIcon
                    message="产品身份待核查"
                    description="当前对象来自 SP 广告来源草稿，不等同于完整销售表现商品；需要人工核查后再设置产品目标和规则。"
                  />
                  <div>
                    <Text strong>可能相关的销售表现产品</Text>
                    <div className="source-line">候选只读展示，不会自动合并产品、迁移归因或改广告。</div>
                  </div>
                  <div className="ad-draft-attribution-review-action">
                    <Text type="secondary">先到广告归因页人工核查或修正归因，再回来设置产品目标和规则。</Text>
                    <Button
                      size="small"
                      icon={<SearchOutlined />}
                      onClick={() => openAdDraftAttributionReview(selectedGoalRuleIdentityCandidates[0]?.id)}
                    >
                      去广告归因页核查 / 修正归因
                    </Button>
                  </div>
                  {selectedGoalRuleIdentityCandidates.length > 0 ? (
                    selectedGoalRuleIdentityCandidates.map((candidate) => {
                      const snapshot = candidate.sales_snapshot;
                      return (
                        <div className="ad-draft-identity-candidate-card" key={candidate.id}>
                          <Text strong>{candidate.product_name || candidate.msku || candidate.asin || `产品 ${candidate.id}`}</Text>
                          <Text type="secondary">
                            候选 ASIN {candidate.asin || "-"} / 候选 MSKU {candidate.msku || "-"}
                          </Text>
                          <div className="ad-draft-candidate-metrics">
                            <span>
                              <Text type="secondary">销售额</Text>
                              <Text strong>{formatMoney(snapshot?.sales ?? 0)}</Text>
                            </span>
                            <span>
                              <Text type="secondary">订单</Text>
                              <Text strong>{(snapshot?.orders ?? 0).toLocaleString()}</Text>
                            </span>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <Empty description="暂无可匹配的销售表现产品候选" />
                  )}
                </div>
              ) : null}
              <div className="goal-rule-metric-grid">
                <span>
                  <Text type="secondary">SP 花费</Text>
                  <Text strong>{formatMoney(selectedGoalRuleProduct.sp_metrics.cost)}</Text>
                </span>
                <span>
                  <Text type="secondary">订单</Text>
                  <Text strong>{selectedGoalRuleProduct.sp_metrics.orders.toLocaleString()}</Text>
                </span>
                <span>
                  <Text type="secondary">ACOS</Text>
                  <Text strong>{formatPercent(selectedGoalRuleProduct.sp_metrics.acos)}</Text>
                </span>
                <span>
                  <Text type="secondary">CVR</Text>
                  <Text strong>{formatPercent(selectedGoalRuleProduct.sp_metrics.cvr)}</Text>
                </span>
              </div>
              <Form layout="vertical">
                <Form.Item label="产品目标" required>
                  <Select
                    placeholder="选择目标"
                    value={selectedGoalRuleProductDraft.goal_type}
                    options={goalOptions}
                    onChange={(value) => updateProductDraft(selectedGoalRuleProduct.id, { goal_type: value })}
                  />
                </Form.Item>
                <div className="batch-rule-grid">
                  <Form.Item label="目标 ACOS">
                    <InputNumber
                      className="table-control"
                      min={0}
                      step={0.05}
                      value={selectedGoalRuleProductDraft.rules.target_acos}
                      placeholder="例如 0.3"
                      onChange={(value) => updateProductRuleDraft(selectedGoalRuleProduct.id, "target_acos", value)}
                    />
                  </Form.Item>
                  <Form.Item label="目标 CVR">
                    <InputNumber
                      className="table-control"
                      min={0}
                      step={0.01}
                      value={selectedGoalRuleProductDraft.rules.target_cvr}
                      placeholder="例如 0.08"
                      onChange={(value) => updateProductRuleDraft(selectedGoalRuleProduct.id, "target_cvr", value)}
                    />
                  </Form.Item>
                  <Form.Item label="最小点击">
                    <InputNumber
                      className="table-control"
                      min={0}
                      precision={0}
                      value={selectedGoalRuleProductDraft.rules.min_clicks}
                      onChange={(value) => updateProductRuleDraft(selectedGoalRuleProduct.id, "min_clicks", value)}
                    />
                  </Form.Item>
                  <Form.Item label="最小花费">
                    <InputNumber
                      className="table-control"
                      min={0}
                      step={1}
                      value={selectedGoalRuleProductDraft.rules.min_spend}
                      onChange={(value) => updateProductRuleDraft(selectedGoalRuleProduct.id, "min_spend", value)}
                    />
                  </Form.Item>
                  <Form.Item label="最小订单">
                    <InputNumber
                      className="table-control"
                      min={0}
                      precision={0}
                      value={selectedGoalRuleProductDraft.rules.min_orders}
                      onChange={(value) => updateProductRuleDraft(selectedGoalRuleProduct.id, "min_orders", value)}
                    />
                  </Form.Item>
                  <Form.Item label="最大 CPC">
                    <InputNumber
                      className="table-control"
                      min={0}
                      step={0.1}
                      value={selectedGoalRuleProductDraft.rules.max_cpc}
                      onChange={(value) => updateProductRuleDraft(selectedGoalRuleProduct.id, "max_cpc", value)}
                    />
                  </Form.Item>
                  <Form.Item label="库存阈值">
                    <InputNumber
                      className="table-control"
                      min={0}
                      precision={0}
                      value={selectedGoalRuleProductDraft.rules.inventory_guard}
                      onChange={(value) => updateProductRuleDraft(selectedGoalRuleProduct.id, "inventory_guard", value)}
                    />
                  </Form.Item>
                </div>
                <Form.Item label="目标备注">
                  <Input
                    value={selectedGoalRuleProductDraft.note}
                    placeholder="记录为什么给这个产品设置该目标"
                    onChange={(event) => updateProductDraft(selectedGoalRuleProduct.id, { note: event.target.value })}
                  />
                </Form.Item>
              </Form>
              <Space>
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  loading={productSavingId === selectedGoalRuleProduct.id}
                  onClick={() => void saveProductSettings(selectedGoalRuleProduct.id)}
                >
                  人工保存设置
                </Button>
                <Button onClick={() => setSelectedGoalRuleProduct(null)}>关闭</Button>
              </Space>
            </Space>
          ) : null}
        </Drawer>

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
                <Text type="secondary">店铺 {formatStoreIdentityLabel(dashboard?.market)}</Text>
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
                    <div className="business-context-panel">
                      <div className="business-context-header">
                        <Text strong>产品经营背景</Text>
                        <Tag color="blue">销售表现</Tag>
                      </div>
                      {selectedBusinessSnapshot ? (
                        <>
                          <div className="source-line">
                            快照周期: {selectedBusinessSnapshot.period_start || "-"} 至 {selectedBusinessSnapshot.period_end || "-"}
                          </div>
                          {selectedBusinessSnapshotMetrics.length ? (
                            <div className="business-context-grid">
                              {selectedBusinessSnapshotMetrics.map((item) => (
                                <div className="business-context-metric" key={item.label}>
                                  <Text type="secondary">{item.label}</Text>
                                  <Text strong>{item.value}</Text>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <Text type="secondary">暂无可读经营指标</Text>
                          )}
                        </>
                      ) : (
                        <Text type="secondary">暂无产品经营快照，仍可查看下方规则证据和原始溯源。</Text>
                      )}
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
        <Drawer
          title="产品归因证据详情"
          open={attributionEvidenceOpen}
          onClose={() => setAttributionEvidenceOpen(false)}
          width={760}
        >
          {attributionEvidenceLoading ? (
            <Spin />
          ) : attributionEvidence ? (
            <Space direction="vertical" size={16} className="drawer-body attribution-evidence-drawer">
              <Alert
                type="info"
                showIcon
                message="仅保存本地归因规则和证据快照，不会自动修改广告活动、广告组、关键词或竞价。"
                description="只更新本地归因关系和证据快照，不会修改广告；草稿对象上的产品目标 / 规则不会自动迁移。"
              />
              <section>
                <Text strong>归因对象</Text>
                <div className="object-name">{attributionEvidence.source.scope_name || attributionEvidence.source.scope_id}</div>
                <div className="source-line">
                  周期 {attributionEvidence.period.start} 至 {attributionEvidence.period.end} / Campaign{" "}
                  {attributionEvidence.source.campaign_name || attributionEvidence.source.campaign_id || "-"} / Ad Group{" "}
                  {attributionEvidence.source.ad_group_name || attributionEvidence.source.ad_group_id || "-"}
                </div>
                <div className="detail-metric-grid attribution-metric-grid">
                  <div className="detail-metric">
                    <Text type="secondary">花费</Text>
                    <Text strong>${formatMoney(attributionEvidence.source.cost)}</Text>
                  </div>
                  <div className="detail-metric">
                    <Text type="secondary">销售额</Text>
                    <Text strong>${formatMoney(attributionEvidence.source.sales)}</Text>
                  </div>
                  <div className="detail-metric">
                    <Text type="secondary">订单</Text>
                    <Text strong>{attributionEvidence.source.orders}</Text>
                  </div>
                  <div className="detail-metric">
                    <Text type="secondary">ACOS</Text>
                    <Text strong>{formatPercent(attributionEvidence.source.acos)}</Text>
                  </div>
                </div>
              </section>
              {attributionEvidence.conflicts.length ? (
                <Alert
                  type="warning"
                  showIcon
                  message="存在已确认归因规则"
                  description={attributionEvidence.conflicts.map((item) => item.message).join("；")}
                />
              ) : null}
              <section>
                <Text strong>产品候选与可信度</Text>
                <div className="candidate-list">
                  {attributionEvidence.candidate_products.length ? (
                    attributionEvidence.candidate_products.slice(0, 5).map((candidate) => (
                      <div className="candidate-row" key={candidate.product_id}>
                        <div>
                          <Space wrap>
                            <Text strong>{candidate.product_name || candidate.asin || candidate.msku || `产品 ${candidate.product_id}`}</Text>
                            <Tag color={confidenceColor(candidate.confidence_level)}>
                              可信度 {confidenceLabel(candidate.confidence_level)} {candidate.confidence_score}
                            </Tag>
                            {candidate.product_id === attributionProductId ? <Tag color="blue">已选择</Tag> : null}
                          </Space>
                          <div className="source-line">
                            ASIN {candidate.asin || "-"} / MSKU {candidate.msku || "-"} / 目标 {productGoalLabel(candidate.goal_type)}
                          </div>
                          <div className="source-line">{candidate.reasons.join("；")}</div>
                        </div>
                        <Button size="small" onClick={() => setAttributionProductId(candidate.product_id)}>
                          选择产品
                        </Button>
                      </div>
                    ))
                  ) : (
                    <Empty description="暂无产品候选" />
                  )}
                </div>
                <Button size="small" onClick={() => prefillProductFromAdSource(attributionEvidence.source)}>
                  从广告来源创建产品草稿
                </Button>
              </section>
              <section>
                <Text strong>广告对象证据快照</Text>
                <div className="source-line">下面证据来自当前广告对象，不会随候选产品切换；切换产品只改变保存的归因对象。</div>
                <div className="evidence-columns">
                  <div>
                    <Text type="secondary">Top 关键词</Text>
                    <Space direction="vertical" size={4} className="drawer-body">
                      {attributionEvidence.top_keywords.length ? (
                        attributionEvidence.top_keywords.map((item) => (
                          <div className="source-line" key={`${item.keyword_id || item.keyword_text}-${item.cost}`}>
                            {item.keyword_text || item.keyword_id || "-"} / 花费 ${formatMoney(item.cost)} / 订单 {item.orders}
                          </div>
                        ))
                      ) : (
                        <Text type="secondary">暂无关键词证据</Text>
                      )}
                    </Space>
                  </div>
                  <div>
                    <Text type="secondary">Top 搜索词</Text>
                    <Space direction="vertical" size={4} className="drawer-body">
                      {attributionEvidence.top_search_terms.length ? (
                        attributionEvidence.top_search_terms.map((item) => (
                          <div className="source-line" key={`${item.search_term || item.keyword_text}-${item.cost}`}>
                            {item.search_term || item.keyword_text || "-"} / 花费 ${formatMoney(item.cost)} / 订单 {item.orders}
                          </div>
                        ))
                      ) : (
                        <Text type="secondary">暂无搜索词证据</Text>
                      )}
                    </Space>
                  </div>
                </div>
              </section>
              <section>
                <Text strong>当前将归因到的产品</Text>
                {attributionProductId ? (
                  <div className="source-line">
                    {selectedAttributionCandidate?.product_name ||
                      selectedAttributionProduct?.product_name ||
                      selectedAttributionCandidate?.asin ||
                      selectedAttributionProduct?.asin ||
                      selectedAttributionCandidate?.msku ||
                      selectedAttributionProduct?.msku ||
                      `产品 ${attributionProductId}`}
                    {" / "}ASIN {selectedAttributionCandidate?.asin || selectedAttributionProduct?.asin || "-"} / MSKU{" "}
                    {selectedAttributionCandidate?.msku || selectedAttributionProduct?.msku || "-"}
                    {selectedAttributionCandidate ? (
                      <>
                        {" / "}可信度 {confidenceLabel(selectedAttributionCandidate.confidence_level)}{" "}
                        {selectedAttributionCandidate.confidence_score}
                      </>
                    ) : null}
                  </div>
                ) : (
                  <Text type="secondary">尚未选择归因产品</Text>
                )}
              </section>
              <section>
                <Text strong>人工确认备注</Text>
                <Input.TextArea
                  rows={3}
                  value={attributionEvidenceNote}
                  onChange={(event) => setAttributionEvidenceNote(event.target.value)}
                  placeholder="记录为什么确认该广告对象属于所选产品"
                />
              </section>
              <Space wrap>
                <Select
                  showSearch
                  className="filter attribution-product-select"
                  value={attributionProductId}
                  onChange={(value: number | null) => setAttributionProductId(value ?? null)}
                  options={attributionProductOptions}
                  placeholder="选择归因产品"
                  optionFilterProp="label"
                />
                <Button
                  type="primary"
                  disabled={!attributionProductId}
                  loading={attributionSavingKey === adSourceKey(attributionEvidence.source)}
                  onClick={() => void confirmAdSourceAttribution(attributionEvidence.source, attributionEvidenceNote)}
                >
                  确认归因并保存证据快照
                </Button>
              </Space>
            </Space>
          ) : (
            <Empty description="暂无归因证据" />
          )}
        </Drawer>
        <Modal
          title="记录搜索词归类组人工判断"
          open={!!searchTermGroupDecisionGroup}
          onCancel={() => setSearchTermGroupDecisionGroup(null)}
          onOk={() => void submitSearchTermGroupDecision()}
          confirmLoading={searchTermGroupDecisionSubmitting}
          okText="保存记录"
          cancelText="取消"
        >
          <Form form={searchTermGroupDecisionForm} layout="vertical">
            <Alert
              type="info"
              showIcon
              message={searchTermGroupDecisionScopeLabel}
              description={`${searchTermGroupDecisionScopeDetail} 仅保存本地组级人工判断和证据快照，不代表广告已自动修改。`}
            />
            {searchTermGroupDecisionGroup ? (
              <div className="search-term-decision-meta">
                <Text strong>{searchTermGroupDecisionGroup.group_label}</Text>
                <div className="source-line">
                  {searchTermGroupDecisionGroup.terms.toLocaleString()} 个词 / 点击{" "}
                  {searchTermGroupDecisionGroup.clicks.toLocaleString()} / 订单{" "}
                  {searchTermGroupDecisionGroup.orders.toLocaleString()}
                </div>
              </div>
            ) : null}
            <Form.Item name="decision_type" label="人工判断" rules={[{ required: true, message: "请选择人工判断" }]}>
              <Select
                options={[
                  { value: "adopt_with_changes", label: "修改后采纳" },
                  { value: "observe", label: "加入观察" },
                  { value: "reject", label: "拒绝并记录原因" }
                ]}
              />
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(prev, next) => prev.decision_type !== next.decision_type}>
              {({ getFieldValue }) =>
                getFieldValue("decision_type") === "observe" ? (
                  <Form.Item name="observe_period" label="观察周期" rules={[{ required: true, message: "请选择观察周期" }]}>
                    <Select
                      options={[
                        { value: "7d", label: "7 天" },
                        { value: "14d", label: "14 天" }
                      ]}
                    />
                  </Form.Item>
                ) : null
              }
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(prev, next) => prev.decision_type !== next.decision_type}>
              {({ getFieldValue }) =>
                getFieldValue("decision_type") === "adopt_with_changes" ? (
                  <Form.Item name="modified_action" label="修改后处理说明" rules={[{ required: true, message: "请输入处理说明" }]}>
                    <Input.TextArea rows={3} placeholder="记录运营准备如何处理，但系统不会自动执行" />
                  </Form.Item>
                ) : null
              }
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(prev, next) => prev.decision_type !== next.decision_type}>
              {({ getFieldValue }) => (
                <Form.Item
                  name="reason"
                  label={getFieldValue("decision_type") === "reject" ? "拒绝原因" : "判断依据"}
                  rules={
                    getFieldValue("decision_type") === "reject" || getFieldValue("decision_type") === "adopt_with_changes"
                      ? [{ required: true, message: "请输入判断依据" }]
                      : []
                  }
                >
                  <Input.TextArea rows={3} placeholder="记录人工判断依据" />
                </Form.Item>
              )}
            </Form.Item>
            <Form.Item name="operator_name" label="处理人" rules={[{ required: true, message: "请输入处理人" }]}>
              <Input placeholder="请输入处理人姓名" />
            </Form.Item>
          </Form>
        </Modal>
        <Modal
          title="记录搜索词候选人工判断"
          open={!!searchTermDecisionCandidate}
          onCancel={() => setSearchTermDecisionCandidate(null)}
          onOk={() => void submitSearchTermCandidateDecision()}
          confirmLoading={searchTermDecisionSubmitting}
          okText="保存记录"
          cancelText="取消"
        >
          <Form form={searchTermDecisionForm} layout="vertical">
            <Alert
              type="info"
              showIcon
              message="仅保存本地人工判断和证据快照，不会自动调整竞价、否词、暂停或新增广告。"
            />
            {searchTermDecisionCandidate ? (
              <div className="search-term-decision-meta">
                <Text strong>{searchTermDecisionCandidate.search_term}</Text>
                <div className="source-line">
                  {searchTermDecisionCandidate.candidate_label} / {searchTermDecisionCandidate.performance_label}
                </div>
              </div>
            ) : null}
            <Form.Item name="decision_type" label="人工判断" rules={[{ required: true, message: "请选择人工判断" }]}>
              <Select
                options={[
                  { value: "adopt_with_changes", label: "修改后采纳" },
                  { value: "observe", label: "加入观察" },
                  { value: "reject", label: "拒绝并记录原因" }
                ]}
              />
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(prev, next) => prev.decision_type !== next.decision_type}>
              {({ getFieldValue }) =>
                getFieldValue("decision_type") === "observe" ? (
                  <Form.Item name="observe_period" label="观察周期" rules={[{ required: true, message: "请选择观察周期" }]}>
                    <Select
                      options={[
                        { value: "7d", label: "7 天" },
                        { value: "14d", label: "14 天" }
                      ]}
                    />
                  </Form.Item>
                ) : null
              }
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(prev, next) => prev.decision_type !== next.decision_type}>
              {({ getFieldValue }) =>
                getFieldValue("decision_type") === "adopt_with_changes" ? (
                  <Form.Item name="modified_action" label="修改后处理说明" rules={[{ required: true, message: "请输入处理说明" }]}>
                    <Input.TextArea rows={3} placeholder="记录运营准备如何处理，但系统不会自动执行" />
                  </Form.Item>
                ) : null
              }
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(prev, next) => prev.decision_type !== next.decision_type}>
              {({ getFieldValue }) => (
                <Form.Item
                  name="reason"
                  label={getFieldValue("decision_type") === "reject" ? "拒绝原因" : "判断依据"}
                  rules={
                    getFieldValue("decision_type") === "reject" || getFieldValue("decision_type") === "adopt_with_changes"
                      ? [{ required: true, message: "请输入判断依据" }]
                      : []
                  }
                >
                  <Input.TextArea rows={3} placeholder="记录人工判断依据" />
                </Form.Item>
              )}
            </Form.Item>
            <Form.Item name="operator_name" label="处理人" rules={[{ required: true, message: "请输入处理人" }]}>
              <Input placeholder="请输入处理人姓名" />
            </Form.Item>
          </Form>
        </Modal>
        <Modal
          title="搜索词处理记录复盘"
          open={!!searchTermReviewDecision}
          onCancel={() => {
            setSearchTermReviewDecision(null);
            setSearchTermCandidateReview(null);
          }}
          footer={[
            <Button
              key="close"
              onClick={() => {
                setSearchTermReviewDecision(null);
                setSearchTermCandidateReview(null);
              }}
            >
              关闭
            </Button>
          ]}
          width={760}
        >
          <Spin spinning={searchTermReviewLoading}>
            {searchTermCandidateReview ? (
              <Space direction="vertical" size={14} className="full-width">
                <Alert
                  type="info"
                  showIcon
                  message={searchTermCandidateReview.manual_hint}
                />
                <Space wrap>
                  <Tag color={searchTermCandidateColors[searchTermCandidateReview.candidate_type] || "default"}>
                    {searchTermCandidateLabels[searchTermCandidateReview.candidate_type] || searchTermCandidateReview.candidate_type}
                  </Tag>
                  <Tag color={searchTermReviewColors[searchTermCandidateReview.result]}>
                    {searchTermCandidateReview.result_label}
                  </Tag>
                  <Text strong>{searchTermCandidateReview.search_term}</Text>
                </Space>
                <div className="search-term-review-grid">
                  <div className="search-term-review-card">
                    <Text type="secondary">记录时指标快照</Text>
                    <Title level={5}>
                      {searchTermCandidateReview.before_period.start} 至 {searchTermCandidateReview.before_period.end}
                    </Title>
                    <Space wrap className="metric-pills">
                      <Tag>点击 {searchTermCandidateReview.before_metrics.clicks.toLocaleString()}</Tag>
                      <Tag>花费 {formatMoney(searchTermCandidateReview.before_metrics.cost)}</Tag>
                      <Tag>订单 {searchTermCandidateReview.before_metrics.orders.toLocaleString()}</Tag>
                      <Tag>销售 {formatMoney(searchTermCandidateReview.before_metrics.sales)}</Tag>
                      <Tag color="orange">ACOS {formatPercent(searchTermCandidateReview.before_metrics.acos)}</Tag>
                      <Tag>CVR {formatPercent(searchTermCandidateReview.before_metrics.cvr)}</Tag>
                    </Space>
                  </div>
                  <div className="search-term-review-card">
                    <Text type="secondary">后续 {searchTermCandidateReview.review_period === "7d" ? "7 天复盘" : "14 天复盘"}</Text>
                    <Title level={5}>
                      {searchTermCandidateReview.after_period.start} 至 {searchTermCandidateReview.after_period.end}
                    </Title>
                    <Space wrap className="metric-pills">
                      <Tag>点击 {searchTermCandidateReview.after_metrics.clicks.toLocaleString()}</Tag>
                      <Tag>花费 {formatMoney(searchTermCandidateReview.after_metrics.cost)}</Tag>
                      <Tag>订单 {searchTermCandidateReview.after_metrics.orders.toLocaleString()}</Tag>
                      <Tag>销售 {formatMoney(searchTermCandidateReview.after_metrics.sales)}</Tag>
                      <Tag color="orange">ACOS {formatPercent(searchTermCandidateReview.after_metrics.acos)}</Tag>
                      <Tag>CVR {formatPercent(searchTermCandidateReview.after_metrics.cvr)}</Tag>
                    </Space>
                  </div>
                </div>
                <div className="search-term-review-card">
                  <Text type="secondary">变化</Text>
                  <Space wrap className="metric-pills">
                    <Tag>点击 {searchTermCandidateReview.delta.clicks_delta.toLocaleString()}</Tag>
                    <Tag>花费 {formatMoney(searchTermCandidateReview.delta.cost_delta)}</Tag>
                    <Tag>订单 {searchTermCandidateReview.delta.orders_delta.toLocaleString()}</Tag>
                    <Tag>销售 {formatMoney(searchTermCandidateReview.delta.sales_delta)}</Tag>
                    <Tag color={searchTermCandidateReview.delta.acos_delta <= 0 ? "green" : "red"}>
                      ACOS {formatPercent(searchTermCandidateReview.delta.acos_delta)}
                    </Tag>
                    <Tag color={searchTermCandidateReview.delta.cvr_delta >= 0 ? "green" : "red"}>
                      CVR {formatPercent(searchTermCandidateReview.delta.cvr_delta)}
                    </Tag>
                  </Space>
                </div>
              </Space>
            ) : (
              <Empty description="暂无复盘数据" />
            )}
          </Spin>
        </Modal>
        <Modal
          title={searchTermGroupReviewDecision ? `组级复盘 ${searchTermGroupReviewDecision.group_label}` : "组级复盘"}
          open={!!searchTermGroupReviewDecision}
          onCancel={() => {
            setSearchTermGroupReviewDecision(null);
            setSearchTermGroupDecisionReview(null);
          }}
          footer={[
            <Button
              key="close"
              onClick={() => {
                setSearchTermGroupReviewDecision(null);
                setSearchTermGroupDecisionReview(null);
              }}
            >
              关闭
            </Button>
          ]}
          width={760}
        >
          <Spin spinning={searchTermGroupReviewLoading}>
            {searchTermGroupDecisionReview ? (
              <Space direction="vertical" size={14} className="full-width search-term-group-review-panel">
                <Alert
                  type="info"
                  showIcon
                  message="人工判断复盘"
                  description={searchTermGroupDecisionReview.manual_hint}
                />
                <Space wrap>
                  <Tag color={searchTermSemanticColors[searchTermGroupDecisionReview.semantic_category] || "default"}>
                    {searchTermSemanticLabels[searchTermGroupDecisionReview.semantic_category] || searchTermGroupDecisionReview.semantic_category}
                  </Tag>
                  <Tag color={searchTermPerformanceColors[searchTermGroupDecisionReview.performance_status] || "default"}>
                    {searchTermPerformanceLabels[searchTermGroupDecisionReview.performance_status] || searchTermGroupDecisionReview.performance_status}
                  </Tag>
                  <Tag color={searchTermReviewColors[searchTermGroupDecisionReview.result]}>
                    {searchTermGroupDecisionReview.result_label}
                  </Tag>
                  <Text strong>{searchTermGroupDecisionReview.group_label}</Text>
                </Space>
                <div className="search-term-review-grid">
                  <div className="search-term-review-card">
                    <Text type="secondary">记录时组快照</Text>
                    <Title level={5}>
                      {searchTermGroupDecisionReview.before_period.start} 至 {searchTermGroupDecisionReview.before_period.end}
                    </Title>
                    <Space wrap className="metric-pills">
                      <Tag>点击 {searchTermGroupDecisionReview.before_metrics.clicks.toLocaleString()}</Tag>
                      <Tag>花费 {formatMoney(searchTermGroupDecisionReview.before_metrics.cost)}</Tag>
                      <Tag>订单 {searchTermGroupDecisionReview.before_metrics.orders.toLocaleString()}</Tag>
                      <Tag>销售 {formatMoney(searchTermGroupDecisionReview.before_metrics.sales)}</Tag>
                      <Tag color="orange">ACOS {formatPercent(searchTermGroupDecisionReview.before_metrics.acos)}</Tag>
                      <Tag>CVR {formatPercent(searchTermGroupDecisionReview.before_metrics.cvr)}</Tag>
                    </Space>
                  </div>
                  <div className="search-term-review-card">
                    <Text type="secondary">后续 {searchTermGroupDecisionReview.review_period === "7d" ? "7 天复盘" : "14 天复盘"}</Text>
                    <Title level={5}>
                      {searchTermGroupDecisionReview.after_period.start} 至 {searchTermGroupDecisionReview.after_period.end}
                    </Title>
                    <Space wrap className="metric-pills">
                      <Tag>点击 {searchTermGroupDecisionReview.after_metrics.clicks.toLocaleString()}</Tag>
                      <Tag>花费 {formatMoney(searchTermGroupDecisionReview.after_metrics.cost)}</Tag>
                      <Tag>订单 {searchTermGroupDecisionReview.after_metrics.orders.toLocaleString()}</Tag>
                      <Tag>销售 {formatMoney(searchTermGroupDecisionReview.after_metrics.sales)}</Tag>
                      <Tag color="orange">ACOS {formatPercent(searchTermGroupDecisionReview.after_metrics.acos)}</Tag>
                      <Tag>CVR {formatPercent(searchTermGroupDecisionReview.after_metrics.cvr)}</Tag>
                    </Space>
                  </div>
                </div>
                <div className="search-term-review-card">
                  <Text type="secondary">变化</Text>
                  <Space wrap className="metric-pills">
                    <Tag>点击 {searchTermGroupDecisionReview.delta_metrics.clicks_delta.toLocaleString()}</Tag>
                    <Tag>花费 {formatMoney(searchTermGroupDecisionReview.delta_metrics.cost_delta)}</Tag>
                    <Tag>订单 {searchTermGroupDecisionReview.delta_metrics.orders_delta.toLocaleString()}</Tag>
                    <Tag>销售 {formatMoney(searchTermGroupDecisionReview.delta_metrics.sales_delta)}</Tag>
                    <Tag color={searchTermGroupDecisionReview.delta_metrics.acos_delta <= 0 ? "green" : "red"}>
                      ACOS {formatPercent(searchTermGroupDecisionReview.delta_metrics.acos_delta)}
                    </Tag>
                    <Tag color={searchTermGroupDecisionReview.delta_metrics.cvr_delta >= 0 ? "green" : "red"}>
                      CVR {formatPercent(searchTermGroupDecisionReview.delta_metrics.cvr_delta)}
                    </Tag>
                  </Space>
                </div>
              </Space>
            ) : (
              <Empty description="暂无组级复盘数据" />
            )}
          </Spin>
        </Modal>
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
          onCancel={() => {
            setCreateProductOpen(false);
            setProductSeedSource(null);
          }}
          onOk={() => void submitCreateProduct()}
          confirmLoading={creatingProduct}
          okText="创建"
          cancelText="取消"
        >
          <Form form={productForm} layout="vertical">
            {productSeedSource ? (
              <Alert
                type="info"
                showIcon
                message="先创建产品草稿，再人工确认归因"
                description="系统只预填广告来源名称和店铺 ID；创建产品不会自动保存归因规则，也不会修改广告。"
              />
            ) : null}
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
            <Form.Item name="market_id" hidden>
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
          <Alert
            className="section-alert"
            type="info"
            showIcon
            message="人工复盘边界"
            description="复盘只记录人工判断和指标快照，不自动修改广告，也不会自动调整竞价、预算、否词、暂停或新增广告。"
          />
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
