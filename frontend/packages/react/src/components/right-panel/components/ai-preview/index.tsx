import { Modal, Button, Message } from "@arco-design/web-react";
import type { FC } from "react";
import React, { useMemo, useRef } from "react";
import type { DeltaState, Editor } from "sketching-core";
import { TSON } from "sketching-utils";
import type { RichTextLines } from "sketching-plugin";
import type { Delta as BlockDelta } from "@block-kit/delta";

// 复用现有的转换逻辑和编辑器组件
import { sketchToTextDelta } from "../text/utils/transform";
import { RichTextEditor } from "../text/modules/editor";
import { getDefaultTextDelta } from "../text/utils/constant";
import styles from "../../index.m.scss"; // 复用右侧面板样式

interface AIPreviewModalProps {
  visible: boolean;
  onCancel: () => void;
  onApply: () => void;
  originalState: DeltaState; // 原始状态用于提供上下文
  editor: Editor;            // 编辑器实例
  modifiedData: any;         // AI 返回的 Delta JSON 数据
}

export const AIPreviewModal: FC<AIPreviewModalProps> = ({
  visible,
  onCancel,
  onApply,
  originalState,
  editor,
  modifiedData,
}) => {
  // 转换数据格式以适应 RichTextEditor
  const dataRef = useRef<BlockDelta | null>(null);

  useMemo(() => {
    if (modifiedData) {
      try {
        // 假设 AI 返回的是 sketch 插件标准的 { chars: [...] } 或直接是 Delta
        // 这里我们需要做一层防御性转换，确保格式符合 block-kit
        let sourceData = modifiedData;
        
        // 如果是字符串，尝试解析
        if (typeof modifiedData === "string") {
            sourceData = JSON.parse(modifiedData);
        }

        // 尝试转换
        dataRef.current = sketchToTextDelta(sourceData as RichTextLines);
      } catch (e) {
        console.error("Preview Data Parse Error:", e);
        dataRef.current = getDefaultTextDelta();
      }
    } else {
      dataRef.current = getDefaultTextDelta();
    }
  }, [modifiedData]);

  return (
    <Modal
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>✨ AI 修改预览</span>
          <span style={{ fontSize: 12, color: "var(--color-text-3)", fontWeight: "normal" }}>
            请确认修改内容，点击应用生效
          </span>
        </div>
      }
      visible={visible}
      onOk={onApply}
      onCancel={onCancel}
      autoFocus={false}
      focusLock={true}
      style={{ width: 600 }}
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
           <Button onClick={onCancel}>取消修改</Button>
           <Button type="primary" status="success" onClick={onApply}>确认应用</Button>
        </div>
      }
    >
      <div 
        style={{ 
          border: "1px solid var(--color-border-2)", 
          borderRadius: 4, 
          padding: 12,
          minHeight: 200,
          maxHeight: 400,
          overflowY: "auto",
          backgroundColor: "var(--color-bg-1)"
        }}
      >
        {/* 注意：RichTextEditor 内部可能依赖 state.getAttr 获取数据。
            但在预览模式下，我们需要它渲染 modifiedData。
            如果 RichTextEditor 强绑定了 state，我们可能需要 mock 一个 state 或者
            修改 RichTextEditor 支持传入 initialData。
            
            根据查看 index.tsx，RichTextEditor 接收 dataRef 作为数据源。
            只要 dataRef 更新，且组件重新渲染，应该能显示新内容。
        */}
        <RichTextEditor 
            editor={editor} 
            state={originalState} 
            dataRef={dataRef} 
        />
      </div>
    </Modal>
  );
};