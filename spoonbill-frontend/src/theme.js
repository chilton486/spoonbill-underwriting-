import { createTheme } from '@mui/material/styles'

/**
 * Internal Console Theme - Black/White ChatGPT-style colorway
 * 
 * Design principles:
 * - White background, black text for maximum readability
 * - Neutral grays for borders and muted elements
 * - High contrast for all interactive elements
 * - Consistent styling across all components
 */

// Theme tokens - single source of truth for all colors
export const themeTokens = {
  colors: {
    // Core colors
    background: '#ffffff',
    paper: '#ffffff',
    
    // Text colors
    text: {
      primary: '#000000',
      secondary: '#6b7280',
      disabled: '#9ca3af',
    },
    
    // Border colors
    border: {
      light: '#e5e7eb',
      medium: '#d1d5db',
      dark: '#9ca3af',
    },
    
    // Interactive states
    hover: '#f9fafb',
    active: '#f3f4f6',
    focus: '#000000',
    
    // Status colors (used sparingly, with borders for accessibility)
    status: {
      success: '#10b981',
      warning: '#f59e0b',
      error: '#ef4444',
      info: '#3b82f6',
    },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  },
}

export const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#000000',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#6b7280',
      contrastText: '#ffffff',
    },
    background: {
      default: themeTokens.colors.background,
      paper: themeTokens.colors.paper,
    },
    text: {
      primary: themeTokens.colors.text.primary,
      secondary: themeTokens.colors.text.secondary,
      disabled: themeTokens.colors.text.disabled,
    },
    success: { 
      main: themeTokens.colors.status.success,
      contrastText: '#ffffff',
    },
    warning: { 
      main: themeTokens.colors.status.warning,
      contrastText: '#000000',
    },
    error: { 
      main: themeTokens.colors.status.error,
      contrastText: '#ffffff',
    },
    info: {
      main: themeTokens.colors.status.info,
      contrastText: '#ffffff',
    },
    divider: themeTokens.colors.border.light,
    action: {
      hover: themeTokens.colors.hover,
      selected: themeTokens.colors.active,
      disabled: themeTokens.colors.text.disabled,
      disabledBackground: themeTokens.colors.hover,
    },
  },
  shape: {
    borderRadius: 6,
  },
  typography: {
    fontFamily: themeTokens.typography.fontFamily,
    h1: { color: themeTokens.colors.text.primary },
    h2: { color: themeTokens.colors.text.primary },
    h3: { color: themeTokens.colors.text.primary },
    h4: { color: themeTokens.colors.text.primary },
    h5: { color: themeTokens.colors.text.primary },
    h6: { color: themeTokens.colors.text.primary },
    body1: { color: themeTokens.colors.text.primary },
    body2: { color: themeTokens.colors.text.secondary },
  },
  components: {
    // CSS Baseline - ensure white background
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: themeTokens.colors.background,
          color: themeTokens.colors.text.primary,
        },
      },
    },
    
    // Buttons - black primary, outlined secondary
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 6,
        },
        contained: {
          backgroundColor: '#000000',
          color: '#ffffff',
          '&:hover': {
            backgroundColor: '#333333',
          },
          '&:disabled': {
            backgroundColor: themeTokens.colors.border.medium,
            color: themeTokens.colors.text.disabled,
          },
        },
        outlined: {
          borderColor: themeTokens.colors.border.medium,
          color: themeTokens.colors.text.primary,
          '&:hover': {
            borderColor: themeTokens.colors.border.dark,
            backgroundColor: themeTokens.colors.hover,
          },
          '&:disabled': {
            borderColor: themeTokens.colors.border.light,
            color: themeTokens.colors.text.disabled,
          },
        },
        text: {
          color: themeTokens.colors.text.primary,
          '&:hover': {
            backgroundColor: themeTokens.colors.hover,
          },
        },
      },
    },
    
    // Paper - white with subtle border
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundColor: themeTokens.colors.paper,
          borderColor: themeTokens.colors.border.light,
        },
        outlined: {
          borderColor: themeTokens.colors.border.light,
        },
      },
    },
    
    // Cards - white background
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: themeTokens.colors.paper,
          border: `1px solid ${themeTokens.colors.border.light}`,
        },
      },
    },
    
    // Tables - high contrast headers and rows
    MuiTableContainer: {
      styleOverrides: {
        root: {
          backgroundColor: themeTokens.colors.paper,
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          backgroundColor: themeTokens.colors.hover,
          '& .MuiTableCell-head': {
            color: themeTokens.colors.text.primary,
            fontWeight: 600,
            borderBottom: `2px solid ${themeTokens.colors.border.medium}`,
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:hover': {
            backgroundColor: themeTokens.colors.hover,
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          color: themeTokens.colors.text.primary,
          borderBottom: `1px solid ${themeTokens.colors.border.light}`,
        },
        head: {
          color: themeTokens.colors.text.primary,
          fontWeight: 600,
        },
      },
    },
    
    // Tabs - black text, clear active state
    MuiTabs: {
      styleOverrides: {
        root: {
          borderBottom: `1px solid ${themeTokens.colors.border.light}`,
        },
        indicator: {
          backgroundColor: themeTokens.colors.text.primary,
          height: 2,
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          color: themeTokens.colors.text.secondary,
          textTransform: 'none',
          fontWeight: 500,
          '&.Mui-selected': {
            color: themeTokens.colors.text.primary,
            fontWeight: 600,
          },
          '&:hover': {
            backgroundColor: themeTokens.colors.hover,
          },
        },
      },
    },
    
    // Dialogs/Modals - white background
    MuiDialog: {
      styleOverrides: {
        paper: {
          backgroundColor: themeTokens.colors.paper,
          border: `1px solid ${themeTokens.colors.border.light}`,
        },
      },
    },
    MuiDialogTitle: {
      styleOverrides: {
        root: {
          color: themeTokens.colors.text.primary,
          fontWeight: 600,
        },
      },
    },
    MuiDialogContent: {
      styleOverrides: {
        root: {
          color: themeTokens.colors.text.primary,
        },
      },
    },
    
    // Chips/Badges - outlined style for better accessibility
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          borderRadius: 4,
        },
        filled: {
          backgroundColor: themeTokens.colors.active,
          color: themeTokens.colors.text.primary,
        },
        outlined: {
          borderColor: themeTokens.colors.border.medium,
          color: themeTokens.colors.text.primary,
        },
        colorSuccess: {
          backgroundColor: '#dcfce7',
          color: '#166534',
          border: '1px solid #86efac',
        },
        colorWarning: {
          backgroundColor: '#fef3c7',
          color: '#92400e',
          border: '1px solid #fcd34d',
        },
        colorError: {
          backgroundColor: '#fee2e2',
          color: '#991b1b',
          border: '1px solid #fca5a5',
        },
        colorInfo: {
          backgroundColor: '#dbeafe',
          color: '#1e40af',
          border: '1px solid #93c5fd',
        },
      },
    },
    
    // Text Fields - clear borders and focus states
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            backgroundColor: themeTokens.colors.paper,
            '& fieldset': {
              borderColor: themeTokens.colors.border.medium,
            },
            '&:hover fieldset': {
              borderColor: themeTokens.colors.border.dark,
            },
            '&.Mui-focused fieldset': {
              borderColor: themeTokens.colors.focus,
              borderWidth: 2,
            },
          },
          '& .MuiInputBase-input': {
            color: themeTokens.colors.text.primary,
          },
          '& .MuiInputLabel-root': {
            color: themeTokens.colors.text.secondary,
          },
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: themeTokens.colors.paper,
          '& fieldset': {
            borderColor: themeTokens.colors.border.medium,
          },
          '&:hover fieldset': {
            borderColor: themeTokens.colors.border.dark,
          },
          '&.Mui-focused fieldset': {
            borderColor: themeTokens.colors.focus,
            borderWidth: 2,
          },
        },
        input: {
          color: themeTokens.colors.text.primary,
        },
      },
    },
    
    // Select - consistent with text fields
    MuiSelect: {
      styleOverrides: {
        root: {
          backgroundColor: themeTokens.colors.paper,
        },
        icon: {
          color: themeTokens.colors.text.secondary,
        },
      },
    },
    MuiMenuItem: {
      styleOverrides: {
        root: {
          color: themeTokens.colors.text.primary,
          '&:hover': {
            backgroundColor: themeTokens.colors.hover,
          },
          '&.Mui-selected': {
            backgroundColor: themeTokens.colors.active,
            '&:hover': {
              backgroundColor: themeTokens.colors.active,
            },
          },
        },
      },
    },
    
    // Alerts - high contrast with borders
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 6,
        },
        standardSuccess: {
          backgroundColor: '#dcfce7',
          color: '#166534',
          border: '1px solid #86efac',
          '& .MuiAlert-icon': {
            color: '#166534',
          },
        },
        standardWarning: {
          backgroundColor: '#fef3c7',
          color: '#92400e',
          border: '1px solid #fcd34d',
          '& .MuiAlert-icon': {
            color: '#92400e',
          },
        },
        standardError: {
          backgroundColor: '#fee2e2',
          color: '#991b1b',
          border: '1px solid #fca5a5',
          '& .MuiAlert-icon': {
            color: '#991b1b',
          },
        },
        standardInfo: {
          backgroundColor: '#dbeafe',
          color: '#1e40af',
          border: '1px solid #93c5fd',
          '& .MuiAlert-icon': {
            color: '#1e40af',
          },
        },
      },
    },
    
    // Dividers
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: themeTokens.colors.border.light,
        },
      },
    },
    
    // Tooltips
    MuiTooltip: {
      styleOverrides: {
        tooltip: {
          backgroundColor: themeTokens.colors.text.primary,
          color: themeTokens.colors.paper,
        },
      },
    },
    
    // Circular Progress
    MuiCircularProgress: {
      styleOverrides: {
        root: {
          color: themeTokens.colors.text.primary,
        },
      },
    },
    
    // Container
    MuiContainer: {
      styleOverrides: {
        root: {
          backgroundColor: themeTokens.colors.background,
        },
      },
    },
  },
})
