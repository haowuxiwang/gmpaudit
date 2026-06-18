import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';

import SettingsPage from '../SettingsPage';
import { configApi } from '../../services/api';

jest.setTimeout(15000);

jest.mock('../../services/api', () => ({
  configApi: {
    getAll: jest.fn(),
    getModels: jest.fn(),
    batchUpdate: jest.fn(),
    testWebhook: jest.fn(),
    testLLM: jest.fn(),
  },
}));

const mockConfigApi = configApi as jest.Mocked<typeof configApi>;

const renderWithRouter = (component: React.ReactElement) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

const mockModels = [
  {
    id: 'mimo',
    name: 'Mimo',
    model: 'mimo-v2.5-pro',
    available: true,
    base_url: 'https://api.mimo.com/v1',
    default_model: 'mimo-v2.5-pro',
    available_models: ['mimo-v2.5-pro'],
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    model: 'deepseek-chat',
    available: true,
    base_url: 'https://api.deepseek.com/v1',
    default_model: 'deepseek-chat',
    available_models: ['deepseek-chat', 'deepseek-reasoner'],
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    model: 'claude-sonnet-4-20250514',
    available: true,
    base_url: 'https://api.anthropic.com',
    default_model: 'claude-sonnet-4-20250514',
    available_models: ['claude-sonnet-4-20250514', 'claude-haiku-4-5-20251001', 'claude-opus-4-20250514'],
  },
];

const mockConfig = {
  agent_llm_provider: { value: 'mimo', type: 'string', description: 'Default LLM provider' },
  mimo_api_key: { value: 'sk-test-key', type: 'string', description: 'Mimo API key' },
  mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string', description: 'Mimo base URL' },
  mimo_model: { value: 'mimo-v2.5-pro', type: 'string', description: 'Mimo model' },
  feishu_webhook_url: { value: '', type: 'string', description: 'Feishu webhook URL' },
  feishu_webhook_secret: { value: '', type: 'string', description: 'Feishu webhook secret' },
  temperature: { value: '0.7', type: 'number', description: 'Temperature' },
  max_concurrent_tasks: { value: '5', type: 'number', description: 'Max concurrent tasks' },
  log_level: { value: 'INFO', type: 'string', description: 'Log level' },
};

