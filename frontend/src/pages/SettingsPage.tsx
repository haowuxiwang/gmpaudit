import React, { useState, useEffect } from 'react';
import { Typography, Tabs, Form, Input, Button, Card, message, Select } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { configApi } from '../services/api';

const { Title } = Typography;

const SettingsPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState<any>({});
  const [models, setModels] = useState<any[]>([]);

  useEffect(() => { loadConfig(); loadModels(); }, []);

  const loadConfig = async () => {
    try {
      const result = await configApi.getAll();
      setConfig(result || {});
    } catch (error) {
      console.error('加载配置失败');
    }
  };

  const loadModels = async () => {
    try {
      const result = await configApi.getAvailableModels();
      setModels(result || []);
    } catch (error) {
      console.error('加载模型列表失败');
    }
  };

  const handleSave = async (key: string, value: string) => {
    try {
      setLoading(true);
      await configApi.update(key, value);
      message.success('配置保存成功');
      loadConfig();
    } catch (error) {
      message.error('配置保存失败');
    } finally {
      setLoading(false);
    }
  };

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
                  <Select value={config.default_model?.value || 'deepseek'} onChange={(value) => handleSave('default_model', value)} options={models.map((m) => ({ value: m.id, label: m.name }))} />
                </Form.Item>
                <Form.Item label="DeepSeek API Key">
                  <Input.Password value={config.deepseek_api_key?.value || ''} onChange={(e) => handleSave('deepseek_api_key', e.target.value)} placeholder="请输入DeepSeek API Key" />
                </Form.Item>
                <Form.Item label="Temperature">
                  <Input type="number" min={0} max={2} step={0.1} value={config.temperature?.value || 0.7} onChange={(e) => handleSave('temperature', e.target.value)} />
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
                  <Input type="number" min={1} max={10} value={config.max_concurrent_tasks?.value || 5} onChange={(e) => handleSave('max_concurrent_tasks', e.target.value)} />
                </Form.Item>
                <Form.Item label="日志级别">
                  <Select value={config.log_level?.value || 'INFO'} onChange={(value) => handleSave('log_level', value)} options={[
                    { value: 'DEBUG', label: 'DEBUG' },
                    { value: 'INFO', label: 'INFO' },
                    { value: 'WARNING', label: 'WARNING' },
                    { value: 'ERROR', label: 'ERROR' },
                  ]} />
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
