document.addEventListener('DOMContentLoaded', function () {
  const $ = id => document.getElementById(id);

  const ring = $('sp-ring');
  const progress = $('sp-progress');
  const timeEl = $('sp-time');
  const phaseEl = $('sp-phase');
  const pillEl = $('sp-begin');
  const calibrationEl = $('sp-calibration');
  const calibrationLinesEl = $('sp-calibration-lines');
  const guidedEl = $('sp-guided');
  const select = $('sp-audio-select');
  const audio = $('sp-audio');
  const statSessions = $('sp-stat-sessions');
  const recentDaysEl = $('sp-recent-days');

  const R = 110;
  const CIRC = 2 * Math.PI * R;
  progress.style.strokeDasharray = CIRC;

  // Signed-in users are database-only, full stop — clear any local demo
  // data left over from before they logged in (or from an earlier
  // anonymous visit on this browser) so it can never resurface and be
  // mistaken for real, synced history.
  if (window.STILLPOINT_AUTHENTICATED) {
    try { localStorage.removeItem('stillpoint.sessions'); } catch (e) { /* ignore */ }
  }

  let mode = 'master';
  let durationSec = 15 * 60;
  let remaining = durationSec;
  let running = false;
  let armed = false;
  let endAt = 0;
  let rafId = null;
  let completionTimer = null;
  let armTimer = null;
  let disarmTextTimer = null;
  let wakeLock = null;
  let bellTimers = [];

  // ── Bell: a real struck-bowl recording, decoded once up front so it's
  // ready by the time anyone actually presses Begin. If it hasn't finished
  // loading yet (slow connection, first paint), synthesizedChime() below
  // is the fallback — same four-partial swell used before the recording
  // existed — so a session is never silently missing its bell.
  let audioCtx = null;
  let bowlBuffer = null;
  let bowlLoadPromise = null;
  function loadBowl() {
    if (bowlLoadPromise || !window.STILLPOINT_BELL_URL) return bowlLoadPromise;
    bowlLoadPromise = fetch(window.STILLPOINT_BELL_URL)
      .then(r => r.arrayBuffer())
      .then(data => {
        audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
        return audioCtx.decodeAudioData(data);
      })
      .then(buf => { bowlBuffer = buf; })
      .catch(() => { /* stays null: chime() falls back to the synthesized bell */ });
    return bowlLoadPromise;
  }
  loadBowl();

  // A second, distinct set of struck-bowl recordings for the two-minute
  // interval marks during Master mode — one is picked at random for each
  // mark, so a long sit hears a varying mix rather than the same bell on
  // repeat (repeats are allowed; nothing tracks "last played").
  let intervalBowlBuffers = [];
  let intervalBowlLoadPromise = null;
  function loadIntervalBowls() {
    const urls = window.STILLPOINT_INTERVAL_BELL_URLS;
    if (intervalBowlLoadPromise || !urls || !urls.length) return intervalBowlLoadPromise;
    intervalBowlLoadPromise = Promise.all(urls.map(url =>
      fetch(url)
        .then(r => r.arrayBuffer())
        .then(data => {
          audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
          return audioCtx.decodeAudioData(data);
        })
        .catch(() => null)
    )).then(buffers => {
      intervalBowlBuffers = buffers.filter(Boolean);
    });
    return intervalBowlLoadPromise;
  }
  loadIntervalBowls();

  // Shared playback for any decoded bowl buffer — tiny fades at each end
  // guard against a click at the sample boundary (the recording's own
  // strike-and-decay already does the "soft start, slow fade" shape, so
  // nothing more is layered on top of it). `peak` lets interval bells sit
  // quieter than the start/end chime without needing a second code path.
  function playBowlBuffer(buffer, peak) {
    const now = audioCtx.currentTime;
    const source = audioCtx.createBufferSource();
    const gain = audioCtx.createGain();
    source.buffer = buffer;
    source.connect(gain);
    gain.connect(audioCtx.destination);
    const fadeOutStart = Math.max(0, buffer.duration - 0.3);
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(peak, now + 0.06);
    gain.gain.setValueAtTime(peak, now + fadeOutStart);
    gain.gain.linearRampToValueAtTime(0, now + buffer.duration);
    source.start(now);
  }
  function playBowl() { playBowlBuffer(bowlBuffer, 0.9); }

  // Fallback only — four inharmonic partials, each a pair of oscillators a
  // fraction of a Hz apart so the pair slowly beats against itself, soft
  // swell in, slow fade over ~12s.
  function synthesizedChime() {
    const now = audioCtx.currentTime;
    const duration = 12;
    const partials = [
      { freq: 220, gain: 0.30 },
      { freq: 396, gain: 0.16 },
      { freq: 583, gain: 0.10 },
      { freq: 887, gain: 0.06 }
    ];
    partials.forEach(({ freq, gain }) => {
      [-0.6, 0.6].forEach(detune => {
        const osc = audioCtx.createOscillator();
        const g = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq + detune;
        osc.connect(g);
        g.connect(audioCtx.destination);
        g.gain.setValueAtTime(0.0001, now);
        g.gain.exponentialRampToValueAtTime(gain / 2, now + 3.2);
        g.gain.exponentialRampToValueAtTime(0.0001, now + duration);
        osc.start(now);
        osc.stop(now + duration + 0.2);
      });
    });
  }

  function chime() {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      if (bowlBuffer) { playBowl(); return; }
      synthesizedChime();
      loadBowl(); // in case the first attempt hasn't kicked off yet
    } catch (e) { /* audio not available: stay silent */ }
  }

  // A quieter, single-tone variant for interval bells during Master mode —
  // distinct from the start/end chime so it reads as a gentle marker, not
  // another completion signal. Used only as a fallback when none of the
  // recorded interval bowls have finished decoding yet.
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
      gain.gain.setValueAtTime(0.0001, now);
      gain.gain.exponentialRampToValueAtTime(0.18, now + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + 2.2);
      osc.start(now);
      osc.stop(now + 2.3);
    } catch (e) { /* audio not available: stay silent */ }
  }

  // Picks one of the interval bowl recordings at random (repeats allowed —
  // that's what makes a long sit hear "two or three in a row" sometimes
  // instead of a strict rotation) and plays it quieter than the start/end
  // chime. Falls back to the synthesized soft bell if the recordings
  // haven't finished loading.
  function intervalBell() {
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      if (intervalBowlBuffers.length) {
        const buffer = intervalBowlBuffers[Math.floor(Math.random() * intervalBowlBuffers.length)];
        playBowlBuffer(buffer, 0.5);
        return;
      }
      softBell();
      loadIntervalBowls(); // in case the first attempt hasn't kicked off yet
    } catch (e) { /* audio not available: stay silent */ }
  }

  // Interval bells always run in Master mode, no toggle — scheduled from
  // the point a session (re)starts, not from a fixed session start, so
  // resuming after a pause only schedules whatever marks are still ahead
  // rather than replaying missed ones.
  function scheduleIntervalBells() {
    clearIntervalBells();
    const intervalSec = 2 * 60;
    const elapsedAtStart = durationSec - remaining;
    for (let mark = intervalSec; mark < durationSec; mark += intervalSec) {
      if (mark <= elapsedAtStart) continue;
      const delayMs = (mark - elapsedAtStart) * 1000;
      bellTimers.push(setTimeout(() => { if (running) intervalBell(); }, delayMs));
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
  // ── Fullscreen: compels focus on desktop/web-app use, where a browser
  // chrome full of tabs and bookmarks is one glance away from a session.
  // Skipped on touch-primary, narrow-viewport devices — mobile fullscreen
  // support is inconsistent (iOS Safari has none at all for non-video
  // elements) and the OS chrome there is already minimal, so there's
  // little to gain and a real risk of a jarring no-op or layout jump.
  function isMobileLike() {
    return window.matchMedia('(pointer: coarse)').matches && window.innerWidth < 768;
  }
  function enterFullscreenIfDesktop() {
    if (isMobileLike() || document.fullscreenElement) return;
    const request = document.documentElement.requestFullscreen;
    if (request) request.call(document.documentElement).catch(() => {});
  }
  function exitFullscreenIfActive() {
    if (document.fullscreenElement && document.exitFullscreen) {
      document.exitFullscreen().catch(() => {});
    }
  }

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

  // ── Session history: localStorage always (anonymous demo fallback),
  // plus the server when signed in, so sessions survive across devices. ──
  function isoDateFor(date) {
    return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
  }
  function loadSessions() {
    try {
      const parsed = JSON.parse(localStorage.getItem('stillpoint.sessions') || '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) { return []; }
  }
  function currentGuidedSessionId() {
    if (!select) return null;
    const opt = select.options[select.selectedIndex];
    return opt && opt.dataset.id ? opt.dataset.id : null;
  }
  let serverSessionDates = null;
  function fetchServerSessions() {
    if (!window.STILLPOINT_AUTHENTICATED || !window.STILLPOINT_SESSIONS_URL) return;
    fetch(window.STILLPOINT_SESSIONS_URL, { credentials: 'same-origin' })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data || !Array.isArray(data.sessions)) return;
        serverSessionDates = data.sessions.map(s => isoDateFor(new Date(s.completedAt)));
        renderStats();
      })
      .catch(() => {});
  }
  function postSessionToServer(durationSeconds, sessionMode) {
    if (!window.STILLPOINT_AUTHENTICATED || !window.STILLPOINT_SESSIONS_URL) return;
    const body = {
      completedAt: new Date().toISOString(),
      durationSeconds: Math.round(durationSeconds),
      mode: sessionMode
    };
    if (sessionMode === 'student') {
      const guidedId = currentGuidedSessionId();
      if (guidedId) body.guidedSessionId = guidedId;
    }
    fetch(window.STILLPOINT_SESSIONS_URL, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': window.STILLPOINT_CSRF_TOKEN },
      keepalive: true,
      body: JSON.stringify(body)
    }).then(fetchServerSessions).catch(() => {});
  }
  function recordSession(durationSeconds, sessionMode) {
    if (window.STILLPOINT_AUTHENTICATED) {
      // Database-only for signed-in users — never touches localStorage.
      postSessionToServer(durationSeconds, sessionMode);
    } else {
      const sessions = loadSessions();
      sessions.push({ date: isoDateFor(new Date()) });
      localStorage.setItem('stillpoint.sessions', JSON.stringify(sessions));
    }
    renderStats();
  }
  // A quieter alternative to a numeric streak: the last two days trail to
  // the left, today is the rightmost dot with nothing after it — filled in
  // if a session happened that day.
  const RECENT_DAY_OFFSETS = [2, 1, 0]; // two days ago, yesterday, today (rightmost)
  function renderStats() {
    if (!statSessions) return;
    // Signed-in: server data only, even mid-load (empty, not localStorage,
    // while the fetch is in flight) — a logged-in user's stats must never
    // be able to show local-only numbers.
    const dates = window.STILLPOINT_AUTHENTICATED
      ? (serverSessionDates || [])
      : loadSessions().map(s => s.date);
    statSessions.textContent = dates.length;
    if (!recentDaysEl) return;
    const days = new Set(dates);
    const dayEls = recentDaysEl.querySelectorAll('.sp-day');
    dayEls.forEach((el, index) => {
      const offset = RECENT_DAY_OFFSETS[index];
      const cursor = new Date();
      cursor.setDate(cursor.getDate() - offset);
      el.classList.toggle('is-done', days.has(isoDateFor(cursor)));
      el.classList.toggle('is-today', offset === 0);
    });
  }
  fetchServerSessions();

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
  // The pill is a plain <span> inside the ring, not its own control — the
  // ring itself is the button, so clicking the pill or anywhere else on
  // the circle does the exact same thing.
  function setPillLabel(text) { pillEl.textContent = text; }
  // Blank/hidden at idle rather than "Press begin" — the pill already says
  // that; this caption is reserved for actual state (Breathe, Guided,
  // Complete, the end-early confirm) so it's never just repeating the pill.
  function setPhase(text) {
    if (text) {
      phaseEl.textContent = text;
      phaseEl.hidden = false;
    } else {
      phaseEl.textContent = '';
      phaseEl.hidden = true;
    }
  }

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
    setPhase('Breathe');
    setPillLabel('End early');
    ring.setAttribute('aria-label', 'End meditation early');
    document.body.classList.add('sp-focus');
    enterFullscreenIfDesktop();
    rafId = requestAnimationFrame(tick);
    scheduleCompletionCheck();
    scheduleIntervalBells();
    acquireWakeLock();
  }
  function finish() {
    running = false;
    armed = false;
    clearTimeout(armTimer);
    cancelAnimationFrame(rafId);
    clearTimeout(completionTimer);
    clearIntervalBells();
    releaseWakeLock();
    exitFullscreenIfActive();
    ring.classList.remove('is-breathing', 'is-armed');
    document.body.classList.remove('sp-focus', 'is-armed');
    document.body.classList.add('is-complete');
    chime();
    setProgress(1);
    setPhase('Complete for today.');
    setPillLabel('Begin');
    ring.setAttribute('aria-label', 'Begin a new session');
    recordSession(durationSec, 'master');
  }
  function endMasterEarly() {
    cancelAnimationFrame(rafId);
    clearTimeout(completionTimer);
    clearIntervalBells();
    remaining = durationSec;
    renderTime();
    endEarlyCommon();
  }

  // ── Student mode (audio-led) ──
  function startStudent() {
    if (!audio || !audio.src) return;
    running = true;
    audio.play();
    ring.classList.add('is-breathing');
    setPhase('Guided');
    setPillLabel('End early');
    ring.setAttribute('aria-label', 'End meditation early');
    document.body.classList.add('sp-focus');
    enterFullscreenIfDesktop();
    acquireWakeLock();
  }
  function finishStudent() {
    running = false;
    armed = false;
    clearTimeout(armTimer);
    releaseWakeLock();
    exitFullscreenIfActive();
    ring.classList.remove('is-breathing', 'is-armed');
    document.body.classList.remove('sp-focus', 'is-armed');
    document.body.classList.add('is-complete');
    chime();
    setProgress(1);
    setPhase('Complete for today.');
    setPillLabel('Begin');
    ring.setAttribute('aria-label', 'Begin a new session');
    recordSession(audio && !isNaN(audio.duration) ? audio.duration : durationSec, 'student');
  }
  function endStudentEarly() {
    if (audio) { audio.pause(); audio.currentTime = 0; }
    endEarlyCommon();
  }

  // ── Ending early: a light guilt trip, not a hard stop. The first click
  // while running arms a confirmation (amber accent, gentle nudge, pill
  // stays visible instead of only-on-hover); a second click within the
  // window actually ends the session. Nothing is recorded to the session
  // history — the point is that it's not the same as sitting the whole
  // time.
  const GUILT_MESSAGE = "The bell hasn't rung yet — end early?";
  function armEndEarly() {
    armed = true;
    clearTimeout(armTimer);
    document.body.classList.add('is-armed');
    ring.classList.add('is-armed');
    setPhase(GUILT_MESSAGE);
    setPillLabel('Yes, end early');
    ring.setAttribute('aria-label', 'Confirm end session early');
    armTimer = setTimeout(disarmEndEarly, 4000);
  }
  function disarmEndEarly() {
    if (!armed) return;
    armed = false;
    clearTimeout(armTimer);
    document.body.classList.remove('is-armed');
    ring.classList.remove('is-armed');
    setPhase(mode === 'master' ? 'Breathe' : 'Guided');
    setPillLabel('End early');
    ring.setAttribute('aria-label', 'End meditation early');
  }
  function endEarlyCommon() {
    running = false;
    armed = false;
    clearTimeout(armTimer);
    releaseWakeLock();
    exitFullscreenIfActive();
    ring.classList.remove('is-breathing', 'is-armed');
    document.body.classList.remove('sp-focus', 'is-armed');
    setPhase('Ended early. The stillness will keep.');
    setPillLabel('Begin');
    ring.setAttribute('aria-label', 'Begin meditation');
    clearTimeout(disarmTextTimer);
    disarmTextTimer = setTimeout(() => {
      if (!running) setPhase('');
    }, 2600);
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

  // ── Shared idle state ── used for mode switches and before a fresh start
  function goIdle() {
    running = false;
    armed = false;
    cancelAnimationFrame(rafId);
    clearTimeout(completionTimer);
    clearTimeout(armTimer);
    clearTimeout(disarmTextTimer);
    clearIntervalBells();
    releaseWakeLock();
    ring.classList.remove('is-breathing', 'is-armed');
    document.body.classList.remove('sp-focus', 'is-armed', 'is-complete');
    if (mode === 'student' && audio) { audio.pause(); audio.currentTime = 0; }
    if (mode === 'student' && audio && !isNaN(audio.duration)) {
      durationSec = audio.duration;
    }
    remaining = durationSec;
    renderTime();
    setPhase('');
    setPillLabel('Begin');
    ring.setAttribute('aria-label', 'Begin meditation');
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

  // ── Controls ── the ring is the only control (the pill inside it is just
  // its visible label) — Begin / End early, no pause, no separate reset.
  ring.addEventListener('click', () => {
    if (running) {
      if (armed) {
        clearTimeout(armTimer);
        if (mode === 'master') endMasterEarly(); else endStudentEarly();
      } else {
        armEndEarly();
      }
      return;
    }
    goIdle();
    if (mode === 'master') startMaster(); else startStudent();
  });

  // Duration calibration marks (master) — same behaviour as the old preset
  // buttons, just renamed to match the dial-marking markup/classes. Each
  // number has a matching radial line (same data-min) in the calibration
  // SVG; both get their active class toggled together so the line stays
  // in sync with the number it points to.
  if (calibrationEl) {
    calibrationEl.querySelectorAll('.sp-calmark').forEach(btn => {
      btn.addEventListener('click', () => {
        if (running) return;
        calibrationEl.querySelectorAll('.sp-calmark').forEach(b => b.classList.remove('sp-calmark--active'));
        btn.classList.add('sp-calmark--active');
        if (calibrationLinesEl) {
          calibrationLinesEl.querySelectorAll('.sp-calibration-line').forEach(l => l.classList.remove('sp-calibration-line--active'));
          const line = calibrationLinesEl.querySelector('[data-min="' + btn.dataset.min + '"]');
          if (line) line.classList.add('sp-calibration-line--active');
        }
        durationSec = parseInt(btn.dataset.min, 10) * 60;
        remaining = durationSec;
        renderTime();
        document.body.classList.remove('is-complete');
        setPhase('');
      });
    });
  }

  // Guided session picker (student)
  if (select && audio) {
    const load = () => { audio.src = select.value; audio.load(); };
    select.addEventListener('change', load);
    load();
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
      if (calibrationEl) calibrationEl.hidden = mode !== 'master';
      if (guidedEl) guidedEl.hidden = mode !== 'student';

      // Disable begin in guided mode when no audio is configured.
      ring.disabled = (mode === 'student' && !window.STILLPOINT_HAS_AUDIO);

      if (mode === 'master') { durationSec = (parseInt((calibrationEl.querySelector('.sp-calmark--active') || {}).dataset?.min, 10) || 15) * 60; }
      goIdle();
    });
  });

  renderTime();
  renderStats();
});
