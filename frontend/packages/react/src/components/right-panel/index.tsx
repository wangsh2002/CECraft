import { IconPlus, IconRobot, IconClose, IconCopy, IconEye } from "@arco-design/web-react/icon";
import { Input, Button, Message, Spin, Tag } from "@arco-design/web-react";
import type { FC } from "react";
import { useEffect, useState, useRef } from "react";
import type { SelectionChangeEvent } from "sketching-core";
import { EDITOR_EVENT } from "sketching-core";
import { cs } from "sketching-utils";
import { TEXT_ATTRS } from "sketching-plugin";
import { Op, OP_TYPE } from "sketching-delta";

import { useEditor } from "../../hooks/use-editor";
import { NAV_ENUM } from "../header/utils/constant";
import { Image } from "./components/image";
import { Rect } from "./components/rect";
import { Text } from "./components/text";
import { AIPreviewModal } from "./components/ai-preview"; // 引入预览组件
import styles from "./index.m.scss";

export const RightPanel: FC = () => {
  const { editor } = useEditor();
  const [collapse, setCollapse] = useState(false);
  const [active, setActive] = useState<string[]>([]);
  
  // AI 状态
  const [aiResponse, setAiResponse] = useState("");
  const [isLoading, setIsLoading] = useState(false); // 替换 isStreaming，改为整体加载状态
  
  // 修改预览状态
  const [previewData, setPreviewData] = useState<any>(null); // 存储后端返回的 delta json
  const [showPreview, setShowPreview] = useState(false);

  useEffect(() => {
    const onSelect = (e: SelectionChangeEvent) => {
      setActive([...editor.selection.getActiveDeltaIds()]);
      // 切换选中项时，重置状态
      if (e.previous !== e.current) {
        setAiResponse("");
        setPreviewData(null);
        setShowPreview(false);
      }
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
  const isTextSelected = activeState?.key === NAV_ENUM.TEXT;

  // 处理 AI 请求 (Agent 模式)
  const handleAISubmit = async (value: string) => {
    if (!value || isLoading) return;
    if (!isTextSelected || !activeState) {
      Message.warning("请先选中一个文本框");
      return;
    }

    setIsLoading(true);
    setAiResponse("");
    setPreviewData(null);

    // 1. 获取带有 Delta 格式的原始 JSON 数据 (不再是纯文本)
    // 这样 Agent 才能理解结构并返回正确的格式
    const rawDeltaData = activeState.getAttr(TEXT_ATTRS.DATA);
    
    // 如果是字符串对象，保证传给后端的是字符串
    const contextStr = typeof rawDeltaData === 'object' ? JSON.stringify(rawDeltaData) : rawDeltaData;

    try {
      const response = await fetch("http://localhost:8000/api/ai/agent", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ 
            prompt: value, 
            context: contextStr || "{}" // 兜底
        }),
      });

      if (!response.ok) {
        throw new Error(`Status ${response.status}`);
      }

      const result = await response.json();
      
      // 2. 处理 Agent 返回结果
      setAiResponse(result.reply);

      // 3. 意图识别处理
      if (result.intention === "modify" && result.modified_data) {
          setPreviewData(result.modified_data);
          Message.info("AI 已生成修改建议，请点击预览查看");
      }

    } catch (error) {
      console.error('AI Request failed:', error);
      Message.error('AI 请求失败，请检查后端服务');
      setAiResponse("服务暂时不可用，请稍后再试。");
    } finally {
      setIsLoading(false);
    }
  };

  // 应用修改到画布
  const handleApplyModification = () => {
    if (activeState && previewData) {
        // 将预览数据应用到当前节点
        // 注意：这里假设 previewData 是符合 TEXT_ATTRS.DATA 结构的 (即 { chars: ... } 或 Delta)
        // 后端 Agent 需要严格控制输出格式
        const payload = typeof previewData === 'string' ? previewData : JSON.stringify(previewData);
        
        editor.state.apply(new Op(OP_TYPE.REVISE, { 
            id: activeState.id, 
            attrs: { [TEXT_ATTRS.DATA]: payload } 
        }));
        
        Message.success("修改已应用");
        setShowPreview(false);
        setPreviewData(null);
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
            <IconRobot style={{ color: '#165DFF' }} /> 简历智能助手
          </div>

          {/* 输入框区域 */}
          {isTextSelected ? (
            <Input.Search
              placeholder="例如：把这段经历改得更专业..."
              searchButton={isLoading ? <Spin size={14} /> : "发送"}
              onSearch={handleAISubmit}
              disabled={isLoading}
              style={{ width: '100%', marginBottom: '12px' }}
            />
          ) : (
            <div style={{ fontSize: '12px', color: 'var(--color-text-3)', background: 'var(--color-fill-2)', padding: '8px', borderRadius: '4px' }}>
              💡 选中简历中的文本框，即可让 AI 帮你润色内容。
            </div>
          )}

          {/* 回复展示区域 */}
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
                <div style={{ fontWeight: 'bold', marginBottom: '4px', fontSize: '12px', color: 'var(--color-text-3)' }}>AI 回复:</div>
                <div style={{ whiteSpace: 'pre-wrap' }}>{aiResponse}</div>
                
                <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
                    {/* 如果有修改数据，显示预览按钮 */}
                    {previewData && (
                        <Button 
                            type="primary" 
                            size="mini" 
                            status="warning"
                            icon={<IconEye />} 
                            onClick={() => setShowPreview(true)}
                        >
                            预览修改
                        </Button>
                    )}
                    
                    {!isLoading && (
                        <Button type="text" size="mini" icon={<IconCopy />} onClick={() => {
                            navigator.clipboard.writeText(aiResponse);
                            Message.success("已复制到剪贴板");
                        }}>复制</Button>
                    )}
                </div>
            </div>
          )}
        </div>

        {/* 属性编辑器区域 (保留) */}
        {active.length === 0 && <div style={{ padding: 12, color: 'var(--color-text-3)' }}>请选择画布上的元素进行编辑</div>}
        {active.length === 1 && loadEditor()}

        {/* 修改预览弹窗 */}
        {showPreview && activeState && (
            <AIPreviewModal 
                visible={showPreview}
                onCancel={() => setShowPreview(false)}
                onApply={handleApplyModification}
                originalState={activeState}
                editor={editor}
                modifiedData={previewData}
            />
        )}
      </div>
    </div>
  );
};