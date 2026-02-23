import { createTheme } from '@mui/material/styles'

export const tokens = {
  colors: {
    background: '#f8fafc',
    surface: '#ffffff',
    surfaceHover: '#f1f5f9',
    surfaceActive: '#e2e8f0',

    text: {
      primary: '#0f172a',
      secondary: '#475569',
      muted: '#94a3b8',
      inverse: '#ffffff',
    },

    border: {
      light: '#e2e8f0',
      DEFAULT: '#cbd5e1',
      dark: '#94a3b8',
    },

    accent: {
      50: '#eff6ff',
      100: '#dbeafe',
      200: '#bfdbfe',
      300: '#93c5fd',
      400: '#60a5fa',
      500: '#3b82f6',
      600: '#2563eb',
      700: '#1d4ed8',
    },

    status: {
      success: '#059669',
      successBg: '#ecfdf5',
      successBorder: '#a7f3d0',
      warning: '#d97706',
      warningBg: '#fffbeb',
      warningBorder: '#fcd34d',
      error: '#dc2626',
      errorBg: '#fef2f2',
      errorBorder: '#fca5a5',
      info: '#2563eb',
      infoBg: '#eff6ff',
      infoBorder: '#93c5fd',
    },
  },

  spacing: {
    xs: 4,
    sm: 8,
    md: 12,
    lg: 16,
    xl: 24,
    xxl: 32,
  },

  radius: {
    sm: 6,
    md: 10,
    lg: 14,
    full: 9999,
  },

  shadow: {
    sm: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
    md: '0 1px 3px 0 rgb(0 0 0 / 0.08), 0 1px 2px -1px rgb(0 0 0 / 0.08)',
    lg: '0 4px 6px -1px rgb(0 0 0 / 0.08), 0 2px 4px -2px rgb(0 0 0 / 0.05)',
    xl: '0 10px 15px -3px rgb(0 0 0 / 0.08), 0 4px 6px -4px rgb(0 0 0 / 0.05)',
  },

  transition: {
    fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
    normal: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
    slow: '300ms cubic-bezier(0.4, 0, 0.2, 1)',
  },

  typography: {
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    mono: '"JetBrains Mono", "Fira Code", "SF Mono", Consolas, monospace',
  },
}

