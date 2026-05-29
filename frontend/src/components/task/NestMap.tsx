import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Card, Space, Tag } from 'antd';
import AMapLoader from '@amap/amap-jsapi-loader';
import type { Nest, TaskImage } from '../../types/task';
import { getSeverityTag } from './taskUtils';

declare global {
  interface Window {
    AMap?: any;
    _AMapSecurityConfig?: {
      securityJsCode: string;
    };
  }
}

interface Props {
  nests: Nest[];
  images: TaskImage[];
  loading: boolean;
}

interface MapPoint {
  id: string;
  code: string;
  latitude: number;
  longitude: number;
  severity: string;
  confidence?: number;
  detectionCount?: number;
}

const AMAP_KEY = import.meta.env.VITE_AMAP_KEY as string | undefined;
const AMAP_SECURITY_JS_CODE = import.meta.env.VITE_AMAP_SECURITY_JS_CODE as
  | string
  | undefined;

const OUT_OF_CHINA = {
  minLng: 72.004,
  maxLng: 137.8347,
  minLat: 0.8293,
  maxLat: 55.8271,
};

const transformLat = (lng: number, lat: number) => {
  let ret =
    -100.0 +
    2.0 * lng +
    3.0 * lat +
    0.2 * lat * lat +
    0.1 * lng * lat +
    0.2 * Math.sqrt(Math.abs(lng));
  ret +=
    ((20.0 * Math.sin(6.0 * lng * Math.PI) +
      20.0 * Math.sin(2.0 * lng * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((20.0 * Math.sin(lat * Math.PI) +
      40.0 * Math.sin((lat / 3.0) * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((160.0 * Math.sin((lat / 12.0) * Math.PI) +
      320 * Math.sin((lat * Math.PI) / 30.0)) *
      2.0) /
    3.0;
  return ret;
};

const transformLng = (lng: number, lat: number) => {
  let ret =
    300.0 +
    lng +
    2.0 * lat +
    0.1 * lng * lng +
    0.1 * lng * lat +
    0.1 * Math.sqrt(Math.abs(lng));
  ret +=
    ((20.0 * Math.sin(6.0 * lng * Math.PI) +
      20.0 * Math.sin(2.0 * lng * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((20.0 * Math.sin(lng * Math.PI) +
      40.0 * Math.sin((lng / 3.0) * Math.PI)) *
      2.0) /
    3.0;
  ret +=
    ((150.0 * Math.sin((lng / 12.0) * Math.PI) +
      300.0 * Math.sin((lng / 30.0) * Math.PI)) *
      2.0) /
    3.0;
  return ret;
};

const isInChina = (lng: number, lat: number) =>
  lng >= OUT_OF_CHINA.minLng &&
  lng <= OUT_OF_CHINA.maxLng &&
  lat >= OUT_OF_CHINA.minLat &&
  lat <= OUT_OF_CHINA.maxLat;

const wgs84ToGcj02 = (lng: number, lat: number): [number, number] => {
  if (!isInChina(lng, lat)) return [lng, lat];

  const a = 6378245.0;
  const ee = 0.006693421622965943;
  let dLat = transformLat(lng - 105.0, lat - 35.0);
  let dLng = transformLng(lng - 105.0, lat - 35.0);
  const radLat = (lat / 180.0) * Math.PI;
  let magic = Math.sin(radLat);
  magic = 1 - ee * magic * magic;
  const sqrtMagic = Math.sqrt(magic);
  dLat = (dLat * 180.0) / (((a * (1 - ee)) / (magic * sqrtMagic)) * Math.PI);
  dLng = (dLng * 180.0) / ((a / sqrtMagic) * Math.cos(radLat) * Math.PI);
  return [lng + dLng, lat + dLat];
};

const severityColor = (severity: string) => {
  if (severity === 'severe') return '#c2413b';
  if (severity === 'medium') return '#d97706';
  return '#1f7a4d';
};

const buildPoints = (nests: Nest[], images: TaskImage[]): MapPoint[] => {
  if (nests.length > 0) {
    return nests.map((nest) => ({
      id: nest.id,
      code: nest.nest_code,
      latitude: nest.latitude,
      longitude: nest.longitude,
      severity: nest.severity,
      confidence: nest.confidence,
      detectionCount: nest.detection_count,
    }));
  }

  return images
    .filter((image) => image.has_gps && image.latitude && image.longitude)
    .map((image) => ({
      id: image.id,
      code: image.filename,
      latitude: image.latitude as number,
      longitude: image.longitude as number,
      severity: image.detection?.max_severity || 'light',
    }));
};

const NestMap: React.FC<Props> = ({ nests, images, loading }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);
  const infoWindowRef = useRef<any>(null);
  const [mapError, setMapError] = useState<string | null>(null);

  const points = useMemo(() => buildPoints(nests, images), [nests, images]);
  const center = useMemo<[number, number]>(() => {
    const first = points[0];
    if (!first) return [121.4737, 31.2304];
    return wgs84ToGcj02(first.longitude, first.latitude);
  }, [points]);

  useEffect(() => {
    if (!AMAP_KEY || !containerRef.current) return undefined;

    let disposed = false;

    if (AMAP_SECURITY_JS_CODE) {
      window._AMapSecurityConfig = {
        securityJsCode: AMAP_SECURITY_JS_CODE,
      };
    }

    AMapLoader.load({
      key: AMAP_KEY,
      version: '2.0',
      plugins: ['AMap.Scale', 'AMap.ToolBar'],
    })
      .then((AMap) => {
        if (disposed || !containerRef.current) return;

        mapRef.current = new AMap.Map(containerRef.current, {
          center,
          zoom: points.length > 0 ? 16 : 11,
          viewMode: '2D',
          mapStyle: 'amap://styles/normal',
        });
        mapRef.current.addControl(new AMap.Scale());
        mapRef.current.addControl(new AMap.ToolBar({ position: 'RB' }));
        infoWindowRef.current = new AMap.InfoWindow({ offset: new AMap.Pixel(0, -28) });
        setMapError(null);
      })
      .catch((error) => {
        setMapError(error instanceof Error ? error.message : '高德地图加载失败');
      });

    return () => {
      disposed = true;
      markersRef.current.forEach((marker) => marker.setMap(null));
      markersRef.current = [];
      if (mapRef.current) {
        mapRef.current.destroy();
        mapRef.current = null;
      }
    };
  }, [center, points.length]);

  useEffect(() => {
    const map = mapRef.current;
    const AMap = window.AMap;
    if (!map || !AMap) return;

    markersRef.current.forEach((marker) => marker.setMap(null));
    markersRef.current = [];

    points.forEach((point) => {
      const [lng, lat] = wgs84ToGcj02(point.longitude, point.latitude);
      const color = severityColor(point.severity);
      const marker = new AMap.Marker({
        position: [lng, lat],
        anchor: 'center',
        content: `<div class="amap-nest-marker" style="--marker-color:${color}"></div>`,
      });

      marker.on('click', () => {
        const confidence =
          typeof point.confidence === 'number'
            ? `<div>置信度：${(point.confidence * 100).toFixed(1)}%</div>`
            : '';
        const detectionCount =
          typeof point.detectionCount === 'number'
            ? `<div>检测次数：${point.detectionCount}</div>`
            : '';
        infoWindowRef.current?.setContent(
          `<div class="amap-info-window">
            <strong>${point.code}</strong>
            <div>坐标：${point.latitude.toFixed(6)}, ${point.longitude.toFixed(6)}</div>
            <div>严重程度：${point.severity}</div>
            ${confidence}
            ${detectionCount}
          </div>`,
        );
        infoWindowRef.current?.open(map, [lng, lat]);
      });

      marker.setMap(map);
      markersRef.current.push(marker);
    });

    if (points.length > 1) {
      map.setFitView(markersRef.current, false, [80, 80, 80, 80], 17);
    } else {
      map.setCenter(center);
      map.setZoom(points.length > 0 ? 16 : 11);
    }
  }, [center, points]);

  return (
    <Card className="eco-panel" title="虫巢分布地图" loading={loading}>
      {!AMAP_KEY ? (
        <Alert
          type="warning"
          showIcon
          message="未配置高德地图 Key"
          description="请在前端构建环境中配置 VITE_AMAP_KEY。若使用 2021-12-02 之后创建的高德 Web Key，还需要配置 VITE_AMAP_SECURITY_JS_CODE。"
        />
      ) : (
        <>
          <div className="amap-summary">
            <Space size={8} wrap>
              <Tag color="green">高德地图</Tag>
              <Tag>{points.length > 0 ? `${points.length} 个点位` : '暂无点位'}</Tag>
              {nests.length > 0 && (
                <>
                  {getSeverityTag('light')}
                  {getSeverityTag('medium')}
                  {getSeverityTag('severe')}
                </>
              )}
            </Space>
          </div>
          {mapError ? (
            <Alert
              type="error"
              showIcon
              message="高德地图加载失败"
              description={mapError}
            />
          ) : (
            <div ref={containerRef} className="amap-container" />
          )}
        </>
      )}
    </Card>
  );
};

export default NestMap;
