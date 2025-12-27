import { Modal, Button, Message } from "@arco-design/web-react";
import type { FC } from "react";
import React, { useMemo, useRef } from "react";
import type { DeltaState, Editor } from "sketching-core";
import { TSON } from "sketching-utils";
import type { RichTextLines } from "sketching-plugin";
import { TEXT_ATTRS } from "sketching-plugin";
import { Delta as BlockDelta } from "@block-kit/delta";
import { Op, OP_TYPE } from "sketching-delta";

import { sketchToTextDelta, textDeltaToSketch } from "../text/utils/transform";
import { RichTextEditor } from "../text/modules/editor";
import { getDefaultTextDelta } from "../text/utils/constant";
import { getDiffDeltas, cleanHighlight } from "./utils/diff"; // 引入 Diff 工具

interface AIPreviewModalProps {
  visible: boolean;
  onCancel: () => void;
  onApply: () => void; // 这里仅用于通知父组件关闭弹窗
  originalState: DeltaState;
  editor: Editor;
  modifiedData: any;
}

export const AIPreviewModal: FC<AIPreviewModalProps> = ({
  visible,
  onCancel,
  onApply,
  originalState,
  editor,
  modifiedData,
}) => {
  // 左侧（修改前）数据 Ref
  const originalDataRef = useRef<BlockDelta | null>(null);
  
  // 右侧（修改后）数据 Ref - 初始带高亮
  const modifiedDataRef = useRef<BlockDelta | null>(null);
  
  // 暂存用户在右侧编辑器中最终修改的结果
  const finalResultRef = useRef<BlockDelta | null>(null);

  // 计算 Diff 逻辑
  useMemo(() => {
    if (!visible) return;

    try {
      // 1. 获取左侧原始数据 (Sketch Format -> Delta)
      let originalDelta = getDefaultTextDelta();
      if (originalState) {
        const rawData = originalState.getAttr(TEXT_ATTRS.DATA);
        if (rawData) {
          const parsed = TSON.parse<RichTextLines>(rawData);
          if (parsed) originalDelta = sketchToTextDelta(parsed);
        }
      }

      // 2. 获取右侧 AI 数据 (Json/Delta -> Delta)
      let newDelta = getDefaultTextDelta();
      let sourceData = modifiedData;
      if (typeof modifiedData === "string") {
        try {
            sourceData = JSON.parse(modifiedData);
        } catch(e) {}
      }
      
      // Check if it is a DeltaSet (Dict of Deltas) returned by backend
      const isDeltaSet = sourceData && typeof sourceData === 'object' && !Array.isArray(sourceData) && !Array.isArray(sourceData.ops) && Object.keys(sourceData).some(k => {
          const item = sourceData[k];
          return item && typeof item === 'object' && item.key === 'text';
      });

      if (isDeltaSet) {
          // Sort by y to maintain order
          const sortedItems = Object.values(sourceData).sort((a: any, b: any) => (a.y || 0) - (b.y || 0));
          
          const combinedOps: any[] = [];
          
          for (const item of sortedItems) {
              const dataStr = (item as any).attrs?.DATA;
              if (dataStr) {
                  const lines = TSON.parse<RichTextLines>(dataStr);
                  if (lines) {
                      const partDelta = sketchToTextDelta(lines);
                      if (partDelta && partDelta.ops) {
                          combinedOps.push(...partDelta.ops);
                          // Ensure newline between blocks if needed (simple heuristic)
                          const lastOp = combinedOps[combinedOps.length - 1];
                          if (typeof lastOp.insert === 'string' && !lastOp.insert.endsWith('\n')) {
                              combinedOps.push({ insert: '\n' });
                          }
                      }
                  }
              }
          }
          newDelta = new BlockDelta(combinedOps);
      } else if (sourceData && Array.isArray(sourceData.ops)) {
        newDelta = new BlockDelta(sourceData.ops);
      } else if (sourceData) {
        newDelta = sketchToTextDelta(sourceData as RichTextLines);
      }

      // 3. 计算 Diff 并生成左右两份带高亮的 Delta
      const { left, right } = getDiffDeltas(originalDelta, newDelta);

      originalDataRef.current = left;
      modifiedDataRef.current = right;
      finalResultRef.current = right; // 默认最终结果就是 AI 生成的结果

    } catch (e) {
      console.error("Diff Calculation Error:", e);
      originalDataRef.current = getDefaultTextDelta();
      modifiedDataRef.current = getDefaultTextDelta();
    }
  }, [modifiedData, originalState, visible]);

  // 点击“确认应用”时的处理逻辑
  const handleApply = () => {
    if (finalResultRef.current && originalState) {
        try {
            // 1. 清洗高亮背景 (移除红绿背景色)
            const cleanDelta = cleanHighlight(finalResultRef.current);
            
            // 2. 转换回 Sketch 内部格式 (Delta -> RichTextLines)
            // 注意：确保 textDeltaToSketch 已经修复了字符串拆分问题
            const sketchData = textDeltaToSketch(cleanDelta);
            
            // 3. 序列化
            const payload = TSON.stringify(sketchData);

            // 4. 应用到画布 State
            editor.state.apply(new Op(OP_TYPE.REVISE, { 
                id: originalState.id, 
                attrs: { [TEXT_ATTRS.DATA]: payload } 
            }));
            
            Message.success("修改已应用");
            onApply(); // 关闭弹窗
        } catch (e) {
            console.error("Apply Error:", e);
            Message.error("应用失败，请检查数据格式");
        }
    }
  };

  return (
    <Modal
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>✨ AI 修改预览</span>
          <span style={{ fontSize: 12, color: "var(--color-text-3)", fontWeight: "normal" }}>
            <span style={{background: '#ffe6e6', padding: '0 4px', borderRadius: 2, marginRight: 4, color: '#f53f3f'}}>红色</span>代表删除，
            <span style={{background: '#e6ffec', padding: '0 4px', borderRadius: 2, marginRight: 4, color: '#00b42a'}}>绿色</span>代表新增。
          </span>
        </div>
      }
      visible={visible}
      onOk={handleApply}
      onCancel={onCancel}
      autoFocus={false}
      focusLock={true}
      style={{ width: 1000 }} // 宽模态框
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
           <Button onClick={onCancel}>取消修改</Button>
           <Button type="primary" status="success" onClick={handleApply}>确认应用</Button>
        </div>
      }
    >
      <div style={{ display: 'flex', gap: 20, height: 500 }}>
        
        {/* 左侧：修改前 (只读) */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ marginBottom: 8, fontWeight: 600, color: 'var(--color-text-2)', display: 'flex', justifyContent: 'space-between' }}>
                <span>修改前</span>
                <span style={{ fontSize: 12, color: 'var(--color-text-3)' }}>只读</span>
            </div>
            <div style={{ flex: 1, border: "1px solid var(--color-border-2)", borderRadius: 4, padding: 12, overflowY: "auto", backgroundColor: "var(--color-fill-2)" }}>
                <RichTextEditor 
                    editor={editor} 
                    state={originalState} 
                    dataRef={originalDataRef}
                    readonly={true} // 开启只读
                />
            </div>
        </div>

        {/* 中间箭头 */}
        <div style={{ display: 'flex', alignItems: 'center', color: 'var(--color-text-3)' }}>
            👉
        </div>

        {/* 右侧：修改后 (可编辑) */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ marginBottom: 8, fontWeight: 600, color: 'rgb(22, 93, 255)' }}>修改后 (可微调)</div>
            <div style={{ flex: 1, border: "1px solid rgb(22, 93, 255)", borderRadius: 4, padding: 12, overflowY: "auto", backgroundColor: "var(--color-bg-1)" }}>
                <RichTextEditor 
                    editor={editor} 
                    state={originalState} 
                    dataRef={modifiedDataRef}
                    // 接管数据流，防止实时写入画布
                    onChange={(newVal) => {
                        finalResultRef.current = newVal;
                    }}
                />
            </div>
        </div>

      </div>
    </Modal>
  );
};