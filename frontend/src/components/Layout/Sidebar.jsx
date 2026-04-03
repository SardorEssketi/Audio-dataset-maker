import React, { useState } from 'react';
import {
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Box,
  Toolbar,
  Divider,
  Chip,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Settings as SettingsIcon,
  PlayArrow as PlayIcon,
  History as HistoryIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const DRAWER_WIDTH = 240;

function Sidebar() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (!user) {
    return null;
  }

  const menuItems = [
    {
      text: 'Dashboard',
      icon: <DashboardIcon />,
      path: '/dashboard',
    },
    {
      text: 'Run Pipeline',
      icon: <PlayIcon />,
      path: '/pipeline/run',
    },
    {
      text: 'Jobs History',
      icon: <HistoryIcon />,
      path: '/dashboard',  // For now, history is part of dashboard
    },
    {
      text: 'Settings',
      icon: <SettingsIcon />,
      path: '/settings',
    },
  ];

  const handleNavigation = (path) => {
    setMobileOpen(false);
    navigate(path);
  };

  return (
    <>
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
        <Box sx={{ overflow: 'auto' }}>
          <List>
            {menuItems.map((item) => {
              const isActive = location.pathname === item.path;

              return (
                <ListItem
                  key={item.text}
                  disablePadding
                  sx={{
                    py: 0.5,
                  }}
                >
                  <ListItemButton
                    selected={isActive}
                    onClick={() => handleNavigation(item.path)}
                    sx={{
                      borderRadius: 1,
                      mx: 1,
                      ...(isActive && {
                        backgroundColor: 'primary.main',
                        '&:hover': {
                          backgroundColor: 'primary.dark',
                        },
                        '& .MuiListItemIcon-root': {
                          color: 'white',
                        },
                        '& .MuiTypography-root': {
                          color: 'white',
                        },
                      }),
                    }}
                  >
                    <ListItemIcon
                      sx={{
                        minWidth: 40,
                      }}
                    >
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText
                      primary={item.text}
                      primaryTypographyProps={{
                        fontWeight: isActive ? 600 : 400,
                      }}
                    />
                    {isActive && (
                      <Chip
                        label="Active"
                        size="small"
                        sx={{
                          ml: 1,
                          bgcolor: 'white',
                          color: 'primary.main',
                        }}
                      />
                    )}
                  </ListItemButton>
                </ListItem>
              );
            })}
          </List>
        </Box>
      </Drawer>
    </>
  );
}

export default Sidebar;