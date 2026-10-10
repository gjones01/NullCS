import assert from 'node:assert/strict';
import test from 'node:test';
import { desktopReleaseUrl } from '../src/lib/desktop-release.ts';

test('download only accepts a concrete project release installer', () => {
  const good = 'https://github.com/gjones01/NullCS/releases/download/v1/NullCS%20Setup.exe';
  assert.equal(desktopReleaseUrl(good), good);
  for (const value of [undefined, '', 'garbage', good+'?token=private', good+'#fragment',
    good.replace('https:', 'http:'), good.replace('github.com', 'github.com:8080'),
    good.replace('github.com', 'user:password@github.com'), good.replace('NullCS/releases', 'Other/releases'),
    good.replace('/v1/', '//'), good.replace('/v1/', '/v1/more/'), good.replace('/v1/', '/v1%2Fnext/'),
    good.replace('Setup.exe', 'Setup%00.exe'), good.replace('Setup.exe', 'Setup%5c.exe'),
    good.replace('Setup.exe', 'Setup.zip'), good.replace('Setup.exe', 'Setup%.exe')]) {
    assert.equal(desktopReleaseUrl(value), null, value);
  }
});
