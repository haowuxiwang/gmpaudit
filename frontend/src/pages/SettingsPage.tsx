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
import type { ConfigMap } from '../types/api';
import { THEME } from '../constants/theme';

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
      const result: ConfigMap = await configApi.getAll();
      const flat: Record<string, string> = {};
      if (result) {
        for (const [key, val] of Object.entries(result)) {
          flat[key] = val.value ?? '';
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
        message.info('无配置变更');
        return;
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
          保存配置
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
                <Paragraph type="secondary">
                  选择审计任务的默认大模型，配置各模型的密钥和参数
                </Paragraph>
                <Form layout="vertical">
                  <Form.Item label="默认审计模型">
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
                    style={{ marginBottom: 12, borderRadius: 8 }}
                    title={(
                      <Space>
                        <Badge status={isConfigured(provider) ? 'success' : 'default'} />
                        <span>{provider.name}</span>
                        {defaultProvider === provider.id && <Text type="secondary">（默认）</Text>}
                      </Space>
                    )}
                  >
                    <Form layout="inline" style={{ flexWrap: 'wrap', gap: 8 }}>
                      <Form.Item label="模型名称">
                        <Input
                          value={getVal(`${provider.id}_model`, provider.defaultModel)}
                          onChange={(event) => setVal(`${provider.id}_model`, event.target.value)}
                          placeholder={provider.defaultModel}
                          style={{ width: 220 }}
                        />
                      </Form.Item>
                      <Form.Item label="接口地址">
                        <Input
                          value={getVal(`${provider.id}_base_url`, provider.defaultUrl)}
                          onChange={(event) => setVal(`${provider.id}_base_url`, event.target.value)}
                          placeholder={provider.defaultUrl}
                          style={{ width: 360 }}
                        />
                      </Form.Item>
                      <Form.Item label="API 密钥">
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
                  <Form.Item label="签名密钥">
                    <Input.Password
                      value={getVal('feishu_webhook_secret')}
                      onChange={(event) => setVal('feishu_webhook_secret', event.target.value)}
                      placeholder="可选签名密钥"
                    />
                  </Form.Item>
                  <Form.Item>
                    <Space>
                      <Button icon={<SendOutlined />} onClick={handleTestWebhook}>
                        保存并测试
                      </Button>
                      {testWebhookResult && (
                        <Text type={testWebhookResult.includes('成功') ? 'success' : 'danger'}>
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
