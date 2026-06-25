document.addEventListener('DOMContentLoaded', function () {
  const $ = id => document.getElementById(id);

  const ring = $('sp-ring');
  const progress = $('sp-progress');
  const timeEl = $('sp-time');
  const phaseEl = $('sp-phase');
  const beginBtn = $('sp-begin');
  const resetBtn = $('sp-reset');
  const durationsEl = $('sp-durations');
  const guidedEl = $('sp-guided');
  const select = $('sp-audio-select');
  const audio = $('sp-audio');

  const R = 110;
  const CIRC = 2 * Math.PI * R;
  progress.style.strokeDasharray = CIRC;

  let mode = 'master';
  let durationSec = 15 * 60;
  let remaining = durationSec;
  let running = false;
  let endAt = 0;
  let rafId = null;

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
        const vol = i === 0 ? 0.35 : 0.12;
        gain.gain.setValueAtTime(0.0001, now);
        gain.gain.exponentialRampToValueAtTime(vol, now + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 3.5);
        osc.start(now);
        osc.stop(now + 3.6);
      });
    } catch (e) { /* audio not available — stay silent */ }
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
  }
  function pauseMaster() {
    running = false;
    cancelAnimationFrame(rafId);
    remaining = (endAt - Date.now()) / 1000;
    ring.classList.remove('is-breathing');
    phaseEl.textContent = 'Paused';
    setBeginLabel('Resume');
  }
  function finish() {
    running = false;
    cancelAnimationFrame(rafId);
    ring.classList.remove('is-breathing');
    chime();
    phaseEl.textContent = 'Complete';
    setBeginLabel('Begin');
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
  }
  function pauseStudent() {
    running = false;
    audio.pause();
    ring.classList.remove('is-breathing');
    phaseEl.textContent = 'Paused';
    setBeginLabel('Resume');
  }
  function finishStudent() {
    running = false;
    ring.classList.remove('is-breathing');
    chime();
    phaseEl.textContent = 'Complete';
    setBeginLabel('Begin');
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
      if (guidedEl) guidedEl.hidden = mode !== 'student';

      // Disable begin in guided mode when no audio is configured.
      beginBtn.disabled = (mode === 'student' && !window.STILLPOINT_HAS_AUDIO);

      if (mode === 'master') { durationSec = (parseInt((durationsEl.querySelector('.sp-duration--active') || {}).dataset?.min, 10) || 15) * 60; }
      reset();
    });
  });

  renderTime();
});
