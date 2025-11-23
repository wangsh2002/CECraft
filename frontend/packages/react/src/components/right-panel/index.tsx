import { IconPlus, IconRobot, IconClose, IconCopy, IconEye } from "@arco-design/web-react/icon";
import { Input, Button, Message, Spin, Tag } from "@arco-design/web-react";
import type { FC } from "react";
import { useEffect, useState, useRef } from "react";
import type { SelectionChangeEvent } from "sketching-core";
import { EDITOR_EVENT } from "sketching-core";
import { cs, TSON } from "sketching-utils"; // 确保引入 TSON
import { TEXT_ATTRS } from "sketching-plugin";
import type { RichTextLines } from "sketching-plugin"; // [新增] 引入类型
import { Op, OP_TYPE } from "sketching-delta";
import { Delta as BlockDelta } from "@block-kit/delta";

import { useEditor } from "../../hooks/use-editor";
import { NAV_ENUM } from "../header/utils/constant";
import { Image } from "./components/image";
import { Rect } from "./components/rect";
import { Text } from "./components/text";
import { AIPreviewModal } from "./components/ai-preview";
// [新增] 引入 sketchToTextDelta (用于发送前转换) 和 textDeltaToSketch (用于接收后转换)
import { sketchToTextDelta, textDeltaToSketch } from "./components/text/utils/transform"; 
import styles from "./index.m.scss";

export const RightPanel: FC = () => {
  const { editor } = useEditor();
  const [collapse, setCollapse] = useState(false);
  const [active, setActive] = useState<string[]>([]);
  
  // AI 状态
  const [aiResponse, setAiResponse] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  // 修改预览状态
  const [previewData, setPreviewData] = useState<any>(null);
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

    // ============ [核心修复] ============
    // 1. 获取原始 Sketch 数据 (JSON 字符串)
    const rawSketchData = activeState.getAttr(TEXT_ATTRS.DATA);
    let contextStr = "";

    try {
        if (rawSketchData) {
            // 2. 解析为 RichTextLines 对象
            const lines = TSON.parse<RichTextLines>(rawSketchData);
            if (lines) {
                // 3. 转换为标准 Delta 格式 (这一步会自动合并相邻的相同属性字符，如 'A','n','t' -> 'Ant')
                const delta = sketchToTextDelta(lines);
                // 4. 序列化 Delta 发送给后端
                contextStr = JSON.stringify(delta);
            } else {
                contextStr = typeof rawSketchData === 'object' ? JSON.stringify(rawSketchData) : rawSketchData;
            }
        }
    } catch (e) {
        console.error("Context conversion failed:", e);
        contextStr = typeof rawSketchData === 'object' ? JSON.stringify(rawSketchData) : rawSketchData;
    }
    // ====================================

    try {
      const response = await fetch("http://localhost:8000/api/ai/agent", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ 
            prompt: value, 
            context: contextStr 
        }),
      });

      if (!response.ok) {
        throw new Error(`Status ${response.status}`);
      }

      const result = await response.json();
      
      setAiResponse(result.reply);

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
    // 这里其实会被 AIPreviewModal 的 onApply 接管，
    // 但保留此函数作为备用或非预览模式下的逻辑
    if (activeState && previewData) {
      try {
        let sourceData = previewData;
        if (typeof previewData === "string") {
          sourceData = JSON.parse(previewData);
        }

        if (sourceData && Array.isArray(sourceData.ops)) {
          const blockDelta = new BlockDelta(sourceData.ops);
          const sketchData = textDeltaToSketch(blockDelta);
          const payload = TSON.stringify(sketchData);

          editor.state.apply(new Op(OP_TYPE.REVISE, { 
              id: activeState.id, 
              attrs: { [TEXT_ATTRS.DATA]: payload } 
          }));
          
          Message.success("修改已应用");
          setShowPreview(false);
          setPreviewData(null);
        }
      } catch (e) {
        console.error("Apply Error:", e);
      }
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

        {/* 属性编辑器区域 */}
        {active.length === 0 && <div style={{ padding: 12, color: 'var(--color-text-3)' }}>请选择画布上的元素进行编辑</div>}
        {active.length === 1 && loadEditor()}

        {/* 修改预览弹窗 */}
        {showPreview && activeState && (
            <AIPreviewModal 
                visible={showPreview}
                onCancel={() => setShowPreview(false)}
                // 注意：这里我们让 AIPreviewModal 内部处理应用逻辑（因为涉及到 Diff 清洗），
                // 这里的 onApply 只是用来关闭弹窗的回调
                onApply={() => {
                    setShowPreview(false);
                    setPreviewData(null);
                }}
                originalState={activeState}
                editor={editor}
                modifiedData={previewData}
            />
        )}
      </div>
    </div>
  );
};