// Offline component-handler regression tests; no API calls or browser required.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('typescript')

function harness(component, api) {
  let cursor = 0
  const slots = []
  const react = {
    useState(initial) {
      const i = cursor++
      if (!(i in slots)) slots[i] = initial
      return [slots[i], value => { slots[i] = typeof value === 'function' ? value(slots[i]) : value }]
    },
    useRef(initial) {
      const i = cursor++
      if (!(i in slots)) slots[i] = { current: initial }
      return slots[i]
    },
    useEffect() {},
    useCallback: fn => fn,
  }
  const translations = new Proxy(() => '', { get: () => translations })
  const module = { exports: {} }
  const source = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/components', component + '.tsx'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText
  new Function('require', 'module', 'exports', source)(name => {
    if (name === 'react') return react
    if (name === 'react/jsx-runtime') return { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) }
    if (name === '@/lib/api-client') return api
    if (name === '@/lib/auth') return { getUser: () => null }
    if (name === '@/components/Toast') return { useToast: () => ({ push() {} }) }
    if (name === '@/i18n/I18nProvider') return { useT: () => ({ t: translations }) }
    if (name === 'lucide-react') return {}
    throw new Error(name)
  }, module, module.exports)
  return props => { cursor = 0; return module.exports.default(props) }
}

function find(node, predicate) {
  if (!node || typeof node !== 'object') return null
  if (Array.isArray(node)) {
    for (const child of node) { const match = find(child, predicate); if (match) return match }
    return null
  }
  if (predicate(node)) return node
  return find(node.props?.children, predicate)
}
const handler = (tree, prop, name) => {
  const node = find(tree, n => n.props?.[prop]?.name === name)
  assert.ok(node, name)
  return node.props[prop]
}

async function check(component) {
  let finishUpload, saves = 0, closes = 0, payload
  const api = {
    uploadImage: () => new Promise(resolve => { finishUpload = resolve }),
    createProduct: async value => { saves++; payload = value },
    createReview: async (id, rating, content, images) => { saves++; payload = { images } },
    getSellerReviews: async () => ({ items: [], score: null, review_count: 0 }),
  }
  const render = harness(component, api)
  const props = { open: true, initial: null, canWrite: true, sellerId: 1, sellerName: 'Seller', onClose: () => { closes++ }, onSaved() {} }
  let tree = render(props)
  const field = find(tree, n => n.type === 'input' && (component === 'ReviewModal' ? n.props.type === 'range' : n.props.value === ''))
  field.props.onChange({ target: { value: component === 'ReviewModal' ? '5' : 'Product' } })
  tree = render(props)
  const upload = handler(tree, 'onChange', 'handleImageUpload')({ target: { files: [{}], value: 'photo' } })
  const submitName = 'handleSubmit'
  await handler(tree, 'onClick', submitName)()
  handler(tree, 'onClick', 'closeWhenIdle')()
  assert.equal(saves, 0, 'upload must finish before submission')
  assert.equal(closes, 0, 'cannot reopen modal while old upload is pending')
  finishUpload({ url: 'uploaded-photo' })
  await upload
  tree = render(props)
  const submit = handler(tree, 'onClick', submitName)
  await Promise.all([submit(), submit()])
  assert.equal(saves, 1, 'double click must not duplicate submission')
  assert.deepEqual(payload.images, ['uploaded-photo'])
  tree = render(props)
  handler(tree, 'onClick', 'closeWhenIdle')()
  assert.equal(closes, 1, 'modal unlocks after completion')
}

Promise.all(['ProductFormModal', 'ReviewModal'].map(check)).then(() => {
  console.log('PASS: upload/submit ordering, modal closure, duplicate submission, image persistence')
}).catch(error => { console.error(error); process.exitCode = 1 })
