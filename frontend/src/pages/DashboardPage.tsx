import React, { useState, useEffect } from 'react';
import { Row, Col, Typography, Card, Statistic, Spin } from 'antd';
import { FileTextOutlined, AuditOutlined, CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import { auditApi, documentApi } from '../services/api';

const { Title } = Typography;

const DashboardPage: React.FC = () => {
  const [stats, setStats] = useState({ totalDocuments: 0, totalTasks: 0, completedTasks: 0, highRiskFindings: 0 });
  const [dashboard, setDashboard] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { loadDashboardData(); }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const [docResult, tasksResult, dashResult] = await Promise.all([
        documentApi.list(1, 1000) as any,
        auditApi.listTasks() as any,
        auditApi.getDashboard() as any,
      ]);
      const tasks = tasksResult || [];
      setStats({
        totalDocuments: docResult?.length || 0,
        totalTasks: tasks.length,
        completedTasks: tasks.filter((t: any) => t.status === 'completed').length,
        highRiskFindings: dashResult?.severity_counts?.high || 0,
      });
      setDashboard(dashResult);
    } catch (error) {
      console.error('加载仪表盘数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const taskStatusOption = dashboard ? {
    title: { text: '任务状态分布', left: 'center' },
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data: [
        { value: dashboard.task_counts?.pending || 0, name: '待执行', itemStyle: { color: '#d9d9d9' } },
        { value: dashboard.task_counts?.running || 0, name: '运行中', itemStyle: { color: '#1890ff' } },
        { value: dashboard.task_counts?.completed || 0, name: '已完成', itemStyle: { color: '#52c41a' } },
        { value: dashboard.task_counts?.failed || 0, name: '失败', itemStyle: { color: '#ff4d4f' } },
      ].filter(d => d.value > 0),
    }],
  } : null;

  const severityOption = dashboard ? {
    title: { text: '发现严重程度分布', left: 'center' },
    tooltip: { trigger: 'axis' },
    xAxis: {
      type: 'category',
      data: ['高', '中', '低'],
      axisLabel: { formatter: (v: string) => ({ '高': '高 (High)', '中': '中 (Medium)', '低': '低 (Low)' }[v] || v) },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{
      type: 'bar',
      data: [
        { value: dashboard.severity_counts?.high || 0, itemStyle: { color: '#ff4d4f' } },
        { value: dashboard.severity_counts?.medium || 0, itemStyle: { color: '#faad14' } },
        { value: dashboard.severity_counts?.low || 0, itemStyle: { color: '#52c41a' } },
      ],
      barWidth: '40%',
    }],
  } : null;

  if (loading) return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;

  return (
    <div>
      <Title level={4}>仪表盘</Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card><Statistic title="文档总数" value={stats.totalDocuments} prefix={<FileTextOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="审计任务" value={stats.totalTasks} prefix={<AuditOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="已完成" value={stats.completedTasks} prefix={<CheckCircleOutlined />} valueStyle={{ color: '#3f8600' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="高风险发现" value={stats.highRiskFindings} prefix={<WarningOutlined />} valueStyle={{ color: '#cf1322' }} /></Card>
        </Col>
      </Row>
      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Card>{taskStatusOption && <ReactECharts option={taskStatusOption} style={{ height: 300 }} />}</Card>
        </Col>
        <Col span={12}>
          <Card>{severityOption && <ReactECharts option={severityOption} style={{ height: 300 }} />}</Card>
        </Col>
      </Row>
    </div>
  );
};

export default DashboardPage;
