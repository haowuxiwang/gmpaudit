import React, { useState, useEffect } from 'react';
import { Typography, Tabs, Form, Input, Card, message, Select, InputNumber } from 'antd';
import { configApi } from '../services/api';

const { Title } = Typography;

const MODEL_OPTIONS = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'qwen', label: '通义千问' },
  { value: 'glm', label: '智谱GLM' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic/Claude' },
];

const LOG_LEVEL_OPTIONS = [
  { value: 'DEBUG', label: 'DEBUG' },
  { value: 'INFO', label: 'INFO' },
  { value: 'WARNING', label: 'WARNING' },
  { value: 'ERROR', label: 'ERROR' },
];

const SettingsPage: React.FC = () => {
  const [config, setConfig] = useState<any>({});

  useEffect(() => { loadConfig(); }, []);

  const loadConfig = async () => {
    try {
      const result = await configApi.getAll();
      setConfig(result || {});
    } catch (error) {
      console.error('加载配置失败');
    }
  };

  const handleSave = async (key: string, value: string) => {
    try {
      await configApi.update(key, value);
      message.success('配置保存成功');
      loadConfig();
    } catch (error) {
      message.error('配置保存失败');
    }
  };

  const getVal = (key: string, fallback: string = '') => config[key]?.value || fallback;

  return (
    <div>
      <Title level={4}>系统设置</Title>
      <Tabs defaultActiveKey="llm" items={[
        {
          key: 'llm',
          label: 'LLM配置',
          children: (
            <Card>
              <Form layout="vertical">
                <Form.Item label="默认模型">
                  <Select
                    value={getVal('default_model', 'deepseek')}
                    onChange={(value) => handleSave('default_model', value)}
                    options={MODEL_OPTIONS}
                  />
                </Form.Item>
                <Form.Item label="DeepSeek API Key">
                  <Input.Password
                    value={getVal('deepseek_api_key')}
                    onChange={(e) => handleSave('deepseek_api_key', e.target.value)}
                    placeholder="请输入DeepSeek API Key"
                  />
                </Form.Item>
                <Form.Item label="DeepSeek Base URL">
                  <Input
                    value={getVal('deepseek_base_url', 'https://api.deepseek.com')}
                    onChange={(e) => handleSave('deepseek_base_url', e.target.value)}
                    placeholder="https://api.deepseek.com"
                  />
                </Form.Item>
                <Form.Item label="通义千问 API Key">
                  <Input.Password
                    value={getVal('qwen_api_key')}
                    onChange={(e) => handleSave('qwen_api_key', e.target.value)}
                    placeholder="请输入通义千问 API Key"
                  />
                </Form.Item>
                <Form.Item label="智谱GLM API Key">
                  <Input.Password
                    value={getVal('glm_api_key')}
                    onChange={(e) => handleSave('glm_api_key', e.target.value)}
                    placeholder="请输入智谱GLM API Key"
                  />
                </Form.Item>
                <Form.Item label="OpenAI API Key">
                  <Input.Password
                    value={getVal('openai_api_key')}
                    onChange={(e) => handleSave('openai_api_key', e.target.value)}
                    placeholder="请输入OpenAI API Key"
                  />
                </Form.Item>
                <Form.Item label="OpenAI Base URL">
                  <Input
                    value={getVal('openai_base_url', 'https://api.openai.com')}
                    onChange={(e) => handleSave('openai_base_url', e.target.value)}
                    placeholder="https://api.openai.com"
                  />
                </Form.Item>
                <Form.Item label="Anthropic API Key">
                  <Input.Password
                    value={getVal('anthropic_api_key')}
                    onChange={(e) => handleSave('anthropic_api_key', e.target.value)}
                    placeholder="请输入Anthropic API Key"
                  />
                </Form.Item>
                <Form.Item label="Temperature">
                  <InputNumber
                    min={0}
                    max={2}
                    step={0.1}
                    value={parseFloat(getVal('temperature', '0.7'))}
                    onChange={(value) => handleSave('temperature', String(value ?? 0.7))}
                    style={{ width: '100%' }}
                  />
                </Form.Item>
              </Form>
            </Card>
          ),
        },
        {
          key: 'feishu',
          label: '飞书配置',
          children: (
            <Card>
              <Form layout="vertical">
                <Form.Item label="App ID">
                  <Input
                    value={getVal('feishu_app_id')}
                    onChange={(e) => handleSave('feishu_app_id', e.target.value)}
                    placeholder="请输入飞书 App ID"
                  />
                </Form.Item>
                <Form.Item label="App Secret">
                  <Input.Password
                    value={getVal('feishu_app_secret')}
                    onChange={(e) => handleSave('feishu_app_secret', e.target.value)}
                    placeholder="请输入飞书 App Secret"
                  />
                </Form.Item>
                <Form.Item label="Webhook URL">
                  <Input
                    value={getVal('feishu_webhook_url')}
                    onChange={(e) => handleSave('feishu_webhook_url', e.target.value)}
                    placeholder="请输入飞书 Webhook URL"
                  />
                </Form.Item>
              </Form>
            </Card>
          ),
        },
        {
          key: 'system',
          label: '系统参数',
          children: (
            <Card>
              <Form layout="vertical">
                <Form.Item label="最大并发任务数">
                  <InputNumber
                    min={1}
                    max={10}
                    value={parseInt(getVal('max_concurrent_tasks', '5'), 10)}
                    onChange={(value) => handleSave('max_concurrent_tasks', String(value ?? 5))}
                    style={{ width: '100%' }}
                  />
                </Form.Item>
                <Form.Item label="日志级别">
                  <Select
                    value={getVal('log_level', 'INFO')}
                    onChange={(value) => handleSave('log_level', value)}
                    options={LOG_LEVEL_OPTIONS}
                  />
                </Form.Item>
              </Form>
            </Card>
          ),
        },
      ]} />
    </div>
  );
};

export default SettingsPage;
