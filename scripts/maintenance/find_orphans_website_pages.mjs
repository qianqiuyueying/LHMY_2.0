import fs from 'node:fs'
import path from 'node:path'

const repoRoot = path.resolve(process.cwd())
const websiteSrc = path.join(repoRoot, 'frontend', 'website', 'src')
const pagesDir = path.join(websiteSrc, 'pages')
const routerFile = path.join(websiteSrc, 'router', 'index.ts')

function walkFiles(dir, out = []) {
  const entries = fs.readdirSync(dir, { withFileTypes: true })
  for (const ent of entries) {
    const full = path.join(dir, ent.name)
    if (ent.isDirectory()) walkFiles(full, out)
    else out.push(full)
  }
  return out
}

function toPosix(p) {
  return p.split(path.sep).join('/')
}

function readText(filePath) {
  return fs.readFileSync(filePath, 'utf8')
}

function main() {
  if (!fs.existsSync(routerFile)) {
    console.error(`router file not found: ${routerFile}`)
    process.exit(1)
  }
  if (!fs.existsSync(pagesDir)) {
    console.error(`pages dir not found: ${pagesDir}`)
    process.exit(1)
  }

  const router = readText(routerFile)
  const used = new Set()
  const re = /\.\.\/pages\/([A-Za-z0-9_./-]+\.vue)/g
  for (let m; (m = re.exec(router)); ) used.add(m[1])

  const pages = walkFiles(pagesDir).filter((p) => p.endsWith('.vue'))
  const orphans = []
  for (const p of pages) {
    const rel = toPosix(path.relative(pagesDir, p))
    if (!used.has(rel)) orphans.push(rel)
  }

  console.log(`website pages total: ${pages.length}`)
  console.log(`website pages referenced by router: ${used.size}`)
  if (orphans.length === 0) {
    console.log('orphans: none ✅')
    return
  }

  console.log(`orphans (${orphans.length}):`)
  for (const o of orphans.sort()) console.log(`- ${o}`)
  process.exitCode = 2
}

main()