export function createSpoonbillTheme(overrides = {}) {
  const t = tokens

  return createTheme({
    palette: {
      mode: 'light',
      primary: {
        main: t.colors.accent[600],
        light: t.colors.accent[400],
        dark: t.colors.accent[700],
        contrastText: '#ffffff',
      },
      secondary: {
        main: t.colors.text.secondary,
        contrastText: '#ffffff',
      },
      background: {
        default: t.colors.background,
        paper: t.colors.surface,
      },
      text: {
        primary: t.colors.text.primary,
        secondary: t.colors.text.secondary,
        disabled: t.colors.text.muted,
      },
      success: { main: t.colors.status.success, contrastText: '#fff' },
      warning: { main: t.colors.status.warning, contrastText: '#fff' },
      error: { main: t.colors.status.error, contrastText: '#fff' },
      info: { main: t.colors.status.info, contrastText: '#fff' },
      divider: t.colors.border.light,
      action: {
        hover: t.colors.surfaceHover,
        selected: t.colors.surfaceActive,
        disabled: t.colors.text.muted,
        disabledBackground: t.colors.surfaceHover,
      },
    },
    shape: { borderRadius: t.radius.sm },
    typography: {
      fontFamily: t.typography.fontFamily,
      h1: { fontWeight: 700, color: t.colors.text.primary, letterSpacing: '-0.025em' },
      h2: { fontWeight: 700, color: t.colors.text.primary, letterSpacing: '-0.02em' },
      h3: { fontWeight: 700, color: t.colors.text.primary, letterSpacing: '-0.015em' },
      h4: { fontWeight: 700, color: t.colors.text.primary, letterSpacing: '-0.01em' },
      h5: { fontWeight: 600, color: t.colors.text.primary },
      h6: { fontWeight: 600, color: t.colors.text.primary },
      subtitle1: { fontWeight: 600, color: t.colors.text.primary },
      subtitle2: { fontWeight: 600, color: t.colors.text.secondary, fontSize: '0.8rem' },
      body1: { color: t.colors.text.primary, lineHeight: 1.6 },
      body2: { color: t.colors.text.secondary, lineHeight: 1.6 },
      caption: { color: t.colors.text.muted, fontSize: '0.75rem' },
      button: { textTransform: 'none', fontWeight: 600 },
    },
    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            backgroundColor: t.colors.background,
            color: t.colors.text.primary,
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
          },
          '*:focus-visible': {
            outline: `2px solid ${t.colors.accent[500]}`,
            outlineOffset: 2,
          },
        },
      },

      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: {
            borderRadius: t.radius.md,
            fontWeight: 600,
            padding: '8px 20px',
            transition: `all ${t.transition.fast}`,
          },
          contained: {
            backgroundColor: t.colors.accent[600],
            color: '#ffffff',
            boxShadow: t.shadow.sm,
            '&:hover': {
              backgroundColor: t.colors.accent[700],
              boxShadow: t.shadow.md,
            },
            '&:disabled': {
              backgroundColor: t.colors.border.DEFAULT,
              color: t.colors.text.muted,
            },
          },
          outlined: {
            borderColor: t.colors.border.DEFAULT,
            color: t.colors.text.primary,
            '&:hover': {
              borderColor: t.colors.accent[500],
              backgroundColor: t.colors.accent[50],
              color: t.colors.accent[700],
            },
          },
          text: {
            color: t.colors.accent[600],
            '&:hover': {
              backgroundColor: t.colors.accent[50],
            },
          },
          sizeSmall: { padding: '4px 12px', fontSize: '0.8rem' },
          sizeLarge: { padding: '12px 28px', fontSize: '1rem' },
          containedError: {
            backgroundColor: t.colors.status.error,
            '&:hover': { backgroundColor: '#b91c1c' },
          },
        },
      },

      MuiPaper: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            backgroundColor: t.colors.surface,
            border: `1px solid ${t.colors.border.light}`,
            borderRadius: t.radius.lg,
            transition: `box-shadow ${t.transition.normal}`,
          },
          outlined: {
            borderColor: t.colors.border.light,
          },
        },
      },

      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            border: `1px solid ${t.colors.border.light}`,
            borderRadius: t.radius.lg,
            transition: `all ${t.transition.normal}`,
            '&:hover': {
              boxShadow: t.shadow.md,
              borderColor: t.colors.border.DEFAULT,
            },
          },
        },
      },

      MuiTableContainer: {
        styleOverrides: {
          root: {
            borderRadius: t.radius.lg,
            border: `1px solid ${t.colors.border.light}`,
            overflow: 'hidden',
          },
        },
      },
      MuiTableHead: {
        styleOverrides: {
          root: {
            backgroundColor: t.colors.surfaceHover,
            '& .MuiTableCell-head': {
              color: t.colors.text.secondary,
              fontWeight: 600,
              fontSize: '0.75rem',
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              borderBottom: `2px solid ${t.colors.border.light}`,
              padding: '12px 16px',
            },
          },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            transition: `background-color ${t.transition.fast}`,
            '&:hover': { backgroundColor: t.colors.surfaceHover },
            '&:last-child td': { borderBottom: 0 },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            borderBottom: `1px solid ${t.colors.border.light}`,
            padding: '12px 16px',
            fontSize: '0.875rem',
          },
        },
      },

      MuiTabs: {
        styleOverrides: {
          root: {
            minHeight: 44,
          },
          indicator: {
            height: 2.5,
            borderRadius: '2px 2px 0 0',
            backgroundColor: t.colors.accent[600],
          },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 500,
            fontSize: '0.875rem',
            minHeight: 44,
            padding: '8px 16px',
            color: t.colors.text.muted,
            transition: `all ${t.transition.fast}`,
            '&.Mui-selected': {
              color: t.colors.accent[700],
              fontWeight: 600,
            },
            '&:hover': {
              color: t.colors.text.primary,
              backgroundColor: t.colors.surfaceHover,
            },
          },
        },
      },

      MuiDialog: {
        styleOverrides: {
          paper: {
            borderRadius: t.radius.lg,
            border: `1px solid ${t.colors.border.light}`,
            boxShadow: t.shadow.xl,
          },
        },
      },
      MuiDialogTitle: {
        styleOverrides: {
          root: {
            fontWeight: 600,
            fontSize: '1.125rem',
            padding: '20px 24px 12px',
          },
        },
      },
      MuiDialogContent: {
        styleOverrides: {
          root: { padding: '12px 24px 20px' },
          dividers: { borderColor: t.colors.border.light },
        },
      },
      MuiDialogActions: {
        styleOverrides: {
          root: {
            padding: '12px 24px 20px',
            gap: 8,
          },
        },
      },

      MuiChip: {
        styleOverrides: {
          root: {
            fontWeight: 600,
            borderRadius: t.radius.sm,
            fontSize: '0.75rem',
            height: 26,
          },
          colorSuccess: {
            backgroundColor: t.colors.status.successBg,
            color: t.colors.status.success,
            border: `1px solid ${t.colors.status.successBorder}`,
          },
          colorWarning: {
            backgroundColor: t.colors.status.warningBg,
            color: t.colors.status.warning,
            border: `1px solid ${t.colors.status.warningBorder}`,
          },
          colorError: {
            backgroundColor: t.colors.status.errorBg,
            color: t.colors.status.error,
            border: `1px solid ${t.colors.status.errorBorder}`,
          },
          colorInfo: {
            backgroundColor: t.colors.status.infoBg,
            color: t.colors.status.info,
            border: `1px solid ${t.colors.status.infoBorder}`,
          },
        },
      },

      MuiTextField: {
        defaultProps: { variant: 'outlined', size: 'small' },
        styleOverrides: {
          root: {
            '& .MuiOutlinedInput-root': {
              borderRadius: t.radius.md,
              backgroundColor: t.colors.surface,
              transition: `all ${t.transition.fast}`,
              '& fieldset': { borderColor: t.colors.border.DEFAULT },
              '&:hover fieldset': { borderColor: t.colors.accent[400] },
              '&.Mui-focused fieldset': {
                borderColor: t.colors.accent[500],
                borderWidth: 2,
              },
            },
            '& .MuiInputLabel-root': {
              color: t.colors.text.secondary,
              '&.Mui-focused': { color: t.colors.accent[600] },
            },
            '& .MuiFormHelperText-root': {
              marginLeft: 4,
              fontSize: '0.72rem',
            },
          },
        },
      },
      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            borderRadius: t.radius.md,
            '& fieldset': { borderColor: t.colors.border.DEFAULT },
            '&:hover fieldset': { borderColor: t.colors.accent[400] },
            '&.Mui-focused fieldset': { borderColor: t.colors.accent[500], borderWidth: 2 },
          },
        },
      },

      MuiSelect: {
        styleOverrides: {
          root: { borderRadius: t.radius.md },
          icon: { color: t.colors.text.muted },
        },
      },
      MuiMenuItem: {
        styleOverrides: {
          root: {
            fontSize: '0.875rem',
            '&:hover': { backgroundColor: t.colors.surfaceHover },
            '&.Mui-selected': {
              backgroundColor: t.colors.accent[50],
              '&:hover': { backgroundColor: t.colors.accent[100] },
            },
          },
        },
      },

      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: t.radius.md },
          standardSuccess: {
            backgroundColor: t.colors.status.successBg,
            color: '#065f46',
            border: `1px solid ${t.colors.status.successBorder}`,
            '& .MuiAlert-icon': { color: t.colors.status.success },
          },
          standardWarning: {
            backgroundColor: t.colors.status.warningBg,
            color: '#92400e',
            border: `1px solid ${t.colors.status.warningBorder}`,
            '& .MuiAlert-icon': { color: t.colors.status.warning },
          },
          standardError: {
            backgroundColor: t.colors.status.errorBg,
            color: '#991b1b',
            border: `1px solid ${t.colors.status.errorBorder}`,
            '& .MuiAlert-icon': { color: t.colors.status.error },
          },
          standardInfo: {
            backgroundColor: t.colors.status.infoBg,
            color: '#1e40af',
            border: `1px solid ${t.colors.status.infoBorder}`,
            '& .MuiAlert-icon': { color: t.colors.status.info },
          },
        },
      },

      MuiDivider: {
        styleOverrides: {
          root: { borderColor: t.colors.border.light },
        },
      },

      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: t.colors.text.primary,
            color: '#fff',
            fontSize: '0.75rem',
            borderRadius: t.radius.sm,
            padding: '6px 12px',
          },
        },
      },

      MuiCircularProgress: {
        styleOverrides: {
          root: { color: t.colors.accent[600] },
        },
      },

      MuiStepper: {
        styleOverrides: {
          root: { padding: '16px 0' },
        },
      },
      MuiStepLabel: {
        styleOverrides: {
          label: {
            fontSize: '0.8rem',
            '&.Mui-active': { color: t.colors.accent[700], fontWeight: 600 },
            '&.Mui-completed': { color: t.colors.status.success },
          },
        },
      },
      MuiStepIcon: {
        styleOverrides: {
          root: {
            '&.Mui-active': { color: t.colors.accent[600] },
            '&.Mui-completed': { color: t.colors.status.success },
          },
        },
      },

      MuiSwitch: {
        styleOverrides: {
          root: {
            '& .Mui-checked': {
              color: t.colors.accent[600],
              '& + .MuiSwitch-track': { backgroundColor: t.colors.accent[400] },
            },
          },
        },
      },

      MuiCheckbox: {
        styleOverrides: {
          root: {
            color: t.colors.border.DEFAULT,
            '&.Mui-checked': { color: t.colors.accent[600] },
          },
        },
      },

      MuiLinearProgress: {
        styleOverrides: {
          root: {
            borderRadius: t.radius.full,
            backgroundColor: t.colors.accent[100],
          },
          bar: {
            borderRadius: t.radius.full,
            backgroundColor: t.colors.accent[600],
          },
        },
      },

      MuiSkeleton: {
        styleOverrides: {
          root: {
            borderRadius: t.radius.sm,
            backgroundColor: t.colors.surfaceHover,
          },
        },
      },

      MuiList: {
        styleOverrides: {
          root: { padding: 0 },
        },
      },
      MuiListItem: {
        styleOverrides: {
          root: {
            borderRadius: t.radius.sm,
            '&:hover': { backgroundColor: t.colors.surfaceHover },
          },
        },
      },
    },
    ...overrides,
  })
}

export const theme = createSpoonbillTheme()
