import { Modal, Button, Message } from "@arco-design/web-react";
import type { FC } from "react";
import React, { useMemo, useRef } from "react";
import type { DeltaState, Editor } from "sketching-core";
import { TSON } from "sketching-utils";
import type { RichTextLines } from "sketching-plugin";
// [修改点 1] 去掉 type，我们需要使用 Delta 类
import { Delta as BlockDelta } from "@block-kit/delta";

import { sketchToTextDelta } from "../text/utils/transform";
import { RichTextEditor } from "../text/modules/editor";
import { getDefaultTextDelta } from "../text/utils/constant";
import styles from "../../index.m.scss";


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
  const dataRef = useRef<BlockDelta | null>(null);

  useMemo(() => {
    if (modifiedData) {
      try {
        let sourceData = modifiedData;
        if (typeof modifiedData === "string") {
            sourceData = JSON.parse(modifiedData);
        }

        // [修改点 2] 增加格式判断逻辑
        // 如果后端返回的是标准的 Delta 格式（包含 ops 数组）
        if (sourceData && Array.isArray(sourceData.ops)) {
            // 直接构建 BlockDelta 对象，跳过 sketchToTextDelta 转换
            dataRef.current = new BlockDelta(sourceData.ops);
        } 
        // 否则尝试按照 Sketch 内部格式转换
        else {
            dataRef.current = sketchToTextDelta(sourceData as RichTextLines);
        }

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
        <RichTextEditor 
            editor={editor} 
            state={originalState} 
            dataRef={dataRef} 
        />
      </div>
    </Modal>
  );
};