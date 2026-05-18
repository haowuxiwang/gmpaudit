import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Button,
  Card,
  Col,
  Empty,
  Input,
  List,
  Modal,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  Upload,
  message,
} from 'antd';
import {
  BranchesOutlined,
  BuildOutlined,
  DeleteOutlined,
  SearchOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import ReactECharts from 'echarts-for-react';
import { useSearchParams } from 'react-router-dom';

import { kgApi } from '../services/api';
import type { GraphData, GraphNode, KGDocument, KGQueryResult, KGStatus } from '../types/api';

const { Title, Paragraph, Text } = Typography;

const CATEGORY_COLORS: Record<string, string> = {
  concept: '#2563eb',
  organization: '#10b981',
  person: '#f59e0b',
  method: '#7c3aed',
  regulation: '#0f766e',
  unknown: '#94a3b8',
};

const KnowledgeGraphPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialQuery = searchParams.get('q') || '';
  const [status, setStatus] = useState<KGStatus | null>(null);
  const [documents, setDocuments] = useState<KGDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [queryText, setQueryText] = useState(initialQuery);
  const [queryResults, setQueryResults] = useState<KGQueryResult['results']>([]);
  const [queryLoading, setQueryLoading] = useState(false);
  const [buildLogs, setBuildLogs] = useState('');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [uploading, setUploading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [statusResult, docsResult] = await Promise.allSettled([
        kgApi.getStatus(),
        kgApi.getDocuments(),
      ]);

      if (statusResult.status === 'fulfilled') setStatus(statusResult.value);
      if (docsResult.status === 'fulfilled') setDocuments(docsResult.value.documents || []);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadGraphData = useCallback(async () => {
    setGraphLoading(true);
    try {
      const data = await kgApi.getGraphData();
      setGraphData(data);
    } catch {
      setGraphData(null);
    } finally {
      setGraphLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    if (status?.built) {
      void loadGraphData();
    }
  }, [loadGraphData, status?.built]);

  useEffect(() => {
    if (!building) return;

    pollRef.current = setInterval(async () => {
      try {
        const buildStatus = await kgApi.getBuildStatus();
        setBuildLogs((buildStatus.recent_logs || []).join('\n'));
        if (!buildStatus.building) {
          setBuilding(false);
          message.success('知识图谱构建完成');
          void loadData();
          void loadGraphData();
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      } catch {
        setBuilding(false);
      }
    }, 4000);

    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [building, loadData, loadGraphData]);

  const handleBuild = async (force = false) => {
    try {
      setBuilding(true);
      await kgApi.build(force);
      message.info('图谱构建已在后台启动');
    } catch (error: any) {
      setBuilding(false);
      message.error(error?.response?.data?.detail || '启动图谱构建失败');
    }
  };

  const handleQuery = useCallback(async (value?: string) => {
    const nextQuery = (value ?? queryText).trim();
    if (!nextQuery) {
      message.warning('请输入法规或发现的查询词');
      return;
    }

    setQueryLoading(true);
    setSearchParams({ q: nextQuery }, { replace: true });
    try {
      const result = await kgApi.query(nextQuery);
      setQueryResults(result?.results || []);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '查询失败');
      setQueryResults([]);
    } finally {
      setQueryLoading(false);
    }
  }, [queryText, setSearchParams]);

  useEffect(() => {
    if (initialQuery && status?.built) {
      void handleQuery(initialQuery);
    }
  }, [handleQuery, initialQuery, status?.built]);

  const handleUpload: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options;
    setUploading(true);
    try {
      const result = await kgApi.uploadDocument(file as File);
      onSuccess?.(result);
      message.success(`已上传 ${result.filename}`);
      void loadData();
    } catch (error) {
      onError?.(error as Error);
      message.error('上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = (filename: string) => {
    Modal.confirm({
      title: '删除源文档',
      content: `确认从图谱输入集中移除 ${filename}？`,
      okText: '删除',
      okType: 'danger',
      onOk: async () => {
        try {
          await kgApi.deleteDocument(filename);
          message.success('文档已移除');
          void loadData();
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  const focusedGraph = useMemo(() => {
    if (!graphData) return null;

    const searchTerms = new Set(
      queryResults
        .flatMap((item) => [item.regulation, item.title, item.chapter])
        .filter(Boolean)
        .map((item) => item.toLowerCase()),
    );

    const sourceNodes =
      searchTerms.size === 0
        ? graphData.nodes.slice(0, 120)
        : graphData.nodes.filter((node) => {
            const haystack = `${node.name} ${node.description || ''} ${node.category}`.toLowerCase();
            return Array.from(searchTerms).some((term) => haystack.includes(term));
          }).slice(0, 80);

    const selectedIds = new Set(sourceNodes.map((node) => node.id));
    const links = graphData.edges.filter((edge) => selectedIds.has(edge.source) || selectedIds.has(edge.target)).slice(0, 160);
    links.forEach((edge) => {
      selectedIds.add(edge.source);
      selectedIds.add(edge.target);
    });

    return {
      nodes: graphData.nodes.filter((node) => selectedIds.has(node.id)).slice(0, 140),
      edges: links,
    };
  }, [graphData, queryResults]);

  const chartOption = useMemo(() => {
    if (!focusedGraph) return null;
    const categories = Array.from(new Set(focusedGraph.nodes.map((node) => node.category)));

    return {
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            const description = params.data.description ? `<br/>${params.data.description}` : '';
            return `<strong>${params.data.name}</strong><br/>${params.data.category}${description}`;
          }
          return params.data.label || '关系';
        },
      },
      legend: { data: categories, bottom: 0 },
      series: [
        {
          type: 'graph',
          layout: 'force',
          roam: true,
          data: focusedGraph.nodes.map((node) => ({
            id: node.id,
            name: node.name,
            category: categories.indexOf(node.category),
            description: node.description,
            symbolSize: 18,
            itemStyle: {
              color: CATEGORY_COLORS[node.category] || CATEGORY_COLORS.unknown,
            },
          })),
          links: focusedGraph.edges.map((edge) => ({
            source: edge.source,
            target: edge.target,
            label: { show: false },
          })),
          categories: categories.map((name) => ({ name })),
          label: { show: true, fontSize: 11 },
          force: {
            repulsion: 150,
            edgeLength: [40, 140],
          },
          lineStyle: {
            color: '#94a3b8',
            opacity: 0.55,
          },
          emphasis: {
            focus: 'adjacency',
          },
        },
      ],
    };
  }, [focusedGraph]);

  const docColumns = [
    { title: '文件名', dataIndex: 'filename', key: 'filename' },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: 120,
      render: (size: number) => `${(size / 1024).toFixed(1)} KB`,
    },
    {
      title: '修改时间',
      dataIndex: 'modified',
      key: 'modified',
      width: 220,
      render: (value: string) => (value ? new Date(value).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 90,
      render: (_: unknown, record: KGDocument) => (
        <Button type="link" danger size="small" icon={<DeleteOutlined />} onClick={() => handleDelete(record.filename)}>
          删除
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Card
        bordered={false}
        style={{
          marginBottom: 24,
          borderRadius: 12,
          background: '#FFFFFF',
          borderLeft: '4px solid #D97757',
        }}
        styles={{ body: { padding: 28 } }}
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Tag color="#D97757" style={{ borderRadius: 999, alignSelf: 'flex-start' }}>
            知识图谱
          </Tag>
          <Title level={2} style={{ color: '#1A1A1A', margin: 0 }}>
            基于法规文档构建知识图谱，支持语义检索
          </Title>
          <Paragraph style={{ color: '#6B7280', fontSize: 16, marginBottom: 0 }}>
            使用与审计智能体相同的检索词查询图谱，在审批报告前审查关联的法规概念
          </Paragraph>
          <Input.Search
            placeholder="试试：偏差处理、CAPA、文件管理"
            enterButton="查询图谱"
            size="large"
            value={queryText}
            onChange={(event) => setQueryText(event.target.value)}
            onSearch={() => void handleQuery()}
            loading={queryLoading}
            disabled={!status?.built}
          />
        </Space>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} md={8}>
          <Card bordered={false} loading={loading} style={{ borderRadius: 12 }}>
            <Statistic title="法规文档" value={documents.length} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} loading={loading} style={{ borderRadius: 12 }}>
            <Statistic title="图谱文件" value={status?.file_count || 0} prefix={<BranchesOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} loading={loading} style={{ borderRadius: 12 }}>
            <Statistic title="图谱状态" value={status?.built ? '已构建' : '未构建'} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={8}>
          <Card bordered={false} style={{ borderRadius: 12 }} title="图谱操作">
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Button type="primary" icon={<BuildOutlined />} loading={building} onClick={() => void handleBuild(false)} block>
                {status?.built ? '重新构建' : '构建图谱'}
              </Button>
              <Button onClick={() => void handleBuild(true)} disabled={building || !documents.length} block>
                强制重建
              </Button>
              <Upload customRequest={handleUpload} showUploadList={false} accept=".txt,.md" disabled={uploading}>
                <Button icon={<UploadOutlined />} loading={uploading} block>
                  上传法规文档
                </Button>
              </Upload>
              <Text type="secondary">仅支持文本和 Markdown 文件</Text>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card bordered={false} style={{ borderRadius: 12 }} title="检索结果">
            {queryResults.length > 0 ? (
              <List
                dataSource={queryResults}
                renderItem={(item) => (
                  <List.Item>
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                      <Space wrap>
                        <Tag color="blue">{item.regulation}</Tag>
                        {item.chapter && <Tag>{item.chapter}</Tag>}
                        {item.title && <Text strong>{item.title}</Text>}
                      </Space>
                      <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>{item.content}</Paragraph>
                    </Space>
                  </List.Item>
                )}
              />
            ) : (
              <Empty description={status?.built ? '执行图谱查询以检查证据' : '请先构建图谱'} />
            )}
          </Card>
        </Col>
      </Row>

      {building && (
        <Card bordered={false} style={{ marginBottom: 24, borderRadius: 12 }} title="构建日志">
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', maxHeight: 220, overflow: 'auto' }}>
            {buildLogs || '等待构建输出...'}
          </pre>
        </Card>
      )}

      <Card
        bordered={false}
        style={{ marginBottom: 24, borderRadius: 12 }}
        title="聚焦视图"
        extra={<Button type="link" icon={<SearchOutlined />} onClick={() => void loadGraphData()}>刷新图谱</Button>}
      >
        {graphLoading ? (
          <div style={{ height: 520, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>加载图谱中...</div>
        ) : chartOption ? (
          <div style={{ height: 520 }}>
            <ReactECharts
              option={chartOption}
              style={{ height: '100%' }}
              onEvents={{
                click: (params: any) => {
                  if (params.dataType === 'node') {
                    setSelectedNode(params.data);
                  }
                },
              }}
            />
          </div>
        ) : (
          <Empty description="暂无图谱数据" />
        )}
      </Card>

      <Card bordered={false} style={{ borderRadius: 12 }} title="法规库">
        <Table
          columns={docColumns}
          dataSource={documents}
          rowKey="filename"
          pagination={false}
          loading={loading}
          locale={{ emptyText: <Empty description="暂无已上传的法规源文件" /> }}
        />
      </Card>

      <Modal
        title={selectedNode?.name || '节点详情'}
        open={!!selectedNode}
        onCancel={() => setSelectedNode(null)}
        footer={null}
      >
        {selectedNode && (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Tag color={CATEGORY_COLORS[selectedNode.category] || CATEGORY_COLORS.unknown}>{selectedNode.category}</Tag>
            <Paragraph style={{ marginBottom: 0 }}>
              {selectedNode.description || '暂无节点描述'}
            </Paragraph>
          </Space>
        )}
      </Modal>
    </div>
  );
};

export default KnowledgeGraphPage;
