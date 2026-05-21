import React, { useEffect, useState } from 'react';
import {
  Card,
  Tree,
  Button,
  Modal,
  Input,
  message,
  Popconfirm,
  Space,
  Empty,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { regionApi } from '../../services/api';

interface RegionNode {
  id: string;
  name: string;
  level: string;
  full_path: string;
  children: RegionNode[];
}

const LEVEL_LABEL: Record<string, string> = {
  city: '市',
  district: '区',
  town: '街镇',
};
// 每一级的下一级（town 无下级）
const CHILD_LEVEL: Record<string, string> = {
  city: 'district',
  district: 'town',
};

interface ModalState {
  open: boolean;
  mode: 'create' | 'rename';
  level?: string;
  parentId?: string;
  targetId?: string;
  title: string;
}

const RegionAdmin: React.FC = () => {
  const [tree, setTree] = useState<RegionNode[]>([]);
  const [loading, setLoading] = useState(false);
  const [modal, setModal] = useState<ModalState>({
    open: false,
    mode: 'create',
    title: '',
  });
  const [nameInput, setNameInput] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const data: any = await regionApi.getTree();
      setTree(data?.items || []);
    } catch {
      message.error('加载区域树失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const openCreate = (level: string, parentId?: string) => {
    setNameInput('');
    setModal({
      open: true,
      mode: 'create',
      level,
      parentId,
      title: `新增${LEVEL_LABEL[level]}`,
    });
  };

  const openRename = (node: RegionNode) => {
    setNameInput(node.name);
    setModal({
      open: true,
      mode: 'rename',
      targetId: node.id,
      title: `重命名「${node.name}」`,
    });
  };

  const handleOk = async () => {
    const name = nameInput.trim();
    if (!name) {
      message.warning('名称不能为空');
      return;
    }
    try {
      if (modal.mode === 'create') {
        await regionApi.create({
          name,
          level: modal.level as string,
          parent_id: modal.parentId,
        });
        message.success('已创建');
      } else {
        await regionApi.update(modal.targetId as string, { name });
        message.success('已重命名');
      }
      setModal((m) => ({ ...m, open: false }));
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await regionApi.remove(id);
      message.success('已删除');
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  // RegionNode 树 -> antd Tree DataNode，title 内联操作按钮
  const toTreeData = (nodes: RegionNode[]): any[] =>
    nodes.map((n) => {
      const childLevel = CHILD_LEVEL[n.level];
      return {
        key: n.id,
        title: (
          <Space size={4}>
            <span>{n.name}</span>
            <span style={{ color: '#999', fontSize: 12 }}>
              [{LEVEL_LABEL[n.level] || n.level}]
            </span>
            {childLevel && (
              <Button
                size="small"
                type="link"
                icon={<PlusOutlined />}
                onClick={() => openCreate(childLevel, n.id)}
              >
                加{LEVEL_LABEL[childLevel]}
              </Button>
            )}
            <Button
              size="small"
              type="link"
              icon={<EditOutlined />}
              onClick={() => openRename(n)}
            >
              改名
            </Button>
            <Popconfirm
              title="确认删除该区域？仅当其下无子区域、无巡检任务时可删。"
              onConfirm={() => handleDelete(n.id)}
            >
              <Button
                size="small"
                type="link"
                danger
                icon={<DeleteOutlined />}
              >
                删除
              </Button>
            </Popconfirm>
          </Space>
        ),
        children:
          n.children && n.children.length > 0
            ? toTreeData(n.children)
            : undefined,
      };
    });

  return (
    <div className="eco-page">
      <div className="eco-page-header">
        <div>
          <div className="eco-eyebrow">Region Directory</div>
          <h1 className="eco-page-title">行政区域管理</h1>
          <div className="eco-page-desc">
            维护市 / 区 / 街镇三级目录，巡检任务必须归属到街镇级区域。
          </div>
        </div>
        <div className="eco-actions">
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => openCreate('city')}
          >
            新增市
          </Button>
        </div>
      </div>
      <Card className="eco-panel" title="区域树" loading={loading}>
        {tree.length === 0 ? (
          <Empty description="尚无区域，点右上角「新增市」开始建立三级目录" />
        ) : (
          <Tree
            treeData={toTreeData(tree)}
            defaultExpandAll
            selectable={false}
          />
        )}
        <Modal
          title={modal.title}
          open={modal.open}
          onOk={handleOk}
          onCancel={() => setModal((m) => ({ ...m, open: false }))}
          destroyOnHidden
        >
          <Input
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            placeholder="区域名称"
            onPressEnter={handleOk}
          />
        </Modal>
      </Card>
    </div>
  );
};

export default RegionAdmin;
