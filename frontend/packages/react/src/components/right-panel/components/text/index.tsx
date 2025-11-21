// 右侧面板 — 富文本展示/编辑组件
// 该组件用于在右侧面板或模态框中渲染富文本编辑器。
// - 在普通侧栏中显示时会有一个可调整宽度的面板
// - 双击编辑区或点击右上角展开图标时，会以模态框形式打开编辑器

import { Modal } from "@arco-design/web-react";
import { IconLaunch } from "@arco-design/web-react/icon";
import type { Delta as BlockDelta } from "@block-kit/delta";
import { throttle } from "@block-kit/utils";
import type { FC } from "react";
import React, { useEffect, useMemo, useRef, useState } from "react";
import type { DeltaState, Editor } from "sketching-core";
import { EDITOR_EVENT } from "sketching-core";
import type { RichTextLines } from "sketching-plugin";
import { TEXT_ATTRS } from "sketching-plugin";
import { TSON } from "sketching-utils";

import { NAV_ENUM } from "../../../header/utils/constant";
import styles from "../index.m.scss";
import { RichTextEditor } from "./modules/editor";
import { DEFAULT_MODAL_WIDTH, getDefaultTextDelta } from "./utils/constant";
import { sketchToTextDelta } from "./utils/transform";

// Props: editor - 编辑器实例，state - 当前 delta 的状态对象
export const Text: FC<{ editor: Editor; state: DeltaState }> = props => {
  const { editor, state } = props;

  // 模态框/侧边栏宽度，默认值来自常量
  const [width, setWidth] = useState(DEFAULT_MODAL_WIDTH);

  // 是否以模态框形式展示富文本编辑器
  const [modalMode, setModalMode] = useState(false);

  // 存放经过转换后的 BlockDelta（用于富文本编辑器的数据源）
  const dataRef = useRef<BlockDelta | null>(null);

  // 根据 delta 的属性（TEXT_ATTRS.DATA）构建编辑器数据
  // 使用 useMemo 以便在 state 变化时更新，但不会在每次渲染都重新解析
  useMemo(() => {
    const data = state.getAttr(TEXT_ATTRS.DATA);
    const blockDelta = data && TSON.parse<RichTextLines>(data);
    if (blockDelta) {
      // 将 sketch 插件的富文本数据转换为编辑器可识别的 BlockDelta
      dataRef.current = sketchToTextDelta(blockDelta);
    } else {
      // 没有数据时使用默认值，保证编辑器能够正常初始化
      dataRef.current = getDefaultTextDelta();
    }
  }, [state]);

  // 监听编辑器的点击事件（用于检测双击以进入模态编辑模式）
  useEffect(() => {
    const onDoubleClick = (e: MouseEvent) => {
      // e.detail === 2 表示双击
      if (e.detail !== 2) return void 0;
      const active = Array.from(editor.selection.getActiveDeltaIds());
      const id = active.length === 1 && active[0];
      const state = id && editor.state.getDeltaState(id);
      // 仅当选中的是文本类型的 delta 时触发模态框打开
      state && state.key === NAV_ENUM.TEXT && setModalMode(true);
    };
    editor.event.on(EDITOR_EVENT.CLICK, onDoubleClick);
    return () => {
      editor.event.off(EDITOR_EVENT.CLICK, onDoubleClick);
    };
  }, [editor.event, editor.selection, editor.state]);

  // 侧栏内拖拽改变宽度的处理函数
  const onResizeDown = (e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const startWidth = width;
    // 使用防抖/节流，避免频繁 setState 导致性能问题
    const onMouseMove = throttle((moveEvent: MouseEvent) => {
      const newWidth = startWidth + (moveEvent.clientX - startX) * 2;
      // 限制最小和最大宽度，避免超出窗口
      const normalized = Math.min(window.innerWidth - 100, Math.max(DEFAULT_MODAL_WIDTH, newWidth));
      setWidth(normalized);
    }, 17);
    const onMouseUp = () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };

  // 组合的富文本编辑器节点：在侧栏模式下包含标题和缩放手柄
  const TextEditor = (
    <React.Fragment key={state.id}>
      {/* 非模态时在顶部显示标题和展开图标 */}
      {!modalMode && (
        <div className={styles.title}>
          富文本
          <IconLaunch className={styles.launch} onClick={() => setModalMode(true)} />
        </div>
      )}
      {/* 真正的富文本编辑器组件，接收 editor、state 和 dataRef */}
      <RichTextEditor editor={editor} state={state} dataRef={dataRef}></RichTextEditor>
      {/* 右侧拖拽区域，用于调整侧栏宽度 */}
      <div className={styles.resize} onMouseDown={onResizeDown}></div>
    </React.Fragment>
  );

  // 根据 modalMode 切换在模态框中渲染或直接渲染侧栏内容
  return modalMode ? (
    <Modal
      visible={modalMode}
      footer={null}
      focusLock={false}
      className={styles.modal}
      onCancel={() => setModalMode(false)}
      style={{ width }}
      title={<div className={styles.modalTitle}>富文本</div>}
    >
      {TextEditor}
    </Modal>
  ) : (
    TextEditor
  );
};
