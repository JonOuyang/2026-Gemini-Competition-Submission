const { app, BrowserWindow, screen, ipcMain, Menu, Tray, nativeImage, globalShortcut } = require('electron');
const fs = require('fs');
const path = require('path');
let win;
let tray;
let isInteractive = false;
let cursorPoller;

console.log('[main] boot', { cwd: process.cwd(), dir: __dirname });

function registerShortcut(accelerator, label, callback) {
  try {
    const registered = globalShortcut.register(accelerator, callback);
    if (registered) {
      console.log(`[main] shortcut registered: ${label} (${accelerator})`);
    } else {
      console.error(`[main] shortcut registration failed: ${label} (${accelerator})`);
    }
    return registered;
  } catch (error) {
    console.error(`[main] shortcut registration error: ${label} (${accelerator})`, error);
    return false;
  }
}

function getServerConfig() {
  const defaultConfig = { host: '127.0.0.1', port: 8765 };
  try {
    const settingsPath = path.join(__dirname, '..', 'settings.json');
    const raw = fs.readFileSync(settingsPath, 'utf-8');
    const parsed = JSON.parse(raw);
    const host = typeof parsed.host === 'string' && parsed.host.trim() ? parsed.host.trim() : defaultConfig.host;
    const portValue = Number(parsed.port);
    const port = Number.isInteger(portValue) && portValue > 0 ? portValue : defaultConfig.port;
    return { host, port };
  } catch (error) {
    return defaultConfig;
  }
}

function getVirtualBounds() {
  const displays = screen.getAllDisplays();
  const bounds = displays.reduce((acc, display) => {
    acc.minX = Math.min(acc.minX, display.bounds.x);
    acc.minY = Math.min(acc.minY, display.bounds.y);
    acc.maxX = Math.max(acc.maxX, display.bounds.x + display.bounds.width);
    acc.maxY = Math.max(acc.maxY, display.bounds.y + display.bounds.height);
    return acc;
  }, { minX: 0, minY: 0, maxX: 0, maxY: 0 });

  return {
    x: bounds.minX,
    y: bounds.minY,
    width: bounds.maxX - bounds.minX,
    height: bounds.maxY - bounds.minY
  };
}

function setWindowInteractive(shouldCapture) {
  if (!win || win.isDestroyed()) return;
  if (isInteractive === shouldCapture) return;
  isInteractive = shouldCapture;

  if (process.platform === 'win32') {
    win.setIgnoreMouseEvents(!shouldCapture, { forward: true });
    return;
  }

  win.setIgnoreMouseEvents(!shouldCapture);
}

function createWindow() {
  const { x, y, width, height } = getVirtualBounds();
  const platformOptions = process.platform === 'darwin'
    ? { type: 'panel', hiddenInMissionControl: true }
    : { type: 'toolbar' };

  win = new BrowserWindow({
    x,
    y,
    width,
    height,
    transparent: true,
    backgroundColor: '#00000000',
    frame: false,
    hasShadow: false,
    enableLargerThanScreen: true,
    alwaysOnTop: true,
    resizable: false,
    fullscreenable: false,
    skipTaskbar: true,
    focusable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    },
    ...platformOptions
  });

  win.setMenuBarVisibility(false);
  const indexPath = path.join(__dirname, 'index.html');
  win.loadFile(indexPath);
  win.webContents.on('console-message', (event, level, message) => {
    console.log('[renderer]', message);
  });
  win.webContents.on('did-finish-load', () => {
    console.log('[main] renderer loaded', indexPath);
    console.log('[main] window url', win.webContents.getURL());
  });
  win.webContents.on('did-fail-load', (event, code, desc) => {
    console.error('[main] renderer failed to load', code, desc);
  });

  if (process.platform === 'darwin') {
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
    win.setAlwaysOnTop(true, 'screen-saver');
    win.setIgnoreMouseEvents(true);
  } else {
    win.setIgnoreMouseEvents(true, { forward: true });
  }

  if (process.platform === 'darwin') {
    cursorPoller = setInterval(() => {
      if (!win || win.isDestroyed()) return;
      const point = screen.getCursorScreenPoint();
      win.webContents.send('cursor-position', point);
    }, 30);
  }
}

function createTray() {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
      <circle cx="8" cy="8" r="5" fill="black"/>
    </svg>
  `;
  const icon = nativeImage.createFromDataURL(`data:image/svg+xml;utf8,${encodeURIComponent(svg)}`);
  if (process.platform === 'darwin') {
    icon.setTemplateImage(true);
  }

  tray = new Tray(icon);
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Reset/Configure',
      click: () => {
        if (win && !win.isDestroyed()) {
          win.webContents.send('tray-reset-configure');
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => app.quit()
    }
  ]);
  tray.setToolTip('Python-Powered Desktop Overlay');
  tray.setContextMenu(contextMenu);
}

app.whenReady().then(() => {
  if (process.platform === 'darwin' && app.dock) {
    app.dock.hide();
  }

  createWindow();
  createTray();
  registerShortcut('Command+Shift+Space', 'show overlay', () => {
    if (win && !win.isDestroyed()) {
      win.webContents.send('show-overlay-image');
    }
  });
  registerShortcut('CommandOrControl+Shift+C', 'stop all', () => {
    if (win && !win.isDestroyed()) {
      console.log('[main] stop-all shortcut triggered');
      win.webContents.send('stop-all');
    }
  });
  // Keep this alias during migration so users who learned the accidental combo
  // still have a working keypath.
  registerShortcut('CommandOrControl+Alt+Shift+C', 'stop all (legacy alias)', () => {
    if (win && !win.isDestroyed()) {
      console.log('[main] stop-all shortcut triggered');
      win.webContents.send('stop-all');
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('before-quit', () => {
  globalShortcut.unregisterAll();
  if (cursorPoller) {
    clearInterval(cursorPoller);
    cursorPoller = null;
  }

});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

ipcMain.on('toggle-mouse', (event, shouldEnableClicks) => {
  setWindowInteractive(shouldEnableClicks);
});

ipcMain.on('cursor-hit-test', (event, isOverElement) => {
  setWindowInteractive(isOverElement);
});

ipcMain.on('toggle-input-mode', (event, enabled) => {
  if (!win || win.isDestroyed()) return;
  if (enabled) {
    win.setIgnoreMouseEvents(false);
    win.setFocusable(true);
    win.focus();
    return;
  }
  win.setIgnoreMouseEvents(true, { forward: true });
  win.setFocusable(false);
});

ipcMain.handle('get-model-name', async () => {
  return 'CLOVIS';
});

ipcMain.handle('get-server-config', async () => {
  return getServerConfig();
});
