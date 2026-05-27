import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Badge,
  Button,
  Card,
  Collapse,
  Col,
  Form,
  Input,
  InputNumber,
  Row,
  Select,
  Space,
  Spin,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  ApiOutlined,
  CheckCircleFilled,
  SaveOutlined,
  SendOutlined,
  SettingOutlined,
} from '@ant-design/icons';

import { configApi, LLMModel } from '../services/api';
import type { ConfigMap } from '../types/api';
import { THEME } from '../constants/theme';

const { Title, Text, Paragraph } = Typography;

const PROVIDER_DEFAULTS: Record<string, { defaultUrl: string; defaultModel: string; keyPlaceholder: string; color: string; icon: string }> = {
  mimo: { defaultUrl: 'https://api.xiaomimimo.com/v1', defaultModel: 'mimo-v2.5-pro', keyPlaceholder: 'sk-...', color: '#FF6B35', icon: 'M' },
  deepseek: { defaultUrl: 'https://api.deepseek.com/v1', defaultModel: 'deepseek-chat', keyPlaceholder: 'sk-...', color: '#4F46E5', icon: 'D' },
  qwen: { defaultUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', defaultModel: 'qwen-plus', keyPlaceholder: 'sk-...', color: '#7C3AED', icon: 'Q' },
  glm: { defaultUrl: 'https://open.bigmodel.cn/api/paas/v4', defaultModel: 'glm-4-flash', keyPlaceholder: 'token', color: '#059669', icon: 'G' },
  siliconflow: { defaultUrl: 'https://api.siliconflow.cn/v1', defaultModel: 'deepseek-ai/DeepSeek-V3.2', keyPlaceholder: 'sk-...', color: '#0EA5E9', icon: 'S' },
  openai: { defaultUrl: 'https://api.openai.com/v1', defaultModel: 'gpt-4o', keyPlaceholder: 'sk-...', color: '#10A37F', icon: 'O' },
  anthropic: { defaultUrl: 'https://api.anthropic.com', defaultModel: 'claude-sonnet-4-20250514', keyPlaceholder: 'sk-ant-...', color: '#D97706', icon: 'A' },
  openrouter: { defaultUrl: 'https://openrouter.ai/api/v1', defaultModel: 'deepseek/deepseek-chat', keyPlaceholder: 'sk-or-...', color: '#6366F1', icon: 'R' },
};

const PROVIDER_MODELS: Record<string, string[]> = {
  mimo: ['mimo-v2.5-pro'],
  deepseek: ['deepseek-chat', 'deepseek-reasoner'],
  qwen: ['qwen-plus', 'qwen-turbo', 'qwen-max', 'qwen-long'],
  glm: ['glm-4-flash', 'glm-4-plus', 'glm-4-long'],
  siliconflow: ['deepseek-ai/DeepSeek-V3.2', 'Qwen/Qwen2.5-72B-Instruct', 'meta-llama/Meta-Llama-3.1-70B-Instruct'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'o1-mini'],
  anthropic: ['claude-sonnet-4-20250514', 'claude-haiku-4-5-20251001', 'claude-opus-4-20250514'],
  openrouter: ['deepseek/deepseek-chat', 'anthropic/claude-sonnet-4', 'openai/gpt-4o'],
};

interface TestResult {
  provider: string;
  success: boolean;
  model_used?: string;
  latency_ms?: number;
  error?: string | null;
}

const SettingsPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [testWebhookResult, setTestWebhookResult] = useState('');
  const [testingProvider, setTestingProvider] = useState<string | null>(null);
  const [providerTestResult, setProviderTestResult] = useState<TestResult | null>(null);
  const [providers, setProviders] = useState<LLMModel[]>([]);

  useEffect(() => {
    void loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [models, result]: [LLMModel[], ConfigMap] = await Promise.all([
        configApi.getModels(),
        configApi.getAll(),
      ]);

      setProviders(models);

      const flat: Record<string, string> = {};
      if (result) {
        for (const [key, val] of Object.entries(result)) {
          flat[key] = val.value ?? '';
        }
      }

      const isPlaceholder = (v: string) => !v || /^your_.*_here$/i.test(v);
      for (const p of models) {
        const defaults = PROVIDER_DEFAULTS[p.id] || {};
        const modelKey = `${p.id}_model`;
        const urlKey = `${p.id}_base_url`;
        if (isPlaceholder(flat[modelKey] || '') && defaults.defaultModel) {
          flat[modelKey] = defaults.defaultModel;
        }
        if (isPlaceholder(flat[urlKey] || '') && defaults.defaultUrl) {
          flat[urlKey] = defaults.defaultUrl;
        }
      }

      setConfig(flat);
      setDraft(flat);
    } catch {
      message.error('加载配置失败');
    } finally {
      setLoading(false);
    }
  };

  const getVal = (key: string, fallback = '') => draft[key] ?? fallback;

  const setVal = (key: string, value: string) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
  };

  // Track dirty keys per provider
  const dirtyKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const [key, value] of Object.entries(draft)) {
      if (value !== (config[key] || '')) {
        keys.add(key);
      }
    }
    return keys;
  }, [draft, config]);

  const providerDirtyCount = (providerId: string) => {
    let count = 0;
    for (const key of Array.from(dirtyKeys)) {
      if (key.startsWith(`${providerId}_`) || key === 'agent_llm_provider') count++;
    }
    return count;
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      const changes: Record<string, string> = {};
      for (const [key, value] of Object.entries(draft)) {
        if (value !== (config[key] || '')) {
          changes[key] = value;
        }
      }

      if (Object.keys(changes).length === 0) {
        message.info('无配置变更');
        return;
      }

      for (const [key, value] of Object.entries(changes)) {
        if (key.includes('api_key') && value && value.startsWith('your_')) {
          const providerName = key.replace('_api_key', '');
          message.warning(`${providerName} 的 API Key 为占位符值，请填写真实密钥`);
          setSaving(false);
          return;
        }
      }

      await configApi.batchUpdate(changes);
      setConfig((prev) => ({ ...prev, ...changes }));
      message.success(`已保存 ${Object.keys(changes).length} 项配置`);
    } catch {
      message.error('保存配置失败');
    } finally {
      setSaving(false);
    }
  };

  const handleTestWebhook = async () => {
    try {
      const webhookUrl = getVal('feishu_webhook_url');
      if (!webhookUrl) {
        message.warning('请先输入 Webhook 地址');
        return;
      }

      setTestWebhookResult('发送中...');
      const payload: Record<string, string> = { feishu_webhook_url: webhookUrl };
      const secret = getVal('feishu_webhook_secret');
      if (secret) payload.feishu_webhook_secret = secret;

      await configApi.batchUpdate(payload);
      const result: { success: boolean; error: string | null } = await configApi.testWebhook();
      if (result.success) {
        setTestWebhookResult('测试消息发送成功');
        message.success('测试消息发送成功');
      } else {
        setTestWebhookResult(`Webhook 测试失败: ${result?.error || '未知错误'}`);
      }
    } catch (error: unknown) {
      const detail = error instanceof Error ? error.message : '网络或地址异常';
      setTestWebhookResult(`Webhook 测试失败: ${detail}`);
    }
  };

  const handleTestProvider = async (provider: LLMModel) => {
    const apiKey = getVal(`${provider.id}_api_key`);
    if (!apiKey) {
      message.warning('请先输入 API Key');
      return;
    }

    const defaults = PROVIDER_DEFAULTS[provider.id] || {};
    setTestingProvider(provider.id);
    setProviderTestResult(null);
    try {
      const raw = await configApi.testLLM({
        provider: provider.id,
        api_key: apiKey,
        base_url: getVal(`${provider.id}_base_url`, defaults.defaultUrl || ''),
        model: getVal(`${provider.id}_model`, provider.model || defaults.defaultModel || ''),
      });
      const result: TestResult = { ...raw, provider: provider.id };
      setProviderTestResult(result);
      if (result.success) {
        message.success(`${provider.name} 连接成功 (${result.latency_ms}ms)`);
      }
    } catch (error: unknown) {
      setProviderTestResult({
        provider: provider.id,
        success: false,
        error: error instanceof Error ? error.message : '连接失败',
      });
    } finally {
      setTestingProvider(null);
    }
  };

  const isConfigured = (provider: LLMModel) => {
    const key = getVal(`${provider.id}_api_key`);
    return Boolean(key) && !key.startsWith('your_');
  };
  const defaultProvider = getVal('agent_llm_provider', 'mimo');

  const renderProviderPanel = (provider: LLMModel) => {
    const defaults = PROVIDER_DEFAULTS[provider.id] || {};
    const configured = isConfigured(provider);
    const isDefault = defaultProvider === provider.id;
    const testResult = providerTestResult?.provider === provider.id ? providerTestResult : null;
    const dirty = providerDirtyCount(provider.id) > 0;
    const modelOptions = (PROVIDER_MODELS[provider.id] || []).map((m) => ({ value: m, label: m }));

    return {
      key: provider.id,
      className: 'provider-panel',
      label: (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', paddingRight: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Badge dot={dirty} color="orange" offset={[-2, 2]}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: 8,
                  background: `${defaults.color || THEME.primary}15`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: 16,
                  fontWeight: 700,
                  color: defaults.color || THEME.primary,
                }}
              >
                {defaults.icon || provider.id[0].toUpperCase()}
              </div>
            </Badge>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Text strong style={{ fontSize: 14 }}>{provider.name}</Text>
                {isDefault && <Tag color="orange" style={{ margin: 0, fontSize: 11 }}>默认</Tag>}
              </div>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {configured ? `模型: ${getVal(`${provider.id}_model`, defaults.defaultModel)}` : '未配置'}
              </Text>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Tooltip title={configured ? '已配置' : '未配置'}>
              <CheckCircleFilled style={{ fontSize: 16, color: configured ? THEME.success : THEME.pending }} />
            </Tooltip>
            {!isDefault && (
              <Button
                size="small"
                type="link"
                onClick={(e) => { e.stopPropagation(); setVal('agent_llm_provider', provider.id); }}
                style={{ padding: 0, fontSize: 12 }}
              >
                设为默认
              </Button>
            )}
          </div>
        </div>
      ),
      children: (
        <Form layout="vertical" size="small">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label={<Text type="secondary" style={{ fontSize: 12 }}>模型</Text>} style={{ marginBottom: 12 }}>
                <Select
                  showSearch
                  allowClear
                  value={getVal(`${provider.id}_model`, defaults.defaultModel || provider.model) || undefined}
                  onChange={(value) => setVal(`${provider.id}_model`, value || '')}
                  placeholder={defaults.defaultModel || provider.model}
                  options={modelOptions}
                  style={{ width: '100%' }}
                  popupMatchSelectWidth={false}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label={<Text type="secondary" style={{ fontSize: 12 }}>接口地址</Text>} style={{ marginBottom: 12 }}>
                <Input
                  value={getVal(`${provider.id}_base_url`, defaults.defaultUrl || '')}
                  onChange={(e) => setVal(`${provider.id}_base_url`, e.target.value)}
                  placeholder={defaults.defaultUrl || ''}
                  style={{ borderRadius: 8 }}
                />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item label={<Text type="secondary" style={{ fontSize: 12 }}>API 密钥</Text>} style={{ marginBottom: 12 }}>
            <Input.Password
              value={getVal(`${provider.id}_api_key`)}
              onChange={(e) => setVal(`${provider.id}_api_key`, e.target.value)}
              placeholder={defaults.keyPlaceholder || 'sk-...'}
              style={{ borderRadius: 8 }}
            />
          </Form.Item>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Button
              size="small"
              icon={<ApiOutlined />}
              loading={testingProvider === provider.id}
              onClick={() => void handleTestProvider(provider)}
              style={{ borderRadius: 8 }}
            >
              测试连接
            </Button>
          </div>
          {testResult && (
            <Alert
              type={testResult.success ? 'success' : 'error'}
              showIcon
              message={
                <Text style={{ fontSize: 12 }}>
                  {testResult.success
                    ? `${testResult.model_used} - ${testResult.latency_ms}ms`
                    : testResult.error}
                </Text>
              }
              style={{ marginTop: 8, borderRadius: 8 }}
            />
          )}
        </Form>
      ),
    };
  };

  const totalDirty = dirtyKeys.size;

  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  return (
    <div>
      <Card
        bordered={false}
        style={{
          marginBottom: 24,
          borderRadius: 12,
          borderLeft: `4px solid ${THEME.primary}`,
        }}
        styles={{ body: { padding: 28 } }}
      >
        <Title level={2} style={{ color: THEME.text, marginTop: 0 }}>
          系统设置
        </Title>
        <Paragraph style={{ color: THEME.textSecondary, fontSize: 16, marginBottom: 0 }}>
          选择审计任务的默认大模型，配置各模型的密钥和参数
        </Paragraph>
      </Card>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>配置管理</Title>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>
          {totalDirty > 0 ? `保存配置 (${totalDirty})` : '保存配置'}
        </Button>
      </div>

      <Tabs
        defaultActiveKey="llm"
        items={[
          {
            key: 'llm',
            label: '大模型配置',
            children: (
              <>
                {/* Default provider selector */}
                <Card
                  bordered={false}
                  style={{ borderRadius: 12, marginBottom: 16, background: THEME.bgWarm }}
                  styles={{ body: { padding: '12px 20px' } }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <SettingOutlined style={{ color: THEME.primary, fontSize: 16 }} />
                    <Text strong>默认审计模型</Text>
                    <Select
                      value={defaultProvider}
                      onChange={(value) => setVal('agent_llm_provider', value)}
                      style={{ width: 200 }}
                      options={providers.map((p) => ({
                        value: p.id,
                        label: `${p.name}${isConfigured(p) ? ' ✓' : ''}`,
                      }))}
                    />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      审计任务将使用此模型进行分析
                    </Text>
                  </div>
                </Card>

                {/* Provider collapse panels */}
                <Collapse
                  defaultActiveKey={[defaultProvider]}
                  items={providers.map(renderProviderPanel)}
                  style={{ background: THEME.bgContainer, borderRadius: 12, border: `1px solid ${THEME.border}` }}
                />
              </>
            ),
          },
          {
            key: 'feishu',
            label: '飞书通知',
            children: (
              <Card bordered={false} style={{ borderRadius: 12 }}>
                <Card type="inner" title="Webhook 配置指南" style={{ marginBottom: 16, borderRadius: 8 }}>
                  <ol style={{ margin: 0, paddingLeft: 20 }}>
                    <li>创建或打开飞书群机器人</li>
                    <li>复制生成的 Webhook 地址</li>
                    <li>如需签名验证，启用签名校验并填入密钥</li>
                    <li>将地址粘贴到下方并发送测试消息</li>
                  </ol>
                </Card>
                <Form layout="vertical">
                  <Form.Item label="Webhook 地址">
                    <Input
                      value={getVal('feishu_webhook_url')}
                      onChange={(event) => setVal('feishu_webhook_url', event.target.value)}
                      placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
                    />
                  </Form.Item>
                  <Form.Item label="签名密钥" extra="留空则不更新已有密钥">
                    <Input.Password
                      value={getVal('feishu_webhook_secret')}
                      onChange={(event) => setVal('feishu_webhook_secret', event.target.value)}
                      placeholder="可选签名密钥"
                    />
                  </Form.Item>
                  <Form.Item>
                    <Space direction="vertical" size={8}>
                      <Space>
                        <Button icon={<SendOutlined />} onClick={handleTestWebhook}>
                          保存并测试
                        </Button>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          将先保存配置再发送测试消息
                        </Text>
                      </Space>
                      {testWebhookResult && (
                        <Alert
                          type={testWebhookResult.includes('成功') ? 'success' : 'error'}
                          showIcon
                          message={testWebhookResult}
                        />
                      )}
                    </Space>
                  </Form.Item>
                </Form>
              </Card>
            ),
          },
          {
            key: 'system',
            label: '运行参数',
            children: (
              <Card bordered={false} style={{ borderRadius: 12 }}>
                <Form layout="vertical">
                  <Form.Item label="温度">
                    <InputNumber
                      min={0}
                      max={2}
                      step={0.1}
                      value={parseFloat(getVal('temperature', '0.7'))}
                      onChange={(value) => setVal('temperature', String(value ?? 0.7))}
                      style={{ width: 220 }}
                    />
                    <Text type="secondary" style={{ marginLeft: 8 }}>
                      值越低，智能体输出越确定
                    </Text>
                  </Form.Item>
                  <Form.Item label="最大并发任务">
                    <InputNumber
                      min={1}
                      max={10}
                      value={parseInt(getVal('max_concurrent_tasks', '5'), 10)}
                      onChange={(value) => setVal('max_concurrent_tasks', String(value ?? 5))}
                      style={{ width: 220 }}
                    />
                  </Form.Item>
                  <Form.Item label="日志级别">
                    <Select
                      value={getVal('log_level', 'INFO')}
                      onChange={(value) => setVal('log_level', value)}
                      options={[
                        { value: 'DEBUG', label: '调试' },
                        { value: 'INFO', label: '信息' },
                        { value: 'WARNING', label: '警告' },
                        { value: 'ERROR', label: '错误' },
                      ]}
                      style={{ width: 220 }}
                    />
                  </Form.Item>
                </Form>
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
};

export default SettingsPage;
