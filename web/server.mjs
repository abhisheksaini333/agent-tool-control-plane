import http from 'node:http';
import { readFile } from 'node:fs/promises';

const files = {
  '/': ['index.html', 'text/html; charset=utf-8'],
  '/app.js': ['app.js', 'text/javascript; charset=utf-8'],
  '/app.css': ['app.css', 'text/css; charset=utf-8'],
  '/config.json': ['config.json', 'application/json'],
};
const config = JSON.parse(await readFile(new URL('./dist/config.json', import.meta.url), 'utf8'));
const connections = [config.apiOrigin, config.authority].map(value => new URL(value).origin).join(' ');
const csp = `default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self' ${connections}; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'`;
const server = http.createServer(async (request, response) => {
  const route = files[new URL(request.url, 'http://localhost').pathname];
  if (!['GET', 'HEAD'].includes(request.method) || !route) {
    response.writeHead(route ? 405 : 404);
    response.end();
    return;
  }
  try {
    const [file, type] = route;
    const body = await readFile(new URL(`./dist/${file}`, import.meta.url));
    response.writeHead(200, {
      'Content-Type': type,
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'no-referrer',
      'X-Frame-Options': 'DENY',
      'Content-Security-Policy': csp,
    });
    response.end(request.method === 'HEAD' ? undefined : body);
  } catch {
    response.writeHead(503);
    response.end('Build the console before starting it.');
  }
});
server.listen(Number(process.env.PORT ?? 5294), process.env.BIND_HOST ?? '127.0.0.1');
