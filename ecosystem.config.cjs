/** pm2 进程管理配置。 */
module.exports = {
  apps: [
    {
      name: 'ragportal',
      script: 'C:/conda_envs/ragportal/Scripts/uvicorn.exe',
      args: 'app.main:app --host 127.0.0.1 --port 8004',
      cwd: __dirname + '/backend',
      env: {
        APP_ENV: 'production',
        PYTHONUNBUFFERED: '1',
        FRONTEND_DIST: '../frontend/dist',
      },
      instances: 1,
      autorestart: true,
    },
  ],
}
