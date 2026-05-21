import React, { useEffect, useState } from 'react';
import { Image as AntImage, Skeleton, type ImageProps } from 'antd';
import { ReloadOutlined, FileImageOutlined } from '@ant-design/icons';
import { fetchAuthedImageUrl } from '../services/api';

/**
 * 一个会自动带 Bearer token 取图的 antd <Image> 包装。
 *
 * 后端 /api/v1/images/* 接口在安全加固后强制鉴权，浏览器原生 <img src>
 * 不会自动带 Authorization 头，因此这里用 fetch 取回 blob 再喂给 antd Image。
 *
 * 用 path（不带 host 的相对路径，例如 `/api/v1/images/abc/thumbnail`）替代 src。
 * 组件会在 path 变化或卸载时自动 revokeObjectURL，避免内存泄漏。
 *
 * 三态显示：
 *   - loading（首屏/重试中）→ 灰底 + Skeleton.Image 占位
 *   - errored                → "加载失败" 文案 + 重试按钮
 *   - success                → antd <Image>（支持点击预览）
 *
 * 之所以不把 antd 的 src=undefined 直接交给它：antd v5 在 src=undefined
 * 时会渲染默认 broken image 图标，UX 比明确的 loading 状态差很多，而且
 * 用户分不清"还没加载完"和"加载真的失败了"。
 */
interface AuthedImageProps extends Omit<ImageProps, 'src' | 'preview'> {
  path: string;
  // 单独的预览路径；不传则复用主图 path
  previewPath?: string;
  // 透传给 antd Image 的 preview 配置（src 由本组件管理，不要在外面传）
  previewExtra?: Omit<NonNullable<ImageProps['preview']>, 'src'>;
  // T3 图片压缩：默认 path / previewPath 拿到的都是后端压缩版（1920px）。
  // 传 originalPath（通常是 `...?max_width=0`）后，组件在图片右下角叠一个
  // "原图" 按钮，点击带 token 取未压缩原图并在新标签打开。
  originalPath?: string;
}

const AuthedImage: React.FC<AuthedImageProps> = ({
  path,
  previewPath,
  previewExtra,
  originalPath,
  fallback,
  style,
  ...rest
}) => {
  const [src, setSrc] = useState<string | undefined>(undefined);
  const [previewSrc, setPreviewSrc] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [errored, setErrored] = useState(false);
  // 重试触发器：递增即重跑 effect
  const [retryToken, setRetryToken] = useState(0);
  // "查看原图" 进行中标志，防止重复点击
  const [openingOriginal, setOpeningOriginal] = useState(false);

  const handleViewOriginal = async (e: React.MouseEvent) => {
    // 阻止冒泡，否则会同时触发 antd Image 的放大预览
    e.stopPropagation();
    if (!originalPath || openingOriginal) return;
    setOpeningOriginal(true);
    try {
      const url = await fetchAuthedImageUrl(originalPath);
      // 新标签打开原图。blob URL 不立即 revoke——新标签还在用它，
      // 交给该标签关闭时浏览器自行回收（用户手动触发，泄漏可忽略）。
      window.open(url, '_blank', 'noopener');
    } catch {
      // fetchAuthedImageUrl 内部已处理 401 跳转，这里静默
    } finally {
      setOpeningOriginal(false);
    }
  };

  useEffect(() => {
    // 每个 effect 闭包持有独立的 cancelled / mainUrl / previewUrl，
    // React 18 StrictMode dev 下双调用安全：
    //   首次 effect 的 fetch 即使在 cleanup 后才 resolve，也会因为自己的
    //   cancelled=true 走 revoke 分支，不会污染第二次 effect 的状态。
    let mainUrl: string | null = null;
    let previewUrl: string | null = null;
    let cancelled = false;

    setErrored(false);
    setLoading(true);
    setSrc(undefined);
    setPreviewSrc(undefined);

    (async () => {
      try {
        const url = await fetchAuthedImageUrl(path);
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        mainUrl = url;
        setSrc(url);
        setLoading(false);

        if (previewPath && previewPath !== path) {
          try {
            const pUrl = await fetchAuthedImageUrl(previewPath);
            if (cancelled) {
              URL.revokeObjectURL(pUrl);
            } else {
              previewUrl = pUrl;
              setPreviewSrc(pUrl);
            }
          } catch {
            // 预览失败不影响主图展示
          }
        }
      } catch {
        if (!cancelled) {
          setErrored(true);
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
      if (mainUrl) URL.revokeObjectURL(mainUrl);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [path, previewPath, retryToken]);

  // 容器宽高继承自外部 style，给 loading / error 占位时能保持表格行高稳定
  const containerStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#fafafa',
    border: '1px solid #f0f0f0',
    borderRadius: 4,
    color: '#999',
    fontSize: 12,
    overflow: 'hidden',
    ...(style || {}),
  };

  if (loading) {
    return (
      <div style={containerStyle} aria-label="加载中">
        <Skeleton.Image
          active
          style={{ width: '100%', height: '100%', minWidth: 40, minHeight: 30 }}
        />
      </div>
    );
  }

  if (errored) {
    // 用户给了字符串 fallback：仍走 antd Image 渲染该 URL
    if (typeof fallback === 'string') {
      return <AntImage src={fallback as string} preview={false} style={style} {...rest} />;
    }
    return (
      <div
        style={{ ...containerStyle, cursor: 'pointer', flexDirection: 'column' }}
        title="点击重试"
        onClick={(e) => {
          e.stopPropagation();
          setRetryToken((t) => t + 1);
        }}
      >
        <FileImageOutlined style={{ fontSize: 16 }} />
        <span style={{ marginTop: 2 }}>
          加载失败 <ReloadOutlined />
        </span>
      </div>
    );
  }

  // 正常态：src 一定有值
  const previewConfig = previewSrc
    ? { ...(previewExtra || {}), src: previewSrc }
    : src
      ? { ...(previewExtra || {}), src }
      : false;

  const image = (
    <AntImage
      src={src}
      preview={previewConfig}
      style={style}
      {...rest}
      // 放在 rest 之后强制覆盖：罕见情况下 blob URL 拿到了但浏览器渲染
      // 失败（损坏的 JPEG 等），走我们自己的 errored 分支显示重试 UI
      onError={() => {
        setErrored(true);
      }}
    />
  );

  // 没有 originalPath：直接返回图片，行为与改造前一致
  if (!originalPath) {
    return image;
  }

  // 有 originalPath：包一层 relative 容器，右下角叠 "原图" 按钮
  return (
    <span style={{ position: 'relative', display: 'inline-block', lineHeight: 0 }}>
      {image}
      <button
        type="button"
        onClick={handleViewOriginal}
        disabled={openingOriginal}
        title="在新标签查看未压缩原图"
        style={{
          position: 'absolute',
          right: 2,
          bottom: 2,
          padding: '1px 6px',
          fontSize: 11,
          lineHeight: '16px',
          color: '#fff',
          background: 'rgba(0,0,0,0.55)',
          border: 'none',
          borderRadius: 3,
          cursor: openingOriginal ? 'wait' : 'pointer',
        }}
      >
        <FileImageOutlined style={{ marginRight: 2 }} />
        {openingOriginal ? '打开中' : '原图'}
      </button>
    </span>
  );
};

export default AuthedImage;
