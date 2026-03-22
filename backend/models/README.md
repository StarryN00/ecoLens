# 模型目录

此目录用于存放AI模型权重文件。

## 文件说明

### 虫巢检测模型
- **文件名**: `nest_det.pt`
- **类型**: YOLOv8 目标检测模型
- **用途**: 检测香樟树上的虫巢
- **放置位置**: `./models/nest_det.pt`

### 树种识别模型
- **文件名**: `tree_seg.pt`
- **类型**: DeepLabV3+ 语义分割模型
- **用途**: 识别图像中的香樟树区域
- **放置位置**: `./models/tree_seg.pt`

## 配置说明

模型路径可在 `backend/app/core/config.py` 中配置：

```python
NEST_DETECTION_MODEL_PATH: str = "./models/nest_det.pt"
TREE_CLASSIFICATION_MODEL_PATH: str = "./models/tree_seg.pt"
```

或通过环境变量设置：

```bash
NEST_DETECTION_MODEL_PATH=/path/to/nest_det.pt
TREE_CLASSIFICATION_MODEL_PATH=/path/to/tree_seg.pt
```

## 注意事项

1. 模型文件较大（通常 100MB-1GB），请勿提交到Git仓库
2. 系统启动时会自动检查模型文件是否存在
3. 如果模型文件不存在，系统将使用模拟模式运行（返回空结果）
4. 确保模型文件有正确的读取权限

## 模型更新

如需更新模型：
1. 将新的 `.pt` 文件复制到此目录
2. 重启后端服务和Worker容器
3. 系统会自动加载新的模型权重
