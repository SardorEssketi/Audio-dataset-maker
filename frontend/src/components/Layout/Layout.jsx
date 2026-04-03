import React, { useState, useEffect } from 'react';
import {
  Box,
  CssBaseline,
  AppBar,
  Toolbar,
  Drawer,
  IconButton,
  Menu,
  MenuItem,
  useMediaQuery,
  useTheme,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
  Chip,
  Typography,
} from '@mui/material';
import { Menu as MenuIcon } from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import Header from './Header';
import Sidebar from './Sidebar';

const DRAWER_WIDTH = 240;

function Layout({ children, requireAuth = false }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [mobileOpen, setMobileOpen] = useState(false);

  // Redirect to login if not authenticated (only for protected routes)
  useEffect(() => {
    if (requireAuth && !user && location.pathname !== '/login') {
      navigate('/login', { replace: true });
    }
  }, [user, requireAuth, location.pathname, navigate]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const drawer = (
    <Box onClick={() => setMobileOpen(false)}>
      <Sidebar />
    </Box>
  );

  return (
    <Box sx={{ display: 'flex' }}>
      <CssBaseline />
      <AppBar
        position="fixed"
        sx={{
          zIndex: (theme) => theme.zIndex.drawer + 1,
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)`, xs: '100%' },
        }}
      >
        <Toolbar>
          <Typography variant="h6" noWrap component="div" sx={{ mr: 2, display: { xs: 'none', sm: 'block' } }}>
            Audio Pipeline
          </Typography>

          {user && (
            <>
              <IconButton
                color="inherit"
                edge="start"
                onClick={() => navigate('/dashboard')}
                sx={{ mr: 2, display: { md: 'none', xs: 'flex' } }}
              >
                <MenuIcon />
              </IconButton>

              <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Typography variant="body2" sx={{ mr: 2 }}>
                  {user.username}
                </Typography>

                <IconButton
                  color="inherit"
                  onClick={handleLogout}
                  title="Logout"
                >
                  Logout
                </IconButton>
              </Box>
            </>
          )}

          {isMobile && user && (
            <IconButton
              color="inherit"
              edge="end"
              onClick={() => setMobileOpen(!mobileOpen)}
            >
              <MenuIcon />
            </IconButton>
          )}
        </Toolbar>
      </AppBar>

      {user && (
        <Box
          component="nav"
          sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { sm: 0 } }}
        >
          {/* Desktop Drawer */}
          <Drawer
            variant="permanent"
            sx={{
              display: { xs: 'none', sm: 'block' },
              width: DRAWER_WIDTH,
              flexShrink: 0,
              '& .MuiDrawer-paper': {
                boxSizing: 'border-box',
                width: DRAWER_WIDTH,
                borderRight: 'none',
                backgroundColor: '#f5f5f5',
              },
            }}
            open
          >
            <Toolbar />
            <Divider />
            <Sidebar />
          </Drawer>

          {/* Mobile Drawer */}
          <Drawer
            variant="temporary"
            open={mobileOpen}
            onClose={() => setMobileOpen(false)}
            ModalProps={{
              keepMounted: true, // Better open performance on mobile.
            }}
            sx={{
              display: { xs: 'block', sm: 'none' },
              '& .MuiDrawer-paper': {
                boxSizing: 'border-box',
                width: DRAWER_WIDTH,
                backgroundColor: '#f5f5f5',
              },
            }}
          >
            <Box onClick={() => setMobileOpen(false)}>
              <Sidebar />
            </Box>
          </Drawer>
        </Box>
      )}

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)`, xs: '100%' },
          mt: '64px', // AppBar height
          backgroundColor: '#fafafa',
          minHeight: 'calc(100vh - 64px)',
        }}
      >
        {children}
      </Box>
    </Box>
  );
}

export default Layout;