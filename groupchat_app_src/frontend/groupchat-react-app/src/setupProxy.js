const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  app.use(
    "/api",
    createProxyMiddleware({
      target: "http://localhost:8000",  // backend address
      changeOrigin: true,
    })
  );

  app.use(
    "/ws",
    createProxyMiddleware({
      target: "ws://localhost:8000",
      ws: true,
      changeOrigin: true,
    })
  );
};
