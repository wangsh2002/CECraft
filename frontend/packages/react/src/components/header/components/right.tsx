import { Button, Dropdown, InputNumber, Menu, Modal, Message, Input } from "@arco-design/web-react";
import type { RefInputType } from "@arco-design/web-react/es/Input";
import { IconDown, IconGithub, IconRedo, IconUndo } from "@arco-design/web-react/icon";
import { useMemoFn } from "@block-kit/utils/dist/es/hooks";
import type { FC } from "react";
import { useEffect, useRef, useState } from "react";
import type { Editor } from "sketching-core";
import { EDITOR_EVENT, Range } from "sketching-core";
import { cs, Storage } from "sketching-utils";

import { Background } from "../../../modules/background";
import type { LocalStorageData } from "../../../utils/storage";
import { STORAGE_KEY } from "../../../utils/storage";
import styles from "../index.m.scss";
import { exportJSON, exportPDF } from "../utils/export";
import { importJSON } from "../utils/import";
import { AuthModal } from "../../auth";
import { useAuth } from "../../../hooks/use-auth";
import { api } from "../../../utils/api";
import { ResumeListModal } from "../../resume-list";

export const Right: FC<{
  editor: Editor;
}> = ({ editor }) => {
  const [undoAble, setUndoAble] = useState<boolean>(false);
  const [redoAble, setRedoAble] = useState<boolean>(false);
  const widthRef = useRef<RefInputType>(null);
  const heightRef = useRef<RefInputType>(null);
  const { user, logout } = useAuth();
  const [authVisible, setAuthVisible] = useState(false);
  const [resumeListVisible, setResumeListVisible] = useState(false);
  const [saveModalVisible, setSaveModalVisible] = useState(false);
  const [saveTitle, setSaveTitle] = useState("");

  const query = useMemoFn(() => {
    setUndoAble(editor.history.canUndo());
    setRedoAble(editor.history.canRedo());
  });

  useEffect(() => {
    query();
    editor.event.on(EDITOR_EVENT.CONTENT_CHANGE, query);
    return () => {
      editor.event.off(EDITOR_EVENT.CONTENT_CHANGE, query);
    };
  }, [editor, query]);

  const onResizeBackGround = () => {
    const { x, y, width, height } = Background.rect;
    Modal.confirm({
      title: "调整画布大小",
      className: styles.resizeModal,
      content: (
        <div className={styles.modalContent}>
          <div>宽(width) x 高(height):</div>
          <InputNumber
            size="small"
            ref={widthRef}
            className={styles.input}
            min={600}
            max={2000}
            defaultValue={width}
          />
          <InputNumber
            size="small"
            ref={heightRef}
            className={styles.input}
            min={1000}
            max={4000}
            defaultValue={height}
          />
        </div>
      ),
      onConfirm: () => {
        if (!widthRef.current || !heightRef.current) return;
        const width = Number(widthRef.current.dom.value);
        const height = Number(heightRef.current.dom.value);
        width && height && Background.setRange(Range.fromRect(x, y, width, height));
        const deltaSetLike = editor.deltaSet.getDeltas();
        const storageData: LocalStorageData = { ...Background.rect, deltaSetLike };
        Storage.local.set(STORAGE_KEY, storageData);
        Background.render();
      },
    });
  };

  const onSaveClick = () => {
    if (!user) {
      setAuthVisible(true);
      return;
    }
    setSaveTitle("我的简历 " + new Date().toLocaleString());
    setSaveModalVisible(true);
  };

  const handleConfirmSave = async () => {
    if (!saveTitle.trim()) {
      Message.warning("请输入简历名称");
      return;
    }
    const deltaSetLike = editor.deltaSet.getDeltas();
    const content = JSON.stringify({ ...Background.rect, deltaSetLike });
    try {
      await api.post("/resumes/", { title: saveTitle, content });
      Message.success("保存成功");
      setSaveModalVisible(false);
    } catch (e) {
      Message.error("保存失败");
    }
  };

  return (
    <div className={cs(styles.externalGroup)}>
      <div className={styles.history}>
        <Button
          onClick={() => editor.history.undo()}
          disabled={!undoAble}
          iconOnly
          icon={<IconUndo />}
          type="text"
          size="small"
        ></Button>
        <Button
          onClick={() => editor.history.redo()}
          disabled={!redoAble}
          iconOnly
          icon={<IconRedo />}
          type="text"
          size="small"
        ></Button>
      </div>
      <Dropdown
        droplist={
          <Menu className={styles.menu}>
            <Menu.Item key="0">
              <a href="?preview" target="_blank">
                预览
              </a>
            </Menu.Item>
            <Menu.Item key="1">
              <div className={styles.export} onClick={() => onResizeBackGround()}>
                画布大小
              </div>
            </Menu.Item>
            <Menu.Item key="2">
              <div className={styles.export} onClick={() => importJSON(editor)}>
                导入JSON
              </div>
            </Menu.Item>
          </Menu>
        }
        trigger="click"
        position="br"
      >
        <Button size="mini" type="text">
          操作
          <IconDown />
        </Button>
      </Dropdown>
      <Dropdown
        droplist={
          <Menu className={styles.menu}>
            <Menu.Item key="1">
              <div className={styles.export} onClick={() => exportPDF()}>
                PDF
              </div>
            </Menu.Item>
            <Menu.Item key="3">
              <div className={styles.export} onClick={() => exportJSON(editor)}>
                JSON
              </div>
            </Menu.Item>
            <Menu.Item key="2">
              <div className={styles.export} onClick={() => exportPDF(2)}>
                PDF(高清)
              </div>
            </Menu.Item>
          </Menu>
        }
        trigger="click"
        position="br"
      >
        <Button size="mini" type="text">
          导出
          <IconDown />
        </Button>
      </Dropdown>
      
      <Button type="primary" size="mini" onClick={onSaveClick} style={{ marginRight: 8 }}>
        保存到云端
      </Button>

      <Modal
        title="保存简历"
        visible={saveModalVisible}
        onOk={handleConfirmSave}
        onCancel={() => setSaveModalVisible(false)}
      >
        <div style={{ marginBottom: 10 }}>请输入简历名称：</div>
        <Input 
            value={saveTitle} 
            onChange={setSaveTitle} 
            placeholder="请输入简历名称" 
            onPressEnter={handleConfirmSave}
        />
      </Modal>

      {user ? (
        <Dropdown
          droplist={
            <Menu>
              <Menu.Item key="my-resumes" onClick={() => setResumeListVisible(true)}>我的简历</Menu.Item>
              <Menu.Item key="logout" onClick={logout}>退出登录</Menu.Item>
            </Menu>
          }
        >
          <Button type="text" size="small">{user.email}</Button>
        </Dropdown>
      ) : (
        <Button type="secondary" size="small" onClick={() => setAuthVisible(true)}>登录</Button>
      )}
      <AuthModal visible={authVisible} onCancel={() => setAuthVisible(false)} />
      <ResumeListModal 
        visible={resumeListVisible} 
        onCancel={() => setResumeListVisible(false)} 
        editor={editor}
      />

      <a
        className={styles.github}
        target="_blank"
        href={"https://github.com/WindrunnerMax/CanvasEditor"}
      >
        <IconGithub />
      </a>
    </div>
  );
};
