import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const PORT = Number(process.env.PORT) || 4568;
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WORKTREE_FAMILY = fs.existsSync('/Users/firejune/Workspace/Firejune/parts-examples-naru-homewear/family/tools/bust-region-rebuild.py')
  ? '/Users/firejune/Workspace/Firejune/parts-examples-naru-homewear/family'
  : ROOT;
const REBUILD_SCRIPT = path.join(WORKTREE_FAMILY, 'tools/bust-region-rebuild.py');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js':   'text/javascript; charset=utf-8',
  '.mjs':  'text/javascript; charset=utf-8',
  '.css':  'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png':  'image/png',
  '.jpg':  'image/jpeg',
  '.gif':  'image/gif',
  '.atlas': 'text/plain; charset=utf-8',
};

function runPython(args) {
  return new Promise((resolve, reject) => {
    execFile('python3', [REBUILD_SCRIPT, '--family-dir', WORKTREE_FAMILY, '--live-family-dir', ROOT, ...args], { maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) {
        reject(new Error((stderr || stdout || err.message).trim()));
        return;
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (parseErr) {
        reject(new Error(`Invalid JSON from rebuild script: ${stdout}`));
      }
    });
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  if (url.pathname === '/api/bust-regions') {
    if (req.method === 'GET') {
      try {
        const data = await runPython(['--action', 'get']);
        res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
        res.end(JSON.stringify(data));
      } catch (error) {
        res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
        res.end(JSON.stringify({ ok: false, error: error.message }));
      }
      return;
    }
    if (req.method === 'POST') {
      let body = '';
      req.on('data', chunk => { body += chunk; });
      req.on('end', async () => {
        try {
          const payload = JSON.parse(body || '{}');
          const { character, outfit = 'swimwear', bust_r, bust_l } = payload;
          const rArg = `${bust_r.cx},${bust_r.cy},${bust_r.r},${bust_r.band}`;
          const lArg = `${bust_l.cx},${bust_l.cy},${bust_l.r},${bust_l.band}`;
          const result = await runPython([
            '--action', 'set',
            '--character', String(character),
            '--outfit', String(outfit),
            '--bust-r', rArg,
            '--bust-l', lArg,
          ]);
          res.writeHead(200, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
          res.end(JSON.stringify(result));
        } catch (error) {
          res.writeHead(500, { 'Content-Type': 'application/json; charset=utf-8' });
          res.end(JSON.stringify({ ok: false, error: error.message }));
        }
      });
      return;
    }
  }

  let rel = decodeURIComponent(url.pathname);
  if (rel === '/' || rel === '/index.html') {
    rel = '/viewer/index.html';
  }
  const full = path.resolve(ROOT, '.' + rel);
  if (!full.startsWith(ROOT) || !fs.existsSync(full) || fs.statSync(full).isDirectory()) {
    res.writeHead(404);
    res.end('Not found: ' + rel);
    return;
  }
  const ext = path.extname(full).toLowerCase();
  res.writeHead(200, {
    'Content-Type': MIME[ext] || 'application/octet-stream',
    'Cache-Control': 'no-store, no-cache, must-revalidate',
  });
  fs.createReadStream(full).pipe(res);
});

server.listen(PORT, () => {
  console.log(`Rig-C Viewer running at http://localhost:${PORT}`);
});
