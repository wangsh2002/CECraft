import { Delta } from "@block-kit/delta";
import diff from "fast-diff";

// 定义高亮颜色
const COLOR_ADDED = "#e6ffec";   // 浅绿 (新增)
const COLOR_REMOVED = "#ffe6e6"; // 浅红 (删除)

/**
 * 将 Delta 转换为纯文本，用于 fast-diff 计算
 */
const deltaToText = (delta: Delta): string => {
  return delta.ops
    .map(op => (typeof op.insert === "string" ? op.insert : "\u0000"))
    .join("");
};

/**
 * 将 diff 结果映射回 Delta，叠加高亮属性
 * * @param baseDelta 基础 Delta (用于 Left 视图时是 originalDelta，用于 Right 视图时是 modifiedDelta)
 * @param diffs fast-diff 的计算结果
 * @param targetType 要高亮的 diff 类型 (-1: 删除, 1: 新增)
 * @param highlightColor 高亮颜色
 */
const applyHighlight = (
  baseDelta: Delta,
  diffs: [number, string][],
  targetType: number,
  highlightColor: string
): Delta => {
  // 克隆原始 ops 以保留原有格式 (Bold, Italic 等)
  const targetDelta = new Delta(baseDelta.ops);
  
  // 构建一个仅包含样式变更的 attributeDelta
  const attributeDelta = new Delta();
  let cursor = 0; // 当前在 baseDelta 文本中的位置

  for (const [diffType, diffText] of diffs) {
    if (diffType === 0) {
      // 相等: 移动游标，保留原样
      cursor += diffText.length;
    } else if (diffType === targetType) {
      // 命中目标类型 (例如 Left 视图中的 -1，或 Right 视图中的 1)
      // 这段文本在当前 baseDelta 中是存在的，我们需要给它加高亮
      // 1. 移动到当前位置
      if (cursor > 0) {
        // 计算 attributeDelta 的当前长度，补齐 retain
        // 注意：这里简化处理，attributeDelta 是全新的，我们需要根据 cursor 累积 retain
        // 但更好的方式是直接根据 ranges 构造
      }
      // 这种方式比较绕，我们采用 "Ranges" 收集法
    } else {
      // 另一种类型 (例如在 Left 视图中遇到了 1 新增)，它在 Left 的 baseDelta 中不存在，忽略
    }
  }

  // --- 重构逻辑：收集 Ranges 然后统一 Apply ---
  
  const ranges: { start: number; length: number }[] = [];
  let currentPos = 0;

  for (const [diffType, diffText] of diffs) {
    if (diffType === 0) {
      // 内容存在于 baseDelta，无变化
      currentPos += diffText.length;
    } else if (diffType === targetType) {
      // 内容存在于 baseDelta，且是目标变更类型 -> 记录高亮区间
      ranges.push({ start: currentPos, length: diffText.length });
      currentPos += diffText.length;
    } else {
      // diffType !== targetType (例如 Left 视图遇到了 "新增")
      // 该内容不占用 baseDelta 的字符空间，跳过
    }
  }

  // 构建样式叠加层
  let lastPos = 0;
  for (const range of ranges) {
    const gap = range.start - lastPos;
    if (gap > 0) {
      attributeDelta.retain(gap);
    }
    attributeDelta.retain(range.length, { background: highlightColor });
    lastPos = range.start + range.length;
  }

  // 将样式 Delta 叠加到 内容 Delta 上
  return targetDelta.compose(attributeDelta);
};

export const getDiffDeltas = (oldDelta: Delta, newDelta: Delta) => {
  const text1 = deltaToText(oldDelta);
  const text2 = deltaToText(newDelta);
  
  const diffResult = diff(text1, text2); // fast-diff 计算
  
  // 生成左侧视图：基于 oldDelta，高亮被删除部分 (-1)
  const left = applyHighlight(oldDelta, diffResult, -1, COLOR_REMOVED);
  
  // 生成右侧视图：基于 newDelta，高亮新增部分 (1)
  const right = applyHighlight(newDelta, diffResult, 1, COLOR_ADDED);
  
  return { left, right };
};

/**
 * 清洗 Delta，移除 diff 高亮颜色（用于最终保存）
 */
export const cleanHighlight = (delta: Delta): Delta => {
  const clean = new Delta();
  delta.forEach(op => {
    const attributes = { ...op.attributes };
    // 如果背景色是我们定义的高亮色，则移除
    if (attributes.background === COLOR_ADDED || attributes.background === COLOR_REMOVED) {
      delete attributes.background;
    }
    // 如果移除后 attributes 为空，则设为 undefined
    const finalAttrs = Object.keys(attributes).length > 0 ? attributes : undefined;
    
    clean.push({ insert: op.insert, attributes: finalAttrs });
  });
  return clean;
};