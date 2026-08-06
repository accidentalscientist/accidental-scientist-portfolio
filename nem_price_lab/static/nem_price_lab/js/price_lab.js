/* NEM Price Predictor Lab
 *
 * Every region payload is rendered server-side, so switching regions is a
 * redraw rather than a request. The region selector mirrors the fuel-mix
 * dashboard: it opens on the market-wide view and cycles until you pin a
 * region, at which point cycling stops until you resume it.
 */
(function () {
  'use strict';

  var dataNode = document.getElementById('plab-data');
  var orderNode = document.getElementById('plab-region-order');
  if (!dataNode || !orderNode) { return; }

  var REGIONS = JSON.parse(dataNode.textContent);
  var ORDER = JSON.parse(orderNode.textContent);
  if (!ORDER.length) { return; }

  // Set server-side so the control can state its own speed and the page and
  // the template never disagree about it.
  var CYCLE_SECONDS = window.PLAB_CYCLE_SECONDS || 8;
  var CYCLE_MS = CYCLE_SECONDS * 1000;

  var currentIndex = Math.max(0, ORDER.indexOf(window.PLAB_DEFAULT_REGION || 'NEM'));
  var cycleTimer = null;
  var forecastChart = null;
  var historyChart = null;
  var betaChart = null;

  var autoEl = document.getElementById('plab-auto');
  var statusEl = document.getElementById('plab-cycle-status');
  // Scoped to the selector row. The per-chart indicators reuse the same
  // .nem-region styling, so an unscoped query would collect those too and
  // then strip their active class on every render, since they carry no
  // data-region of their own.
  var pills = Array.from(document.querySelectorAll('.plab-regions__pills .nem-region'));
  var toggles = Array.from(document.querySelectorAll('.plab-toggle__input'));

  // ── Formatting ──────────────────────────────────────────────────────
  function money(value) {
    if (value === null || value === undefined) { return '–'; }
    return '$' + value.toFixed(2);
  }

  function ink() {
    return getComputedStyle(document.body).getPropertyValue('--text-secondary').trim() || '#5a6e52';
  }

  function gridColor() {
    return getComputedStyle(document.body).getPropertyValue('--border-color').trim() || 'rgba(0,0,0,0.1)';
  }

  function setText(id, value) {
    var node = document.getElementById(id);
    if (node) { node.textContent = value; }
  }

  function enabledModels() {
    return toggles.filter(function (t) { return t.checked; }).map(function (t) { return t.value; });
  }

  // ── Per-chart region badges ─────────────────────────────────────────
  // The selector lives at the top of a long page. Once a reader has scrolled
  // to a chart they cannot see it, so every chart states its own region and
  // whether the page is cycling.
  var badgeNames = Array.from(document.querySelectorAll('[data-region-badge-name]'));
  var badgeAutos = Array.from(document.querySelectorAll('[data-region-badge-auto]'));

  function renderBadges(region) {
    var cycling = autoEl && autoEl.getAttribute('aria-pressed') === 'true';
    badgeNames.forEach(function (node) { node.textContent = region.short || ''; });
    badgeAutos.forEach(function (node) { node.hidden = !cycling; });
  }

  // ── The six models, side by side ────────────────────────────────────
  function renderLineup(region) {
    var grid = document.getElementById('plab-lineup');
    if (!grid) { return; }
    grid.innerHTML = '';

    (region.models || []).forEach(function (model) {
      var card = document.createElement('article');
      card.className = 'plab-card';
      if (model.is_best) { card.classList.add('plab-card--best'); }
      card.style.setProperty('--model-color', model.color);

      var head = document.createElement('div');
      head.className = 'plab-card__head';

      var family = document.createElement('span');
      family.className = 'plab-card__family';
      family.textContent = model.family;
      head.appendChild(family);

      if (model.is_best) {
        var flag = document.createElement('span');
        flag.className = 'plab-card__flag';
        flag.textContent = 'best here';
        head.appendChild(flag);
      } else if (model.is_baseline) {
        var base = document.createElement('span');
        base.className = 'plab-card__flag plab-card__flag--muted';
        base.textContent = 'baseline';
        head.appendChild(base);
      }
      card.appendChild(head);

      var name = document.createElement('h3');
      name.className = 'plab-card__name';
      name.textContent = model.label;
      card.appendChild(name);

      var desc = document.createElement('p');
      desc.className = 'plab-card__desc';
      desc.textContent = model.description;
      card.appendChild(desc);

      var facts = document.createElement('dl');
      facts.className = 'plab-card__facts';
      [['Inputs', model.inputs], ['Fitted', model.fitted]].forEach(function (pair) {
        var dt = document.createElement('dt');
        dt.textContent = pair[0];
        var dd = document.createElement('dd');
        dd.textContent = pair[1];
        facts.appendChild(dt);
        facts.appendChild(dd);
      });
      card.appendChild(facts);

      var score = document.createElement('div');
      score.className = 'plab-card__score';

      if (model.avg_mae === null || model.avg_mae === undefined) {
        var pending = document.createElement('p');
        pending.className = 'plab-card__pending';
        pending.textContent = model.needs_training
          ? 'Not yet scored here. Needs a completed week and an offline training run.'
          : 'Not yet scored here.';
        score.appendChild(pending);
      } else {
        score.appendChild(stat('Avg error', money(model.avg_mae)));

        var skillText, skillClass;
        if (model.is_baseline) {
          skillText = 'baseline';
          skillClass = 'plab-skill--flat';
        } else if (model.avg_skill === null) {
          skillText = '–';
          skillClass = 'plab-skill--flat';
        } else {
          // Sign character as well as colour: colour is never the only cue.
          skillText = (model.avg_skill > 0 ? '▲ +' : (model.avg_skill < 0 ? '▼ ' : ''))
            + model.avg_skill.toFixed(1) + '%';
          skillClass = model.avg_skill > 0 ? 'plab-skill--up'
            : (model.avg_skill < 0 ? 'plab-skill--down' : 'plab-skill--flat');
        }
        score.appendChild(stat('Skill', skillText, skillClass));
        score.appendChild(stat('Weeks', String(model.weeks)));
      }
      card.appendChild(score);

      grid.appendChild(card);
    });
  }

  function stat(label, value, valueClass) {
    var wrap = document.createElement('div');
    wrap.className = 'plab-card__stat';

    var l = document.createElement('span');
    l.className = 'plab-card__stat-label';
    l.textContent = label;

    var v = document.createElement('span');
    v.className = 'plab-card__stat-value' + (valueClass ? ' ' + valueClass : '');
    v.textContent = value;

    wrap.appendChild(l);
    wrap.appendChild(v);
    return wrap;
  }

  // ── Headline stats ──────────────────────────────────────────────────
  function renderStats(region) {
    setText('plab-region-label', region.short || '');
    setText('plab-latest', region.latest || 'no data');

    // The market-wide series is derived, not settled. Say so whenever it is on.
    var derived = document.getElementById('plab-derived');
    if (derived) { derived.hidden = !region.derived; }

    var stats = region.stats;
    if (!stats) {
      ['plab-avg', 'plab-low', 'plab-high', 'plab-negative'].forEach(function (id) {
        setText(id, '–');
      });
      return;
    }
    setText('plab-avg', money(stats.avg));
    setText('plab-low', money(stats.low));
    setText('plab-high', money(stats.high));
    setText('plab-negative', stats.negative_pct.toFixed(1) + '%');
  }

  // ── Forecast chart ──────────────────────────────────────────────────
  function renderForecast(region) {
    var canvas = document.getElementById('plab-forecast-chart');
    var note = document.getElementById('plab-forecast-note');
    if (!canvas) { return; }

    if (forecastChart) { forecastChart.destroy(); forecastChart = null; }

    var forecast = region.forecast;
    if (!forecast) {
      setText('plab-issued', 'no run published');
      if (note) {
        note.hidden = false;
        note.textContent = 'No forecast has been published for this region yet.';
      }
      return;
    }

    setText('plab-issued', 'Issued Sunday ' + forecast.issued_at);

    var shown = enabledModels();
    var visible = forecast.series.filter(function (s) { return shown.indexOf(s.key) !== -1; });

    // A run that fell back to observed temperature saw information it could
    // not have had. Say so in plain words rather than letting it pass.
    var fallback = visible.some(function (s) { return s.leakage_safe === false; });
    if (note) {
      if (fallback) {
        note.hidden = false;
        note.textContent = 'Caution: no archived temperature forecast was available for this '
          + 'window, so the temperature model used the temperature that actually occurred. '
          + 'Its score here is optimistic and is not a fair comparison.';
      } else if (!forecast.complete) {
        note.hidden = false;
        note.textContent = 'This week is still running: ' + forecast.settled_intervals + ' of '
          + forecast.total_intervals + ' intervals have settled so far.';
      } else {
        note.hidden = true;
        note.textContent = '';
      }
    }

    var datasets = [{
      label: 'Actual',
      data: forecast.actual,
      borderColor: forecast.actual_color,
      backgroundColor: forecast.actual_color,
      borderWidth: 2.5,
      pointRadius: 0,
      tension: 0.15,
      spanGaps: false,
      order: 0
    }];

    visible.forEach(function (series) {
      datasets.push({
        label: series.label,
        data: series.values,
        borderColor: series.color,
        backgroundColor: series.color,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.15,
        spanGaps: false,
        order: 1
      });
    });

    forecastChart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: { labels: forecast.labels, datasets: datasets },
      options: lineOptions('$/MWh', forecast.origin_index)
    });
  }

  function lineOptions(axisLabel, originIndex) {
    var options = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: { color: ink(), boxWidth: 12, usePointStyle: true, pointStyle: 'line' }
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              if (context.parsed.y === null) { return null; }
              return context.dataset.label + ': ' + money(context.parsed.y);
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: ink(), maxTicksLimit: 12, autoSkip: true },
          grid: { color: gridColor() }
        },
        y: {
          title: { display: true, text: axisLabel, color: ink() },
          ticks: { color: ink() },
          grid: { color: gridColor() }
        }
      }
    };

    if (typeof originIndex === 'number' && originIndex > 0) {
      options.plugins.annotationLine = { index: originIndex };
    }
    return options;
  }

  // Vertical marker at the forecast origin, drawn by hand so the page does
  // not need the chartjs annotation plugin for a single line.
  var originMarker = {
    id: 'plabOriginMarker',
    afterDatasetsDraw: function (chart) {
      var config = chart.options.plugins && chart.options.plugins.annotationLine;
      if (!config) { return; }
      var xScale = chart.scales.x;
      var area = chart.chartArea;
      if (!xScale || !area) { return; }

      var x = xScale.getPixelForValue(config.index);
      var ctx = chart.ctx;
      ctx.save();
      ctx.beginPath();
      ctx.setLineDash([4, 4]);
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = ink();
      ctx.moveTo(x, area.top);
      ctx.lineTo(x, area.bottom);
      ctx.stroke();

      ctx.setLineDash([]);
      ctx.font = '11px Inter, system-ui, sans-serif';
      ctx.fillStyle = ink();
      ctx.textAlign = 'left';
      ctx.fillText('forecast origin', x + 5, area.top + 12);
      ctx.restore();
    }
  };

  // ── Performance table ───────────────────────────────────────────────
  function skillCell(value, isBaseline) {
    var cell = document.createElement('td');
    if (isBaseline) {
      cell.textContent = 'baseline';
      cell.className = 'plab-skill--flat';
    } else if (value === null || value === undefined) {
      cell.textContent = '–';
      cell.className = 'plab-skill--flat';
    } else {
      // Sign character as well as colour: colour is never the only encoding.
      var sign = value > 0 ? '▲ +' : (value < 0 ? '▼ ' : '');
      cell.textContent = sign + value.toFixed(1) + '%';
      cell.className = value > 0 ? 'plab-skill--up'
        : (value < 0 ? 'plab-skill--down' : 'plab-skill--flat');
    }
    return cell;
  }

  function renderPerformance(region) {
    var table = document.getElementById('plab-review-table');
    if (!table) { return; }
    var body = table.querySelector('tbody');
    body.innerHTML = '';

    var performance = region.performance;
    if (!performance || !performance.rows.length) {
      setText('plab-review-window', 'not yet scored');
      var empty = document.createElement('tr');
      var cell = document.createElement('td');
      cell.colSpan = 8;
      cell.className = 'plab-table__muted';
      cell.textContent = 'No week has fully settled since the first forecast was published. '
        + 'Scores appear here once a complete Sunday-to-Sunday week of actuals exists.';
      empty.appendChild(cell);
      body.appendChild(empty);
      return;
    }

    setText('plab-review-window',
      performance.weeks + (performance.weeks === 1 ? ' week' : ' weeks')
      + ' since ' + performance.average_since);

    performance.rows.forEach(function (row) {
      var tr = document.createElement('tr');

      var nameCell = document.createElement('td');
      var wrap = document.createElement('span');
      wrap.className = 'plab-table__model';
      var swatch = document.createElement('span');
      swatch.className = 'plab-swatch';
      swatch.style.setProperty('--swatch', row.color);
      wrap.appendChild(swatch);
      wrap.appendChild(document.createTextNode(row.label));
      nameCell.appendChild(wrap);

      if (row.is_baseline) {
        var tag = document.createElement('span');
        tag.className = 'plab-baseline-tag';
        tag.textContent = 'baseline';
        nameCell.appendChild(tag);
      }
      if (row.leakage_safe === false) {
        var warn = document.createElement('span');
        warn.className = 'plab-baseline-tag';
        warn.textContent = 'optimistic';
        nameCell.appendChild(warn);
      }
      tr.appendChild(nameCell);

      [money(row.last_mae), money(row.last_medae)].forEach(function (value) {
        var cell = document.createElement('td');
        cell.textContent = value;
        tr.appendChild(cell);
      });
      tr.appendChild(skillCell(row.last_skill, row.is_baseline));

      [money(row.avg_mae), money(row.avg_medae)].forEach(function (value) {
        var cell = document.createElement('td');
        cell.className = 'plab-td-avg';
        cell.textContent = value;
        tr.appendChild(cell);
      });
      var avgSkill = skillCell(row.avg_skill, row.is_baseline);
      avgSkill.className += ' plab-td-avg';
      tr.appendChild(avgSkill);

      var worst = document.createElement('td');
      worst.textContent = money(row.worst_ever);
      tr.appendChild(worst);

      body.appendChild(tr);
    });
  }

  // ── Coefficients: chart and table ───────────────────────────────────
  function renderBetas(region) {
    var table = document.getElementById('plab-beta-table');
    var canvas = document.getElementById('plab-beta-chart');
    if (betaChart) { betaChart.destroy(); betaChart = null; }
    if (!table) { return; }

    var body = table.querySelector('tbody');
    body.innerHTML = '';

    var betas = region.betas;
    if (!betas || !betas.rows.length) {
      var empty = document.createElement('tr');
      var cell = document.createElement('td');
      cell.colSpan = 6;
      cell.className = 'plab-table__muted';
      cell.textContent = 'No coefficients fitted yet. They appear once price and temperature '
        + 'history are both loaded and a run has been published.';
      empty.appendChild(cell);
      body.appendChild(empty);
      return;
    }

    if (canvas && betas.chart) {
      betaChart = new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
          labels: betas.chart.labels,
          datasets: [
            {
              label: 'Cooling ($/MWh per °C above 18)',
              data: betas.chart.cooling,
              backgroundColor: betas.chart.cooling_color,
              borderColor: betas.chart.cooling_color
            },
            {
              label: 'Heating ($/MWh per °C below 18)',
              data: betas.chart.heating,
              backgroundColor: betas.chart.heating_color,
              borderColor: betas.chart.heating_color
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: ink(), boxWidth: 12 } },
            tooltip: {
              callbacks: {
                label: function (context) {
                  return context.dataset.label + ': ' + money(context.parsed.y);
                }
              }
            }
          },
          scales: {
            x: { ticks: { color: ink() }, grid: { display: false } },
            y: {
              title: { display: true, text: '$/MWh per °C', color: ink() },
              ticks: { color: ink() },
              grid: { color: gridColor() }
            }
          }
        }
      });
    }

    function coefficientCell(value, fitted) {
      var cell = document.createElement('td');
      if (!fitted || value === null || value === undefined) {
        cell.textContent = 'not fitted';
        cell.className = 'plab-table__muted';
      } else {
        cell.textContent = (value > 0 ? '+' : '') + value.toFixed(2);
      }
      return cell;
    }

    betas.rows.forEach(function (row) {
      var tr = document.createElement('tr');

      var band = document.createElement('td');
      band.textContent = row.label;
      tr.appendChild(band);

      var hours = document.createElement('td');
      hours.textContent = row.hours;
      tr.appendChild(hours);

      tr.appendChild(coefficientCell(row.cooling, row.fitted));
      tr.appendChild(coefficientCell(row.heating, row.fitted));

      var used = document.createElement('td');
      used.textContent = row.fitted ? row.used.toLocaleString() : (row.reason || '–');
      if (!row.fitted) { used.className = 'plab-table__muted'; }
      tr.appendChild(used);

      var note = document.createElement('td');
      note.className = 'plab-table__muted';
      note.textContent = row.note;
      tr.appendChild(note);

      body.appendChild(tr);
    });
  }

  // ── History chart ───────────────────────────────────────────────────
  function renderHistory(region) {
    var canvas = document.getElementById('plab-history-chart');
    if (!canvas) { return; }
    if (historyChart) { historyChart.destroy(); historyChart = null; }

    var history = region.history;
    if (!history || !history.labels.length) { return; }

    historyChart = new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels: history.labels,
        datasets: [
          {
            label: 'Daily high',
            data: history.high,
            borderColor: 'rgba(184, 74, 26, 0.35)',
            backgroundColor: 'rgba(184, 74, 26, 0.10)',
            borderWidth: 1,
            pointRadius: 0,
            fill: '+2',
            tension: 0.2
          },
          {
            label: 'Daily average',
            data: history.avg,
            borderColor: '#2d6a2d',
            backgroundColor: '#2d6a2d',
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.2
          },
          {
            label: 'Daily low',
            data: history.low,
            borderColor: 'rgba(63, 125, 166, 0.35)',
            backgroundColor: 'rgba(63, 125, 166, 0.10)',
            borderWidth: 1,
            pointRadius: 0,
            tension: 0.2
          }
        ]
      },
      options: lineOptions('$/MWh')
    });
  }

  // ── Region switching and cycling ────────────────────────────────────
  function render() {
    var region = REGIONS[ORDER[currentIndex]];
    if (!region) { return; }

    renderBadges(region);
    renderStats(region);
    renderForecast(region);
    renderLineup(region);
    renderPerformance(region);
    renderBetas(region);
    renderHistory(region);

    pills.forEach(function (pill) {
      var active = pill.dataset.region === ORDER[currentIndex];
      pill.classList.toggle('nem-region--active', active);
      pill.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function go(index) {
    currentIndex = (index + ORDER.length) % ORDER.length;
    render();
    announce(REGIONS[ORDER[currentIndex]] || {});
  }

  function startCycle() {
    if (autoEl) { autoEl.classList.add('nem-auto--on'); }
    setAutoState(true);
    clearInterval(cycleTimer);
    cycleTimer = setInterval(function () { go(currentIndex + 1); }, CYCLE_MS);
  }

  function stopCycle() {
    if (autoEl) { autoEl.classList.remove('nem-auto--on'); }
    setAutoState(false);
    clearInterval(cycleTimer);
  }

  // Clicking a region pins it and stops the cycle.
  pills.forEach(function (pill) {
    pill.addEventListener('click', function () {
      stopCycle();
      go(ORDER.indexOf(pill.dataset.region));
    });
  });

  // Auto is a toggle: click while cycling to stop, click again to resume.
  // Its state propagates to every chart's indicator, so turning the cycle off
  // is visible wherever the reader happens to be on the page.
  function setAutoState(on) {
    if (!autoEl) { return; }
    autoEl.setAttribute('aria-pressed', on ? 'true' : 'false');
    autoEl.title = on
      ? 'Cycling through all ' + ORDER.length + ' regions every ' + CYCLE_SECONDS
        + ' seconds. Click to stop on the current region.'
      : 'Paused on one region. Click to cycle through all ' + ORDER.length + '.';
    badgeAutos.forEach(function (node) { node.hidden = !on; });
  }

  function announce(region) {
    if (!statusEl) { return; }
    statusEl.textContent = autoEl && autoEl.getAttribute('aria-pressed') === 'true'
      ? 'Now showing ' + (region.label || '') + '. Cycling automatically.'
      : '';
  }

  if (autoEl) {
    var toggleAuto = function () {
      if (autoEl.classList.contains('nem-auto--on')) {
        stopCycle();
      } else {
        go(currentIndex);
        startCycle();
      }
    };
    autoEl.addEventListener('click', toggleAuto);
  }

  // Toggling a model only redraws the forecast chart; nothing else changes.
  toggles.forEach(function (toggle) {
    toggle.addEventListener('change', function () {
      renderForecast(REGIONS[ORDER[currentIndex]]);
    });
  });

  if (window.Chart) { Chart.register(originMarker); }

  render();
  if (window.PLAB_AUTO_CYCLE) { startCycle(); }
}());
