import assert from 'node:assert/strict';
import test from 'node:test';
import { newSession, signSession, sessionOwner, permittedPath } from '../src/lib/analysis-security.ts';

test('signed ownership rejects tampering, expiry and wrong secrets', () => {
  const secret = 'test-secret-'.repeat(4);
  const session = newSession(secret);
  assert.match(sessionOwner(session, secret), /^[a-f0-9]{64}$/);
  assert.equal(sessionOwner(session, 'wrong'), null);
  assert.equal(sessionOwner(session.slice(0, -1), secret), null);
  assert.equal(sessionOwner(signSession('a'.repeat(64), secret, 1000000000), secret), null);
  assert.notEqual(sessionOwner(newSession(secret), secret), sessionOwner(session, secret));
});
test('gateway allows only small control requests and safe evidence paths', () => {
  const job = 'TEST_20261005000000_' + 'a'.repeat(32);
  assert.equal(permittedPath([job, 'results'], 'GET'), `/${job}/results`);
  assert.equal(permittedPath([job, 'upload'], 'PUT'), null);
  assert.equal(permittedPath([job, 'players', '123', 'evidence', '../private.csv'], 'GET'), null);
  assert.equal(permittedPath([job, 'players', '123', 'evidence', 'evidence_rt.csv'], 'GET'), `/${job}/players/123/evidence/evidence_rt.csv`);
  assert.equal(permittedPath(['..', 'health'], 'GET'), null);
  assert.equal(permittedPath([], 'POST'), '');
});
