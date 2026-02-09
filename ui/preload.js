const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  setWindowInteractive: (interactive) => ipcRenderer.send('toggle-mouse', interactive),
  reportHitTest: (isOver) => ipcRenderer.send('cursor-hit-test', isOver),
  onCursorPosition: (callback) =>
    ipcRenderer.on('cursor-position', (event, point) => callback(point)),
  onResetConfigure: (callback) =>
    ipcRenderer.on('tray-reset-configure', () => callback()),
  onOverlayImage: (callback) =>
    ipcRenderer.on('show-overlay-image', () => callback()),
  onClearOverlay: (callback) =>
    ipcRenderer.on('clear-overlay', () => callback()),
  onStopAll: (callback) =>
    ipcRenderer.on('stop-all', () => callback()),
  setInputMode: (enabled) => ipcRenderer.send('toggle-input-mode', enabled),
  getPlatform: () => process.platform,
  getModelName: () => ipcRenderer.invoke('get-model-name'),
  getServerConfig: () => ipcRenderer.invoke('get-server-config')
});
