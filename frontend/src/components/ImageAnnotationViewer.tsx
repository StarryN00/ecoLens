import React from 'react';
import { Modal, Image } from 'antd';

interface ImageAnnotationViewerProps {
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
          src={imageUrl}
          alt="Annotated"
          onLoad={handleImageLoad}
          style={{ maxWidth: '100%', maxHeight: '600px' }}
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
