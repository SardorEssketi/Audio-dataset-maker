import React from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  IconButton,
  Box,
  Menu,
  MenuItem,
  Avatar,
  Divider,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Settings as SettingsIcon,
  Dashboard as DashboardIcon,
  PlayArrow as PlayIcon,
  Logout as LogoutIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

function Header() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = React.useState(null);

  const handleMenuClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    logout();
    handleMenuClose();
    navigate('/login');
  };

  const handleNavigation = (path) => {
    handleMenuClose();
    navigate(path);
  };

  return (
    <AppBar position="static" elevation={1}>
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: 600 }}>
          Audio Pipeline
        </Typography>

        {user && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Button
                variant="contained"
                startIcon={<PlayIcon />}
                onClick={() => handleNavigation('/pipeline/run')}
              >
                Run Pipeline
              </Button>

            <IconButton
              size="large"
              edge="end"
              color="inherit"
              onClick={handleMenuClick}
            >
              <Avatar sx={{ width: 32, height: 32 }}>
                {user.username.charAt(0).toUpperCase()}
              </Avatar>
            </IconButton>

            <Menu
              id="user-menu"
              anchorEl={anchorEl}
              keepMounted
              open={Boolean(anchorEl)}
              onClose={handleMenuClose}
              anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'right',
              }}
              transformOrigin={{
                vertical: 'top',
                horizontal: 'right',
              }}
            >
              <MenuItem onClick={() => handleNavigation('/dashboard')}>
                <DashboardIcon sx={{ mr: 1 }} />
                Dashboard
              </MenuItem>
              <MenuItem onClick={() => handleNavigation('/settings')}>
                <SettingsIcon sx={{ mr: 1 }} />
                Settings
              </MenuItem>
              <Divider />
              <MenuItem onClick={handleLogout}>
                <LogoutIcon sx={{ mr: 1 }} />
                Logout
              </MenuItem>
            </Menu>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
}

export default Header;
