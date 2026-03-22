import React, { useState } from 'react';
import { Form, Input, Button, Card, Upload, message, Steps } from 'antd';
import { UploadOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { taskApi } from '../services/api';

const { Step } = Steps;
const { TextArea } = Input;

const TaskCreate: React.FC = () => {
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [fileList, setFileList] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const navigate = useNavigate();

  const handleCreateTask = async (values: any) => {
    try {
      const result = await taskApi.createTask(values);
      setTaskId(result.id);
      setCurrentStep(1);
      message.success('任务创建成功');
    } catch (error) {
      message.error('创建任务失败');
    }
  };

  const handleUpload = async () => {
    if (!taskId || fileList.length === 0) {
      message.warning('请选择要上传的图片');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      fileList.forEach((file) => {
        formData.append('files', file.originFileObj || file);
      });

      await taskApi.uploadImages(taskId, formData);
      message.success('图片上传成功');
      setCurrentStep(2);
    } catch (error) {
      message.error('上传失败');
    } finally {
      setUploading(false);
    }
  };

  const uploadProps = {
    onRemove: (file: any) => {
      const index = fileList.indexOf(file);
      const newFileList = fileList.slice();
      newFileList.splice(index, 1);
      setFileList(newFileList);
    },
    beforeUpload: (file: any) => {
      setFileList(prev => [...prev, file]);
      return false;
    },
    fileList,
    multiple: true,
    accept: '.jpg,.jpeg,.png'
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <Form
            form={form}
            layout="vertical"
            onFinish={handleCreateTask}
          >
            <Form.Item
              label="任务名称"
              name="task_name"
              rules={[{ required: true, message: '请输入任务名称' }]}
            >
              <Input placeholder="例如: XX公园巡检" />
            </Form.Item>

            <Form.Item
              label="巡检区域"
              name="area_name"
            >
              <Input placeholder="例如: 人民公园" />
            </Form.Item>

            <Form.Item
              label="操作员"
              name="operator"
            >
              <Input placeholder="操作员姓名" />
            </Form.Item>

            <Form.Item>
              <Button type="primary" htmlType="submit">
                下一步
              </Button>
            </Form.Item>
          </Form>
        );

      case 1:
        return (
          <div>
            <Upload {...uploadProps}>
              <Button icon={<UploadOutlined />}>选择图片</Button>
            </Upload>
            <p style={{ marginTop: 16 }}>已选择 {fileList.length} 张图片</p>
            <Button
              type="primary"
              onClick={handleUpload}
              loading={uploading}
              disabled={fileList.length === 0}
              style={{ marginTop: 16 }}
            >
              开始上传
            </Button>
          </div>
        );

      case 2:
        return (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <CheckCircleOutlined style={{ fontSize: 64, color: '#52c41a' }} />
            <h2 style={{ marginTop: 24 }}>任务创建完成</h2>
            <p>系统正在处理图片,请稍后查看结果</p>
            <Button
              type="primary"
              onClick={() => navigate('/tasks')}
              style={{ marginTop: 24 }}
            >
              返回任务列表
            </Button>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <Card title="新建巡检任务">
      <Steps current={currentStep} style={{ marginBottom: 32 }}>
        <Step title="基本信息" />
        <Step title="上传图片" />
        <Step title="完成" />
      </Steps>
      {renderStepContent()}
    </Card>
  );
};

export default TaskCreate;
