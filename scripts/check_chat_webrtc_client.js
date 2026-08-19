const fs = require('fs');
const path = require('path');

const templatePath = path.join(__dirname, '..', 'app', 'templates', 'messages', 'chat.html');
const template = fs.readFileSync(templatePath, 'utf8');
const scripts = [...template.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((match) => match[1]);

if (scripts.length !== 1) {
  throw new Error(`عدد كتل JavaScript غير متوقع: ${scripts.length}`);
}

const requiredFragments = [
  'RTCPeerConnection',
  'getUserMedia',
  'startVoiceCall',
  'data-retry-call',
  "querySelectorAll('[data-retry-call]')",
  'acceptIncomingCall',
  'sendCallSignal',
  'handleCallSignal',
  'startRinging',
  'stopRinging',
  'startNoAnswerTimeout',
  "reason: 'no_answer'",
  "sendCallSignal('invite'",
  "sendCallSignal('answer'",
  "sendCallSignal('candidate'",
  "sendCallSignal('hangup'",
];
for (const fragment of requiredFragments) {
  if (!scripts[0].includes(fragment)) {
    throw new Error(`منطق الاتصال يفتقد الجزء المطلوب: ${fragment}`);
  }
}

// يحل محل تعبيرات Jinja بقيم JavaScript محايدة لفحص صياغة النص البرمجي فقط.
const normalizedScript = scripts[0].replace(/\{\{[\s\S]*?\}\}/g, 'null');
try {
  new Function(normalizedScript);
} catch (error) {
  throw new Error(`صياغة JavaScript في عميل الاتصال غير صالحة: ${error.message}`);
}

console.log('WebRTC عميل المحادثة: OK');
