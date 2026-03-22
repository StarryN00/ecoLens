import React, { useState, useEffect } from 'react';
import { Button, Modal, Table, Tag, message } from 'antd';
import { jsPDF } from 'jspdf';
import 'jspdf-autotable';
import * as XLSX from 'xlsx';
import { DownloadOutlined, FilePdfOutlined, FileExcelOutlined } from '@ant-design/icons';

interface Nest {
  id: string;
  nest_code: string;
  latitude: number;
  longitude: number;
  severity: string;
  confidence: number;
  detection_count: number;
}

interface ReportData {
  task_name: string;
  area_name: string;
  operator: string;
  created_at: string;
  completed_at?: string;
  total_images: number;
  processed_images: number;
  nests: Nest[];
}

interface ReportGeneratorProps {
  data: ReportData;
}

const ReportGenerator: React.FC<ReportGeneratorProps> = ({ data }) => {
  const [modalVisible, setModalVisible] = useState(false);

  const exportPDF = () => {
    const doc = new jsPDF();
    
    // 标题
    doc.setFontSize(20);
    doc.text('樟巢螟巡检报告', 105, 20, { align: 'center' });
    
    // 基本信息
    doc.setFontSize(12);
    doc.text(`任务名称: ${data.task_name}`, 20, 40);
    doc.text(`巡检区域: ${data.area_name || '-'}`, 20, 50);
    doc.text(`操作员: ${data.operator || '-'}`, 20, 60);
    doc.text(`创建时间: ${new Date(data.created_at).toLocaleString()}`, 20, 70);
    doc.text(`完成时间: ${data.completed_at ? new Date(data.completed_at).toLocaleString() : '-'}`, 20, 80);
    
    // 统计信息
    doc.text('统计信息', 20, 95);
    doc.text(`图片总数: ${data.total_images}`, 30, 105);
    doc.text(`已处理: ${data.processed_images}`, 30, 115);
    doc.text(`发现虫巢: ${data.nests.length} 个`, 30, 125);
    
    // 虫巢列表表格
    const tableData = data.nests.map(nest => [
      nest.nest_code,
      nest.latitude.toFixed(6),
      nest.longitude.toFixed(6),
      nest.severity === 'severe' ? '重度' : nest.severity === 'medium' ? '中度' : '轻度',
      `${(nest.confidence * 100).toFixed(1)}%`,
      nest.detection_count
    ]);
    
    (doc as any).autoTable({
      startY: 140,
      head: [['编号', '纬度', '经度', '严重程度', '置信度', '检测次数']],
      body: tableData,
      theme: 'grid',
      styles: { fontSize: 10 },
      headStyles: { fillColor: [66, 139, 202] }
    });
    
    doc.save(`巡检报告_${data.task_name}_${new Date().toISOString().split('T')[0]}.pdf`);
    message.success('PDF报告已导出');
  };

  const exportExcel = () => {
    const wb = XLSX.utils.book_new();
    
    // 基本信息sheet
    const infoData = [
      ['任务名称', data.task_name],
      ['巡检区域', data.area_name || '-'],
      ['操作员', data.operator || '-'],
      ['创建时间', new Date(data.created_at).toLocaleString()],
      ['完成时间', data.completed_at ? new Date(data.completed_at).toLocaleString() : '-'],
      ['图片总数', data.total_images],
      ['已处理', data.processed_images],
      ['虫巢数量', data.nests.length],
    ];
    const infoWs = XLSX.utils.aoa_to_sheet(infoData);
    XLSX.utils.book_append_sheet(wb, infoWs, '基本信息');
    
    // 虫巢列表sheet
    const nestsData = data.nests.map(nest => ({
      '编号': nest.nest_code,
      '纬度': nest.latitude,
      '经度': nest.longitude,
      '严重程度': nest.severity === 'severe' ? '重度' : nest.severity === 'medium' ? '中度' : '轻度',
      '置信度': `${(nest.confidence * 100).toFixed(1)}%`,
      '检测次数': nest.detection_count,
    }));
    const nestsWs = XLSX.utils.json_to_sheet(nestsData);
    XLSX.utils.book_append_sheet(wb, nestsWs, '虫巢列表');
    
    XLSX.writeFile(wb, `巡检报告_${data.task_name}_${new Date().toISOString().split('T')[0]}.xlsx`);
    message.success('Excel报告已导出');
  };

  const exportCSV = () => {
    const csvData = data.nests.map(nest => ({
      编号: nest.nest_code,
      纬度: nest.latitude,
      经度: nest.longitude,
      严重程度: nest.severity,
      置信度: nest.confidence,
      检测次数: nest.detection_count,
    }));
    
    const ws = XLSX.utils.json_to_sheet(csvData);
    const csv = XLSX.utils.sheet_to_csv(ws);
    
    const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `虫巢数据_${data.task_name}_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    
    message.success('CSV文件已导出');
  };

  return (
    <>
      <Button 
        type="primary" 
        icon={<DownloadOutlined />}
        onClick={() => setModalVisible(true)}
      >
        导出报告
      </Button>
      
      <Modal
        title="导出报告"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Button 
            icon={<FilePdfOutlined />} 
            size="large"
            onClick={exportPDF}
            block
          >
            导出PDF报告
          </Button>
          <Button 
            icon={<FileExcelOutlined />} 
            size="large"
            onClick={exportExcel}
            block
          >
            导出Excel报告
          </Button>
          <Button 
            size="large"
            onClick={exportCSV}
            block
          >
            导出CSV数据
          </Button>
        </div>
      </Modal>
    </>
  );
};

export default ReportGenerator;
