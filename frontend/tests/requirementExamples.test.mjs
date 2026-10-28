import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

// Compile the pure TypeScript module in memory; no test dependency or output files.
const source = readFileSync(new URL('../src/requirementExamples.ts', import.meta.url), 'utf8')
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } })
const { requirementExamples: examples, selectRandomExample: select, needsExampleReplacementConfirmation: confirm } =
  await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)

test('exactly five unique examples fit the existing input limits', () => {
  assert.deepEqual(examples.map(example => example.id), [1, 2, 3, 4, 5])
  assert.equal(new Set(examples.map(example => example.title)).size, 5)
  for (const example of examples) {
    assert.ok(example.title.length > 0 && example.title.length <= 200)
    assert.ok(example.description.length > 0 && example.description.length <= 10000)
  }
})

test('first click covers all five equal probability intervals and boundaries', () => {
  for (let index = 0; index < 5; index++) {
    assert.equal(select(undefined, () => index / 5).id, index + 1)
    assert.equal(select(undefined, () => (index + 0.999) / 5).id, index + 1)
  }
})

test('every current example excludes only itself with four equal intervals', () => {
  for (const current of examples) {
    const remaining = examples.filter(example => example.id !== current.id)
    for (let index = 0; index < 4; index++) {
      assert.equal(select(current.id, () => index / 4), remaining[index])
      assert.equal(select(current.id, () => (index + 0.999) / 4), remaining[index])
    }
  }
})

test('empty form and unchanged loaded example can be replaced', () => {
  assert.equal(confirm('', '', null), false)
  for (const example of examples) assert.equal(confirm(example.title, example.description, example), false)
})

test('manual input and either edited field require confirmation', () => {
  const previous = examples[0]
  assert.equal(confirm('직접 작성', '', null), true)
  assert.equal(confirm('', '직접 작성', null), true)
  assert.equal(confirm(' ', '', null), true)
  assert.equal(confirm(previous.title + ' 수정', previous.description, previous), true)
  assert.equal(confirm(previous.title, previous.description + '\n추가', previous), true)
  assert.equal(confirm('', previous.description, previous), true)
})
