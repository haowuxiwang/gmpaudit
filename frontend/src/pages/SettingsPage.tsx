import React, { useEffect, useState } from 'react';
import {
  Badge,
  Button,
  Card,
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
import { SaveOutlined, SendOutlined } from '@ant-design/icons';

import { configApi } from '../services/api';

const { Title, Text, Paragraph } = Typography;

interface ProviderConfig {
  id: string;
  name: string;
  defaultModel: string;
  defaultUrl: string;
  keyPlaceholder: string;
}

const PROVIDERS: ProviderConfig[] = [
  { id: 'mimo', name: 'Mimo', defaultModel: 'mimo-v2.5-pro', defaultUrl: 'https://api.xiaomimimo.com/v1', keyPlaceholder: 'sk-...' },
  { id: 'deepseek', name: 'DeepSeek', defaultModel: 'deepseek-chat', defaultUrl: 'https://api.deepseek.com/v1', keyPlaceholder: 'sk-...' },
  { id: 'qwen', name: 'Qwen', defaultModel: 'qwen-plus', defaultUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1', keyPlaceholder: 'sk-...' },
  { id: 'glm', name: 'GLM', defaultModel: 'glm-4-flash', defaultUrl: 'https://open.bigmodel.cn/api/paas/v4', keyPlaceholder: 'token' },
  { id: 'siliconflow', name: 'SiliconFlow', defaultModel: 'deepseek-ai/DeepSeek-V3.2', defaultUrl: 'https://api.siliconflow.cn/v1', keyPlaceholder: 'sk-...' },
  { id: 'openai', name: 'OpenAI', defaultModel: 'gpt-4o', defaultUrl: 'https://api.openai.com/v1', keyPlaceholder: 'sk-...' },
  { id: 'anthropic', name: 'Anthropic', defaultModel: 'claude-sonnet-4-20250514', defaultUrl: 'https://api.anthropic.com', keyPlaceholder: 'sk-ant-...' },
  { id: 'openrouter', name: 'OpenRouter', defaultModel: 'deepseek/deepseek-chat', defaultUrl: 'https://openrouter.ai/api/v1', keyPlaceholder: 'sk-or-...' },
];

const SettingsPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [config, setConfig] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [testWebhookResult, setTestWebhookResult] = useState('');

  useEffect(() => {
    void loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const result: any = await configApi.getAll();
      const flat: Record<string, string> = {};
      if (result) {
        for (const [key, val] of Object.entries(result)) {
          flat[key] = (val as any)?.value ?? '';
        }
      }
      setConfig(flat);
      setDraft(flat);
    } catch {
      message.error('Failed to load configuration');
    } finally {
      setLoading(false);
    }
  };

  const getVal = (key: string, fallback = '') => draft[key] || fallback;

  const setVal = (key: string, value: string) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
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
        message.info('No configuration changes to save');
        return;
      }

      await configApi.batchUpdate(changes);
      setConfig((prev) => ({ ...prev, ...changes }));
      message.success(`Saved ${Object.keys(changes).length} configuration value(s)`);
    } catch {
      message.error('Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleTestWebhook = async () => {
    try {
      const webhookUrl = getVal('feishu_webhook_url');
      if (!webhookUrl) {
        message.warning('Enter a webhook URL first');
        return;
      }

      setTestWebhookResult('Sending test message...');
      const payload: Record<string, string> = { feishu_webhook_url: webhookUrl };
      const secret = getVal('feishu_webhook_secret');
      if (secret) payload.feishu_webhook_secret = secret;

      await configApi.batchUpdate(payload);
      const result: any = await configApi.testWebhook();
      if (result.success) {
        setTestWebhookResult('Webhook test sent successfully.');
        message.success('Webhook test sent');
      } else {
        setTestWebhookResult(`Webhook test failed: ${result?.error || 'unknown error'}`);
      }
    } catch (error: any) {
      const detail = error?.response?.data?.detail || error?.message || 'network or URL issue';
      setTestWebhookResult(`Webhook test failed: ${detail}`);
    }
  };

  const isConfigured = (provider: ProviderConfig) => Boolean(getVal(`${provider.id}_api_key`));
  const defaultProvider = getVal('agent_llm_provider', 'mimo');

  if (loading) {
    return <Spin size="large" style={{ display: 'block', margin: '100px auto' }} />;
  }

  return (
    <div>
      <Card
        bordered={false}
        style={{
          marginBottom: 24,
          borderRadius: 24,
          background: 'linear-gradient(135deg, #1e293b 0%, #0f766e 100%)',
          color: '#fff',
        }}
        bodyStyle={{ padding: 28 }}
      >
        <Title level={2} style={{ color: '#fff', marginTop: 0 }}>
          System configuration
        </Title>
        <Paragraph style={{ color: 'rgba(255,255,255,0.82)', fontSize: 16, marginBottom: 0 }}>
          Configure the models, webhook, and runtime controls that shape how the audit agent behaves.
        </Paragraph>
      </Card>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>Settings workspace</Title>
        <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>
          Save changes
        </Button>
      </div>

      <Tabs
        defaultActiveKey="llm"
        items={[
          {
            key: 'llm',
            label: 'LLM providers',
            children: (
              <>
                <Paragraph type="secondary">
                  Choose the default provider for audit sessions and maintain provider-specific model, base URL, and API key settings.
                </Paragraph>
                <Form layout="vertical">
                  <Form.Item label="Default provider for audit sessions">
                    <Select
                      value={defaultProvider}
                      onChange={(value) => setVal('agent_llm_provider', value)}
                      options={PROVIDERS.map((provider) => ({
                        value: provider.id,
                        label: `${provider.name}${isConfigured(provider) ? ' ✓' : ''}`,
                      }))}
                      style={{ maxWidth: 320 }}
                    />
                  </Form.Item>
                </Form>

                {PROVIDERS.map((provider) => (
                  <Card
                    key={provider.id}
                    size="small"
                    style={{ marginBottom: 12, borderRadius: 16 }}
                    title={(
                      <Space>
                        <Badge status={isConfigured(provider) ? 'success' : 'default'} />
                        <span>{provider.name}</span>
                        {defaultProvider === provider.id && <Text type="secondary">(default)</Text>}
                      </Space>
                    )}
                  >
                    <Form layout="inline" style={{ flexWrap: 'wrap', gap: 8 }}>
                      <Form.Item label="Model">
                        <Input
                          value={getVal(`${provider.id}_model`, provider.defaultModel)}
                          onChange={(event) => setVal(`${provider.id}_model`, event.target.value)}
                          placeholder={provider.defaultModel}
                          style={{ width: 220 }}
                        />
                      </Form.Item>
                      <Form.Item label="Base URL">
                        <Input
                          value={getVal(`${provider.id}_base_url`, provider.defaultUrl)}
                          onChange={(event) => setVal(`${provider.id}_base_url`, event.target.value)}
                          placeholder={provider.defaultUrl}
                          style={{ width: 360 }}
                        />
                      </Form.Item>
                      <Form.Item label="API key">
                        <Input.Password
                          value={getVal(`${provider.id}_api_key`)}
                          onChange={(event) => setVal(`${provider.id}_api_key`, event.target.value)}
                          placeholder={provider.keyPlaceholder}
                          style={{ width: 300 }}
                        />
                      </Form.Item>
                    </Form>
                  </Card>
                ))}
              </>
            ),
          },
          {
            key: 'feishu',
            label: 'Webhook',
            children: (
              <Card bordered={false} style={{ borderRadius: 20 }}>
                <Card type="inner" title="Webhook setup guide" style={{ marginBottom: 16, borderRadius: 16 }}>
                  <ol style={{ margin: 0, paddingLeft: 20 }}>
                    <li>Create or open a Feishu group bot.</li>
                    <li>Copy the generated webhook URL.</li>
                    <li>Enable signing if your bot requires a secret.</li>
                    <li>Paste the values below and send a test message.</li>
                  </ol>
                </Card>
                <Form layout="vertical">
                  <Form.Item label="Webhook URL">
                    <Input
                      value={getVal('feishu_webhook_url')}
                      onChange={(event) => setVal('feishu_webhook_url', event.target.value)}
                      placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
                    />
                  </Form.Item>
                  <Form.Item label="Webhook secret">
                    <Input.Password
                      value={getVal('feishu_webhook_secret')}
                      onChange={(event) => setVal('feishu_webhook_secret', event.target.value)}
                      placeholder="Optional signing secret"
                    />
                  </Form.Item>
                  <Form.Item>
                    <Space>
                      <Button icon={<SendOutlined />} onClick={handleTestWebhook}>
                        Send test
                      </Button>
                      {testWebhookResult && (
                        <Text type={testWebhookResult.includes('successfully') ? 'success' : 'danger'}>
                          {testWebhookResult}
                        </Text>
                      )}
                    </Space>
                  </Form.Item>
                </Form>
              </Card>
            ),
          },
          {
            key: 'system',
            label: 'Runtime',
            children: (
              <Card bordered={false} style={{ borderRadius: 20 }}>
                <Form layout="vertical">
                  <Form.Item label="Temperature">
                    <InputNumber
                      min={0}
                      max={2}
                      step={0.1}
                      value={parseFloat(getVal('temperature', '0.7'))}
                      onChange={(value) => setVal('temperature', String(value ?? 0.7))}
                      style={{ width: 220 }}
                    />
                    <Text type="secondary" style={{ marginLeft: 8 }}>
                      Lower values make the agent more deterministic.
                    </Text>
                  </Form.Item>
                  <Form.Item label="Max concurrent tasks">
                    <InputNumber
                      min={1}
                      max={10}
                      value={parseInt(getVal('max_concurrent_tasks', '5'), 10)}
                      onChange={(value) => setVal('max_concurrent_tasks', String(value ?? 5))}
                      style={{ width: 220 }}
                    />
                  </Form.Item>
                  <Form.Item label="Log level">
                    <Select
                      value={getVal('log_level', 'INFO')}
                      onChange={(value) => setVal('log_level', value)}
                      options={[
                        { value: 'DEBUG', label: 'DEBUG' },
                        { value: 'INFO', label: 'INFO' },
                        { value: 'WARNING', label: 'WARNING' },
                        { value: 'ERROR', label: 'ERROR' },
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