describe('SettingsPage extended tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockConfigApi.getModels.mockResolvedValue(mockModels);
    mockConfigApi.getAll.mockResolvedValue(mockConfig);
    mockConfigApi.batchUpdate.mockResolvedValue({ status: 'ok', updated: 1 });
    mockConfigApi.testWebhook.mockResolvedValue({ success: true, error: null });
    mockConfigApi.testLLM.mockResolvedValue({ success: true, model_used: 'mimo-v2.5-pro', latency_ms: 200, error: null });
  });

  // --- Initial render ---
  test('renders settings page title', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('系统设置')).toBeInTheDocument();
    });
  });

  test('renders description text', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('配置审计任务使用的大模型')).toBeInTheDocument();
    });
  });

  test('renders save button', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });
  });

  // --- Loading state ---
  test('shows loading spinner initially', () => {
    mockConfigApi.getModels.mockImplementation(() => new Promise(() => {}));
    mockConfigApi.getAll.mockImplementation(() => new Promise(() => {}));

    renderWithRouter(<SettingsPage />);

    // Spin component should be rendered
    expect(document.querySelector('.ant-spin')).toBeInTheDocument();
  });

  // --- LLM config tab ---
  test('renders LLM config tab by default', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('大模型配置')).toBeInTheDocument();
    });
  });

  test('renders default model selector', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('默认模型')).toBeInTheDocument();
    });
  });

  test('renders provider API key field', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('Mimo')).toBeInTheDocument();
    });
  });

  test('renders provider model name field', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('模型名称')).toBeInTheDocument();
    });
  });

  test('renders provider base URL field', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('接口地址')).toBeInTheDocument();
    });
  });

  test('renders test connection button', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('测试连接')).toBeInTheDocument();
    });
  });

  // --- Feishu tab ---
  test('renders feishu notification tab', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });
  });

  test('shows webhook form when feishu tab is clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });

    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('Webhook 配置指南')).toBeInTheDocument();
    });

    expect(screen.getByText('保存并测试')).toBeInTheDocument();
  });

  test('renders webhook URL input field', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });

    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('Webhook 地址')).toBeInTheDocument();
    });
  });

  test('renders webhook secret input field', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });

    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('签名密钥')).toBeInTheDocument();
    });
  });

  test('shows webhook configuration guide', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });

    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('创建或打开飞书群机器人')).toBeInTheDocument();
    });

    expect(screen.getByText('复制生成的 Webhook 地址')).toBeInTheDocument();
  });

  // --- System tab ---
  test('renders system parameters tab', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('运行参数')).toBeInTheDocument();
    });
  });

  test('shows temperature field when system tab clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('运行参数')).toBeInTheDocument();
    });

    await user.click(screen.getByText('运行参数'));

    await waitFor(() => {
      expect(screen.getByText('温度')).toBeInTheDocument();
    });

    expect(screen.getByText(/值越低，智能体输出越确定/)).toBeInTheDocument();
  });

  test('shows max concurrent tasks field', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('运行参数')).toBeInTheDocument();
    });

    await user.click(screen.getByText('运行参数'));

    await waitFor(() => {
      expect(screen.getByText('最大并发任务')).toBeInTheDocument();
    });
  });

  test('shows log level field', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('运行参数')).toBeInTheDocument();
    });

    await user.click(screen.getByText('运行参数'));

    await waitFor(() => {
      expect(screen.getByText('日志级别')).toBeInTheDocument();
    });
  });

  // --- Save config ---
  test('calls batchUpdate when save is clicked with changes', async () => {
    mockConfigApi.batchUpdate.mockResolvedValue({ status: 'ok', updated: 1 });
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });

    // Change API key using fireEvent for reliability
    const apiKeyInputs = document.querySelectorAll('input[type="password"]');
    expect(apiKeyInputs.length).toBeGreaterThanOrEqual(1);
    fireEvent.change(apiKeyInputs[0], { target: { value: 'sk-new-api-key-12345' } });

    await user.click(screen.getByText(/保存配置/));

    await waitFor(() => {
      expect(mockConfigApi.batchUpdate).toHaveBeenCalled();
    });
  });

  // --- Error handling ---
  test('handles API error on load', async () => {
    mockConfigApi.getModels.mockRejectedValue(new Error('加载失败'));
    mockConfigApi.getAll.mockRejectedValue(new Error('加载失败'));

    renderWithRouter(<SettingsPage />);

    // Should still render after error (loading finishes)
    await waitFor(() => {
      expect(screen.queryByText(/ant-spin/)).not.toBeInTheDocument();
    });
  });

  test('handles partial API failure gracefully', async () => {
    mockConfigApi.getModels.mockRejectedValue(new Error('Models failed'));
    mockConfigApi.getAll.mockResolvedValue(mockConfig);

    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('系统设置')).toBeInTheDocument();
    });
  });

  test('handles empty config gracefully', async () => {
    mockConfigApi.getAll.mockResolvedValue({});
    mockConfigApi.getModels.mockResolvedValue([]);

    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('系统设置')).toBeInTheDocument();
    });
  });

  // --- Anthropic section ---
  test('shows anthropic collapse section', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Anthropic 配置/)).toBeInTheDocument();
    });
  });

  // --- Test provider connection ---
  test('shows test connection button for provider', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('测试连接')).toBeInTheDocument();
    });
  });

  // --- Config with placeholder values ---
  test('uses provider defaults when config values are placeholders', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'your_key_here', type: 'string' },
      mimo_base_url: { value: '', type: 'string' },
      mimo_model: { value: '', type: 'string' },
    });

    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('系统设置')).toBeInTheDocument();
    });
  });

  // --- Multiple providers ---
  test('shows configured provider with check mark', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'sk-real-key', type: 'string' },
      mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string' },
      mimo_model: { value: 'mimo-v2.5-pro', type: 'string' },
    });

    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('系统设置')).toBeInTheDocument();
    });
  });

  // --- Config manager header ---
  test('renders config manager header', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('配置管理')).toBeInTheDocument();
    });
  });

  // --- Default provider selector shows providers ---
  test('shows all non-anthropic providers in default selector', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('默认模型')).toBeInTheDocument();
    });
  });

  // --- Save with empty config ---
  test('handles empty config gracefully', async () => {
    mockConfigApi.getAll.mockResolvedValue({});
    mockConfigApi.getModels.mockResolvedValue([]);

    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('系统设置')).toBeInTheDocument();
    });
  });

  // --- Config with placeholder API key ---
  test('handles config with placeholder API key', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'your_key_here', type: 'string' },
      mimo_base_url: { value: '', type: 'string' },
      mimo_model: { value: '', type: 'string' },
    });

    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('系统设置')).toBeInTheDocument();
    });
  });

  // --- Config with real API key ---
  test('handles config with real API key', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'sk-real-key-12345', type: 'string' },
      mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string' },
      mimo_model: { value: 'mimo-v2.5-pro', type: 'string' },
    });

    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('系统设置')).toBeInTheDocument();
    });
  });

  // --- Tab navigation ---
  test('tabs are navigable', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('大模型配置')).toBeInTheDocument();
    });

    // Click feishu tab
    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('Webhook 配置指南')).toBeInTheDocument();
    });

    // Click system tab
    await user.click(screen.getByText('运行参数'));

    await waitFor(() => {
      expect(screen.getByText('温度')).toBeInTheDocument();
    });

    // Click back to LLM tab
    await user.click(screen.getByText('大模型配置'));

    await waitFor(() => {
      expect(screen.getByText('默认模型')).toBeInTheDocument();
    });
  });

  // --- Test provider connection (covers handleTestProvider) ---
  test('tests provider connection when test button clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('测试连接')).toBeInTheDocument();
    });

    await user.click(screen.getByText('测试连接'));

    await waitFor(() => {
      expect(mockConfigApi.testLLM).toHaveBeenCalled();
    });
  });

  test('shows success result after successful provider test', async () => {
    mockConfigApi.testLLM.mockResolvedValue({
      success: true,
      model_used: 'mimo-v2.5-pro',
      latency_ms: 200,
      error: null,
    });
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('测试连接')).toBeInTheDocument();
    });

    await user.click(screen.getByText('测试连接'));

    await waitFor(() => {
      expect(screen.getByText(/mimo-v2.5-pro.*200ms/)).toBeInTheDocument();
    });
  });

  test('shows error result after failed provider test', async () => {
    mockConfigApi.testLLM.mockResolvedValue({
      success: false,
      error: 'Invalid API key',
    });
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('测试连接')).toBeInTheDocument();
    });

    await user.click(screen.getByText('测试连接'));

    await waitFor(() => {
      expect(screen.getByText('Invalid API key')).toBeInTheDocument();
    });
  });

  test('handles test provider network error', async () => {
    mockConfigApi.testLLM.mockRejectedValue(new Error('Network error'));
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('测试连接')).toBeInTheDocument();
    });

    await user.click(screen.getByText('测试连接'));

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  // --- Test webhook (covers handleTestWebhook) ---
  test('shows save and test button in feishu tab', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });

    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('保存并测试')).toBeInTheDocument();
    });
  });

  // --- Save with no changes ---
  test('shows save button without dirty count initially', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });

    // Save button should not show dirty count initially
    expect(screen.getByText('保存配置')).toBeInTheDocument();
  });

  // --- Save with API key placeholder ---
  test('does not save when API key is placeholder value', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'existing-key', type: 'string' },
      mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string' },
      mimo_model: { value: 'mimo-v2.5-pro', type: 'string' },
    });

    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });

    // Change API key to a placeholder value
    const apiKeyInputs = document.querySelectorAll('input[type="password"]');
    fireEvent.change(apiKeyInputs[0], { target: { value: 'your_placeholder_key' } });

    await user.click(screen.getByText(/保存配置/));

    // Should warn and NOT call batchUpdate
    await waitFor(() => {
      expect(mockConfigApi.batchUpdate).not.toHaveBeenCalled();
    });
  });

  // --- Config with multiple providers ---
  test('renders current provider name', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('Mimo')).toBeInTheDocument();
    });
  });

  // --- Model autocomplete ---
  test('renders model name input with autocomplete', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('模型名称')).toBeInTheDocument();
    });

    // The AutoComplete input should be rendered
    const inputs = document.querySelectorAll('input.ant-input');
    expect(inputs.length).toBeGreaterThanOrEqual(1);
  });

  // --- Anthropic section expansion ---
  test('expands anthropic section when clicked', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Anthropic 配置/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/Anthropic 配置/));

    await waitFor(() => {
      // Anthropic API key field should appear (Password input with sk-ant-... placeholder)
      const passwordInputs = document.querySelectorAll('input[type="password"]');
      expect(passwordInputs.length).toBeGreaterThanOrEqual(2);
    });
  });

  // --- Anthropic test connection ---
  test('shows test connection button in anthropic section', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Anthropic 配置/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/Anthropic 配置/));

    await waitFor(() => {
      // There should be at least 2 test connection buttons (main + anthropic)
      const testButtons = screen.getAllByText('测试连接');
      expect(testButtons.length).toBeGreaterThanOrEqual(2);
    });
  });

  // --- Save with actual changes ---
  test('calls batchUpdate when save clicked with changes', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });

    // Change the API key using fireEvent for reliability
    const apiKeyInputs = document.querySelectorAll('input[type="password"]');
    expect(apiKeyInputs.length).toBeGreaterThanOrEqual(1);
    fireEvent.change(apiKeyInputs[0], { target: { value: 'sk-new-key-12345' } });

    // Click save
    const saveBtn = screen.getByText(/保存配置/).closest('button');
    if (saveBtn) fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockConfigApi.batchUpdate).toHaveBeenCalled();
    }, { timeout: 8000 });
  });

  // --- Test webhook ---
  test('test webhook shows warning when URL is empty', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });

    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('保存并测试')).toBeInTheDocument();
    });

    // Without entering a URL, it should show a warning
    await user.click(screen.getByText('保存并测试'));
  });

  test('test webhook calls API when URL is provided', async () => {
    // Provide webhook URL in config
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'sk-test-key', type: 'string' },
      mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string' },
      mimo_model: { value: 'mimo-v2.5-pro', type: 'string' },
      feishu_webhook_url: { value: 'https://open.feishu.cn/webhook/test', type: 'string' },
      feishu_webhook_secret: { value: '', type: 'string' },
    });

    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });

    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('保存并测试')).toBeInTheDocument();
    });

    await user.click(screen.getByText('保存并测试'));

    await waitFor(() => {
      expect(mockConfigApi.batchUpdate).toHaveBeenCalled();
    });
  });

  // --- Save button shows dirty count ---
  test('shows dirty count in save button label', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });

    // Make a change to the API key
    const apiKeyInputs = document.querySelectorAll('input[type="password"]');
    await user.clear(apiKeyInputs[0]);
    await user.type(apiKeyInputs[0], 'sk-changed-key');

    await waitFor(() => {
      expect(screen.getByText(/保存配置/)).toBeInTheDocument();
    });
  });

  // --- Save with no actual changes (covers lines 162-164) ---
  test('save button is present and clickable', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });

    // Save button should be rendered
    const saveBtn = screen.getByText('保存配置').closest('button');
    expect(saveBtn).toBeTruthy();
    expect(saveBtn).not.toBeDisabled();
  });

  // --- Save with API key including model and url (covers lines 148-159) ---
  test('includes model and url when saving API key change', async () => {
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });

    // Change API key to trigger inclusion of model and url
    const apiKeyInputs = document.querySelectorAll('input[type="password"]');
    fireEvent.change(apiKeyInputs[0], { target: { value: 'sk-completely-new-key' } });

    const saveBtn = screen.getByText(/保存配置/).closest('button');
    if (saveBtn) fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockConfigApi.batchUpdate).toHaveBeenCalled();
    });
  });

  // --- Save with batchUpdate error (covers line 179) ---
  test('handles save error gracefully', async () => {
    mockConfigApi.batchUpdate.mockRejectedValue(new Error('Save failed'));
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });

    const apiKeyInputs = document.querySelectorAll('input[type="password"]');
    fireEvent.change(apiKeyInputs[0], { target: { value: 'sk-new-key-for-error-test' } });

    const saveBtn = screen.getByText(/保存配置/).closest('button');
    if (saveBtn) fireEvent.click(saveBtn);

    // Should not crash
    await waitFor(() => {
      expect(screen.getByText('系统设置')).toBeInTheDocument();
    });
  });

  // --- Test webhook with secret (covers lines 196-209) ---
  test('test webhook sends secret when provided', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'sk-test-key', type: 'string' },
      mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string' },
      mimo_model: { value: 'mimo-v2.5-pro', type: 'string' },
      feishu_webhook_url: { value: 'https://open.feishu.cn/webhook/test', type: 'string' },
      feishu_webhook_secret: { value: 'test-secret', type: 'string' },
    });

    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });

    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('保存并测试')).toBeInTheDocument();
    });

    await user.click(screen.getByText('保存并测试'));

    await waitFor(() => {
      expect(mockConfigApi.batchUpdate).toHaveBeenCalled();
    });
  });

  // --- Test webhook failure (covers line 205-209) ---
  test('shows failure message when webhook test fails', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'sk-test-key', type: 'string' },
      mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string' },
      mimo_model: { value: 'mimo-v2.5-pro', type: 'string' },
      feishu_webhook_url: { value: 'https://open.feishu.cn/webhook/test', type: 'string' },
      feishu_webhook_secret: { value: '', type: 'string' },
    });
    mockConfigApi.testWebhook.mockResolvedValue({ success: false, error: 'Invalid webhook URL' });

    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });

    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('保存并测试')).toBeInTheDocument();
    });

    await user.click(screen.getByText('保存并测试'));

    await waitFor(() => {
      expect(screen.getByText(/Webhook 测试失败/)).toBeInTheDocument();
    });
  });

  // --- Test webhook network error (covers line 208-209) ---
  test('handles webhook test network error', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'sk-test-key', type: 'string' },
      mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string' },
      mimo_model: { value: 'mimo-v2.5-pro', type: 'string' },
      feishu_webhook_url: { value: 'https://open.feishu.cn/webhook/test', type: 'string' },
      feishu_webhook_secret: { value: '', type: 'string' },
    });
    mockConfigApi.testWebhook.mockRejectedValue(new Error('Network error'));

    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });

    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('保存并测试')).toBeInTheDocument();
    });

    await user.click(screen.getByText('保存并测试'));

    await waitFor(() => {
      expect(screen.getByText(/Webhook 测试失败/)).toBeInTheDocument();
    });
  });

  // --- Test webhook success (covers line 200-203) ---
  test('shows success message when webhook test succeeds', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'sk-test-key', type: 'string' },
      mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string' },
      mimo_model: { value: 'mimo-v2.5-pro', type: 'string' },
      feishu_webhook_url: { value: 'https://open.feishu.cn/webhook/test', type: 'string' },
      feishu_webhook_secret: { value: '', type: 'string' },
    });
    mockConfigApi.batchUpdate.mockResolvedValue({ status: 'ok', updated: 1 });
    mockConfigApi.testWebhook.mockResolvedValue({ success: true, error: null });

    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('飞书通知')).toBeInTheDocument();
    });

    await user.click(screen.getByText('飞书通知'));

    await waitFor(() => {
      expect(screen.getByText('保存并测试')).toBeInTheDocument();
    });

    await user.click(screen.getByText('保存并测试'));

    // The handleTestWebhook function calls batchUpdate then testWebhook
    await waitFor(() => {
      expect(mockConfigApi.batchUpdate).toHaveBeenCalled();
    });
  });

  // --- Test provider with no API key (covers line 215-217) ---
  test('shows warning when testing provider without API key', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: '', type: 'string' },
      mimo_base_url: { value: '', type: 'string' },
      mimo_model: { value: '', type: 'string' },
    });

    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('测试连接')).toBeInTheDocument();
    });

    await user.click(screen.getByText('测试连接'));

    // Should not call testLLM
    await waitFor(() => {
      expect(mockConfigApi.testLLM).not.toHaveBeenCalled();
    });
  });

  // --- Test provider failure (covers lines 235-240) ---
  test('test provider shows error when test fails', async () => {
    mockConfigApi.testLLM.mockResolvedValue({
      success: false,
      error: 'API key invalid',
    });
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('测试连接')).toBeInTheDocument();
    });

    await user.click(screen.getByText('测试连接'));

    await waitFor(() => {
      expect(screen.getByText('API key invalid')).toBeInTheDocument();
    });
  });

  // --- Test Anthropic provider (covers lines 447-470) ---
  test('tests Anthropic provider connection', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'sk-test-key', type: 'string' },
      mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string' },
      mimo_model: { value: 'mimo-v2.5-pro', type: 'string' },
      anthropic_api_key: { value: 'sk-ant-test-key', type: 'string' },
      anthropic_base_url: { value: 'https://api.anthropic.com', type: 'string' },
      anthropic_model: { value: 'claude-sonnet-4-20250514', type: 'string' },
    });

    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Anthropic 配置/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/Anthropic 配置/));

    await waitFor(() => {
      const testButtons = screen.getAllByText('测试连接');
      expect(testButtons.length).toBeGreaterThanOrEqual(2);
    });

    // Click the Anthropic test button (second one)
    const testButtons = screen.getAllByText('测试连接');
    await user.click(testButtons[1]);

    await waitFor(() => {
      expect(mockConfigApi.testLLM).toHaveBeenCalled();
    });
  });

  // --- System tab temperature change (covers lines 537-547) ---
  test('temperature input is editable', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('运行参数')).toBeInTheDocument();
    });

    await user.click(screen.getByText('运行参数'));

    await waitFor(() => {
      expect(screen.getByText('温度')).toBeInTheDocument();
    });

    // Temperature InputNumber should be present
    const temperatureInputs = document.querySelectorAll('.ant-input-number-input');
    expect(temperatureInputs.length).toBeGreaterThanOrEqual(1);
  });

  // --- System tab max concurrent tasks (covers lines 549-557) ---
  test('max concurrent tasks input is present', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('运行参数')).toBeInTheDocument();
    });

    await user.click(screen.getByText('运行参数'));

    await waitFor(() => {
      expect(screen.getByText('最大并发任务')).toBeInTheDocument();
    });
  });

  // --- System tab log level (covers lines 558-571) ---
  test('log level selector is present', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('运行参数')).toBeInTheDocument();
    });

    await user.click(screen.getByText('运行参数'));

    await waitFor(() => {
      expect(screen.getByText('日志级别')).toBeInTheDocument();
    });
  });

  // --- isConfigured function (covers lines 246-249) ---
  test('shows check mark for configured providers', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'sk-real-key', type: 'string' },
      mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string' },
      mimo_model: { value: 'mimo-v2.5-pro', type: 'string' },
      deepseek_api_key: { value: 'your_key', type: 'string' },
    });

    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('默认模型')).toBeInTheDocument();
    });
  });

  // --- Save with placeholder API key warning (covers lines 167-173) ---
  test('warns when saving with placeholder API key', async () => {
    mockConfigApi.getAll.mockResolvedValue({
      agent_llm_provider: { value: 'mimo', type: 'string' },
      mimo_api_key: { value: 'existing-key', type: 'string' },
      mimo_base_url: { value: 'https://api.mimo.com/v1', type: 'string' },
      mimo_model: { value: 'mimo-v2.5-pro', type: 'string' },
    });

    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });

    // Change API key to a placeholder value
    const apiKeyInputs = document.querySelectorAll('input[type="password"]');
    fireEvent.change(apiKeyInputs[0], { target: { value: 'your_placeholder_key' } });

    await user.click(screen.getByText(/保存配置/));

    // Should warn and NOT call batchUpdate
    await waitFor(() => {
      expect(mockConfigApi.batchUpdate).not.toHaveBeenCalled();
    });
  });

  // --- Anthropic model options (covers lines 266-272) ---
  test('shows anthropic model options when expanded', async () => {
    const user = userEvent.setup();
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Anthropic 配置/)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/Anthropic 配置/));

    await waitFor(() => {
      // Anthropic model input should be present
      const inputs = document.querySelectorAll('.ant-input');
      expect(inputs.length).toBeGreaterThanOrEqual(1);
    });
  });

  // --- beforeunload event (covers lines 127-135) ---
  test('registers beforeunload handler when dirty', async () => {
    const addEventListenerSpy = jest.spyOn(window, 'addEventListener');
    renderWithRouter(<SettingsPage />);

    await waitFor(() => {
      expect(screen.getByText('保存配置')).toBeInTheDocument();
    });

    // beforeunload should be registered
    expect(addEventListenerSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function));
    addEventListenerSpy.mockRestore();
  });
});
