import type { FC } from "react";
import { Modal, Progress } from "@arco-design/web-react";
import { 
  IconExperiment, 
  IconCheckCircleFill, 
  IconCloseCircleFill, 
  IconBulb,
  IconThumbUpFill
} from "@arco-design/web-react/icon";
import { cs } from "sketching-utils"; // 使用 classnames 工具
import styles from "./index.m.scss";

export interface ReviewResult {
  score: number;
  summary: string;
  pros: string[];
  cons: string[];
  suggestions: string[];
}

interface ReviewModalProps {
  visible: boolean;
  onClose: () => void;
  result: ReviewResult | null;
}

export const ReviewModal: FC<ReviewModalProps> = ({ visible, onClose, result }) => {
  const getScoreStatus = (score: number): "success" | "warning" | "error" => {
    if (score >= 80) return "success";
    if (score >= 60) return "warning";
    return "error";
  };

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
          <IconExperiment style={{ color: 'rgb(var(--primary-6))' }} /> 
          简历智能诊断报告
        </div>
      }
      visible={visible}
      onOk={onClose}
      onCancel={onClose}
      hideCancel
      okText="我知道了"
      style={{ width: 620 }}
      maskClosable={false}
    >
      {result && (
        <div className={styles.modalContent}>
          {/* 1. 评分仪表盘 */}
          <div className={styles.scoreBoard}>
            <div className={styles.scoreWrapper}>
              <Progress 
                type="circle" 
                percent={result.score} 
                status={getScoreStatus(result.score)}
                size="large"
                formatText={(val) => <span style={{ fontSize: 24, fontWeight: 'bold' }}>{val}</span>}
              />
              <span className={styles.scoreLabel}>AI 综合评分</span>
            </div>
            <div className={styles.summary}>
              <div style={{ marginBottom: 4, color: 'var(--color-text-3)', fontSize: 12 }}>诊断总评：</div>
              {result.summary}
            </div>
          </div>

          {/* 2. 亮点 & 不足 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 20 }}>
            
            {/* 亮点 - [修改] 统一使用 reviewItem 样式 */}
            {result.pros.length > 0 && (
              <div>
                <div className={styles.sectionTitle}>
                  <IconThumbUpFill style={{ color: '#00B42A' }} /> 
                  亮点展示
                </div>
                <div className={styles.listContainer}>
                  {result.pros.map((item, idx) => (
                    <div key={idx} className={cs(styles.reviewItem, styles.pros)}>
                      <IconCheckCircleFill className={styles.icon} />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 不足 - [修改] 统一使用 reviewItem 样式 */}
            {result.cons.length > 0 && (
              <div>
                <div className={styles.sectionTitle}>
                  <IconCloseCircleFill style={{ color: '#F53F3F' }} /> 
                  待改进问题
                </div>
                <div className={styles.listContainer}>
                  {result.cons.map((item, index) => (
                    <div key={index} className={cs(styles.reviewItem, styles.cons)}>
                      <IconCloseCircleFill className={styles.icon} />
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 3. 优化建议 */}
          {result.suggestions.length > 0 && (
            <div>
              <div className={styles.sectionTitle}>
                <IconBulb style={{ color: '#FF7D00' }} /> 
                AI 优化建议
              </div>
              <div className={styles.suggestionsBox}>
                <ol className={styles.suggestionList}>
                  {result.suggestions.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ol>
              </div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
};