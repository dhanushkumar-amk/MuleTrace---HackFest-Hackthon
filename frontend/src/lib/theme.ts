import { create } from 'zustand';

type Theme = 'light';

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

function applyTheme() {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.classList.remove('dark');
  root.classList.add('light');
  localStorage.setItem('muletrace_theme', 'light');
}

export const useThemeStore = create<ThemeState>((set) => {
  applyTheme();

  return {
    theme: 'light',
    setTheme: () => {
      applyTheme();
      set({ theme: 'light' });
    },
    toggleTheme: () => {
      applyTheme();
      set({ theme: 'light' });
    },
  };
});
