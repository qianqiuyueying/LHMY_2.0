import fs from 'node:fs'
import path from 'node:path'

const repoRoot = path.resolve(process.cwd())
const websiteSrc = path.join(repoRoot, 'frontend', 'website', 'src')
const componentsDir = path.join(websiteSrc, 'components')

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

  const srcFiles = walkFiles(websiteSrc)
    .filter((p) => !p.startsWith(componentsDir))
    .filter((p) => p.endsWith('.ts') || p.endsWith('.vue'))

  const haystack = srcFiles.map(readText).join('\n')

  const components = walkFiles(componentsDir).filter((p) => p.endsWith('.vue'))
  const orphans = []

  for (const comp of components) {
    const rel = toPosix(path.relative(websiteSrc, comp)) // components/Foo.vue
    const base = path.basename(comp) // Foo.vue
    if (!haystack.includes(rel) && !haystack.includes(base)) {
      orphans.push(rel)
    }
  }

  console.log(`website components total: ${components.length}`)
  if (orphans.length === 0) {
    console.log('orphans: none ✅')
    return
  }

  console.log(`orphans (${orphans.length}):`)
  for (const o of orphans.sort()) console.log(`- ${o}`)
  process.exitCode = 2
}

main()


