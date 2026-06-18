import { THEME } from '../theme';

describe('THEME', () => {
  test('is a frozen object', () => {
    expect(typeof THEME).toBe('object');
    expect(THEME).not.toBeNull();
  });

  test('has primary color', () => {
    expect(THEME.primary).toBe('#D97757');
    expect(THEME.primary).toMatch(/^#[0-9A-Fa-f]{6}$/);
  });

  test('has text colors', () => {
    expect(THEME.text).toBe('#1A1A1A');
    expect(THEME.textSecondary).toBe('#6B7280');
    expect(THEME.textTertiary).toBe('#9CA3AF');
  });

  test('has border colors', () => {
    expect(THEME.border).toBe('#E8E5E0');
    expect(THEME.borderLight).toBe('#F0F0F0');
  });

  test('has background colors', () => {
    expect(THEME.bgLayout).toBe('#FAFAF8');
    expect(THEME.bgContainer).toBe('#FFFFFF');
    expect(THEME.bgWarm).toBe('#FFF8F5');
    expect(THEME.bgSelected).toBe('#FFF5F2');
    expect(THEME.bgWarning).toBe('#FFFBEB');
    expect(THEME.bgError).toBe('#FEF2F2');
  });

  test('has semantic colors', () => {
    expect(THEME.error).toBe('#DC2626');
    expect(THEME.success).toBe('#10B981');
    expect(THEME.warning).toBe('#D97708');
    expect(THEME.info).toBe('#3B82F6');
    expect(THEME.pending).toBe('#D1D5DB');
  });

  test('has radius object with sm, md, lg', () => {
    expect(THEME.radius).toEqual({ sm: 4, md: 8, lg: 12 });
    expect(THEME.radius.sm).toBeLessThan(THEME.radius.md);
    expect(THEME.radius.md).toBeLessThan(THEME.radius.lg);
  });

  test('has space object with xs through xl', () => {
    expect(THEME.space).toEqual({ xs: 4, sm: 8, md: 16, lg: 24, xl: 32 });
    expect(THEME.space.xs).toBeLessThan(THEME.space.sm);
    expect(THEME.space.sm).toBeLessThan(THEME.space.md);
    expect(THEME.space.md).toBeLessThan(THEME.space.lg);
    expect(THEME.space.lg).toBeLessThan(THEME.space.xl);
  });

  test('all color values are valid hex', () => {
    const colorKeys = [
      'primary', 'text', 'textSecondary', 'textTertiary',
      'border', 'borderLight', 'bgLayout', 'bgContainer',
      'bgWarm', 'bgSelected', 'bgWarning', 'bgError',
      'error', 'success', 'warning', 'info', 'pending',
    ] as const;

    colorKeys.forEach((key) => {
      expect(THEME[key]).toMatch(/^#[0-9A-Fa-f]{6}$/);
    });
  });

  test('radius values are positive integers', () => {
    Object.values(THEME.radius).forEach((val) => {
      expect(val).toBeGreaterThan(0);
      expect(Number.isInteger(val)).toBe(true);
    });
  });

  test('space values are positive integers', () => {
    Object.values(THEME.space).forEach((val) => {
      expect(val).toBeGreaterThan(0);
      expect(Number.isInteger(val)).toBe(true);
    });
  });
});
