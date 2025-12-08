import { IconPlus } from "@arco-design/web-react/icon";
import type { FC } from "react";
import { useEffect, useState, useRef } from "react";
import type { SelectionChangeEvent } from "sketching-core";
import { EDITOR_EVENT } from "sketching-core";
import { cs } from "sketching-utils"; 

import { useEditor } from "../../hooks/use-editor";
import { NAV_ENUM } from "../header/utils/constant";
import { Image } from "./components/image";
import { Rect } from "./components/rect";
import { Text } from "./components/text";
import { ChatPanel } from "./components/chat-panel";
import styles from "./index.m.scss";

export const RightPanel: FC = () => {
  const { editor } = useEditor();
  const [collapse, setCollapse] = useState(false);
  const [active, setActive] = useState<string[]>([]);
  
  // Resizing logic
  const [width, setWidth] = useState(300);
  const [isResizingState, setIsResizingState] = useState(false); // State for UI render
  const isResizing = useRef(false); // Ref for event logic
  const startX = useRef(0);
  const startWidth = useRef(0);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return;
      const deltaX = startX.current - e.clientX; // Dragging left increases width
      const newWidth = Math.max(200, Math.min(800, startWidth.current + deltaX));
      setWidth(newWidth);
    };

    const onMouseUp = () => {
      if (isResizing.current) {
        isResizing.current = false;
        setIsResizingState(false);
        document.body.style.cursor = 'default';
      }
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);

    return () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  const handleMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    setIsResizingState(true);
    startX.current = e.clientX;
    startWidth.current = width;
    document.body.style.cursor = 'col-resize';
  };
  
  useEffect(() => {
    const onSelect = (e: SelectionChangeEvent) => {
      setActive([...editor.selection.getActiveDeltaIds()]);
    };
    editor.event.on(EDITOR_EVENT.SELECTION_CHANGE, onSelect);
    return () => {
      editor.event.off(EDITOR_EVENT.SELECTION_CHANGE, onSelect);
    };
  }, [editor]);

  const getActiveState = () => {
    const id = active.length === 1 && active[0];
    return id ? editor.state.getDeltaState(id) : null;
  };

  const activeState = getActiveState();

  const loadEditor = () => {
    if (!activeState) return null;
    switch (activeState.key) {
      case NAV_ENUM.RECT: return <Rect key={activeState.id} editor={editor} state={activeState}></Rect>;
      case NAV_ENUM.TEXT: return <Text key={activeState.id} editor={editor} state={activeState}></Text>;
      case NAV_ENUM.IMAGE: return <Image key={activeState.id} editor={editor} state={activeState}></Image>;
      default: return null;
    }
  };

  return (
    <div 
      className={cs(styles.container, collapse && styles.collapse)}
      style={!collapse ? { width: width } : {}}
    >
      <div 
        className={cs(styles.resizeHandle, isResizingState && styles.resizing)}
        onMouseDown={handleMouseDown}
      />
      <div className={cs(styles.op)} onClick={() => setCollapse(!collapse)}>
        <IconPlus />
      </div>
      <div className={styles.scroll}>
        {/* AI 助手区域 */}
        <ChatPanel editor={editor} activeState={activeState} />

        {/* 属性编辑器区域 */}
        {active.length === 0 && <div style={{ padding: 12, color: 'var(--color-text-3)' }}>请选择画布上的元素进行编辑</div>}
        {active.length === 1 && loadEditor()}
      </div>
    </div>
  );
};