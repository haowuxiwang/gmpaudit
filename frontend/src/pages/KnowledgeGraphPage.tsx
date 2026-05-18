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
          message.success('Knowledge graph build completed');
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
      message.info('Graph build started in the background');
    } catch (error: any) {
      setBuilding(false);
      message.error(error?.response?.data?.detail || 'Failed to start graph build');
    }
  };

  const handleQuery = useCallback(async (value?: string) => {
    const nextQuery = (value ?? queryText).trim();
    if (!nextQuery) {
      message.warning('Enter a regulation or finding query');
      return;
    }

    setQueryLoading(true);
    setSearchParams({ q: nextQuery }, { replace: true });
    try {
      const result = await kgApi.query(nextQuery);
      setQueryResults(result?.results || []);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || 'Query failed');
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
      message.success(`Uploaded ${result.filename}`);
      void loadData();
    } catch (error) {
      onError?.(error as Error);
      message.error('Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = (filename: string) => {
    Modal.confirm({
      title: 'Delete source document',
      content: `Remove ${filename} from the graph input set?`,
      okText: 'Delete',
      okType: 'danger',
      onOk: async () => {
        try {
          await kgApi.deleteDocument(filename);
          message.success('Document removed');
          void loadData();
        } catch {
          message.error('Delete failed');
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
          return params.data.label || 'relation';
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
    { title: 'Source document', dataIndex: 'filename', key: 'filename' },
    {
      title: 'Size',
      dataIndex: 'size',
      key: 'size',
      width: 120,
      render: (size: number) => `${(size / 1024).toFixed(1)} KB`,
    },
    {
      title: 'Modified',
      dataIndex: 'modified',
      key: 'modified',
      width: 220,
      render: (value: string) => (value ? new Date(value).toLocaleString() : '-'),
    },
    {
      title: 'Action',
      key: 'action',
      width: 90,
      render: (_: unknown, record: KGDocument) => (
        <Button type="link" danger size="small" icon={<DeleteOutlined />} onClick={() => handleDelete(record.filename)}>
          Delete
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
          borderRadius: 24,
          background: 'linear-gradient(135deg, #082f49 0%, #0f766e 100%)',
          color: '#fff',
        }}
        bodyStyle={{ padding: 28 }}
      >
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <Tag color="rgba(255,255,255,0.18)" style={{ borderRadius: 999, alignSelf: 'flex-start' }}>
            evidence graph
          </Tag>
          <Title level={2} style={{ color: '#fff', margin: 0 }}>
            Trace findings back to regulation evidence instead of trusting the report blindly.
          </Title>
          <Paragraph style={{ color: 'rgba(255,255,255,0.82)', fontSize: 16, marginBottom: 0 }}>
            Build the regulation graph, search it with the same terms your audit agent used, and inspect the connected concepts before approving a report.
          </Paragraph>
          <Input.Search
            placeholder="Try: deviation handling, CAPA, documentation control"
            enterButton="Query graph"
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
          <Card bordered={false} loading={loading} style={{ borderRadius: 20 }}>
            <Statistic title="Source documents" value={documents.length} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} loading={loading} style={{ borderRadius: 20 }}>
            <Statistic title="Graph files" value={status?.file_count || 0} prefix={<BranchesOutlined />} />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} loading={loading} style={{ borderRadius: 20 }}>
            <Statistic title="Graph status" value={status?.built ? 'Ready' : 'Not built'} />
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={8}>
          <Card bordered={false} style={{ borderRadius: 20 }} title="Graph operations">
            <Space direction="vertical" style={{ width: '100%' }} size={12}>
              <Button type="primary" icon={<BuildOutlined />} loading={building} onClick={() => void handleBuild(false)} block>
                {status?.built ? 'Rebuild graph' : 'Build graph'}
              </Button>
              <Button onClick={() => void handleBuild(true)} disabled={building || !documents.length} block>
                Force rebuild
              </Button>
              <Upload customRequest={handleUpload} showUploadList={false} accept=".txt,.md" disabled={uploading}>
                <Button icon={<UploadOutlined />} loading={uploading} block>
                  Upload regulation source
                </Button>
              </Upload>
              <Text type="secondary">Text and Markdown files only.</Text>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={16}>
          <Card bordered={false} style={{ borderRadius: 20 }} title="Evidence signal">
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
              <Empty description={status?.built ? 'Run a graph query to inspect evidence' : 'Build the graph first'} />
            )}
          </Card>
        </Col>
      </Row>

      {building && (
        <Card bordered={false} style={{ marginBottom: 24, borderRadius: 20 }} title="Build log">
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', maxHeight: 220, overflow: 'auto' }}>
            {buildLogs || 'Waiting for build output...'}
          </pre>
        </Card>
      )}

      <Card
        bordered={false}
        style={{ marginBottom: 24, borderRadius: 20 }}
        title="Focused graph view"
        extra={<Button type="link" icon={<SearchOutlined />} onClick={() => void loadGraphData()}>Refresh graph</Button>}
      >
        {graphLoading ? (
          <div style={{ height: 520, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Loading graph...</div>
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
          <Empty description="No graph data available" />
        )}
      </Card>

      <Card bordered={false} style={{ borderRadius: 20 }} title="Graph source library">
        <Table
          columns={docColumns}
          dataSource={documents}
          rowKey="filename"
          pagination={false}
          loading={loading}
          locale={{ emptyText: <Empty description="No graph source files uploaded" /> }}
        />
      </Card>

      <Modal
        title={selectedNode?.name || 'Node details'}
        open={!!selectedNode}
        onCancel={() => setSelectedNode(null)}
        footer={null}
      >
        {selectedNode && (
          <Space direction="vertical" size={12} style={{ width: '100%' }}>
            <Tag color={CATEGORY_COLORS[selectedNode.category] || CATEGORY_COLORS.unknown}>{selectedNode.category}</Tag>
            <Paragraph style={{ marginBottom: 0 }}>
              {selectedNode.description || 'No node description available.'}
            </Paragraph>
          </Space>
        )}
      </Modal>
    </div>
  );
};

export default KnowledgeGraphPage;
