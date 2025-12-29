import fs from 'node:fs'
import path from 'node:path'

const repoRoot = path.resolve(process.cwd())
const adminSrc = path.join(repoRoot, 'frontend', 'admin', 'src')
const componentsDir = path.join(adminSrc, 'components')

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
  if (!fs.existsSync(componentsDir)) {
    console.error(`components dir not found: ${componentsDir}`)
    process.exit(1)
  }

  const srcFiles = walkFiles(adminSrc)
    .filter((p) => !p.startsWith(componentsDir))
    .filter((p) => p.endsWith('.ts') || p.endsWith('.vue'))

  const haystack = srcFiles.map(readText).join('\n')

  const components = walkFiles(componentsDir).filter((p) => p.endsWith('.vue'))
  const orphans = []

  for (const comp of components) {
    const rel = toPosix(path.relative(adminSrc, comp)) // e.g. components/Foo.vue
    const base = path.basename(comp) // Foo.vue
    const stem = base.replace(/\.vue$/, '') // Foo

    // 足够保守的“被引用”判定：
    // - 出现相对路径片段（components/Foo.vue）
    // - 或出现文件名（Foo.vue）
    // - 或出现组件名（Foo）并伴随 Vue import 语句（误报风险较高，所以只作为兜底）
    const used =
      haystack.includes(rel) ||
      haystack.includes(base) ||
      /import\s+.*\s+from\s+['"][^'"]+['"]/.test(haystack) && haystack.includes(stem)

    if (!used) orphans.push(rel)
  }

  console.log(`admin components total: ${components.length}`)
  if (orphans.length === 0) {
    console.log('orphans: none ✅')
    return
  }

  console.log(`orphans (${orphans.length}):`)
  for (const o of orphans.sort()) console.log(`- ${o}`)
  process.exitCode = 2
}

main()


