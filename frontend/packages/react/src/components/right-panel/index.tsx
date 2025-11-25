import { 
  IconPlus, IconRobot, IconCopy, IconEye, 
  IconExperiment // [修改] 移除了 IconCheckCircle, IconCloseCircle, IconBulb
} from "@arco-design/web-react/icon";
import { 
  Input, Button, Message, Spin // [修改] 移除了 Modal, Statistic, Typography, List, Divider, Tag
} from "@arco-design/web-react";
import type { FC } from "react";
import { useEffect, useState } from "react";
import type { SelectionChangeEvent } from "sketching-core";
import { EDITOR_EVENT } from "sketching-core";
import { cs, TSON } from "sketching-utils"; 
import { TEXT_ATTRS } from "sketching-plugin";
import type { RichTextLines } from "sketching-plugin"; 
import { Op, OP_TYPE } from "sketching-delta";
import { Delta as BlockDelta } from "@block-kit/delta";

import { useEditor } from "../../hooks/use-editor";
import { NAV_ENUM } from "../header/utils/constant";
import { Image } from "./components/image";
import { Rect } from "./components/rect";
import { Text } from "./components/text";
import { AIPreviewModal } from "./components/ai-preview";
// [新增] 引入新拆分的组件
import { ReviewModal, type ReviewResult } from "./components/review-modal";
import { sketchToTextDelta, textDeltaToSketch } from "./components/text/utils/transform"; 
import styles from "./index.m.scss";

// [修改] ReviewResult 接口定义已移除，改从 import 导入

export const RightPanel: FC = () => {
  const { editor } = useEditor();
  const [collapse, setCollapse] = useState(false);
  const [active, setActive] = useState<string[]>([]);
  
  // AI 修改状态
  const [aiResponse, setAiResponse] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [showPreview, setShowPreview] = useState(false);

  // [修改] 诊断状态使用导入的 ReviewResult 类型
  const [isReviewing, setIsReviewing] = useState(false);
  const [reviewResult, setReviewResult] = useState<ReviewResult | null>(null);
  const [showReviewModal, setShowReviewModal] = useState(false);

  useEffect(() => {
    const onSelect = (e: SelectionChangeEvent) => {
      setActive([...editor.selection.getActiveDeltaIds()]);
      // 切换选中项时，重置所有状态
      if (e.previous !== e.current) {
        setAiResponse("");
        setPreviewData(null);
        setShowPreview(false);
        setReviewResult(null); // 重置诊断结果
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

  // 提取公共逻辑：获取当前选中内容的 Context
  const extractContext = (): string => {
    if (!activeState) return "";
    const rawSketchData = activeState.getAttr(TEXT_ATTRS.DATA);
    
    try {
      if (rawSketchData) {
        const lines = TSON.parse<RichTextLines>(rawSketchData);
        if (lines) {
          const delta = sketchToTextDelta(lines);
          return JSON.stringify(delta);
        }
        return typeof rawSketchData === 'object' ? JSON.stringify(rawSketchData) : rawSketchData;
      }
    } catch (e) {
      console.error("Context conversion failed:", e);
      return typeof rawSketchData === 'object' ? JSON.stringify(rawSketchData) : rawSketchData;
    }
    return "";
  };

  // 处理诊断请求
  const handleReviewSubmit = async () => {
    if (isReviewing) return;
    if (!isTextSelected || !activeState) {
      Message.warning("请先选中一段简历内容（文本框）");
      return;
    }

    setIsReviewing(true);
    try {
      const contextStr = extractContext();
      
      const response = await fetch("http://localhost:8000/api/ai/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume_content: contextStr }),
      });

      if (!response.ok) throw new Error(`Status ${response.status}`);

      const result: ReviewResult = await response.json();
      setReviewResult(result);
      setShowReviewModal(true);
      Message.success("诊断完成！");

    } catch (error) {
      console.error('Review Request failed:', error);
      Message.error('诊断服务暂时不可用');
    } finally {
      setIsReviewing(false);
    }
  };

  // 处理 AI 修改请求
  const handleAISubmit = async (value: string) => {
    if (!value || isLoading) return;
    if (!isTextSelected || !activeState) {
      Message.warning("请先选中一个文本框");
      return;
    }

    setIsLoading(true);
    setAiResponse("");
    setPreviewData(null);

    const contextStr = extractContext();

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
    <div className={cs(styles.container, collapse && styles.collapse)}>
      <div className={cs(styles.op)} onClick={() => setCollapse(!collapse)}>
        <IconPlus />
      </div>
      <div className={styles.scroll}>
        {/* AI 助手区域 */}
        <div style={{ padding: '12px', borderBottom: '1px solid var(--color-border-2)', background: 'var(--color-bg-2)' }}>
          {/* 标题栏 & 诊断按钮 */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', fontWeight: 600, gap: 6, color: 'var(--color-text-1)' }}>
              <IconRobot style={{ color: '#165DFF' }} /> 简历智能助手
            </div>
            {isTextSelected && (
               <Button 
                 size="mini" 
                 type="secondary" 
                 icon={isReviewing ? <Spin /> : <IconExperiment />}
                 onClick={handleReviewSubmit}
                 disabled={isReviewing || isLoading}
               >
                 AI 诊断
               </Button>
            )}
          </div>

          {isTextSelected ? (
            <Input.Search
              placeholder="例如：把这段经历改得更专业..."
              searchButton={isLoading ? <Spin size={14} /> : "发送"}
              onSearch={handleAISubmit}
              disabled={isLoading || isReviewing}
              style={{ width: '100%', marginBottom: '12px' }}
            />
          ) : (
            <div style={{ fontSize: '12px', color: 'var(--color-text-3)', background: 'var(--color-fill-2)', padding: '8px', borderRadius: '4px' }}>
              💡 选中简历中的文本框，即可让 AI 帮你润色内容或进行诊断。
            </div>
          )}

          {/* AI 回复显示区域 */}
          {aiResponse && (
            <div style={{ 
                background: 'var(--color-fill-2)', 
                padding: '10px', 
                borderRadius: '4px', 
                fontSize: '13px',
                lineHeight: '1.5',
                color: 'var(--color-text-2)',
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
                onApply={() => {
                    setShowPreview(false);
                    setPreviewData(null);
                }}
                originalState={activeState}
                editor={editor}
                modifiedData={previewData}
            />
        )}

        {/* [新增] 替换为拆分后的诊断结果弹窗组件 */}
        <ReviewModal 
          visible={showReviewModal}
          onClose={() => setShowReviewModal(false)}
          result={reviewResult}
        />
      </div>
    </div>
  );
};