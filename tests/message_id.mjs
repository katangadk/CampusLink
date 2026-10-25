import assert from 'node:assert/strict';
import { newMessageId } from '../web/message-id.js';

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
assert.match(newMessageId(), uuid);

// Simulate an HTTP LAN origin: secure-context-only randomUUID is unavailable.
const phoneCrypto = { getRandomValues: crypto.getRandomValues.bind(crypto) };
const ids = Array.from({ length: 100 }, () => newMessageId(phoneCrypto));
assert.equal(new Set(ids).size, 100);
for (const id of ids) assert.match(id, uuid);
console.log('PASS: message IDs work on HTTPS/localhost and plain HTTP LAN origins.');
