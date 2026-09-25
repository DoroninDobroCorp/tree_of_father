#!/usr/bin/env node
/**
 * Test suite for Skill RPG Core rules, state validation, and proposals.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const Core = require(path.join(ROOT, 'src', 'core.js'));

const seed = JSON.parse(fs.readFileSync(path.join(ROOT, 'src', 'seed.json'), 'utf8'));
const schema = JSON.parse(fs.readFileSync(path.join(ROOT, 'src', 'proposal.schema.json'), 'utf8'));

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (e) {
    failed++;
    console.error(`  ✗ ${name}`);
    console.error(`    ${e.message}`);
  }
}

console.log('--- Running Core Rules & State Validation Tests ---');

test('Initial seed state validates against schema and rules', () => {
  assert.strictEqual(Core.validateState(seed, schema), true);
});

test('Stats calculation matches initial seed counts', () => {
  const s = Core.stats(seed);
  assert.strictEqual(s.practice, 70);
  assert.strictEqual(s.theory, 8);
  assert.strictEqual(s.attempt, 0);
  assert.strictEqual(s.historical, 49);
  assert.strictEqual(s.total, 127);
  assert.strictEqual(s.explored, 12);
  assert.strictEqual(s.completed, 2);
});

test('Branch and skill stats calculation', () => {
  const bStats = Core.branchStats(seed, 'wood');
  assert(bStats.count > 10, 'Wood branch should have multiple skills');
  assert.strictEqual(typeof bStats.total, 'number');

  const sStats = Core.skillStats(seed, 'mechanics.fittings');
  assert.strictEqual(sStats.practice, 12);
  assert.strictEqual(sStats.total, 12);
});

test('validateState rejects invalid schemaVersion', () => {
  const corrupted = Core.clone(seed);
  corrupted.schemaVersion = 2;
  assert.throws(() => Core.validateState(corrupted, schema), /Skill RPG v3/);
});

test('validateState rejects skill with nonexistent branchId', () => {
  const corrupted = Core.clone(seed);
  corrupted.skills[0].branchId = 'nonexistent-branch';
  assert.throws(() => Core.validateState(corrupted, schema), /нет ветки/);
});

test('validateState rejects skill with unknown toolId', () => {
  const corrupted = Core.clone(seed);
  corrupted.skills[0].toolIds = ['imaginary-laser-tool'];
  assert.throws(() => Core.validateState(corrupted, schema), /неизвестный инструмент/);
});

test('validateState rejects cyclic prerequisites (A -> B -> A)', () => {
  const corrupted = Core.clone(seed);
  const s1 = corrupted.skills.find(s => s.id === 'base.measure');
  const s2 = corrupted.skills.find(s => s.id === 'wood.square');
  s1.prerequisites = [s2.id];
  s2.prerequisites = [s1.id];
  assert.throws(() => Core.validateState(corrupted, schema), /Циклические зависимости/);
});

test('validateEvent enforces caps for each event kind', () => {
  const testEvent = {
    id: 'e-test-caps',
    title: 'Тестовая практика',
    kind: 'practice',
    date: '2026-09-24',
    dateLabel: '24 сентября 2026',
    description: 'Описание выполнения достаточно подробное для проверки',
    evidence: 'Фото и подтверждение',
    allocations: [{ skillId: 'wood.square', points: 30 }, { skillId: 'base.measure', points: 30 }, { skillId: 'wood.shelf', points: 25 }],
    projectId: null,
    stale: false,
    toolIds: ['square']
  };
  // 30 + 30 + 25 = 85 XP > 80 (practice cap)
  assert.throws(() => Core.validateEvent(testEvent, seed, schema), /Предел одной записи: 80 XP/);

  // Theory cap: 20
  testEvent.kind = 'theory';
  testEvent.allocations = [{ skillId: 'wood.square', points: 25 }];
  assert.throws(() => Core.validateEvent(testEvent, seed, schema), /Предел одной записи: 20 XP/);

  // Attempt cap: 15
  testEvent.kind = 'attempt';
  testEvent.allocations = [{ skillId: 'wood.square', points: 20 }];
  assert.throws(() => Core.validateEvent(testEvent, seed, schema), /Предел одной записи: 15 XP/);

  // Historical cap: 40
  testEvent.kind = 'historical';
  testEvent.allocations = [{ skillId: 'wood.square', points: 30 }, { skillId: 'base.measure', points: 15 }];
  assert.throws(() => Core.validateEvent(testEvent, seed, schema), /Предел одной записи: 40 XP/);
});

test('validateEvent rejects single allocation > 30 XP', () => {
  const testEvent = {
    id: 'e-test-single',
    title: 'Тест одной точки',
    kind: 'practice',
    date: null,
    dateLabel: 'Дата не указана',
    description: 'Подробное описание работы для проверки пределов',
    evidence: 'Подтверждение факта',
    allocations: [{ skillId: 'wood.square', points: 35 }],
    projectId: null,
    stale: false,
    toolIds: []
  };
  assert.throws(() => Core.validateEvent(testEvent, seed, schema), /слишком велико/);
});

test('eventFingerprint detects duplicate events', () => {
  const e1 = { kind: 'practice', date: '2026-09-24', title: 'Сборка стола', description: 'Собрал стол из дуба' };
  const e2 = { kind: 'practice', date: '2026-09-24', title: '  СБОРКА СТОЛА  ', description: '  собрал стол из дуба ' };
  assert.strictEqual(Core.eventFingerprint(e1), Core.eventFingerprint(e2));
});

test('applyProposal succeeds with valid add_skill and add_project', () => {
  const proposal = {
    version: 1,
    id: 'p-test-1',
    baseRevision: seed.revision,
    summary: 'Добавление навыка и проекта для проверки',
    questions: [],
    operations: [
      {
        id: 'op-1',
        type: 'add_skill',
        targetId: 'wood.test_skill',
        reason: 'Тест',
        data: {
          id: 'wood.test_skill',
          branchId: 'wood',
          module: 'Тестовый модуль',
          title: 'Тестовый навык',
          goal: 'Цель',
          exercise: 'Упражнение',
          proof: 'Критерий',
          toolIds: ['square'],
          prerequisites: ['wood.square'],
          risk: 'care',
          stage: 1,
          archived: false
        }
      }
    ]
  };

  const nextState = Core.applyProposal(seed, proposal, ['op-1'], schema);
  assert.strictEqual(nextState.skills.length, seed.skills.length + 1);
  assert(nextState.skills.some(s => s.id === 'wood.test_skill'));
  assert.strictEqual(nextState.appliedProposalIds.includes('p-test-1'), true);
});

test('applyProposal rejects revision mismatch', () => {
  const proposal = {
    version: 1,
    id: 'p-mismatch',
    baseRevision: 999,
    summary: 'Устаревшее предложение',
    questions: [],
    operations: []
  };
  assert.throws(() => Core.applyProposal(seed, proposal, [], schema), /ревизи/i);
});

test('applyProposal rejects risk downgrade (AI cannot lower risk from pro to low)', () => {
  const originalSkill = seed.skills.find(s => s.risk === 'pro');
  assert(originalSkill, 'Seed should contain a skill with risk pro');

  const downgraded = Core.clone(originalSkill);
  downgraded.risk = 'low';

  const proposal = {
    version: 1,
    id: 'p-downgrade-risk',
    baseRevision: seed.revision,
    summary: 'Попытка понизить риск',
    questions: [],
    operations: [
      {
        id: 'op-downgrade',
        type: 'update_skill',
        targetId: originalSkill.id,
        reason: 'Попытка понизить риск',
        data: downgraded
      }
    ]
  };

  assert.throws(() => Core.applyProposal(seed, proposal, ['op-downgrade'], schema), /не может понижать/);
});

test('safeTree rejects prototype pollution attempts', () => {
  const malicious = JSON.parse('{"__proto__": {"polluted": true}}');
  assert.throws(() => Core.safeTree(malicious), /Недопустимый ключ данных/);
});

console.log(`\nCore Tests Result: ${passed} passed, ${failed} failed.`);
if (failed > 0) {
  process.exit(1);
}
