import React, { useEffect, useState } from 'react';
import { Image as AntImage, type ImageProps } from 'antd';
import { fetchAuthedImageUrl } from '../services/api';

/**
 * 一个会自动带 Bearer token 取图的 antd <Image> 包装。
 *
 * 后端 /api/v1/images/* 接口在安全加固后强制鉴权，浏览器原生 <img src>
 * 不会自动带 Authorization 头，因此这里用 fetch 取回 blob 再喂给 antd Image。
 *
 * 用 path（不带 host 的相对路径，例如 `/api/v1/images/abc/thumbnail`）替代 src。
 * 组件会在 path 变化或卸载时自动 revokeObjectURL，避免内存泄漏。
 */
interface AuthedImageProps extends Omit<ImageProps, 'src' | 'preview'> {
  path: string;
  // 单独的预览路径；不传则复用主图 path
  previewPath?: string;
  // 透传给 antd Image 的 preview 配置（src 由本组件管理，不要在外面传）
  previewExtra?: Omit<NonNullable<ImageProps['preview']>, 'src'>;
}

const AuthedImage: React.FC<AuthedImageProps> = ({
  path,
  previewPath,
  previewExtra,
  fallback,
  ...rest
}) => {
  const [src, setSrc] = useState<string | undefined>(undefined);
  const [previewSrc, setPreviewSrc] = useState<string | undefined>(undefined);
  const [errored, setErrored] = useState(false);

  useEffect(() => {
    let mainUrl: string | null = null;
    let previewUrl: string | null = null;
    let cancelled = false;

    setErrored(false);
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
        if (!cancelled) setErrored(true);
      }
    })();

    return () => {
      cancelled = true;
      if (mainUrl) URL.revokeObjectURL(mainUrl);
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [path, previewPath]);

  if (errored && typeof fallback === 'string') {
    return (
      <AntImage
        src={fallback as string}
        preview={false}
        {...rest}
      />
    );
  }

  const previewConfig = previewSrc
    ? { ...(previewExtra || {}), src: previewSrc }
    : src
      ? { ...(previewExtra || {}), src }
      : false;

  return (
    <AntImage
      src={src}
      preview={previewConfig}
      {...rest}
    />
  );
};

export default AuthedImage;
