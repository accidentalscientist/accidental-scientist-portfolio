document.addEventListener('DOMContentLoaded', function () {
  const $ = id => document.getElementById(id);
  const get = id => { const el = $(id); return el ? JSON.parse(el.textContent) : null; };

  const regions = get('nem-regions-data');
  const order = get('nem-region-order');
  const groupMeta = get('nem-group-meta');
  const fuelMeta = get('nem-fuel-meta');
  const trend = get('nem-trend-data') || {};
  if (!regions || !order || !order.length) return;

  const CYCLE_MS = 6000;
  let cycleTimer = null;
  let trendChart = null;
  let currentIndex = Math.max(0, order.indexOf(window.NEM_DEFAULT_REGION || 'NEM'));

  const barsEl = $('nem-bars');
  const groupbarEl = $('nem-groupbar');
  const legendEl = $('nem-legend');
  const autoEl = $('nem-auto');
  const pills = Array.from(document.querySelectorAll('.nem-region'));

  const fmt = n => Math.round(n).toLocaleString();

  // ── Build static scaffolding once; we only animate values on switch ──
  // Grouped stacked bar segments + legend entries
  const groupSegments = {};
  const legendValues = {};
  groupMeta.forEach(g => {
    const seg = document.createElement('div');
    seg.className = 'nem-groupbar__seg';
    seg.style.backgroundColor = g.color;
    groupbarEl.appendChild(seg);
    groupSegments[g.key] = seg;

    const item = document.createElement('div');
    item.className = 'nem-legend__item';
    item.innerHTML = `
      <span class="nem-legend__swatch" style="background-color:${g.color}"></span>
      <span class="nem-legend__label">${g.label}</span>
      <span class="nem-legend__val">—</span>`;
    legendEl.appendChild(item);
    legendValues[g.key] = item.querySelector('.nem-legend__val');
  });

  // Detailed per-fuel rows (union of fuels that appear in any region)
  const fuelRows = {};
  fuelMeta.forEach(f => {
    const row = document.createElement('div');
    row.className = 'nem-bar';
    row.innerHTML = `
      <div class="nem-bar__label">
        <span class="nem-bar__icon">${f.icon}</span>
        <span class="nem-bar__name">${f.fuel}</span>
      </div>
      <div class="nem-bar__track">
        <div class="nem-bar__fill" style="background-color:${f.color}"></div>
      </div>
      <div class="nem-bar__value">
        <span class="nem-bar__pct">—</span>
        <span class="nem-bar__mw">—</span>
      </div>`;
    barsEl.appendChild(row);
    fuelRows[f.fuel] = {
      row,
      fill: row.querySelector('.nem-bar__fill'),
      pct: row.querySelector('.nem-bar__pct'),
      mw: row.querySelector('.nem-bar__mw'),
    };
  });

  function render(regionKey) {
    const r = regions[regionKey];
    if (!r) return;

    $('stat-region').textContent = regionKey;
    const rangeEl = $('nem-mix-range');
    if (rangeEl) rangeEl.textContent = r.range;
    $('stat-total').textContent = fmt(r.total_mw);
    $('stat-renew').textContent = r.renewable_pct + '%';
    $('stat-coal').textContent = r.coal_pct + '%';
    $('stat-gas').textContent = (r.groups.Gas ? r.groups.Gas.pct : 0) + '%';

    // Grouped bar + legend
    groupMeta.forEach(g => {
      const v = r.groups[g.key] || { mw: 0, pct: 0 };
      groupSegments[g.key].style.width = v.pct + '%';
      legendValues[g.key].textContent = v.pct + '%';
    });

    // Detailed fuel bars — widths morph smoothly between regions
    fuelMeta.forEach(f => {
      const cell = fuelRows[f.fuel];
      const v = r.fuels[f.fuel];
      if (v) {
        cell.row.classList.remove('nem-bar--empty');
        cell.fill.style.width = v.pct + '%';
        cell.pct.textContent = v.pct + '%';
        cell.mw.textContent = fmt(v.mw) + ' MW';
      } else {
        cell.row.classList.add('nem-bar--empty');
        cell.fill.style.width = '0%';
        cell.pct.textContent = '0%';
        cell.mw.textContent = '0 MW';
      }
    });

    pills.forEach(p => {
      const active = p.dataset.region === regionKey;
      p.classList.toggle('nem-region--active', active);
      p.setAttribute('aria-pressed', active ? 'true' : 'false');
    });

    updateTrend(regionKey);
  }

  // ── 3-month renewable vs fossil line chart ──
  function buildTrendChart(regionKey) {
    const ctx = $('nem-trend-chart');
    if (!ctx || typeof Chart === 'undefined') return;
    const t = trend[regionKey] || { labels: [], renewable: [], nonrenewable: [] };
    trendChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: t.labels,
        datasets: [
          { label: 'Renewables', data: t.renewable, borderColor: '#2e9e2e', backgroundColor: 'rgba(46,158,46,0.12)', borderWidth: 3.5, pointRadius: 0, tension: 0.35, fill: true },
          { label: 'Fossil fuels', data: t.nonrenewable, borderColor: '#d4342a', backgroundColor: 'rgba(212,52,42,0.12)', borderWidth: 3.5, pointRadius: 0, tension: 0.35, fill: true },
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top', labels: { boxWidth: 12, usePointStyle: true, font: { size: 12 } } },
          tooltip: { enabled: true }
        },
        scales: {
          x: { ticks: { maxTicksLimit: 8, autoSkip: true, font: { size: 11 } }, grid: { display: false } },
          y: { beginAtZero: true, ticks: { font: { size: 11 } }, grid: { color: 'rgba(26,46,26,0.06)' } }
        }
      }
    });
  }

  function updateTrend(regionKey) {
    if (!trendChart) return;
    const t = trend[regionKey];
    if (!t) return;
    trendChart.data.labels = t.labels;
    trendChart.data.datasets[0].data = t.renewable;
    trendChart.data.datasets[1].data = t.nonrenewable;
    trendChart.update();
  }

  function go(index) {
    currentIndex = (index + order.length) % order.length;
    render(order[currentIndex]);
  }

  function startCycle() {
    if (autoEl) autoEl.classList.add('nem-auto--on');
    clearInterval(cycleTimer);
    cycleTimer = setInterval(() => go(currentIndex + 1), CYCLE_MS);
  }

  function stopCycle() {
    if (autoEl) autoEl.classList.remove('nem-auto--on');
    clearInterval(cycleTimer);
  }

  // Clicking a region pins it and stops the auto-cycle.
  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      stopCycle();
      go(order.indexOf(pill.dataset.region));
    });
  });

  // Clicking / pressing the "Auto" indicator resumes cycling.
  if (autoEl) {
    autoEl.style.cursor = 'pointer';
    const resume = () => { go(currentIndex); startCycle(); };
    autoEl.addEventListener('click', resume);
    autoEl.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); resume(); }
    });
  }

  // First visit: build the trend chart, render the default region, then auto-cycle.
  buildTrendChart(order[currentIndex]);
  go(currentIndex);
  startCycle();
});
