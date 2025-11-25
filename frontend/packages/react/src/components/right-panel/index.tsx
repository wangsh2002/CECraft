import { 
  IconPlus, IconRobot, IconCopy, IconEye, 
  IconExperiment, IconCheckCircle, IconCloseCircle, IconBulb // [新增] 图标
} from "@arco-design/web-react/icon";
import { 
  Input, Button, Message, Spin, Tag, 
  Modal, Statistic, Typography, List, Divider // [新增] UI组件
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
import { sketchToTextDelta, textDeltaToSketch } from "./components/text/utils/transform"; 
import styles from "./index.m.scss";

// [新增] 诊断结果类型定义
interface ReviewResult {
  score: number;
  summary: string;
  pros: string[];
  cons: string[];
  suggestions: string[];
}

export const RightPanel: FC = () => {
  const { editor } = useEditor();
  const [collapse, setCollapse] = useState(false);
  const [active, setActive] = useState<string[]>([]);
  
  // AI 修改状态
  const [aiResponse, setAiResponse] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [showPreview, setShowPreview] = useState(false);

  // [新增] 诊断状态
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

  // [重构] 提取公共逻辑：获取当前选中内容的 Context
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

  //  处理诊断请求
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

  // 处理 AI 修改请求 (逻辑已简化，复用 extractContext)
  const handleAISubmit = async (value: string) => {
    if (!value || isLoading) return;
    if (!isTextSelected || !activeState) {
      Message.warning("请先选中一个文本框");
      return;
    }

    setIsLoading(true);
    setAiResponse("");
    setPreviewData(null);

    // [调用] 使用提取好的函数
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

  // 应用修改逻辑 (保留)
  const handleApplyModification = () => {
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
            {/* [新增] 只有选中文本时显示诊断按钮 */}
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

        {/* [新增] 诊断结果弹窗 */}
        <Modal
          title={
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <IconExperiment style={{ color: '#165DFF' }} /> 简历诊断报告
            </div>
          }
          visible={showReviewModal}
          onOk={() => setShowReviewModal(false)}
          onCancel={() => setShowReviewModal(false)}
          hideCancel
          okText="我知道了"
          style={{ width: 600 }}
        >
          {reviewResult && (
            <div>
              {/* 分数和总评 */}
              <div style={{ display: 'flex', gap: 24, marginBottom: 24, alignItems: 'center' }}>
                <Statistic 
                  title="AI 评分" 
                  value={reviewResult.score} 
                  style={{ minWidth: 100 }}
                  valueStyle={{ color: reviewResult.score > 80 ? '#00B42A' : '#FF7D00', fontWeight: 'bold' }} 
                />
                <div style={{ flex: 1, background: 'var(--color-fill-2)', padding: 12, borderRadius: 4, fontSize: 13, color: 'var(--color-text-2)' }}>
                  <strong>综合点评：</strong>{reviewResult.summary}
                </div>
              </div>

              <Divider />

              {/* 详细列表 */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div>
                  <Typography.Title heading={6} style={{ margin: '0 0 8px 0', color: '#00B42A' }}>
                    <IconCheckCircle /> 亮点 (Pros)
                  </Typography.Title>
                  {reviewResult.pros.map((item, idx) => (
                    <Tag key={idx} color="green" style={{ margin: '0 8px 8px 0' }}>{item}</Tag>
                  ))}
                </div>

                <div>
                  <Typography.Title heading={6} style={{ margin: '0 0 8px 0', color: '#F53F3F' }}>
                    <IconCloseCircle /> 不足 (Cons)
                  </Typography.Title>
                  <List
                    size="small"
                    dataSource={reviewResult.cons}
                    render={(item, index) => <List.Item key={index} style={{ padding: '4px 0' }}>• {item}</List.Item>}
                    border={false}
                  />
                </div>

                <div style={{ background: '#E8FFEA', padding: 12, borderRadius: 8, border: '1px dashed #00B42A' }}>
                  <Typography.Title heading={6} style={{ margin: '0 0 8px 0', color: '#009A29' }}>
                    <IconBulb /> 优化建议
                  </Typography.Title>
                  <List
                    size="small"
                    dataSource={reviewResult.suggestions}
                    render={(item, index) => (
                      <List.Item key={index} style={{ padding: '4px 0', color: '#005E19' }}>
                         {index + 1}. {item}
                      </List.Item>
                    )}
                    border={false}
                  />
                </div>
              </div>
            </div>
          )}
        </Modal>
      </div>
    </div>
  );
};