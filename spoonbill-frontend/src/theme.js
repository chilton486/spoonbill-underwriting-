import { createTheme } from '@mui/material/styles'

export const tokens = {
  colors: {
    background: '#f8fafc',
    surface: '#ffffff',
    surfaceHover: '#f1f5f9',
    surfaceActive: '#e2e8f0',

    text: {
      primary: '#1e293b',
      secondary: '#475569',
      muted: '#94a3b8',
      disabled: '#cbd5e1',
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
    md: 16,
    lg: 24,
    xl: 32,
    xxl: 48,
  },

  radius: {
    sm: 8,
    md: 12,
    lg: 16,
    full: 9999,
  },

  shadow: {
    sm: '0 1px 2px 0 rgb(0 0 0 / 0.04)',
    md: '0 2px 4px -1px rgb(0 0 0 / 0.06), 0 1px 2px -1px rgb(0 0 0 / 0.04)',
    lg: '0 4px 8px -2px rgb(0 0 0 / 0.06), 0 2px 4px -2px rgb(0 0 0 / 0.04)',
    xl: '0 12px 24px -4px rgb(0 0 0 / 0.08), 0 4px 8px -4px rgb(0 0 0 / 0.04)',
  },

  transition: {
    fast: '150ms cubic-bezier(0.4, 0, 0.2, 1)',
    normal: '200ms cubic-bezier(0.4, 0, 0.2, 1)',
    slow: '300ms cubic-bezier(0.4, 0, 0.2, 1)',
  },

  typography: {
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    mono: '"JetBrains Mono", "Fira Code", "SF Mono", Consolas, monospace',
    scale: {
      h1: { size: '2rem', weight: 700, lineHeight: 1.3, tracking: '-0.025em' },
      h2: { size: '1.5rem', weight: 700, lineHeight: 1.35, tracking: '-0.02em' },
      h3: { size: '1.25rem', weight: 600, lineHeight: 1.4, tracking: '-0.015em' },
      body: { size: '0.9375rem', weight: 400, lineHeight: 1.7 },
      small: { size: '0.8125rem', weight: 400, lineHeight: 1.6 },
      caption: { size: '0.75rem', weight: 500, lineHeight: 1.5 },
    },
  },
}

export function createSpoonbillTheme(overrides = {}) {
  const t = tokens
  const s = t.typography.scale

  return createTheme({
    palette: {
      mode: 'light',
      primary: {
        main: t.colors.accent[500],
        light: t.colors.accent[300],
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
        disabled: t.colors.text.disabled,
      },
      success: { main: t.colors.status.success, contrastText: '#fff' },
      warning: { main: t.colors.status.warning, contrastText: '#fff' },
      error: { main: t.colors.status.error, contrastText: '#fff' },
      info: { main: t.colors.status.info, contrastText: '#fff' },
      divider: t.colors.border.light,
      action: {
        hover: t.colors.surfaceHover,
        selected: t.colors.accent[50],
        disabled: t.colors.text.disabled,
        disabledBackground: t.colors.surfaceHover,
      },
    },
    shape: { borderRadius: t.radius.md },
    typography: {
      fontFamily: t.typography.fontFamily,
      h1: { fontSize: s.h1.size, fontWeight: s.h1.weight, lineHeight: s.h1.lineHeight, letterSpacing: s.h1.tracking, color: t.colors.text.primary },
      h2: { fontSize: s.h2.size, fontWeight: s.h2.weight, lineHeight: s.h2.lineHeight, letterSpacing: s.h2.tracking, color: t.colors.text.primary },
      h3: { fontSize: s.h3.size, fontWeight: s.h3.weight, lineHeight: s.h3.lineHeight, letterSpacing: s.h3.tracking, color: t.colors.text.primary },
      h4: { fontSize: '1.125rem', fontWeight: 600, lineHeight: 1.4, letterSpacing: '-0.01em', color: t.colors.text.primary },
      h5: { fontSize: '1rem', fontWeight: 600, lineHeight: 1.5, color: t.colors.text.primary },
      h6: { fontSize: s.body.size, fontWeight: 600, lineHeight: 1.5, color: t.colors.text.primary },
      subtitle1: { fontSize: s.body.size, fontWeight: 600, lineHeight: 1.5, color: t.colors.text.primary },
      subtitle2: { fontSize: s.small.size, fontWeight: 600, lineHeight: s.small.lineHeight, color: t.colors.text.secondary },
      body1: { fontSize: s.body.size, fontWeight: s.body.weight, lineHeight: s.body.lineHeight, color: t.colors.text.primary },
      body2: { fontSize: s.small.size, fontWeight: s.small.weight, lineHeight: s.small.lineHeight, color: t.colors.text.secondary },
      caption: { fontSize: s.caption.size, fontWeight: s.caption.weight, lineHeight: s.caption.lineHeight, color: t.colors.text.muted },
      button: { textTransform: 'none', fontWeight: 600, fontSize: s.small.size },
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
            outline: `2px solid ${t.colors.accent[400]}`,
            outlineOffset: 2,
          },
          'a': {
            color: t.colors.accent[600],
            textDecoration: 'none',
            '&:hover': { color: t.colors.accent[700], textDecoration: 'underline' },
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
            backgroundColor: t.colors.accent[500],
            color: '#ffffff',
            boxShadow: t.shadow.sm,
            '&:hover': {
              backgroundColor: t.colors.accent[600],
              boxShadow: t.shadow.md,
              transform: 'translateY(-0.5px)',
            },
            '&:active': {
              backgroundColor: t.colors.accent[700],
              transform: 'translateY(0)',
            },
            '&:disabled': {
              backgroundColor: t.colors.border.light,
              color: t.colors.text.disabled,
            },
          },
          outlined: {
            borderColor: t.colors.border.DEFAULT,
            color: t.colors.text.primary,
            '&:hover': {
              borderColor: t.colors.accent[400],
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
          sizeSmall: { padding: '5px 14px', fontSize: '0.8rem' },
          sizeLarge: { padding: '12px 28px', fontSize: '0.9375rem' },
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
            boxShadow: t.shadow.sm,
            transition: `box-shadow ${t.transition.normal}`,
          },
          outlined: {
            borderColor: t.colors.border.light,
            boxShadow: 'none',
          },
        },
      },

      MuiCard: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            border: `1px solid ${t.colors.border.light}`,
            borderRadius: t.radius.lg,
            boxShadow: t.shadow.sm,
            transition: `all ${t.transition.normal}`,
            '&:hover': {
              boxShadow: t.shadow.lg,
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
              fontSize: s.caption.size,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              borderBottom: `2px solid ${t.colors.border.light}`,
              padding: '14px 16px',
            },
          },
        },
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            transition: `background-color ${t.transition.fast}`,
            '&:hover': { backgroundColor: t.colors.accent[50] },
            '&.Mui-selected': { backgroundColor: t.colors.accent[50] },
            '&:last-child td': { borderBottom: 0 },
          },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            borderBottom: `1px solid ${t.colors.border.light}`,
            padding: '14px 16px',
            fontSize: s.small.size,
            color: t.colors.text.primary,
          },
        },
      },

      MuiTabs: {
        styleOverrides: {
          root: {
            minHeight: 46,
          },
          indicator: {
            height: 2.5,
            borderRadius: '2px 2px 0 0',
            backgroundColor: t.colors.accent[500],
          },
        },
      },
      MuiTab: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 500,
            fontSize: s.small.size,
            minHeight: 46,
            padding: '10px 18px',
            color: t.colors.text.muted,
            transition: `all ${t.transition.fast}`,
            '&.Mui-selected': {
              color: t.colors.accent[600],
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
            padding: '24px 24px 12px',
            color: t.colors.text.primary,
          },
        },
      },
      MuiDialogContent: {
        styleOverrides: {
          root: { padding: '12px 24px 24px' },
          dividers: { borderColor: t.colors.border.light },
        },
      },
      MuiDialogActions: {
        styleOverrides: {
          root: {
            padding: '12px 24px 24px',
            gap: 10,
          },
        },
      },

      MuiChip: {
        styleOverrides: {
          root: {
            fontWeight: 600,
            borderRadius: t.radius.sm,
            fontSize: s.caption.size,
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
              '&:hover fieldset': { borderColor: t.colors.accent[300] },
              '&.Mui-focused fieldset': {
                borderColor: t.colors.accent[500],
                borderWidth: 2,
              },
            },
            '& .MuiInputLabel-root': {
              color: t.colors.text.muted,
              fontSize: s.small.size,
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
            '&:hover fieldset': { borderColor: t.colors.accent[300] },
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
            fontSize: s.small.size,
            borderRadius: t.radius.sm,
            margin: '2px 6px',
            '&:hover': { backgroundColor: t.colors.surfaceHover },
            '&.Mui-selected': {
              backgroundColor: t.colors.accent[50],
              color: t.colors.accent[700],
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
            fontSize: s.caption.size,
            borderRadius: t.radius.sm,
            padding: '6px 12px',
          },
        },
      },

      MuiCircularProgress: {
        styleOverrides: {
          root: { color: t.colors.accent[500] },
        },
      },

      MuiStepper: {
        styleOverrides: {
          root: { padding: '20px 0' },
        },
      },
      MuiStepLabel: {
        styleOverrides: {
          label: {
            fontSize: s.small.size,
            '&.Mui-active': { color: t.colors.accent[600], fontWeight: 600 },
            '&.Mui-completed': { color: t.colors.status.success },
          },
        },
      },
      MuiStepIcon: {
        styleOverrides: {
          root: {
            '&.Mui-active': { color: t.colors.accent[500] },
            '&.Mui-completed': { color: t.colors.status.success },
          },
        },
      },

      MuiSwitch: {
        styleOverrides: {
          root: {
            '& .Mui-checked': {
              color: t.colors.accent[500],
              '& + .MuiSwitch-track': { backgroundColor: t.colors.accent[300] },
            },
          },
        },
      },

      MuiCheckbox: {
        styleOverrides: {
          root: {
            color: t.colors.border.DEFAULT,
            '&.Mui-checked': { color: t.colors.accent[500] },
          },
        },
      },

      MuiLinearProgress: {
        styleOverrides: {
          root: {
            borderRadius: t.radius.full,
            backgroundColor: t.colors.accent[100],
            height: 6,
          },
          bar: {
            borderRadius: t.radius.full,
            backgroundColor: t.colors.accent[500],
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
          root: { padding: 4 },
        },
      },
      MuiListItem: {
        styleOverrides: {
          root: {
            borderRadius: t.radius.sm,
            transition: `background-color ${t.transition.fast}`,
            '&:hover': { backgroundColor: t.colors.surfaceHover },
            '&.Mui-selected': {
              backgroundColor: t.colors.accent[50],
              '&:hover': { backgroundColor: t.colors.accent[100] },
            },
          },
        },
      },

      MuiBreadcrumbs: {
        styleOverrides: {
          root: { fontSize: s.small.size },
          separator: { color: t.colors.text.muted },
        },
      },
    },
    ...overrides,
  })
}

export const theme = createSpoonbillTheme()
export const themeTokens = tokens
