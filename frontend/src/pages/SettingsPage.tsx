import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  AutoComplete,
  Button,
  Card,
  Collapse,
  Form,
  Input,
  InputNumber,
  Select,
  Space,
  Spin,
  Tabs,
  Typography,
  message,
} from 'antd';
import {
  ApiOutlined,
  SaveOutlined,
  SendOutlined,
  SettingOutlined,
} from '@ant-design/icons';

import { configApi, LLMModel } from '../services/api';
import type { ConfigMap } from '../types/api';
import { THEME } from '../constants/theme';

const { Title, Text, Paragraph } = Typography;

// Model descriptions for the combobox
const MODEL_DESCRIPTIONS: Record<string, string> = {
  'deepseek-chat': '通用对话',
  'deepseek-reasoner': '深度推理',
  'qwen-plus': '均衡性能',
  'qwen-turbo': '高速响应',
  'qwen-max': '最强能力',
  'glm-4-flash': '快速响应',
  'mimo-v2.5-pro': '推荐',
  'gpt-4o': '多模态',
  'gpt-4o-mini': '轻量快速',
  'claude-sonnet-4-20250514': '均衡',
  'claude-haiku-4-5-20251001': '快速',
  'claude-opus-4-20250514': '最强能力',
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

      const isPlaceholder = (v: string) => !v || /^your_/i.test(v);
      for (const p of models) {
        const modelKey = `${p.id}_model`;
        const urlKey = `${p.id}_base_url`;
        if (isPlaceholder(flat[modelKey] || '') && p.default_model) {
          flat[modelKey] = p.default_model;
        }
        if (isPlaceholder(flat[urlKey] || '') && p.base_url) {
          flat[urlKey] = p.base_url;
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

  const dirtyKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const [key, value] of Object.entries(draft)) {
      if (value !== (config[key] || '')) {
        keys.add(key);
      }
    }
    return keys;
  }, [draft, config]);

  const handleSave = async () => {
    try {
      setSaving(true);
      const changes: Record<string, string> = {};
      for (const [key, value] of Object.entries(draft)) {
        if (value !== (config[key] || '')) {
          changes[key] = value;
        }
      }

      // For any provider with an API key, always include model and base_url
      for (const p of providers) {
        const apiKey = draft[`${p.id}_api_key`] || '';
        if (apiKey && !apiKey.startsWith('your_')) {
          const modelKey = `${p.id}_model`;
          const urlKey = `${p.id}_base_url`;
          if (!changes[modelKey] && draft[modelKey]) {
            changes[modelKey] = draft[modelKey];
          }
          if (!changes[urlKey] && draft[urlKey]) {
            changes[urlKey] = draft[urlKey];
          }
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

  const handleTestProvider = async (providerId: string) => {
    const apiKey = getVal(`${providerId}_api_key`);
    if (!apiKey) {
      message.warning('请先输入 API Key');
      return;
    }

    const provider = providers.find((p) => p.id === providerId);
    setTestingProvider(providerId);
    setProviderTestResult(null);
    try {
      const raw = await configApi.testLLM({
        provider: providerId,
        api_key: apiKey,
        base_url: getVal(`${providerId}_base_url`, provider?.base_url || ''),
        model: getVal(`${providerId}_model`, provider?.model || provider?.default_model || ''),
      });
      const result: TestResult = { ...raw, provider: providerId };
      setProviderTestResult(result);
      if (result.success) {
        message.success(`连接成功 (${result.latency_ms}ms)`);
      }
    } catch (error: unknown) {
      setProviderTestResult({
        provider: providerId,
        success: false,
        error: error instanceof Error ? error.message : '连接失败',
      });
    } finally {
      setTestingProvider(null);
    }
  };

  const isConfigured = (providerId: string) => {
    const key = getVal(`${providerId}_api_key`);
    return Boolean(key) && !key.startsWith('your_');
  };

  const defaultProvider = getVal('agent_llm_provider', 'mimo');
  const currentProvider = providers.find((p) => p.id === defaultProvider);
  const anthropicProvider = providers.find((p) => p.id === 'anthropic');

  const totalDirty = dirtyKeys.size;

  // Build model options from current provider
  const currentModelOptions = useMemo(() => {
    if (!currentProvider) return [];
    return (currentProvider.available_models || []).map((m) => ({
      value: m,
      label: MODEL_DESCRIPTIONS[m] ? `${m} · ${MODEL_DESCRIPTIONS[m]}` : m,
    }));
  }, [currentProvider]);

  const anthropicModelOptions = useMemo(() => {
    if (!anthropicProvider) return [];
    return (anthropicProvider.available_models || []).map((m) => ({
      value: m,
      label: MODEL_DESCRIPTIONS[m] ? `${m} · ${MODEL_DESCRIPTIONS[m]}` : m,
    }));
  }, [anthropicProvider]);

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
          配置审计任务使用的大模型
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
              <Card bordered={false} style={{ borderRadius: 12 }}>
                {/* Default provider selector */}
                <div style={{ marginBottom: 24 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                    <SettingOutlined style={{ color: THEME.primary, fontSize: 16 }} />
                    <Text strong style={{ fontSize: 15 }}>默认模型</Text>
                    <Select
                      value={defaultProvider}
                      onChange={(value) => setVal('agent_llm_provider', value)}
                      style={{ width: 240 }}
                      options={providers
                        .filter((p) => p.id !== 'anthropic')
                        .map((p) => ({
                          value: p.id,
                          label: `${p.name}${isConfigured(p.id) ? ' ✓' : ''}`,
                        }))}
                    />
                  </div>
                </div>

                {/* Primary provider form */}
                {currentProvider && (
                  <div style={{ marginBottom: 24 }}>
                    <Text strong style={{ display: 'block', marginBottom: 12, fontSize: 14 }}>
                      {currentProvider.name}
                    </Text>
                    <Form layout="vertical" style={{ maxWidth: 560 }}>
                      <Form.Item
                        label="API Key"
                        style={{ marginBottom: 16 }}
                      >
                        <Input.Password
                          value={getVal(`${defaultProvider}_api_key`)}
                          onChange={(e) => setVal(`${defaultProvider}_api_key`, e.target.value)}
                          placeholder="sk-..."
                          style={{ borderRadius: 8 }}
                        />
                      </Form.Item>
                      <Form.Item
                        label="模型名称"
                        style={{ marginBottom: 16 }}
                      >
                        <AutoComplete
                          value={getVal(`${defaultProvider}_model`, currentProvider.default_model || currentProvider.model)}
                          onChange={(value) => setVal(`${defaultProvider}_model`, value)}
                          placeholder={currentProvider.default_model || currentProvider.model}
                          options={currentModelOptions}
                          style={{ width: '100%' }}
                          filterOption={(inputValue, option) =>
                            (option?.label ?? '').toLowerCase().includes(inputValue.toLowerCase())
                          }
                        />
                      </Form.Item>
                      <Form.Item
                        label="接口地址"
                        style={{ marginBottom: 16 }}
                      >
                        <Input
                          value={getVal(`${defaultProvider}_base_url`, currentProvider.base_url || '')}
                          onChange={(e) => setVal(`${defaultProvider}_base_url`, e.target.value)}
                          placeholder={currentProvider.base_url || ''}
                          style={{ borderRadius: 8 }}
                        />
                      </Form.Item>
                      <Form.Item style={{ marginBottom: 0 }}>
                        <Button
                          icon={<ApiOutlined />}
                          loading={testingProvider === defaultProvider}
                          onClick={() => void handleTestProvider(defaultProvider)}
                          style={{ borderRadius: 8 }}
                        >
                          测试连接
                        </Button>
                      </Form.Item>
                    </Form>

                    {/* Test result */}
                    {providerTestResult?.provider === defaultProvider && (
                      <Alert
                        type={providerTestResult.success ? 'success' : 'error'}
                        showIcon
                        message={
                          <Text style={{ fontSize: 13 }}>
                            {providerTestResult.success
                              ? `${providerTestResult.model_used} - ${providerTestResult.latency_ms}ms`
                              : providerTestResult.error}
                          </Text>
                        }
                        style={{ marginTop: 12, maxWidth: 560, borderRadius: 8 }}
                      />
                    )}
                  </div>
                )}

                {/* Anthropic (collapsible) */}
                <Collapse
                  bordered={false}
                  style={{ background: 'transparent' }}
                  items={[
                    {
                      key: 'anthropic',
                      label: (
                        <Text type="secondary" style={{ fontSize: 13 }}>
                          Anthropic 配置（可选，如需使用 Claude）
                        </Text>
                      ),
                      children: anthropicProvider ? (
                        <Form layout="vertical" style={{ maxWidth: 560 }}>
                          <Form.Item label="API Key" style={{ marginBottom: 16 }}>
                            <Input.Password
                              value={getVal('anthropic_api_key')}
                              onChange={(e) => setVal('anthropic_api_key', e.target.value)}
                              placeholder="sk-ant-..."
                              style={{ borderRadius: 8 }}
                            />
                          </Form.Item>
                          <Form.Item label="模型名称" style={{ marginBottom: 16 }}>
                            <AutoComplete
                              value={getVal('anthropic_model', anthropicProvider.default_model || '')}
                              onChange={(value) => setVal('anthropic_model', value)}
                              placeholder={anthropicProvider.default_model || ''}
                              options={anthropicModelOptions}
                              style={{ width: '100%' }}
                              filterOption={(inputValue, option) =>
                                (option?.label ?? '').toLowerCase().includes(inputValue.toLowerCase())
                              }
                            />
                          </Form.Item>
                          <Form.Item label="接口地址" style={{ marginBottom: 16 }}>
                            <Input
                              value={getVal('anthropic_base_url', anthropicProvider.base_url || '')}
                              onChange={(e) => setVal('anthropic_base_url', e.target.value)}
                              placeholder={anthropicProvider.base_url || ''}
                              style={{ borderRadius: 8 }}
                            />
                          </Form.Item>
                          <Form.Item style={{ marginBottom: 0 }}>
                            <Button
                              icon={<ApiOutlined />}
                              loading={testingProvider === 'anthropic'}
                              onClick={() => void handleTestProvider('anthropic')}
                              style={{ borderRadius: 8 }}
                            >
                              测试连接
                            </Button>
                          </Form.Item>
                          {providerTestResult?.provider === 'anthropic' && (
                            <Alert
                              type={providerTestResult.success ? 'success' : 'error'}
                              showIcon
                              message={
                                <Text style={{ fontSize: 13 }}>
                                  {providerTestResult.success
                                    ? `${providerTestResult.model_used} - ${providerTestResult.latency_ms}ms`
                                    : providerTestResult.error}
                                </Text>
                              }
                              style={{ marginTop: 12, borderRadius: 8 }}
                            />
                          )}
                        </Form>
                      ) : null,
                    },
                  ]}
                />
              </Card>
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
