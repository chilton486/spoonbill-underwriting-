import { createTheme } from '@mui/material/styles'

export const theme = createTheme({
  palette: {
    mode: 'light',
    background: {
      default: '#ffffff',
      paper: '#ffffff'
    },
    text: {
      primary: '#1a1a1a',
      secondary: '#6b7280'
    },
    primary: { main: '#1a1a1a' },
    secondary: { main: '#6b7280' },
    success: { main: '#1a1a1a' },
    warning: { main: '#6b7280' },
    error: { main: '#1a1a1a' },
    divider: '#e5e7eb'
  },
  shape: {
    borderRadius: 8
  },
  typography: {
    fontFamily: 'Inter, system-ui, Avenir, Helvetica, Arial, sans-serif'
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600
        },
        contained: {
          backgroundColor: '#1a1a1a',
          color: '#ffffff',
          '&:hover': {
            backgroundColor: '#333333'
          }
        },
        outlined: {
          borderColor: '#d1d5db',
          color: '#1a1a1a',
          '&:hover': {
            borderColor: '#9ca3af',
            backgroundColor: '#f9fafb'
          }
        }
      }
    },
    MuiPaper: {
      styleOverrides: {
        outlined: {
          borderColor: '#e5e7eb'
        }
      }
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600
        }
      }
    }
  }
})
