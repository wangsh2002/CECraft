import { IconPlus, IconRobot, IconClose, IconCopy } from "@arco-design/web-react/icon";
import { Input, Button, Message, Spin } from "@arco-design/web-react";
import type { FC } from "react";
import { useEffect, useState, useRef } from "react";
import type { SelectionChangeEvent } from "sketching-core";
import { EDITOR_EVENT } from "sketching-core";
import { cs } from "sketching-utils";
import { TEXT_ATTRS } from "sketching-plugin";

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
  // AI 状态
  const [aiResponse, setAiResponse] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const aiAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const onSelect = (e: SelectionChangeEvent) => {
      setActive([...editor.selection.getActiveDeltaIds()]);
      // 切换选中项时，清空之前的 AI 对话，避免混淆
      if (e.previous !== e.current) {
        setAiResponse("");
      }
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

  // [核心逻辑] 处理 AI 请求
  const handleAISubmit = async (value: string) => {
    if (!value || isStreaming) return;
    if (!isTextSelected || !activeState) {
      Message.warning("请先选中一个文本框");
      return;
    }

    setIsStreaming(true);
    setAiResponse("");
    aiAbortRef.current = new AbortController();

    // 1. 获取上下文
    const rawTextData = activeState.getAttr(TEXT_ATTRS.DATA) || "";
    let contextContent = "";
    try {
      const parsed = typeof rawTextData === 'string' ? JSON.parse(rawTextData) : rawTextData;
      contextContent = JSON.stringify(parsed);
    } catch (e) {
      contextContent = String(rawTextData);
    }

    try {
      const response = await fetch("http://localhost:8000/api/ai/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt: value, context: contextContent }),
        signal: aiAbortRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`Status ${response.status}`);
      }

      if (!response.body) throw new Error("ReadableStream not supported");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        setAiResponse((prev) => prev + chunk);
      }
    } catch (error) {
      if ((error as any).name === 'AbortError') {
        Message.info('已取消 AI 请求');
      } else {
        console.error('AI Request failed:', error);
        Message.error('AI 请求失败，请检查后端服务');
      }
    } finally {
      setIsStreaming(false);
      aiAbortRef.current = null;
    }
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
        {/* AI 助手区域 */}
        <div style={{ padding: '12px', borderBottom: '1px solid var(--color-border-2)', background: 'var(--color-bg-2)' }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px', fontWeight: 600, gap: 6, color: 'var(--color-text-1)' }}>
            <IconRobot style={{ color: '#165DFF' }} /> 简历优化助手
          </div>

          {/* 输入框区域 */}
          {isTextSelected ? (
            <Input.Search
              placeholder="例如：让这段经历更专业..."
              searchButton={isStreaming ? <Spin size={14} /> : "发送"}
              onSearch={handleAISubmit}
              disabled={isStreaming}
              style={{ width: '100%', marginBottom: '12px' }}
            />
          ) : (
            <div style={{ fontSize: '12px', color: 'var(--color-text-3)', background: 'var(--color-fill-2)', padding: '8px', borderRadius: '4px' }}>
              💡 选中简历中的文本框，即可让 AI 帮你润色内容。
            </div>
          )}

          {/* 流式回复展示区域 */}
          {aiResponse && (
            <div style={{ 
                background: 'var(--color-fill-2)', 
                padding: '10px', 
                borderRadius: '4px', 
                fontSize: '13px',
                lineHeight: '1.5',
                color: 'var(--color-text-2)',
                position: 'relative',
                border: '1px solid var(--color-border-2)'
            }}>
                <div style={{ fontWeight: 'bold', marginBottom: '4px', fontSize: '12px', color: 'var(--color-text-3)' }}>AI 建议:</div>
                <div style={{ whiteSpace: 'pre-wrap' }}>{aiResponse}</div>
                
                {!isStreaming && (
                    <div style={{ marginTop: 8, textAlign: 'right' }}>
                        <Button type="text" size="mini" icon={<IconCopy />} onClick={() => {
                            navigator.clipboard.writeText(aiResponse);
                            Message.success("已复制到剪贴板");
                        }}>复制</Button>
                    </div>
                )}
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