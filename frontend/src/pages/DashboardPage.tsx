import React, { useState, useEffect } from 'react';
import { Row, Col, Typography, Card, Statistic } from 'antd';
import { FileTextOutlined, AuditOutlined, CheckCircleOutlined, WarningOutlined } from '@ant-design/icons';
import { auditApi, documentApi } from '../services/api';

const { Title } = Typography;

const DashboardPage: React.FC = () => {
  const [stats, setStats] = useState({ totalDocuments: 0, totalTasks: 0, completedTasks: 0, highRiskFindings: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      setLoading(true);
      const docResult = await documentApi.list(1, 1000);
      const tasksResult = await auditApi.listTasks();
      const tasks = tasksResult || [];

      setStats({
        totalDocuments: docResult?.length || 0,
        totalTasks: tasks.length,
        completedTasks: tasks.filter((t: any) => t.status === 'completed').length,
        highRiskFindings: 0,
      });
    } catch (error) {
      console.error('加载仪表盘数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Title level={4}>仪表盘</Title>
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="文档总数" value={stats.totalDocuments} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="审计任务" value={stats.totalTasks} prefix={<AuditOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="已完成" value={stats.completedTasks} prefix={<CheckCircleOutlined />} valueStyle={{ color: '#3f8600' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="高风险发现" value={stats.highRiskFindings} prefix={<WarningOutlined />} valueStyle={{ color: '#cf1322' }} />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default DashboardPage;
