const fs = require('fs');
const path = require('path');

const templatePath = path.join(__dirname, '..', 'app', 'templates', 'messages', 'chat.html');
const template = fs.readFileSync(templatePath, 'utf8');
const scripts = [...template.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((match) => match[1]);

if (scripts.length !== 1) {
  throw new Error(`عدد كتل JavaScript غير متوقع: ${scripts.length}`);
}

if (scripts[0].includes("if (document.visibilityState === 'hidden' || pollingInProgress) return;")) {
  throw new Error('استطلاع إشارات المكالمة يجب ألا يتوقف عندما تصبح الصفحة غير نشطة.');
}
if (!scripts[0].includes('const callRes = await fetch(`/messages/calls/poll/${otherUserId}`);')) {
  throw new Error('مسار استطلاع إشارات المكالمة غير موجود.');
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
  'desktopNotificationsSupported',
  'requestCallNotificationPermission',
  'showIncomingDesktopNotification',
  'closeIncomingCallNotification',
  'Notification.requestPermission',
  "new Notification('مكالمة واردة عبر ANTER'",
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
