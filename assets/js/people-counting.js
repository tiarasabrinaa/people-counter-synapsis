/**
 * Main Dashboard Logic for People Counting System (FIXED ENDPOINTS)
 */

const API_BASE = 'http://localhost:8000';

const UPDATE_INTERVAL = 2000;          // 2s
const CHART_UPDATE_INTERVAL = 30000;   // 30s
const TZ = 'Asia/Jakarta';

// ---------- Helpers ----------
function ensureUTCString(ts) {
  if (typeof ts !== 'string') return ts;
  if (ts.endsWith('Z')) return ts;
  if (/[+-]\d{2}:\d{2}$/.test(ts)) return ts;
  return ts + 'Z';
}
function formatUTCToLocal(ts, opts = {}) {
  const z = ensureUTCString(ts);
  const d = new Date(z);
  return d.toLocaleString('id-ID', {
    hour12: false,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: TZ,
    ...opts
  });
}
function formatUTCToLocalTime(ts) {
  const z = ensureUTCString(ts);
  const d = new Date(z);
  return d.toLocaleTimeString('id-ID', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: TZ
  });
}

// ---------- Boot ----------
document.addEventListener('DOMContentLoaded', () => {
  console.log('Initializing People Counting Dashboard...');

  // Live & tabel
  loadLiveStats();
  loadRecentDetections();
  loadRecentEvents();

  // Timeseries per menit (60 bucket)
  loadHourlyStats();

  // Ringkasan 24 jam (INI YANG BENERIN “0 SEMUA”)
  loadSummaryStats();

  setTimeout(loadPolygon, 1000);

  // intervals
  setInterval(loadLiveStats, UPDATE_INTERVAL);
  setInterval(loadRecentDetections, UPDATE_INTERVAL);
  setInterval(loadRecentEvents, UPDATE_INTERVAL);
  setInterval(loadHourlyStats, CHART_UPDATE_INTERVAL);
  setInterval(loadSummaryStats, CHART_UPDATE_INTERVAL);
  setInterval(updateTimestamp, 1000);

  const forecastBtn = document.getElementById('btn-forecast');
  if (forecastBtn) forecastBtn.addEventListener('click', generateForecast);

  const refreshBtn = document.getElementById('btn-refresh');
  if (refreshBtn) refreshBtn.addEventListener('click', () => {
    loadRecentDetections();
    loadRecentEvents();
  });

  console.log('Dashboard initialized successfully');
});

// ---------- Live Stats ----------
async function loadLiveStats() {
  try {
    const response = await fetch(`${API_BASE}/api/stats/live`);
    if (!response.ok) throw new Error('Failed to fetch live stats');
    const data = await response.json();

    document.getElementById('current-count').textContent = data.current_count ?? 0;
    document.getElementById('recent-entries').textContent = data.recent_entries ?? 0;
    document.getElementById('recent-exits').textContent = data.recent_exits ?? 0;

    const activeTracks = Array.isArray(data.active_track_ids)
      ? data.active_track_ids.length
      : (data.active_tracks ?? 0);
    document.getElementById('active-tracks').textContent = activeTracks;

    const bboxCount = document.getElementById('bbox-count');
    if (bboxCount) bboxCount.textContent = `Detected: ${activeTracks} objects`;

    const statusEl = document.getElementById('api-status');
    if (statusEl) {
      statusEl.className = 'badge badge-sm bg-gradient-success ms-3';
      statusEl.textContent = 'Connected';
    }
  } catch (error) {
    console.error('Error loading live stats:', error);
    const statusEl = document.getElementById('api-status');
    if (statusEl) {
      statusEl.className = 'badge badge-sm bg-gradient-danger ms-3';
      statusEl.textContent = 'Disconnected';
    }
  }
}

