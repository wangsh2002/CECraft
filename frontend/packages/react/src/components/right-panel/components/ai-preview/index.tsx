import { Modal, Button } from "@arco-design/web-react";
import type { FC } from "react";
import React, { useMemo, useRef } from "react";
import type { DeltaState, Editor } from "sketching-core";
import { TSON } from "sketching-utils";
import type { RichTextLines } from "sketching-plugin";
import { TEXT_ATTRS } from "sketching-plugin";
import { Delta as BlockDelta } from "@block-kit/delta";

import { sketchToTextDelta } from "../text/utils/transform";
import { RichTextEditor } from "../text/modules/editor";
import { getDefaultTextDelta } from "../text/utils/constant";

interface AIPreviewModalProps {
  visible: boolean;
  onCancel: () => void;
  onApply: () => void;
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
  // 1. 右侧（修改后）的数据 Ref
  const modifiedDataRef = useRef<BlockDelta | null>(null);

  // 2. 左侧（修改前）的数据 Ref
  const originalDataRef = useRef<BlockDelta | null>(null);

  // 处理右侧数据 (AI 返回的数据)
  useMemo(() => {
    if (modifiedData) {
      try {
        let sourceData = modifiedData;
        if (typeof modifiedData === "string") {
            sourceData = JSON.parse(modifiedData);
        }

        if (sourceData && Array.isArray(sourceData.ops)) {
            modifiedDataRef.current = new BlockDelta(sourceData.ops);
        } else {
            modifiedDataRef.current = sketchToTextDelta(sourceData as RichTextLines);
        }
      } catch (e) {
        console.error("Preview Data Parse Error:", e);
        modifiedDataRef.current = getDefaultTextDelta();
      }
    } else {
      modifiedDataRef.current = getDefaultTextDelta();
    }
  }, [modifiedData]);

  // 3. 处理左侧数据 (原始 State 数据)
  useMemo(() => {
    if (originalState) {
        try {
            // 从 activeState 中获取原始的 sketch 数据格式
            const rawData = originalState.getAttr(TEXT_ATTRS.DATA);
            if (rawData) {
                const parsed = TSON.parse<RichTextLines>(rawData);
                // 转换为编辑器可用的 Delta 格式
                originalDataRef.current = parsed ? sketchToTextDelta(parsed) : getDefaultTextDelta();
            } else {
                originalDataRef.current = getDefaultTextDelta();
            }
        } catch (e) {
            console.error("Original Data Parse Error:", e);
            originalDataRef.current = getDefaultTextDelta();
        }
    }
  }, [originalState]);

  return (
    <Modal
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>✨ AI 修改预览</span>
          <span style={{ fontSize: 12, color: "var(--color-text-3)", fontWeight: "normal" }}>
            左侧为原始内容，右侧为 AI 建议。您可以直接在右侧微调内容后应用。
          </span>
        </div>
      }
      visible={visible}
      onOk={onApply}
      onCancel={onCancel}
      autoFocus={false}
      focusLock={true}
      style={{ width: 1000 }} // 加宽模态框
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
           <Button onClick={onCancel}>取消修改</Button>
           <Button type="primary" status="success" onClick={onApply}>确认应用</Button>
        </div>
      }
    >
      {/* 双栏布局容器 */}
      <div style={{ display: 'flex', gap: 20, height: 500 }}>
        
        {/* 左侧：修改前 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ 
                marginBottom: 8, 
                fontWeight: 600, 
                color: 'var(--color-text-2)',
                display: 'flex',
                justifyContent: 'space-between'
            }}>
                <span>修改前</span>
                <span style={{ fontSize: 12, color: 'var(--color-text-3)' }}>只读</span>
            </div>
            <div 
                style={{ 
                flex: 1,
                border: "1px solid var(--color-border-2)", 
                borderRadius: 4, 
                padding: 12,
                overflowY: "auto",
                backgroundColor: "var(--color-fill-2)" // 稍微深一点的背景表示只读
                }}
            >
                {/* 传入 readonly=true */}
                <RichTextEditor 
                    editor={editor} 
                    state={originalState} 
                    dataRef={originalDataRef}
                    readonly={true} 
                />
            </div>
        </div>

        {/* 中间箭头 (可选装饰) */}
        <div style={{ display: 'flex', alignItems: 'center', color: 'var(--color-text-3)' }}>
            👉
        </div>

        {/* 右侧：修改后 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div style={{ marginBottom: 8, fontWeight: 600, color: 'rgb(22, 93, 255)' }}>
                修改后
            </div>
            <div 
                style={{ 
                flex: 1,
                border: "1px solid rgb(22, 93, 255)", // 蓝色边框强调
                borderRadius: 4, 
                padding: 12,
                overflowY: "auto",
                backgroundColor: "var(--color-bg-1)"
                }}
            >
                {/* 右侧可编辑 */}
                <RichTextEditor 
                    editor={editor} 
                    state={originalState} 
                    dataRef={modifiedDataRef}
                />
            </div>
        </div>

      </div>
    </Modal>
  );
};