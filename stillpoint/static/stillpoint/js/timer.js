document.addEventListener('DOMContentLoaded', function () {
  const $ = id => document.getElementById(id);

  const ring = $('sp-ring');
  const progress = $('sp-progress');
  const timeEl = $('sp-time');
  const phaseEl = $('sp-phase');
  const beginBtn = $('sp-begin');
  const resetBtn = $('sp-reset');
  const durationsEl = $('sp-durations');
  const optionsEl = $('sp-options');
  const guidedEl = $('sp-guided');
  const select = $('sp-audio-select');
  const audio = $('sp-audio');
  const bellsInput = $('sp-bells');
  const volumeInput = $('sp-volume');
  const statStreak = $('sp-stat-streak');
  const statSessions = $('sp-stat-sessions');
  const statMinutes = $('sp-stat-minutes');

  const R = 110;
  const CIRC = 2 * Math.PI * R;
  progress.style.strokeDasharray = CIRC;

  let mode = 'master';
  let durationSec = 15 * 60;
  let remaining = durationSec;
  let running = false;
  let endAt = 0;
  let rafId = null;
  let completionTimer = null;
  let wakeLock = null;
  let volume = parseFloat(localStorage.getItem('stillpoint.volume') || '0.8');
  let bellsEnabled = localStorage.getItem('stillpoint.bells') === 'true';
  let bellTimers = [];

  // ── Soft synthesized bell (no audio file needed) ──
  let audioCtx = null;
  function chime() {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const now = audioCtx.currentTime;
      [432, 648].forEach((freq, i) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        const vol = (i === 0 ? 0.35 : 0.12) * volume;
        gain.gain.setValueAtTime(0.0001, now);
        gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, vol), now + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 3.5);
        osc.start(now);
        osc.stop(now + 3.6);
      });
    } catch (e) { /* audio not available: stay silent */ }
  }

  // A quieter, single-tone variant for interval bells during Master mode —
  // distinct from the two-tone start/end chime so it reads as a gentle
  // marker, not another completion signal.
  function softBell() {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const now = audioCtx.currentTime;
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'sine';
      osc.frequency.value = 528;
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      const vol = 0.18 * volume;
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(Math.max(0.0001, vol), now + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 2.2);
      osc.start(now);
      osc.stop(now + 2.3);
    } catch (e) { /* audio not available: stay silent */ }
  }

  // Interval bells are scheduled from the point a session (re)starts, not
  // from a fixed session start, so resuming after a pause only schedules
  // whatever marks are still ahead rather than replaying missed ones.
  function scheduleIntervalBells() {
    clearIntervalBells();
    if (!bellsEnabled) return;
    const intervalSec = 5 * 60;
    const elapsedAtStart = durationSec - remaining;
    for (let mark = intervalSec; mark < durationSec; mark += intervalSec) {
      if (mark <= elapsedAtStart) continue;
      const delayMs = (mark - elapsedAtStart) * 1000;
      bellTimers.push(setTimeout(() => { if (running) softBell(); }, delayMs));
    }
  }
  function clearIntervalBells() {
    bellTimers.forEach(id => clearTimeout(id));
    bellTimers = [];
  }

  // ── Screen wake lock ──
  // Best-effort: unsupported browsers just never acquire one, and the lock
  // is released automatically by the browser whenever the tab is hidden,
  // which the visibilitychange handler below re-acquires on return.
  async function acquireWakeLock() {
    if (!('wakeLock' in navigator)) return;
    try {
      wakeLock = await navigator.wakeLock.request('screen');
    } catch (e) { /* wake lock unavailable (e.g. low battery): stay unlocked */ }
  }
  function releaseWakeLock() {
    if (!wakeLock) return;
    wakeLock.release().catch(() => {});
    wakeLock = null;
  }

  // ── Local session history + streaks (localStorage only, no account) ──
  function isoDateFor(date) {
    return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
  }
  function loadSessions() {
    try {
      const parsed = JSON.parse(localStorage.getItem('stillpoint.sessions') || '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) { return []; }
  }
  function recordSession(minutes) {
    const sessions = loadSessions();
    sessions.push({ date: isoDateFor(new Date()), minutes: Math.round(minutes) });
    localStorage.setItem('stillpoint.sessions', JSON.stringify(sessions));
    renderStats();
  }
  function computeStreak(sessions) {
    const days = new Set(sessions.map(s => s.date));
    const cursor = new Date();
    // If today has no session yet, count from yesterday so the streak
    // doesn't read as broken before the day is actually over.
    if (!days.has(isoDateFor(cursor))) cursor.setDate(cursor.getDate() - 1);
    let streak = 0;
    while (days.has(isoDateFor(cursor))) {
      streak += 1;
      cursor.setDate(cursor.getDate() - 1);
    }
    return streak;
  }
  function renderStats() {
    if (!statStreak) return;
    const sessions = loadSessions();
    statStreak.textContent = computeStreak(sessions);
    statSessions.textContent = sessions.length;
    statMinutes.textContent = sessions.reduce((sum, s) => sum + (s.minutes || 0), 0);
  }

  // ── Rendering ──
  function fmt(sec) {
    sec = Math.max(0, Math.ceil(sec));
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return m + ':' + String(s).padStart(2, '0');
  }
  function setProgress(frac) {
    progress.style.strokeDashoffset = CIRC * (1 - Math.max(0, Math.min(1, frac)));
  }
  function renderTime() {
    timeEl.textContent = fmt(remaining);
    setProgress(durationSec ? remaining / durationSec : 0);
  }
  function setBeginLabel(text) { beginBtn.textContent = text; }
  function showReset(show) { resetBtn.hidden = !show; }

  // ── Master mode (silent countdown) ──
  // requestAnimationFrame is throttled or fully suspended once a tab is
  // backgrounded or a phone screen locks, so it can't be trusted alone to
  // ever call finish() — a session that ends while hidden would otherwise
  // silently never chime. scheduleCompletionCheck() is a setTimeout keyed
  // to the real end time as a backstop, and the visibilitychange listener
  // below catches up (and fires finish() if it's already overdue) the
  // instant the tab becomes visible again, independent of whether rAF or
  // the timeout actually fired while hidden.
  function scheduleCompletionCheck() {
    clearTimeout(completionTimer);
    const msRemaining = endAt - Date.now();
    completionTimer = setTimeout(() => {
      if (running && Date.now() >= endAt) finish();
    }, Math.max(0, msRemaining) + 50);
  }
  function tick() {
    if (!running) return;
    remaining = (endAt - Date.now()) / 1000;
    if (remaining <= 0) {
      remaining = 0;
      renderTime();
      finish();
      return;
    }
    renderTime();
    rafId = requestAnimationFrame(tick);
  }
  function startMaster() {
    running = true;
    endAt = Date.now() + remaining * 1000;
    chime();
    ring.classList.add('is-breathing');
    phaseEl.textContent = 'Breathe';
    setBeginLabel('Pause');
    showReset(true);
    rafId = requestAnimationFrame(tick);
    scheduleCompletionCheck();
    scheduleIntervalBells();
    acquireWakeLock();
  }
  function pauseMaster() {
    running = false;
    cancelAnimationFrame(rafId);
    clearTimeout(completionTimer);
    clearIntervalBells();
    releaseWakeLock();
    remaining = (endAt - Date.now()) / 1000;
    ring.classList.remove('is-breathing');
    phaseEl.textContent = 'Paused';
    setBeginLabel('Resume');
  }
  function finish() {
    const completedMinutes = durationSec / 60;
    running = false;
    cancelAnimationFrame(rafId);
    clearTimeout(completionTimer);
    clearIntervalBells();
    releaseWakeLock();
    ring.classList.remove('is-breathing');
    chime();
    phaseEl.textContent = 'Complete';
    setBeginLabel('Begin');
    recordSession(completedMinutes);
  }

  // ── Student mode (audio-led) ──
  function startStudent() {
    if (!audio || !audio.src) return;
    running = true;
    audio.play();
    ring.classList.add('is-breathing');
    phaseEl.textContent = 'Guided';
    setBeginLabel('Pause');
    showReset(true);
    acquireWakeLock();
  }
  function pauseStudent() {
    running = false;
    audio.pause();
    releaseWakeLock();
    ring.classList.remove('is-breathing');
    phaseEl.textContent = 'Paused';
    setBeginLabel('Resume');
  }
  function finishStudent() {
    const completedMinutes = (durationSec || 0) / 60;
    running = false;
    releaseWakeLock();
    ring.classList.remove('is-breathing');
    chime();
    phaseEl.textContent = 'Complete';
    setBeginLabel('Begin');
    recordSession(completedMinutes);
  }

  if (audio) {
    audio.addEventListener('loadedmetadata', () => {
      // Only let the audio length drive the timer while in guided mode;
      // otherwise Master mode would get clobbered to the track's length.
      if (mode !== 'student') return;
      durationSec = audio.duration || durationSec;
      remaining = durationSec - audio.currentTime;
      renderTime();
    });
    audio.addEventListener('timeupdate', () => {
      if (mode !== 'student' || isNaN(audio.duration)) return;
      remaining = audio.duration - audio.currentTime;
      renderTime();
    });
    audio.addEventListener('ended', finishStudent);
  }

  // ── Shared reset ──
  function reset() {
    running = false;
    cancelAnimationFrame(rafId);
    clearTimeout(completionTimer);
    clearIntervalBells();
    releaseWakeLock();
    ring.classList.remove('is-breathing');
    if (mode === 'student' && audio) { audio.pause(); audio.currentTime = 0; }
    if (mode === 'student' && audio && !isNaN(audio.duration)) {
      durationSec = audio.duration;
    }
    remaining = durationSec;
    renderTime();
    phaseEl.textContent = 'Press begin';
    setBeginLabel('Begin');
    showReset(false);
  }

  // Master mode's rAF loop can go stale or fully stop while the tab is
  // hidden; recompute and catch up (including firing a now-overdue finish())
  // the moment the tab is visible again, rather than trusting rAF to have
  // kept ticking the whole time. The wake lock is also released by the
  // browser automatically on hide, so re-acquire it here too.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible' || !running) return;
    acquireWakeLock();
    if (mode !== 'master') return;
    remaining = (endAt - Date.now()) / 1000;
    if (remaining <= 0) {
      remaining = 0;
      renderTime();
      finish();
      return;
    }
    renderTime();
    cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(tick);
  });

  // ── Controls ──
  beginBtn.addEventListener('click', () => {
    if (mode === 'master') {
      running ? pauseMaster() : startMaster();
    } else {
      running ? pauseStudent() : startStudent();
    }
  });
  resetBtn.addEventListener('click', reset);

  // Duration presets (master)
  if (durationsEl) {
    durationsEl.querySelectorAll('.sp-duration').forEach(btn => {
      btn.addEventListener('click', () => {
        if (running) return;
        durationsEl.querySelectorAll('.sp-duration').forEach(b => b.classList.remove('sp-duration--active'));
        btn.classList.add('sp-duration--active');
        durationSec = parseInt(btn.dataset.min, 10) * 60;
        remaining = durationSec;
        renderTime();
      });
    });
  }

  // Guided session picker (student)
  if (select && audio) {
    const load = () => { audio.src = select.value; audio.load(); };
    select.addEventListener('change', load);
    load();
  }

  // Interval bells + volume (master), persisted across visits
  if (bellsInput) {
    bellsInput.checked = bellsEnabled;
    bellsInput.addEventListener('change', () => {
      bellsEnabled = bellsInput.checked;
      localStorage.setItem('stillpoint.bells', String(bellsEnabled));
      if (running && mode === 'master') scheduleIntervalBells();
    });
  }
  if (volumeInput) {
    volumeInput.value = String(Math.round(volume * 100));
    volumeInput.addEventListener('input', () => {
      volume = volumeInput.value / 100;
      localStorage.setItem('stillpoint.volume', String(volume));
    });
  }

  // Mode switching
  document.querySelectorAll('.stillpoint__mode').forEach(btn => {
    btn.addEventListener('click', () => {
      const next = btn.dataset.mode;
      if (next === mode) return;
      mode = next;
      document.querySelectorAll('.stillpoint__mode').forEach(b => {
        const active = b === btn;
        b.classList.toggle('stillpoint__mode--active', active);
        b.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      if (durationsEl) durationsEl.hidden = mode !== 'master';
      if (optionsEl) optionsEl.hidden = mode !== 'master';
      if (guidedEl) guidedEl.hidden = mode !== 'student';

      // Disable begin in guided mode when no audio is configured.
      beginBtn.disabled = (mode === 'student' && !window.STILLPOINT_HAS_AUDIO);

      if (mode === 'master') { durationSec = (parseInt((durationsEl.querySelector('.sp-duration--active') || {}).dataset?.min, 10) || 15) * 60; }
      reset();
    });
  });

  renderTime();
  renderStats();
});
