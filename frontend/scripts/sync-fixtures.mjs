import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const sourceDir = path.resolve(__dirname, '../../shared/fixtures');
const targetDir = path.resolve(__dirname, '../src/fixtures');

if (!fs.existsSync(sourceDir)) {
  console.error(`Source fixtures directory not found: ${sourceDir}`);
  process.exit(1);
}

if (!fs.existsSync(targetDir)) {
  fs.mkdirSync(targetDir, { recursive: true });
}

const files = fs.readdirSync(sourceDir);
let copiedCount = 0;

for (const file of files) {
  const srcFile = path.join(sourceDir, file);
  const destFile = path.join(targetDir, file);
  const stat = fs.statSync(srcFile);

  if (stat.isFile()) {
    fs.copyFileSync(srcFile, destFile);
    console.log(`Copied ${file} -> src/fixtures/${file}`);
    copiedCount++;
  }
}

console.log(`Successfully synced ${copiedCount} fixture files.`);
