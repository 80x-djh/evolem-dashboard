// StatiCrypt v3 re-encrypt: encrypt generator/plain.html with DASH_PASSWORD and
// splice the new salt + signed message into the existing ../index.html wrapper
// (keeping its StatiCrypt loader untouched). Writes ../index.html in place.
//
// Env: DASH_PASSWORD (required, e.g. "EvolemLogin").
import { webcrypto as crypto } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const subtle = crypto.subtle;
const enc = s => new TextEncoder().encode(s);
const hex2buf = h => Uint8Array.from(h.match(/.{2}/g).map(b => parseInt(b, 16)));
const buf2hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, '0')).join('');
async function pbkdf2(p, s, it, h) {
  const km = await subtle.importKey('raw', enc(p), 'PBKDF2', false, ['deriveBits']);
  return buf2hex(await subtle.deriveBits({ name: 'PBKDF2', hash: h, iterations: it, salt: enc(s) }, km, 256));
}
async function hashPassword(p, salt) {
  let x = await pbkdf2(p, salt, 1000, 'SHA-1');
  x = await pbkdf2(x, salt, 14000, 'SHA-256');
  return pbkdf2(x, salt, 585000, 'SHA-256');
}
async function hmac(hp, m) {
  const k = await subtle.importKey('raw', hex2buf(hp), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return buf2hex(await subtle.sign('HMAC', k, enc(m)));
}
async function encrypt(plain, hp) {
  const iv = crypto.getRandomValues(new Uint8Array(16));
  const key = await subtle.importKey('raw', hex2buf(hp), 'AES-CBC', false, ['encrypt']);
  const ct = await subtle.encrypt({ name: 'AES-CBC', iv }, key, enc(plain));
  return buf2hex(iv) + buf2hex(ct);
}

const pw = process.env.DASH_PASSWORD;
if (!pw) { console.error('DASH_PASSWORD env required'); process.exit(1); }

const plain = fs.readFileSync(path.join(HERE, 'plain.html'), 'utf8');
const indexPath = path.join(HERE, '..', 'index.html');
const salt = buf2hex(crypto.getRandomValues(new Uint8Array(16)));
const hp = await hashPassword(pw, salt);
const encryptedMsg = await encrypt(plain, hp);
const signed = (await hmac(hp, encryptedMsg)) + encryptedMsg;

let wrap = fs.readFileSync(indexPath, 'utf8');
const oldSalt = wrap.match(/"staticryptSaltUniqueVariableName"\s*:\s*"([a-f0-9]+)"/)[1];
const oldMsg = wrap.match(/"staticryptEncryptedMsgUniqueVariableName"\s*:\s*"([a-f0-9]+)"/)[1];
let n1 = 0, n2 = 0;
wrap = wrap.split(oldSalt).join((() => { n1++; return salt; })());
wrap = wrap.replace(oldMsg, () => { n2++; return signed; });
fs.writeFileSync(indexPath, wrap);
console.log(`salt replacements: ${n1} | msg replacements: ${n2} | wrapper bytes: ${wrap.length}`);

// self-verify roundtrip
const em = signed.substring(64);
const iv = hex2buf(em.substring(0, 32));
const key = await subtle.importKey('raw', hex2buf(await hashPassword(pw, salt)), 'AES-CBC', false, ['decrypt']);
const back = new TextDecoder().decode(await subtle.decrypt({ name: 'AES-CBC', iv }, key, hex2buf(em.substring(32))));
if (back !== plain) { console.error('roundtrip FAILED'); process.exit(1); }
console.log('roundtrip OK');
