import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "redirect-local-sign-in",
      // Firebase authorizes localhost for local sign-in, so send old 127.0.0.1 tabs there.
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (req.headers.host?.startsWith("127.0.0.1:")) {
            const address = server.httpServer?.address();
            const port = typeof address === "object" && address ? address.port : 5173;
            res.writeHead(307, { Location: `http://localhost:${port}${req.url || "/"}` });
            res.end();
            return;
          }
          next();
        });
      },
    },
  ],
});