// ---------- Minute Chart (60 buckets) ----------
async function loadHourlyStats() {
  try {
    const response = await fetch(`${API_BASE}/api/stats/?granularity=minute&minutes=60`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    console.log('✅ Raw time buckets:', data.hourly_data);

    // tampilkan summary 60 menit terakhir di header chart (opsional)
    const e60 = data?.summary?.entry_count ?? 0;
    const x60 = data?.summary?.exit_count  ?? 0;
    const elEntry = document.getElementById('total-entry');
    const elExit  = document.getElementById('total-exit');
    if (elEntry) elEntry.textContent = e60;
    if (elExit)  elExit.textContent  = x60;

    const buckets = data.hourly_data || [];
    if (buckets.length === 0) {
      console.warn('⚠️ No time-bucket data found');
      const ctx = document.getElementById('hourlyChart');
      if (ctx && window.hourlyChart instanceof Chart) {
        window.hourlyChart.destroy();
        window.hourlyChart = null;
      }
      return;
    }

    buckets.sort((a, b) => new Date(ensureUTCString(a.hour)) - new Date(ensureUTCString(b.hour)));
    const last60 = buckets.slice(-60);

    const labels = last60.map(d => {
      const z = ensureUTCString(d.hour);
      const date = new Date(z);
      return date.toLocaleTimeString('id-ID', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: TZ
      });
    });

    const entries = last60.map(d => d.entry_count);
    const exits = last60.map(d => d.exit_count);

    const ctx = document.getElementById('hourlyChart');
    if (!ctx) {
      console.error('❌ hourlyChart canvas not found');
      return;
    }

    if (window.hourlyChart instanceof Chart) {
      window.hourlyChart.destroy();
    }

    window.hourlyChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Entry',
            data: entries,
            borderColor: 'rgba(34,197,94,1)',
            backgroundColor: 'rgba(34,197,94,0.2)',
            tension: 0.4,
            fill: true,
            pointRadius: 4
          },
          {
            label: 'Exit',
            data: exits,
            borderColor: 'rgba(239,68,68,1)',
            backgroundColor: 'rgba(239,68,68,0.2)',
            tension: 0.4,
            fill: true,
            pointRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { labels: { color: '#fff' } } },
        scales: {
          x: { ticks: { color: '#ccc' }, grid: { color: 'rgba(255,255,255,0.1)' } },
          y: { beginAtZero: true, ticks: { color: '#ccc', precision: 0 }, grid: { color: 'rgba(255,255,255,0.1)' } }
        }
      }
    });

    console.log('✅ Minute chart updated!');
  } catch (err) {
    console.error('Error loading time-bucket stats:', err);
  }
}

