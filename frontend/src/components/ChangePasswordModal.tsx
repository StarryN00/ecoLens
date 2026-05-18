import React, { useState } from 'react';
import { Modal, Form, Input, message } from 'antd';
import { authApi } from '../services/api';

interface ChangePasswordModalProps {
  open: boolean;
  onClose: () => void;
  /** 改密成功后回调，调用方应在此 logout 并跳 /login */
  onSuccess?: () => void;
}

interface FormValues {
  old_password: string;
  new_password: string;
  confirm_password: string;
}

const ChangePasswordModal: React.FC<ChangePasswordModalProps> = ({
  open,
  onClose,
  onSuccess,
}) => {
  const [form] = Form.useForm<FormValues>();
  const [submitting, setSubmitting] = useState(false);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      try {
        await authApi.changePassword({
          old_password: values.old_password,
          new_password: values.new_password,
        });
        message.success('修改成功，请重新登录');
        form.resetFields();
        onClose();
        onSuccess?.();
      } catch (err: any) {
        // 后端 401 = 原密码错误；其他错误展示通用文案
        const status = err?.response?.status;
        const detail = err?.response?.data?.detail;
        if (status === 401) {
          message.error(detail || '原密码错误');
        } else {
          message.error(detail || '修改失败，请稍后重试');
        }
      } finally {
        setSubmitting(false);
      }
    } catch {
      // form.validateFields 抛错 → 字段已经显示错误信息，无需 toast
    }
  };

  const handleCancel = () => {
    form.resetFields();
    onClose();
  };

  return (
    <Modal
      title="修改密码"
      open={open}
      onOk={handleOk}
      onCancel={handleCancel}
      confirmLoading={submitting}
      okText="确认修改"
      cancelText="取消"
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        autoComplete="off"
        // 防止浏览器把 new_password 也自动填成旧值
        preserve={false}
      >
        <Form.Item
          name="old_password"
          label="原密码"
          rules={[{ required: true, message: '请输入原密码' }]}
        >
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Form.Item
          name="new_password"
          label="新密码"
          rules={[
            { required: true, message: '请输入新密码' },
            { min: 6, message: '新密码至少 6 个字符' },
            { max: 128, message: '新密码不能超过 128 个字符' },
          ]}
        >
          <Input.Password autoComplete="new-password" />
        </Form.Item>
        <Form.Item
          name="confirm_password"
          label="确认新密码"
          dependencies={['new_password']}
          rules={[
            { required: true, message: '请再次输入新密码' },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue('new_password') === value) {
                  return Promise.resolve();
                }
                return Promise.reject(new Error('两次输入的新密码不一致'));
              },
            }),
          ]}
        >
          <Input.Password autoComplete="new-password" />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default ChangePasswordModal;
