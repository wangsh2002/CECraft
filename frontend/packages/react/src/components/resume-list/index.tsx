import { Modal, List, Button, Message, Popconfirm, Empty, Spin } from "@arco-design/web-react";
import { IconDelete, IconEdit } from "@arco-design/web-react/icon";
import { useState, useEffect } from "react";
import { api } from "../../utils/api";
import type { Editor } from "sketching-core";
import { Range } from "sketching-core";
import { DeltaSet } from "sketching-delta";
import { Storage, TSON } from "sketching-utils";
import { Background } from "../../modules/background";
import { STORAGE_KEY } from "../../utils/storage";
import type { LocalStorageData } from "../../utils/storage";

interface Resume {
  id: number;
  title: string;
  content: string;
  updated_at: string;
}

interface ResumeListModalProps {
  visible: boolean;
  onCancel: () => void;
  editor: Editor;
}

export const ResumeListModal = ({ visible, onCancel, editor }: ResumeListModalProps) => {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchResumes = async () => {
    setLoading(true);
    try {
      const response = await api.get("/resumes/");
      setResumes(response.data);
    } catch (error) {
      Message.error("获取简历列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (visible) {
      fetchResumes();
    }
  }, [visible]);

  const handleLoad = (resume: Resume) => {
    try {
      const json = TSON.parse<LocalStorageData>(resume.content);
      if (json) {
        const deltaSetLike = json.deltaSetLike;
        const deltaSet = new DeltaSet(deltaSetLike);
        editor.state.setContent(deltaSet);
        Background.setRange(Range.fromRect(json.x, json.y, json.width, json.height));
        Background.render();
        Storage.local.set(STORAGE_KEY, json);
        Message.success("简历加载成功");
        onCancel();
      } else {
        Message.error("简历数据解析失败");
      }
    } catch (error) {
      console.error(error);
      Message.error("加载失败，数据格式错误");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/resumes/${id}`);
      Message.success("删除成功");
      fetchResumes();
    } catch (error) {
      Message.error("删除失败");
    }
  };

  return (
    <Modal
      title="我的云端简历"
      visible={visible}
      onCancel={onCancel}
      footer={null}
      style={{ width: 600 }}
    >
      <Spin loading={loading} style={{ width: "100%" }}>
        {resumes.length === 0 ? (
          <Empty description="暂无保存的简历" />
        ) : (
          <List
            dataSource={resumes}
            render={(item, index) => (
              <List.Item
                key={item.id}
                actions={[
                  <Button key="load" type="primary" size="small" onClick={() => handleLoad(item)}>
                    加载
                  </Button>,
                  <Popconfirm
                    key="delete"
                    title="确认删除该简历吗？"
                    onOk={() => handleDelete(item.id)}
                  >
                    <Button type="text" status="danger" size="small" icon={<IconDelete />}>
                      删除
                    </Button>
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={item.title}
                  description={`更新时间: ${new Date(item.updated_at || "").toLocaleString()}`}
                />
              </List.Item>
            )}
          />
        )}
      </Spin>
    </Modal>
  );
};
