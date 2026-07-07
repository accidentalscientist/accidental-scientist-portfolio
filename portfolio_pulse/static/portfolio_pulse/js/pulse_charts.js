document.addEventListener('DOMContentLoaded', function () {
  const get = id => { const el = document.getElementById(id); return el ? JSON.parse(el.textContent) : null; };
  if (typeof Chart === 'undefined') return;

  const BAND_COLORS = { Critical: '#c0392b', 'At-risk': '#d4772a', Healthy: '#2d6a2d' };
  const gridColor = 'rgba(26,46,26,0.06)';
  const money = v => '$' + Math.round(v).toLocaleString();

  // Animation is switched off globally rather than hooked to onComplete —
  // it removes the render-race with PDF export entirely and satisfies the
  // reduced-motion quality bar in one move.
  const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: { labels: { boxWidth: 12, usePointStyle: true, font: { size: 12 } } } },
  };

  // ── 1. Revenue tiers — Gold / Silver / Bronze by ARR rank ──
  const tiersData = get('pulse-data-concentration');
  const tiersCanvas = document.getElementById('pulse-chart-concentration');
  const TIER_COLORS = { Gold: '#c9962b', Silver: '#8a9e82', Bronze: '#b0703a' };
  if (tiersData && tiersCanvas) {
    const tiers = tiersData.tiers;
    new Chart(tiersCanvas, {
      type: 'bar',
      data: {
        labels: tiers.map(t => t.tier),
        datasets: [{ label: 'ARR', data: tiers.map(t => t.arr), backgroundColor: tiers.map(t => TIER_COLORS[t.tier]) }],
      },
      options: {
        ...baseOptions,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            label: ctx => `${money(ctx.parsed.y)} · ${tiers[ctx.dataIndex].pct_of_total}% of book · ${tiers[ctx.dataIndex].count} accounts`,
            afterLabel: ctx => tiers[ctx.dataIndex].top_accounts.length ? 'Top: ' + tiers[ctx.dataIndex].top_accounts.join(', ') : '',
          } },
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, ticks: { callback: money }, grid: { color: gridColor } },
        },
      },
    });
  }

  // ── 2a/2b. Revenue vs. risk, and revenue vs. health (bubble, side by side) ──
  function buildRevenueBubble(canvasId, dataId, xField, bandField, xLabel) {
    const rows = get(dataId);
    const canvas = document.getElementById(canvasId);
    if (!rows || !canvas || !rows.length) return;
    const maxHistoric = Math.max(1, ...rows.map(a => a.historic_value));
    const byBand = {};
    rows.forEach(a => {
      (byBand[a[bandField]] = byBand[a[bandField]] || []).push({
        x: a[xField], y: a.current_arr, r: 4 + (a.historic_value / maxHistoric) * 22, name: a.name,
      });
    });
    new Chart(canvas, {
      type: 'bubble',
      data: { datasets: Object.keys(byBand).map(band => ({
        label: band, data: byBand[band], backgroundColor: (BAND_COLORS[band] || '#999') + 'b3', borderColor: BAND_COLORS[band] || '#999',
      })) },
      options: {
        ...baseOptions,
        plugins: { ...baseOptions.plugins, tooltip: { callbacks: { label: ctx => `${ctx.raw.name}: ${xLabel.toLowerCase()} ${ctx.raw.x}, ${money(ctx.raw.y)}` } } },
        scales: {
          x: { min: 0, max: 100, title: { display: true, text: xLabel }, grid: { color: gridColor } },
          y: { beginAtZero: true, title: { display: true, text: 'Current ARR' }, grid: { color: gridColor }, ticks: { callback: money } },
        },
      },
    });
  }
  buildRevenueBubble('pulse-chart-revenue-risk', 'pulse-data-revenue-risk', 'risk_score', 'risk_band', 'Risk score');
  buildRevenueBubble('pulse-chart-revenue-health', 'pulse-data-revenue-health', 'score', 'band', 'Health score');

  // ── 3. Renewal wall (stacked $, by health band) ──
  const renewalWall = get('pulse-data-renewal-wall');
  const renewalWallCanvas = document.getElementById('pulse-chart-renewal-wall');
  if (renewalWall && renewalWallCanvas) {
    new Chart(renewalWallCanvas, {
      type: 'bar',
      data: { labels: renewalWall.labels, datasets: Object.keys(renewalWall.series).map(band => ({
        label: band, data: renewalWall.series[band], backgroundColor: BAND_COLORS[band] || '#999',
      })) },
      options: { ...baseOptions,
        scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, beginAtZero: true, ticks: { callback: money }, grid: { color: gridColor } } } },
    });
  }

  // ── 4. Industry breakdown ──
  const industry = get('pulse-data-industry');
  const industryCanvas = document.getElementById('pulse-chart-industry');
  if (industry && industryCanvas) {
    new Chart(industryCanvas, {
      type: 'bar',
      data: { labels: industry.map(r => r.industry), datasets: [{
        label: 'ARR', data: industry.map(r => r.arr), backgroundColor: industry.map(r => BAND_COLORS[r.band] || '#999'),
      }] },
      options: {
        ...baseOptions,
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: { label: ctx => `${money(ctx.parsed.y)} · avg health ${industry[ctx.dataIndex].avg_health} · ${industry[ctx.dataIndex].account_count} accounts` } },
        },
        scales: {
          x: { ticks: { autoSkip: false, maxRotation: 60, minRotation: 30, font: { size: 10 } }, grid: { display: false } },
          y: { beginAtZero: true, ticks: { callback: money }, grid: { color: gridColor } },
        },
      },
    });
  }

  // ── 5. Coverage & engagement ──
  const coverage = get('pulse-data-coverage');
  const coverageCanvas = document.getElementById('pulse-chart-coverage');
  if (coverage && coverageCanvas && coverage.length) {
    const byBand = {};
    coverage.forEach(a => (byBand[a.band] = byBand[a.band] || []).push({ x: a.days_since_contact, y: a.current_arr, name: a.name }));
    new Chart(coverageCanvas, {
      type: 'scatter',
      data: { datasets: Object.keys(byBand).map(band => ({
        label: band, data: byBand[band], backgroundColor: (BAND_COLORS[band] || '#999') + 'cc', pointRadius: 5,
      })) },
      options: {
        ...baseOptions,
        plugins: { ...baseOptions.plugins, tooltip: { callbacks: { label: ctx => `${ctx.raw.name}: ${ctx.raw.x}d, ${money(ctx.raw.y)}` } } },
        scales: {
          x: { title: { display: true, text: 'Days since contact' }, grid: { color: gridColor } },
          y: { beginAtZero: true, title: { display: true, text: 'Current ARR' }, ticks: { callback: money }, grid: { color: gridColor } },
        },
      },
    });
  }

  // ── 6. Momentum / spend trajectory (diverging) ──
  const momentum = get('pulse-data-momentum');
  const momentumCanvas = document.getElementById('pulse-chart-momentum');
  if (momentum && momentumCanvas) {
    new Chart(momentumCanvas, {
      type: 'bar',
      data: { labels: momentum.map(a => a.name), datasets: [{
        label: 'Momentum vs. lifetime avg', data: momentum.map(a => a.deviation_pct),
        backgroundColor: momentum.map(a => (a.deviation_pct >= 0 ? '#5a9e5a' : '#c0392b')),
      }] },
      options: {
        ...baseOptions,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { autoSkip: false, maxRotation: 60, minRotation: 30, font: { size: 10 } }, grid: { display: false } },
          y: { title: { display: true, text: '% vs. lifetime average' }, ticks: { callback: v => v + '%' }, grid: { color: gridColor } },
        },
      },
    });
  }

  // ── 7. ARR bridge (floating-bar waterfall) ──
  const bridge = get('pulse-data-arr-bridge');
  const bridgeCanvas = document.getElementById('pulse-chart-arr-bridge');
  if (bridge && bridgeCanvas) {
    let running = bridge.start;
    const steps = [
      { label: 'Start', base: 0, value: bridge.start, color: '#8a9e82' },
      { label: 'Expansion', base: running, value: bridge.expansion, color: '#5a9e5a' },
    ];
    running += bridge.expansion;
    steps.push({ label: 'Contraction', base: running - bridge.contraction, value: bridge.contraction, color: '#d4772a' });
    running -= bridge.contraction;
    steps.push({ label: 'Churn', base: running - bridge.churn, value: bridge.churn, color: '#c0392b' });
    running -= bridge.churn;
    steps.push({ label: 'End', base: 0, value: bridge.end, color: '#8a9e82' });

    new Chart(bridgeCanvas, {
      type: 'bar',
      data: {
        labels: steps.map(s => s.label),
        datasets: [{ data: steps.map(s => [s.base, s.base + s.value]), backgroundColor: steps.map(s => s.color) }],
      },
      options: {
        ...baseOptions,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => money(steps[ctx.dataIndex].value) } } },
        scales: { x: { grid: { display: false } }, y: { beginAtZero: true, ticks: { callback: money }, grid: { color: gridColor } } },
      },
    });
  }

  // ── 8. Portfolio health & NRR trend (dual line) ──
  const healthNrr = get('pulse-data-health-nrr');
  const healthNrrCanvas = document.getElementById('pulse-chart-health-nrr');
  if (healthNrr && healthNrrCanvas) {
    const nrrByLabel = {};
    healthNrr.nrr_labels.forEach((label, i) => { nrrByLabel[label] = healthNrr.nrr[i]; });
    const nrrAligned = healthNrr.health_labels.map(label => (label in nrrByLabel ? nrrByLabel[label] : null));

    new Chart(healthNrrCanvas, {
      data: {
        labels: healthNrr.health_labels,
        datasets: [
          { type: 'line', label: 'Health', data: healthNrr.health, borderColor: '#2d6a2d', backgroundColor: 'rgba(45,106,45,0.1)',
            borderWidth: 2.5, pointRadius: 0, tension: 0.3, yAxisID: 'y' },
          { type: 'line', label: 'NRR %', data: nrrAligned, borderColor: '#b84a1a', backgroundColor: 'rgba(184,74,26,0.1)',
            borderWidth: 2.5, pointRadius: 0, tension: 0.3, yAxisID: 'y1', spanGaps: true },
        ],
      },
      options: {
        ...baseOptions,
        interaction: { mode: 'index', intersect: false },
        scales: {
          x: { ticks: { maxTicksLimit: 10, autoSkip: true, font: { size: 10 } }, grid: { display: false } },
          y: { position: 'left', min: 0, max: 100, title: { display: true, text: 'Health' }, grid: { color: gridColor } },
          y1: { position: 'right', title: { display: true, text: 'NRR %' }, grid: { display: false } },
        },
      },
    });
  }

  // ── 9. Usage vs. revenue divergence ──
  const divergence = get('pulse-data-divergence');
  const divergenceCanvas = document.getElementById('pulse-chart-divergence');
  if (divergence && divergenceCanvas && divergence.length) {
    const danger = { id: 'dangerQuadrant', beforeDraw(chart) {
      const { ctx, chartArea, scales } = chart;
      const xZero = scales.x.getPixelForValue(0);
      const yZero = scales.y.getPixelForValue(0);
      ctx.save();
      ctx.fillStyle = 'rgba(192,57,43,0.06)';
      ctx.fillRect(xZero, chartArea.top, chartArea.right - xZero, yZero - chartArea.top);
      ctx.restore();
    } };
    const normal = divergence.filter(a => !a.silent_decliner).map(a => ({ x: a.mrr_trend, y: a.usage_trend, name: a.name }));
    const flagged = divergence.filter(a => a.silent_decliner).map(a => ({ x: a.mrr_trend, y: a.usage_trend, name: a.name }));

    new Chart(divergenceCanvas, {
      type: 'scatter',
      data: {
        datasets: [
          { label: 'Accounts', data: normal, backgroundColor: 'rgba(90,158,90,0.6)', pointRadius: 5 },
          { label: 'Silent decliners', data: flagged, backgroundColor: '#c0392b', pointRadius: 8, pointStyle: 'triangle' },
        ],
      },
      options: {
        ...baseOptions,
        plugins: { ...baseOptions.plugins, tooltip: { callbacks: { label: ctx => `${ctx.raw.name}: MRR ${ctx.raw.x}%, usage ${ctx.raw.y}%` } } },
        scales: {
          x: { title: { display: true, text: 'MRR trend %' }, grid: { color: gridColor } },
          y: { title: { display: true, text: 'Utilisation trend %' }, grid: { color: gridColor } },
        },
      },
      plugins: [danger],
    });
  }

  // ── 10. Revenue by group over time (stacked area, toggle segment/industry) ──
  const revenueGroup = get('pulse-data-revenue-group');
  const revenueGroupCanvas = document.getElementById('pulse-chart-revenue-group');
  let revenueGroupChart = null;
  const groupPalette = ['#2d6a2d', '#b84a1a', '#5a9e5a', '#8e7cc3', '#d4772a', '#3f7da6', '#c0392b', '#9a9488'];

  function buildRevenueGroupChart(key) {
    if (!revenueGroup || !revenueGroupCanvas) return;
    const series = revenueGroup[key];
    const datasets = Object.keys(series).map((group, i) => ({
      label: group, data: series[group], borderColor: groupPalette[i % groupPalette.length],
      backgroundColor: groupPalette[i % groupPalette.length] + '55', fill: true, tension: 0.25, pointRadius: 0,
    }));
    if (revenueGroupChart) revenueGroupChart.destroy();
    revenueGroupChart = new Chart(revenueGroupCanvas, {
      type: 'line',
      data: { labels: revenueGroup.labels, datasets },
      options: { ...baseOptions,
        scales: { x: { ticks: { maxTicksLimit: 10, autoSkip: true, font: { size: 10 } }, grid: { display: false } },
          y: { stacked: true, beginAtZero: true, ticks: { callback: money }, grid: { color: gridColor } } } },
    });
  }
  buildRevenueGroupChart('by_segment');

  document.querySelectorAll('.pulse-group-toggle__btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.pulse-group-toggle__btn').forEach(b => b.classList.remove('is-active'));
      btn.classList.add('is-active');
      buildRevenueGroupChart(btn.dataset.group);
    });
  });
});
