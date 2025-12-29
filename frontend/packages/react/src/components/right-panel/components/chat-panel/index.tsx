import React, { useState, useEffect, useRef } from 'react';
import { Input, Button, Message, Spin, Avatar, Checkbox, Tooltip } from "@arco-design/web-react";
import { 
    IconRobot, IconUser, IconExperiment, IconCopy, IconEye, 
    IconCaretDown, IconCaretRight, IconSend, IconMessage, IconQuestionCircle
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
import { api } from "../../../../utils/api";
import { useAuth } from "../../../../hooks/use-auth";
import { AuthModal } from "../../../auth";

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
    const [useContext, setUseContext] = useState(true);
    
    // Review states
    const [isReviewing, setIsReviewing] = useState(false);
    const [reviewResult, setReviewResult] = useState<ReviewResult | null>(null);
    const [showReviewModal, setShowReviewModal] = useState(false);

    // Preview states
    const [previewData, setPreviewData] = useState<any>(null);
    const [showPreview, setShowPreview] = useState(false);
    const [currentPreviewState, setCurrentPreviewState] = useState<any>(null);

    // Auth states
    const { user } = useAuth();
    const [authVisible, setAuthVisible] = useState(false);

    const scrollRef = useRef<HTMLDivElement>(null);

    const isTextSelected = activeState?.key === NAV_ENUM.TEXT;

    // 移除自动收起的逻辑，允许用户手动控制
    // useEffect(() => {
    //     if (!isTextSelected) {
    //         setIsExpanded(false);
    //     } else {
    //         setIsExpanded(true);
    //     }
    // }, [isTextSelected]);

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
        if (!user) {
            setAuthVisible(true);
            return;
        }
        if (!isTextSelected || !activeState) {
            Message.warning("请先选中一段简历内容（文本框）");
            return;
        }

        setIsReviewing(true);
        try {
            const contextStr = extractContext();
            const response = await api.post("/ai/review", { resume_content: contextStr });

            const result: ReviewResult = response.data;
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
        if (!user) {
            setAuthVisible(true);
            return;
        }
        // 移除强制选中检查，允许纯闲聊
        // if (!isTextSelected || !activeState) { ... }

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

        // 只有在选中了文本且用户勾选了“引用”时，才发送 context
        const shouldSendContext = isTextSelected && useContext;
        const contextStr = shouldSendContext ? extractContext() : "";
        
        let blockSize = null;
        if (shouldSendContext && activeState && typeof activeState.toRange === 'function') {
            try {
                const range = activeState.toRange();
                if (range) {
                    const width = Math.abs(range.end.x - range.start.x);
                    const height = Math.abs(range.end.y - range.start.y);
                    blockSize = { width, height };
                }
            } catch (e) {
                console.warn("Failed to get block size:", e);
            }
        }

        // Placeholder for AI response
        const aiMsgId = (Date.now() + 1).toString();
        setChatHistory(prev => [...prev, {
            id: aiMsgId,
            role: 'ai',
            content: "正在思考...",
            timestamp: Date.now()
        }]);

        try {
            const token = localStorage.getItem("token");
            const baseURL = api.defaults.baseURL || `${window.location.protocol}//${window.location.hostname}:8000/api`;
            
            const response = await fetch(`${baseURL}/ai/agent`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': token ? `Bearer ${token}` : ''
                },
                body: JSON.stringify({ 
                    prompt: userMsg.content, 
                    context: contextStr,
                    block_size: blockSize
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const reader = response.body?.getReader();
            const decoder = new TextDecoder();
            
            if (!reader) throw new Error("No reader available");

            let buffer = "";
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || ""; 
                
                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const event = JSON.parse(line);
                        if (event.type === 'status') {
                            setChatHistory(prev => prev.map(msg => 
                                msg.id === aiMsgId ? { ...msg, content: `🔄 ${event.content}` } : msg
                            ));
                        } else if (event.type === 'result') {
                            const result = event.data;
                            setChatHistory(prev => prev.map(msg => 
                                msg.id === aiMsgId ? { 
                                    ...msg, 
                                    content: result.reply,
                                    previewData: (result.intention === "modify" && result.modified_data) ? result.modified_data : undefined
                                } : msg
                            ));
                        } else if (event.type === 'error') {
                             console.error("Stream error:", event.content);
                        }
                    } catch (e) {
                        console.error("Parse error", e);
                    }
                }
            }

        } catch (error) {
            console.error('AI Request failed:', error);
            Message.error('AI 请求失败');
            setChatHistory(prev => prev.map(msg => 
                msg.id === aiMsgId ? { ...msg, content: "服务暂时不可用，请稍后再试。" } : msg
            ));
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
        // 移除强制选中检查
        // if (!isTextSelected) {
        //     Message.info("请先选中简历中的文本框");
        //     return;
        // }
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
                                                {msg.content.startsWith('🔄') ? (
                                                    <div className={styles.thinking}>
                                                        <Spin size={12} />
                                                        <span className={styles.thinkingText}>
                                                            {msg.content.replace('🔄', '').trim()}
                                                        </span>
                                                    </div>
                                                ) : (
                                                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                                                )}
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
                    </div>
                    
                    <div className={styles.inputArea}>
                        {isTextSelected && (
                            <div className={styles.options}>
                                <Checkbox checked={useContext} onChange={setUseContext}>
                                    引用选中内容
                                </Checkbox>
                                <Tooltip content="勾选后，AI 将基于选中的简历内容进行回答；取消勾选则进行通用闲聊。">
                                    <IconQuestionCircle />
                                </Tooltip>
                            </div>
                        )}
                        <Input.Search
                            placeholder={isTextSelected && useContext ? "针对选中内容提问..." : "输入问题进行闲聊..."}
                            value={inputValue}
                            onChange={setInputValue}
                            onSearch={handleSendMessage}
                            searchButton={isLoading ? <Spin size={14} /> : <IconSend />}
                            disabled={isLoading || isReviewing}
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
            <AuthModal visible={authVisible} onCancel={() => setAuthVisible(false)} />
        </div>
    );
};
