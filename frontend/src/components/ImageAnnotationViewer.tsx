import React from 'react';
import { Modal, Image } from 'antd';
import { fetchAuthedImageUrl } from '../services/api';

interface ImageAnnotationViewerProps {
  /**
   * 图片相对路径（不带 host），例如 `/api/v1/images/{id}`。
   * 组件会自动用 Bearer token fetch 并转成 blob URL，避免 401。
   */
  imageUrl: string;
  detections: Array<{
    bbox: [number, number, number, number]; // [x1, y1, x2, y2]
    confidence: number;
    severity: string;
  }>;
  visible: boolean;
  onClose: () => void;
}

const ImageAnnotationViewer: React.FC<ImageAnnotationViewerProps> = ({
  imageUrl,
  detections,
  visible,
  onClose,
}) => {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);
  const [imageLoaded, setImageLoaded] = React.useState(false);
  const [imageSize, setImageSize] = React.useState({ width: 0, height: 0 });
  const [resolvedUrl, setResolvedUrl] = React.useState<string | undefined>(undefined);

  // 用 fetch + Bearer token 取图，转成 blob URL；卸载或 imageUrl 变化时释放。
  React.useEffect(() => {
    if (!visible || !imageUrl) {
      return;
    }
    let blobUrl: string | null = null;
    let cancelled = false;
    setResolvedUrl(undefined);
    setImageLoaded(false);

    (async () => {
      try {
        const url = await fetchAuthedImageUrl(imageUrl);
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        blobUrl = url;
        setResolvedUrl(url);
      } catch {
        // 鉴权失败 fetchAuthedImageUrl 已经重定向，这里忽略
      }
    })();

    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [imageUrl, visible]);

  React.useEffect(() => {
    if (visible && imageLoaded && canvasRef.current) {
      drawAnnotations();
    }
  }, [visible, imageLoaded, detections]);

  const drawAnnotations = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // 清除画布
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 绘制检测框
    detections.forEach((det) => {
      const [x1, y1, x2, y2] = det.bbox;
      const x = x1 * canvas.width;
      const y = y1 * canvas.height;
      const w = (x2 - x1) * canvas.width;
      const h = (y2 - y1) * canvas.height;

      // 根据严重程度设置颜色
      const color =
        det.severity === 'severe' ? '#ff4d4f' :
        det.severity === 'medium' ? '#faad14' : '#52c41a';

      // 绘制矩形框
      ctx.strokeStyle = color;
      ctx.lineWidth = 3;
      ctx.strokeRect(x, y, w, h);

      // 绘制标签背景
      const label = `${det.severity} ${(det.confidence * 100).toFixed(0)}%`;
      ctx.font = 'bold 14px Arial';
      const textMetrics = ctx.measureText(label);
      const textHeight = 20;
      
      ctx.fillStyle = color;
      ctx.fillRect(x, y - textHeight, textMetrics.width + 10, textHeight);

      // 绘制文字
      ctx.fillStyle = '#fff';
      ctx.fillText(label, x + 5, y - 5);
    });
  };

  const handleImageLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setImageSize({ width: img.naturalWidth, height: img.naturalHeight });
    setImageLoaded(true);
  };

  return (
    <Modal
      title="图片标注预览"
      open={visible}
      onCancel={onClose}
      footer={null}
      width={1000}
      destroyOnClose
    >
      <div style={{ position: 'relative', display: 'inline-block' }}>
        <Image
          src={resolvedUrl}
          alt="Annotated"
          onLoad={handleImageLoad}
          style={{ maxWidth: '100%', maxHeight: '600px' }}
          preview={false}
        />
        <canvas
          ref={canvasRef}
          width={imageSize.width}
          height={imageSize.height}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            pointerEvents: 'none',
            width: '100%',
            height: '100%',
          }}
        />
      </div>
    </Modal>
  );
};

export default ImageAnnotationViewer;
