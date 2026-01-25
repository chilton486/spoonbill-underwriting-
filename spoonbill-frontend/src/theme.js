import { createTheme } from '@mui/material/styles'

export const theme = createTheme({
  palette: {
    mode: 'dark',
    background: {
      default: '#0b1220',
      paper: '#0f172a'
    },
    primary: { main: '#38bdf8' },
    success: { main: '#34d399' },
    warning: { main: '#fbbf24' },
    error: { main: '#fb7185' }
  },
  shape: {
    borderRadius: 14
  },
  typography: {
    fontFamily: 'Inter, system-ui, Avenir, Helvetica, Arial, sans-serif'
  }
})
