import { useTheme } from '../lib/theme';
import { Icon } from './Icons';

export function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const { theme, toggle } = useTheme();
  const label = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme';
  return (
    <button
      type="button"
      className={`btn btn-icon btn-ghost theme-toggle ${compact ? 'theme-toggle-compact' : ''}`.trim()}
      onClick={toggle}
      aria-label={label}
      title={label}
    >
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={18} />
    </button>
  );
}
