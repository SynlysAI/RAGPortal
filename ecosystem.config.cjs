/** pm2 进程管理配置。 */

// ── 实验室公共配置注入（读取共享密钥；文件缺失时返回空对象，本地开发不受影响）──
const COMMON_ENV = (() => {
  try {
    const out = {};
    for (const line of require("fs")
      .readFileSync("/home/fangyikai/lab-common.env", "utf-8")
      .split(/\r?\n/)) {
      if (line.trim().startsWith("#")) continue;
      const idx = line.indexOf("=");
      if (idx > 0) out[line.slice(0, idx).trim()] = line.slice(idx + 1).trim();
    }
    return out;
  } catch {
    return {};
  }
})();

module.exports = {
  apps: [
    {
      name: 'ragportal',
      script: '/polymer/conda/envs/ragportal/bin/uvicorn',
      args: 'app.main:app --host 0.0.0.0 --port 8004',
      cwd: __dirname + '/backend',
      env: {
        ...COMMON_ENV,
        APP_ENV: 'production',
        PYTHONUNBUFFERED: '1',
        FRONTEND_DIST: '../frontend/dist',
      },
      interpreter: 'none',
      instances: 1,
      autorestart: true,
    },
  ],
}
