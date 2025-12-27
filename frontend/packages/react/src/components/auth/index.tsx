import { Modal, Form, Input, Button, Message, Tabs } from "@arco-design/web-react";
import { useState } from "react";
import { api } from "../../utils/api";
import { useAuth } from "../../hooks/use-auth";

const FormItem = Form.Item;
const TabPane = Tabs.TabPane;

interface AuthModalProps {
  visible: boolean;
  onCancel: () => void;
}

export const AuthModal = ({ visible, onCancel }: AuthModalProps) => {
  const [activeTab, setActiveTab] = useState("login");
  const [loading, setLoading] = useState(false);
  const [loginForm] = Form.useForm();
  const [registerForm] = Form.useForm();
  const { login } = useAuth();

  const handleLogin = async () => {
    try {
      const values = await loginForm.validate();
      setLoading(true);
      const formData = new FormData();
      formData.append("username", values.email);
      formData.append("password", values.password);
      
      const response = await api.post("/auth/login", formData, {
        headers: { "Content-Type": "application/x-www-form-urlencoded" }
      });
      
      await login(response.data.access_token);
      Message.success("登录成功");
      onCancel();
    } catch (error) {
      Message.error("登录失败，请检查邮箱和密码");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    try {
      const values = await registerForm.validate();
      setLoading(true);
      await api.post("/auth/register", {
        email: values.email,
        password: values.password
      });
      Message.success("注册成功，请登录");
      setActiveTab("login");
    } catch (error: any) {
      console.error("Register error:", error);
      const msg = error.response?.data?.detail || "注册失败，请稍后重试";
      Message.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title="用户认证"
      visible={visible}
      onCancel={onCancel}
      footer={null}
      unmountOnExit
    >
      <Tabs activeTab={activeTab} onChange={setActiveTab}>
        <TabPane key="login" title="登录">
          <Form form={loginForm} onSubmit={handleLogin} layout="vertical">
            <FormItem label="邮箱" field="email" rules={[{ required: true, type: 'email' }]}>
              <Input placeholder="请输入邮箱" />
            </FormItem>
            <FormItem label="密码" field="password" rules={[{ required: true }]}>
              <Input.Password placeholder="请输入密码" />
            </FormItem>
            <FormItem>
              <Button type="primary" htmlType="submit" long loading={loading}>
                登录
              </Button>
            </FormItem>
          </Form>
        </TabPane>
        <TabPane key="register" title="注册">
          <Form form={registerForm} onSubmit={handleRegister} layout="vertical">
            <FormItem label="邮箱" field="email" rules={[{ required: true, type: 'email' }]}>
              <Input placeholder="请输入邮箱" />
            </FormItem>
            <FormItem label="密码" field="password" rules={[{ required: true, minLength: 6 }]}>
              <Input.Password placeholder="请输入密码 (至少6位)" />
            </FormItem>
            <FormItem label="确认密码" field="confirmPassword" rules={[
              { required: true },
              {
                validator: (v, cb) => {
                  if (registerForm.getFieldValue("password") !== v) {
                    return cb("两次密码输入不一致");
                  }
                  cb(null);
                }
              }
            ]}>
              <Input.Password placeholder="请再次输入密码" />
            </FormItem>
            <FormItem>
              <Button type="primary" htmlType="submit" long loading={loading}>
                注册
              </Button>
            </FormItem>
          </Form>
        </TabPane>
      </Tabs>
    </Modal>
  );
};
