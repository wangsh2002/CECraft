import { IconPlus, IconRobot } from "@arco-design/web-react/icon";
import { Input, Button, Message } from "@arco-design/web-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import type { RangeRect, SelectionChangeEvent } from "sketching-core";
import { EDITOR_EVENT } from "sketching-core";
import { cs } from "sketching-utils";

import { useEditor } from "../../hooks/use-editor";
import { NAV_ENUM } from "../header/utils/constant";
import { Image } from "./components/image";
import { Rect } from "./components/rect";
import { Text } from "./components/text";
import styles from "./index.m.scss";

export const RightPanel: FC = () => {
  const { editor } = useEditor();
  const [collapse, setCollapse] = useState(false);
  const [active, setActive] = useState<string[]>([]);
  // 移除不再需要的 range 状态，除非你在其他地方还需要它
  // const [range, setRange] = useState<RangeRect | null>(null);

  useEffect(() => {
    const onSelect = (e: SelectionChangeEvent) => {
      // setRange(e.current ? e.current.rect() : null); // AI 助手替代了坐标显示，此处可移除以减少渲染
      setActive([...editor.selection.getActiveDeltaIds()]);
    };
    editor.event.on(EDITOR_EVENT.SELECTION_CHANGE, onSelect);
    return () => {
      editor.event.off(EDITOR_EVENT.SELECTION_CHANGE, onSelect);
    };
  }, [editor]);

  // 获取当前选中的节点状态
  const getActiveState = () => {
    const id = active.length === 1 && active[0];
    return id ? editor.state.getDeltaState(id) : null;
  };

  const activeState = getActiveState();
  const isTextSelected = activeState?.key === NAV_ENUM.TEXT;

  // 处理 AI 请求的逻辑占位符
  const handleAISubmit = (value: string) => {
    if (!value) return;
    console.log("AI Request:", value);
    // 在此处集成你的 Agent 调用逻辑
    // 例如：callAgent(value, activeState.getAttr('textData'))
    Message.info("AI 正在思考中... (功能待接入)");
  };

  const loadEditor = () => {
    if (!activeState) return null;
    switch (activeState.key) {
      case NAV_ENUM.RECT:
        return <Rect key={activeState.id} editor={editor} state={activeState}></Rect>;
      case NAV_ENUM.TEXT:
        return <Text key={activeState.id} editor={editor} state={activeState}></Text>;
      case NAV_ENUM.IMAGE:
        return <Image key={activeState.id} editor={editor} state={activeState}></Image>;
      default:
        return null;
    }
  };

  return (
    <div className={cs(styles.container, collapse && styles.collapse)}>
      <div className={cs(styles.op)} onClick={() => setCollapse(!collapse)}>
        <IconPlus />
      </div>
      <div className={styles.scroll}>
        {/* AI 助手区域 - 替代了原来的 rect 坐标显示 */}
        <div style={{ padding: '12px', borderBottom: '1px solid var(--color-border-2)' }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px', fontWeight: 500, gap: 6 }}>
            <IconRobot /> AI 助手
          </div>
          {isTextSelected ? (
            <Input.Search
              placeholder="输入指令优化文案..."
              searchButton="发送"
              onSearch={handleAISubmit}
              style={{ width: '100%' }}
            />
          ) : (
            <div style={{ fontSize: '12px', color: 'var(--color-text-3)', background: 'var(--color-fill-2)', padding: '8px', borderRadius: '4px' }}>
              请选中一个文本框以使用 AI 润色或生成功能。
            </div>
          )}
        </div>

        {/* 属性编辑器区域 */}
        {active.length === 0 && <div style={{ padding: 12, color: 'var(--color-text-3)' }}>请选择画布上的元素进行编辑</div>}
        {active.length === 1 && loadEditor()}
      </div>
    </div>
  );
};