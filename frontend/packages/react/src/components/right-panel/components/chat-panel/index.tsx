import React, { useState, useEffect, useRef } from 'react';
import { Input, Button, Message, Spin, Avatar } from "@arco-design/web-react";
import { 
    IconRobot, IconUser, IconExperiment, IconCopy, IconEye, 
    IconCaretDown, IconCaretRight, IconSend 
} from "@arco-design/web-react/icon";
import ReactMarkdown from 'react-markdown';
import { cs, TSON } from "sketching-utils";
import { TEXT_ATTRS } from "sketching-plugin";
import type { RichTextLines } from "sketching-plugin";
import { NAV_ENUM } from "../../../header/utils/constant";
import { AIPreviewModal } from "../ai-preview";
import { ReviewModal, type ReviewResult } from "../review-modal";
import { sketchToTextDelta } from "../text/utils/transform";
import styles from "./index.m.scss";

interface ChatMessage {
    id: string;
    role: 'user' | 'ai';
    content: string;
    previewData?: any;
    timestamp: number;
}

interface ChatPanelProps {
    editor: any;
    activeState: any;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ editor, activeState }) => {
    const [isExpanded, setIsExpanded] = useState(true);
    const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
    const [inputValue, setInputValue] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    
    // Review states
    const [isReviewing, setIsReviewing] = useState(false);
    const [reviewResult, setReviewResult] = useState<ReviewResult | null>(null);
    const [showReviewModal, setShowReviewModal] = useState(false);

    // Preview states
    const [previewData, setPreviewData] = useState<any>(null);
    const [showPreview, setShowPreview] = useState(false);
    const [currentPreviewState, setCurrentPreviewState] = useState<any>(null);

    const scrollRef = useRef<HTMLDivElement>(null);

    const isTextSelected = activeState?.key === NAV_ENUM.TEXT;

    useEffect(() => {
        if (!isTextSelected) {
            setIsExpanded(false);
        } else {
            setIsExpanded(true);
        }
    }, [isTextSelected]);

    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [chatHistory, isExpanded]);

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

    const handleReviewSubmit = async (e: any) => {
        e.stopPropagation();
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

    const handleSendMessage = async () => {
        if (!inputValue.trim() || isLoading) return;
        if (!isTextSelected || !activeState) {
            Message.warning("请先选中一个文本框");
            return;
        }

        const userMsg: ChatMessage = {
            id: Date.now().toString(),
            role: 'user',
            content: inputValue,
            timestamp: Date.now()
        };

        setChatHistory(prev => [...prev, userMsg]);
        setInputValue("");
        setIsLoading(true);
        setIsExpanded(true);

        const contextStr = extractContext();

        try {
            const response = await fetch("http://localhost:8000/api/ai/agent", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ 
                    prompt: userMsg.content, 
                    context: contextStr 
                }),
            });

            if (!response.ok) throw new Error(`Status ${response.status}`);

            const result = await response.json();
            
            const aiMsg: ChatMessage = {
                id: (Date.now() + 1).toString(),
                role: 'ai',
                content: result.reply,
                previewData: (result.intention === "modify" && result.modified_data) ? result.modified_data : undefined,
                timestamp: Date.now()
            };

            setChatHistory(prev => [...prev, aiMsg]);

        } catch (error) {
            console.error('AI Request failed:', error);
            Message.error('AI 请求失败');
            setChatHistory(prev => [...prev, {
                id: Date.now().toString(),
                role: 'ai',
                content: "服务暂时不可用，请稍后再试。",
                timestamp: Date.now()
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handlePreview = (data: any) => {
        setPreviewData(data);
        setCurrentPreviewState(activeState);
        setShowPreview(true);
    };

    const toggleExpand = () => {
        if (!isTextSelected) {
            Message.info("请先选中简历中的文本框");
            return;
        }
        setIsExpanded(!isExpanded);
    };

    return (
        <div className={styles.container}>
            <div className={styles.header} onClick={toggleExpand}>
                <div className={styles.title}>
                    {isExpanded ? <IconCaretDown /> : <IconCaretRight />}
                    <IconRobot style={{ color: '#165DFF' }} /> 
                    简历智能助手
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

            {isExpanded && (
                <div className={styles.content}>
                    <div className={styles.chatList} ref={scrollRef}>
                        {chatHistory.length === 0 ? (
                            <div className={styles.emptyState}>
                                💡 选中简历中的文本框，即可让 AI 帮你润色内容或进行诊断。
                            </div>
                        ) : (
                            chatHistory.map(msg => (
                                <div key={msg.id} className={cs(styles.message, styles[msg.role])}>
                                    <div className={styles.avatar}>
                                        {msg.role === 'ai' ? 
                                            <Avatar size={24} style={{ backgroundColor: '#165DFF' }}><IconRobot /></Avatar> : 
                                            <Avatar size={24} style={{ backgroundColor: '#FF7D00' }}><IconUser /></Avatar>
                                        }
                                    </div>
                                    <div className={styles.bubble}>
                                        {msg.role === 'ai' ? (
                                            <div className={styles.markdown}>
                                                <ReactMarkdown>{msg.content}</ReactMarkdown>
                                            </div>
                                        ) : (
                                            <pre>{msg.content}</pre>
                                        )}
                                        {msg.role === 'ai' && (
                                            <div className={styles.actions}>
                                                {msg.previewData && (
                                                    <Button 
                                                        type="primary" 
                                                        size="mini" 
                                                        status="warning"
                                                        icon={<IconEye />} 
                                                        onClick={() => handlePreview(msg.previewData)}
                                                    >
                                                        预览
                                                    </Button>
                                                )}
                                                <Button 
                                                    type="text" 
                                                    size="mini" 
                                                    icon={<IconCopy />} 
                                                    onClick={() => {
                                                        navigator.clipboard.writeText(msg.content);
                                                        Message.success("已复制");
                                                    }}
                                                />
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}
                        {isLoading && (
                             <div className={cs(styles.message, styles.ai)}>
                                <div className={styles.avatar}>
                                    <Avatar size={24} style={{ backgroundColor: '#165DFF' }}><IconRobot /></Avatar>
                                </div>
                                <div className={styles.bubble}>
                                    <Spin dot />
                                </div>
                             </div>
                        )}
                    </div>
                    
                    <div className={styles.inputArea}>
                        <Input.Search
                            placeholder={isTextSelected ? "输入修改需求..." : "请先选中文本框"}
                            value={inputValue}
                            onChange={setInputValue}
                            onSearch={handleSendMessage}
                            searchButton={isLoading ? <Spin size={14} /> : <IconSend />}
                            disabled={isLoading || isReviewing || !isTextSelected}
                        />
                    </div>
                </div>
            )}

            {showPreview && currentPreviewState && (
                <AIPreviewModal 
                    visible={showPreview}
                    onCancel={() => setShowPreview(false)}
                    onApply={() => {
                        setShowPreview(false);
                        setPreviewData(null);
                    }}
                    originalState={currentPreviewState}
                    editor={editor}
                    modifiedData={previewData}
                />
            )}

            <ReviewModal 
                visible={showReviewModal}
                onClose={() => setShowReviewModal(false)}
                result={reviewResult}
            />
        </div>
    );
};