// ---------- Summary 24h (FIX 0 semua) ----------
async function loadSummaryStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats/?hours=24&include_hourly=false`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    // Ringkasan 24 jam
    const entry = data?.summary?.entry_count ?? 0;
    const exit  = data?.summary?.exit_count  ?? 0;
    const net   = data?.summary?.net_count   ?? 0;

    // Header kecil di kartu chart (boleh pakai total 24h biar konsisten)
    const elEntryHdr = document.getElementById('total-entry');
    const elExitHdr  = document.getElementById('total-exit');
    if (elEntryHdr) elEntryHdr.textContent = entry;
    if (elExitHdr)  elExitHdr.textContent  = exit;

    // Kartu bawah
    const totDet = document.getElementById('total-detections');
    const totNet = document.getElementById('total-net');
    const uniq   = document.getElementById('unique-tracks');

    if (totDet) totDet.textContent = data?.total_detections ?? 0;
    if (totNet) totNet.textContent = net;
    if (uniq)   uniq.textContent   = data?.unique_tracks ?? 0;

  } catch (e) {
    console.error('Error loading summary stats:', e);
  }
}

// ---------- Recent Detections ----------
async function loadRecentDetections() {
  try {
    const response = await fetch(`${API_BASE}/api/stats/detections?limit=50`);
    if (!response.ok) throw new Error('Failed to fetch detections');
    const data = await response.json();
    const tbody = document.getElementById('detections-tbody');

    if (!data || data.length === 0) {
      if (tbody) tbody.innerHTML = '<tr><td colspan="4" class="text-center text-sm">No detections yet</td></tr>';
      // ❌ JANGAN overwrite unique-tracks dari sini (biar konsisten 24 jam)
      return;
    }

    let html = '';
    data.slice(0, 20).forEach(detection => {
      const time = formatUTCToLocalTime(detection.timestamp);
      const statusClass = detection.in_polygon ? 'bg-gradient-danger' : 'bg-gradient-secondary';
      const statusText = detection.in_polygon ? 'INSIDE' : 'OUTSIDE';
      const conf = (detection.confidence * 100).toFixed(1) + '%';

      html += `
        <tr>
          <td class="text-sm font-weight-bold">#${detection.track_id}</td>
          <td class="text-sm">${time}</td>
          <td><span class="badge badge-sm ${statusClass}">${statusText}</span></td>
          <td class="text-sm">${conf}</td>
        </tr>
      `;
    });

    if (tbody) tbody.innerHTML = html;
  } catch (error) {
    console.error('Error loading detections:', error);
    const tbody = document.getElementById('detections-tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="4" class="text-center text-sm text-danger">Failed to load</td></tr>';
  }
}

// ---------- Recent Events ----------
async function loadRecentEvents() {
  try {
    const response = await fetch(`${API_BASE}/api/stats/events?limit=50`);
    if (!response.ok) throw new Error('Failed to fetch events');
    const data = await response.json();
    const tbody = document.getElementById('events-tbody');

    if (!data || data.length === 0) {
      if (tbody) tbody.innerHTML = '<tr><td colspan="3" class="text-center text-sm">No events yet</td></tr>';
      return;
    }

    let html = '';
    data.slice(0, 20).forEach(event => {
      const time = formatUTCToLocal(event.timestamp);
      const eventClass = event.event_type === 'entry' ? 'bg-gradient-success' : 'bg-gradient-danger';
      const eventText = event.event_type.toUpperCase();

      html += `
        <tr>
          <td class="text-sm font-weight-bold">#${event.track_id}</td>
          <td><span class="badge badge-sm ${eventClass}">${eventText}</span></td>
          <td class="text-sm">${time}</td>
        </tr>
      `;
    });

    if (tbody) tbody.innerHTML = html;
  } catch (error) {
    console.error('Error loading events:', error);
    const tbody = document.getElementById('events-tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="3" class="text-center text-sm text-danger">Failed to load</td></tr>';
  }
}

// ---------- Polygon ----------
async function loadPolygon() {
  try {
    const response = await fetch(`${API_BASE}/api/config/areas`);
    if (!response.ok) throw new Error('Failed to fetch polygon');

    const data = await response.json();
    console.log('Polygon API response:', data);

    if (Array.isArray(data) && data.length > 0 && data[0].coordinates) {
      if (typeof polygonEditor !== 'undefined' && polygonEditor !== null) {
        polygonEditor.loadPoints(data[0].coordinates);
        console.log('Polygon loaded successfully with', data[0].coordinates.length, 'points');
      } else {
        console.warn('PolygonEditor not ready, retrying...');
        setTimeout(loadPolygon, 500);
      }
    } else {
      console.warn('No polygon coordinates found');
    }
  } catch (error) {
    console.error('Error loading polygon:', error);
  }
}
document.addEventListener('DOMContentLoaded', () => setTimeout(loadPolygon, 1000));

// ---------- Forecast ----------


// ---------- Clock ----------
function updateTimestamp() {
  const now = new Date();
  const timeString = now.toLocaleTimeString('id-ID', { hour12: false, timeZone: TZ });
  const timestampEl = document.getElementById('last-updated');
  if (timestampEl) timestampEl.textContent = timeString;
}
 