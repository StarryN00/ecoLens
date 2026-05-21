import React, { useEffect, useState } from 'react';
import {
  Form,
  Input,
  InputNumber,
  Button,
  Card,
  Cascader,
  Upload,
  message,
  Steps,
  Alert,
} from 'antd';
import { UploadOutlined, CheckCircleOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { regionApi, taskApi } from '../services/api';

const { Step } = Steps;

interface RegionNode {
  id: string;
  name: string;
  level: string;
  children?: RegionNode[];
}

interface CascaderOption {
  value: string;
  label: string;
  children?: CascaderOption[];
}

// 区域树 -> antd Cascader options。town 级无 children => 成为可选叶子。
const toCascaderOptions = (nodes: RegionNode[]): CascaderOption[] =>
  nodes.map((n) => ({
    value: n.id,
    label: n.name,
    children:
      n.children && n.children.length > 0
        ? toCascaderOptions(n.children)
        : undefined,
  }));

const TaskCreate: React.FC = () => {
  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [fileList, setFileList] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [regionOptions, setRegionOptions] = useState<CascaderOption[]>([]);
  const [regionLoaded, setRegionLoaded] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    regionApi
      .getTree()
      .then((data: any) => {
        if (!cancelled) {
          setRegionOptions(toCascaderOptions(data?.items || []));
          setRegionLoaded(true);
        }
      })
      .catch(() => {
        if (!cancelled) setRegionLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleCreateTask = async (values: any) => {
    try {
      const { region_cascade, ...rest } = values;
      // Cascader value 是 [cityId, districtId, townId]，取最后一级 town id
      const region_id =
        Array.isArray(region_cascade) && region_cascade.length > 0
          ? region_cascade[region_cascade.length - 1]
          : undefined;
      const result = await taskApi.createTask({ ...rest, region_id });
      setTaskId(result.id);
      setCurrentStep(1);
      message.success('任务创建成功');
    } catch (error: any) {
      // 后端 400/422 的 detail 直接透出，便于用户知道是区域没选对
      const detail = error?.response?.data?.detail;
      message.error(
        typeof detail === 'string' ? detail : '创建任务失败',
      );
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
      setFileList((prev) => [...prev, file]);
      return false;
    },
    fileList,
    multiple: true,
    accept: '.jpg,.jpeg,.png',
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <Form form={form} layout="vertical" onFinish={handleCreateTask}>
            <Form.Item
              label="任务名称"
              name="task_name"
              rules={[{ required: true, message: '请输入任务名称' }]}
            >
              <Input placeholder="例如: XX公园巡检" />
            </Form.Item>

            {regionLoaded && regionOptions.length === 0 && (
              <Alert
                type="warning"
                showIcon
                style={{ marginBottom: 16 }}
                message="尚无行政区域"
                description="请先让管理员在「区域管理」中创建 市/区/街镇 三级目录，任务必须归属到一个街镇。"
              />
            )}

            <Form.Item
              label="所属区域（市 / 区 / 街镇）"
              name="region_cascade"
              rules={[
                { required: true, message: '请选择完整的 市/区/街镇' },
                {
                  validator: (_: any, value: any) =>
                    Array.isArray(value) && value.length === 3
                      ? Promise.resolve()
                      : Promise.reject(
                          new Error('必须选到街镇级（完整三级）'),
                        ),
                },
              ]}
            >
              <Cascader
                options={regionOptions}
                placeholder="依次选择 市 → 区 → 街镇"
                expandTrigger="hover"
              />
            </Form.Item>

            <Form.Item label="巡检区域说明" name="area_name">
              <Input placeholder="例如: 人民公园（可选，自由描述）" />
            </Form.Item>

            <Form.Item label="操作员" name="operator">
              <Input placeholder="操作员姓名" />
            </Form.Item>

            <Form.Item label="地块面积" name="plot_area_mu">
              <InputNumber
                min={0}
                precision={2}
                addonAfter="亩"
                placeholder="可选"
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Form.Item label="林业局小班号" name="forestry_sub_compartment">
              <Input placeholder="例如: A-12-3（可选）" />
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
    <div className="eco-page">
      <div className="eco-page-header">
        <div>
          <div className="eco-eyebrow">Create Inspection</div>
          <h1 className="eco-page-title">新建巡检任务</h1>
          <div className="eco-page-desc">
            选择完整行政区划，补充巡检地块信息后上传无人机影像，系统将自动进入检测流程。
          </div>
        </div>
        <div className="eco-actions">
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/tasks')}>
            返回任务列表
          </Button>
        </div>
      </div>
      <Card className="eco-panel">
        <Steps current={currentStep} style={{ marginBottom: 32 }}>
          <Step title="基本信息" />
          <Step title="上传图片" />
          <Step title="完成" />
        </Steps>
        {renderStepContent()}
      </Card>
    </div>
  );
};

export default TaskCreate;
