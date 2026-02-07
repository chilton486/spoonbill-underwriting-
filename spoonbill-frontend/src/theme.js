import { createTheme } from '@mui/material/styles'

// Shared theme tokens for ChatGPT-style colorway
// Used by both Internal Console and Practice Portal
export const sharedThemeTokens = {
  colors: {
    primary: '#000000',
    secondary: '#666666',
    background: '#ffffff',
    paper: '#ffffff',
    text: {
      primary: '#1a1a1a',
      secondary: '#6b7280',
    },
    border: '#e5e7eb',
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  },
}

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: sharedThemeTokens.colors.primary,
    },
    secondary: {
      main: sharedThemeTokens.colors.secondary,
    },
    background: {
      default: sharedThemeTokens.colors.background,
      paper: sharedThemeTokens.colors.paper,
    },
    text: {
      primary: sharedThemeTokens.colors.text.primary,
      secondary: sharedThemeTokens.colors.text.secondary,
    },
    success: { main: sharedThemeTokens.colors.success },
    warning: { main: sharedThemeTokens.colors.warning },
    error: { main: sharedThemeTokens.colors.error },
    divider: sharedThemeTokens.colors.border,
  },
  shape: {
    borderRadius: 8
  },
  typography: {
    fontFamily: sharedThemeTokens.typography.fontFamily,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
        },
        contained: {
          backgroundColor: '#1a1a1a',
          color: '#ffffff',
          '&:hover': {
            backgroundColor: '#333333',
          },
        },
        outlined: {
          borderColor: '#d1d5db',
          color: '#1a1a1a',
          '&:hover': {
            borderColor: '#9ca3af',
            backgroundColor: '#f9fafb',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderColor: sharedThemeTokens.colors.border,
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
        },
      },
    },
  },
})
