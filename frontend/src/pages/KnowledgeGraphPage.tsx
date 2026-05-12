import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Card, Col, Input, List, Modal, Row, Space, Table, Tag, Typography, Upload, message } from 'antd';
import { BranchesOutlined, BuildOutlined, DeleteOutlined, InboxOutlined, SearchOutlined, UploadOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import ReactECharts from 'echarts-for-react';

import { kgApi } from '../services/api';
import type { KGDocument, KGStatus, GraphData, GraphNode, KGQueryResult } from '../types/api';

const { Title, Text, Paragraph } = Typography;

const CATEGORY_COLORS: Record<string, string> = {
  concept: '#1890ff',
  organization: '#52c41a',
  person: '#faad14',
  method: '#722ed1',
  unknown: '#d9d9d9',
};

const KnowledgeGraphPage: React.FC = () => {
  const [status, setStatus] = useState<KGStatus | null>(null);
  const [documents, setDocuments] = useState<KGDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);
  const [queryText, setQueryText] = useState('');
  const [queryResults, setQueryResults] = useState<KGQueryResult['results']>([]);
  const [queryLoading, setQueryLoading] = useState(false);
  const [buildLogs, setBuildLogs] = useState('');
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [uploading, setUploading] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logRef = useRef<HTMLPreElement>(null);

  const loadData = useCallback(async () => {
    try {
      const [statusRes, docsRes] = await Promise.allSettled([
        kgApi.getStatus(),
        kgApi.getDocuments(),
      ]);
      if (statusRes.status === 'fulfilled') setStatus(statusRes.value);
      if (docsRes.status === 'fulfilled') setDocuments((docsRes.value as any)?.documents || []);
    } catch {
      // silent
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
      // Graph data not available
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
  }, [status?.built, loadGraphData]);

  // Poll build status
  useEffect(() => {
    if (!building) return;
    pollRef.current = setInterval(async () => {
      try {
        const buildStatus = await kgApi.getBuildStatus();
        setBuildLogs((buildStatus as any).recent_logs || '');
        if (!buildStatus.building) {
          setBuilding(false);
          message.success('知识图谱索引构建完成');
          void loadData();
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      } catch {
        // silent
      }
    }, 5000);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [building, loadData]);

  // Auto-scroll build logs
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [buildLogs]);

  const handleBuild = async (force = false) => {
    try {
      setBuilding(true);
      await kgApi.build(force);
      message.info('索引构建已启动，这可能需要几分钟...');
    } catch (err: any) {
      setBuilding(false);
      message.error(err?.response?.data?.detail || '启动构建失败');
    }
  };

  const handleQuery = async () => {
    if (!queryText.trim()) {
      message.warning('请输入查询内容');
      return;
    }
    setQueryLoading(true);
    setQueryResults([]);
    try {
      const result = await kgApi.query(queryText);
      setQueryResults(result?.results || []);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '查询失败');
    } finally {
      setQueryLoading(false);
    }
  };

  const handleUpload: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options;
    setUploading(true);
    try {
      const result = await kgApi.uploadDocument(file as File);
      onSuccess?.(result);
      message.success(`文件 ${result.filename} 上传成功`);
      void loadData();
    } catch (err) {
      onError?.(err as Error);
      message.error('上传失败');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = (filename: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除文件 ${filename} 吗？`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await kgApi.deleteDocument(filename);
          message.success('删除成功');
          void loadData();
        } catch {
          message.error('删除失败');
        }
      },
    });
  };

  // ECharts graph option
  const getChartOption = () => {
    if (!graphData) return null;

    // Limit to top 200 nodes for performance
    const nodes = graphData.nodes.slice(0, 200);
    const nodeIds = new Set(nodes.map((n) => n.id));
    const edges = graphData.edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));

    // Get unique categories
    const categories = Array.from(new Set(nodes.map((n) => n.category)));

    return {
      tooltip: {
        trigger: 'item',
        formatter: (params: any) => {
          if (params.dataType === 'node') {
            return `<strong>${params.data.name}</strong><br/>类型: ${params.data.category}<br/>${params.data.description || ''}`;
          }
          return params.data.label || '';
        },
      },
      legend: {
        data: categories,
        bottom: 0,
      },
      series: [
        {
          type: 'graph',
          layout: 'force',
          data: nodes.map((node) => ({
            id: node.id,
            name: node.name,
            category: categories.indexOf(node.category),
            description: node.description,
            symbolSize: 20,
            itemStyle: {
              color: CATEGORY_COLORS[node.category] || CATEGORY_COLORS.unknown,
            },
          })),
          links: edges.map((edge) => ({
            source: edge.source,
            target: edge.target,
            label: { show: false },
          })),
          categories: categories.map((name) => ({ name })),
          roam: true,
          label: {
            show: true,
            position: 'right',
            fontSize: 10,
          },
          force: {
            repulsion: 100,
            edgeLength: [50, 200],
          },
          emphasis: {
            focus: 'adjacency',
            lineStyle: { width: 3 },
          },
          lineStyle: {
            color: '#aaa',
            curveness: 0.1,
          },
        },
      ],
    };
  };

  const docColumns = [
    { title: '文件名', dataIndex: 'filename', key: 'filename' },
    {
      title: '大小',
      dataIndex: 'size',
      key: 'size',
      width: 100,
      render: (size: number) => `${(size / 1024).toFixed(1)} KB`,
    },
    {
      title: '修改时间',
      dataIndex: 'modified',
      key: 'modified',
      width: 200,
      render: (time: string) => (time ? new Date(time).toLocaleString() : '-'),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: KGDocument) => (
        <Button
          type="link"
          danger
          size="small"
          icon={<DeleteOutlined />}
          onClick={() => handleDelete(record.filename)}
        >
          删除
        </Button>
      ),
    },
  ];

  const isBuilt = status?.built;

  return (
    <div>
      <Title level={4}>知识图谱</Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        {/* Status card */}
        <Col span={6}>
          <Card loading={loading}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">索引状态</Text>
              <div style={{ fontSize: 24, fontWeight: 'bold' }}>
                {isBuilt ? <Tag color="success">已构建</Tag> : <Tag color="warning">未构建</Tag>}
              </div>
              {isBuilt && (
                <Text type="secondary">{status.file_count} 个索引文件</Text>
              )}
            </Space>
          </Card>
        </Col>

        {/* Input files card */}
        <Col span={6}>
          <Card loading={loading}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">法规文件</Text>
              <div style={{ fontSize: 24, fontWeight: 'bold' }}>{documents.length}</div>
              <Text type="secondary">GMP/ICH 法规文本</Text>
            </Space>
          </Card>
        </Col>

        {/* Build card */}
        <Col span={6}>
          <Card>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">构建索引</Text>
              <Button
                type="primary"
                icon={<BuildOutlined />}
                loading={building}
                onClick={() => void handleBuild(false)}
                block
              >
                {building ? '构建中...' : isBuilt ? '重新构建' : '构建索引'}
              </Button>
              {isBuilt && (
                <Button size="small" onClick={() => void handleBuild(true)}>
                  强制重建
                </Button>
              )}
            </Space>
          </Card>
        </Col>

        {/* Upload card */}
        <Col span={6}>
          <Card>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">上传法规文件</Text>
              <Upload
                customRequest={handleUpload}
                showUploadList={false}
                accept=".txt,.md"
                disabled={uploading}
              >
                <Button icon={<UploadOutlined />} loading={uploading} block>
                  {uploading ? '上传中...' : '选择文件'}
                </Button>
              </Upload>
              <Text type="secondary" style={{ fontSize: 11 }}>支持 .txt 和 .md 格式</Text>
            </Space>
          </Card>
        </Col>
      </Row>

      {/* Build logs */}
      {building && (
        <Card title="构建日志" size="small" style={{ marginBottom: 16 }}>
          <pre
            ref={logRef}
            style={{ maxHeight: 200, overflow: 'auto', fontSize: 12, background: '#f5f5f5', padding: 8, borderRadius: 4 }}
          >
            {buildLogs || '等待日志...'}
          </pre>
        </Card>
      )}

      {/* Graph visualization */}
      {isBuilt && (
        <Card
          title={<><BranchesOutlined /> 知识图谱可视化</>}
          size="small"
          style={{ marginBottom: 24 }}
          extra={<Button size="small" onClick={() => void loadGraphData()}>刷新图谱</Button>}
        >
          {graphLoading ? (
            <div style={{ height: 500, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              加载图谱数据中...
            </div>
          ) : graphData ? (
            <div style={{ height: 500 }}>
              <ReactECharts
                option={getChartOption() || {}}
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
            <div style={{ height: 500, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              暂无图谱数据
            </div>
          )}
          <div style={{ marginTop: 8 }}>
            <Text type="secondary">
              节点数: {graphData?.nodes.length || 0} | 边数: {graphData?.edges.length || 0}
              {graphData && graphData.nodes.length > 200 && ' (显示前 200 个节点)'}
            </Text>
          </div>
        </Card>
      )}

      {/* Regulation documents table */}
      <Card title="法规文档列表" size="small" style={{ marginBottom: 24 }}>
        <Table
          columns={docColumns}
          dataSource={documents}
          rowKey="filename"
          pagination={false}
          size="small"
          loading={loading}
        />
      </Card>

      {/* Query test area */}
      <Card title={<><SearchOutlined /> 知识图谱查询测试</>}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <Input.Search
            placeholder="输入 GMP 相关问题，例如：偏差处理的流程是什么？"
            enterButton="查询"
            size="large"
            value={queryText}
            onChange={(e) => setQueryText(e.target.value)}
            onSearch={() => void handleQuery()}
            loading={queryLoading}
            disabled={!isBuilt}
          />
          {!isBuilt && (
            <Text type="secondary">请先构建索引后再进行查询</Text>
          )}
          {queryResults.length > 0 && (
            <List
              header={<Text strong>查询结果 ({queryResults.length} 条)</Text>}
              bordered
              dataSource={queryResults}
              renderItem={(item, index) => (
                <List.Item>
                  <div style={{ width: '100%' }}>
                    <div style={{ marginBottom: 8 }}>
                      <Tag color="blue">{item.regulation}</Tag>
                      {item.chapter && <Tag>{item.chapter}</Tag>}
                      {item.title && <Text strong>{item.title}</Text>}
                    </div>
                    <Paragraph style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
                      {item.content}
                    </Paragraph>
                  </div>
                </List.Item>
              )}
            />
          )}
          {queryResults.length === 0 && queryText && !queryLoading && (
            <Card size="small" style={{ background: '#fffbe6' }}>
              <Text type="secondary">未找到相关结果</Text>
            </Card>
          )}
        </Space>
      </Card>

      {/* Node detail modal */}
      <Modal
        title="节点详情"
        open={!!selectedNode}
        onCancel={() => setSelectedNode(null)}
        footer={null}
        width={600}
      >
        {selectedNode && (
          <div>
            <p><strong>名称:</strong> {selectedNode.name}</p>
            <p><strong>类型:</strong> <Tag color={CATEGORY_COLORS[selectedNode.category]}>{selectedNode.category}</Tag></p>
            {selectedNode.description && (
              <p><strong>描述:</strong> {selectedNode.description}</p>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default KnowledgeGraphPage;
