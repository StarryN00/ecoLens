import React from 'react';
import { Card } from 'antd';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import type { Nest, TaskImage } from '../../types/task';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

interface Props {
  nests: Nest[];
  images: TaskImage[];
  loading: boolean;
}

const NestMap: React.FC<Props> = ({ nests, images, loading }) => {
  const mapCenter: [number, number] =
    nests.length > 0
      ? [nests[0].latitude, nests[0].longitude]
      : images.length > 0 && images[0].latitude
        ? [images[0].latitude!, images[0].longitude!]
        : [30.25, 120.15];

  return (
    <Card title="虫巢分布地图" loading={loading}>
      {nests.length > 0 ? (
        <div style={{ height: 500 }}>
          <MapContainer center={mapCenter} zoom={16} style={{ height: '100%', width: '100%' }}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {nests.map((nest) => (
              <Marker key={nest.id} position={[nest.latitude, nest.longitude]}>
                <Popup>
                  <div>
                    <strong>{nest.nest_code}</strong><br />
                    严重程度: {nest.severity}<br />
                    置信度: {(nest.confidence * 100).toFixed(1)}%<br />
                    检测次数: {nest.detection_count}
                  </div>
                </Popup>
              </Marker>
            ))}
          </MapContainer>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '50px' }}>
          <p>暂无虫巢位置数据</p>
        </div>
      )}
    </Card>
  );
};

export default NestMap;
