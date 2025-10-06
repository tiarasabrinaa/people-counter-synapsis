/**
 * Main Dashboard Logic for People Counting System (FIXED ENDPOINTS)
 */

const API_BASE = 'http://localhost:8000';

const UPDATE_INTERVAL = 2000; // 2s
const CHART_UPDATE_INTERVAL = 30000; // 30s

document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing People Counting Dashboard...');
    
    loadLiveStats();
    loadHourlyStats();
    loadRecentDetections();
    loadRecentEvents();

    setTimeout(loadPolygon, 1000);

    setInterval(loadLiveStats, UPDATE_INTERVAL);
    setInterval(loadHourlyStats, CHART_UPDATE_INTERVAL);
    setInterval(loadRecentDetections, UPDATE_INTERVAL);
    setInterval(loadRecentEvents, UPDATE_INTERVAL);
    setInterval(updateTimestamp, 1000);

    const forecastBtn = document.getElementById('btn-forecast');
    if (forecastBtn) {
        forecastBtn.addEventListener('click', generateForecast);
    }

    const refreshBtn = document.getElementById('btn-refresh');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadRecentDetections();
            loadRecentEvents();
        });
    }

    console.log('Dashboard initialized successfully');
});

/**
 * Load live statistics
 */
async function loadLiveStats() {
    try {
        const response = await fetch(`${API_BASE}/api/stats/live`);
        if (!response.ok) throw new Error('Failed to fetch live stats');

        const data = await response.json();

        document.getElementById('current-count').textContent = data.current_count || 0;
        document.getElementById('recent-entries').textContent = data.recent_entries || 0;
        document.getElementById('recent-exits').textContent = data.recent_exits || 0;
        document.getElementById('active-tracks').textContent = data.active_tracks || 0;

        const bboxCount = document.getElementById('bbox-count');
        if (bboxCount) bboxCount.textContent = `Detected: ${data.active_tracks || 0} objects`;

        document.getElementById('api-status').className = 'badge badge-sm bg-gradient-success ms-3';
        document.getElementById('api-status').textContent = 'Connected';

    } catch (error) {
        console.error('Error loading live stats:', error);
        document.getElementById('api-status').className = 'badge badge-sm bg-gradient-danger ms-3';
        document.getElementById('api-status').textContent = 'Disconnected';
    }
}

/**
 * Load hourly statistics and update chart
 */
async function loadHourlyStats() {
  try {
    const response = await fetch("http://localhost:8000/api/stats/");
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    console.log("✅ Raw hourly_data:", data.hourly_data);

    const hourlyData = data.hourly_data || [];
    if (hourlyData.length === 0) {
      console.warn("⚠️ No hourly data found");
      return;
    }

    // Format labels (jam-nya)
    const labels = hourlyData.map(d => {
      const date = new Date(d.hour);
      // Format: HH:mm, contoh "16:00"
      return date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit" });
    });

    const entries = hourlyData.map(d => d.entry_count);
    const exits = hourlyData.map(d => d.exit_count);

    const ctx = document.getElementById("hourlyChart");
    if (!ctx) {
      console.error("❌ hourlyChart canvas not found");
      return;
    }

    // Jika chart sudah ada, destroy dulu (tapi cek dulu dia valid Chart)
    if (window.hourlyChart instanceof Chart) {
      window.hourlyChart.destroy();
    }

    // Buat chart baru
    window.hourlyChart = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Entry",
            data: entries,
            borderColor: "rgba(34,197,94,1)",
            backgroundColor: "rgba(34,197,94,0.2)",
            tension: 0.4,
            fill: true,
            pointRadius: 5,
          },
          {
            label: "Exit",
            data: exits,
            borderColor: "rgba(239,68,68,1)",
            backgroundColor: "rgba(239,68,68,0.2)",
            tension: 0.4,
            fill: true,
            pointRadius: 5,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            labels: { color: "#fff" },
          },
        },
        scales: {
          x: {
            ticks: { color: "#ccc" },
            grid: { color: "rgba(255,255,255,0.1)" },
          },
          y: {
            ticks: { color: "#ccc" },
            grid: { color: "rgba(255,255,255,0.1)" },
          },
        },
      },
    });

    console.log("✅ Chart updated successfully!");
  } catch (err) {
    console.error("Error loading hourly stats:", err);
  }
}



/**
 * Load recent detections (fixed path)
 */
async function loadRecentDetections() {
    try {
        const response = await fetch(`${API_BASE}/api/stats/detections?limit=50`);
        if (!response.ok) throw new Error('Failed to fetch detections');

        const data = await response.json();
        const tbody = document.getElementById('detections-tbody');

        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="text-center text-sm">No detections yet</td></tr>';
            document.getElementById('unique-tracks').textContent = '0';
            return;
        }

        const uniqueTracks = new Set(data.map(d => d.track_id)).size;
        document.getElementById('unique-tracks').textContent = uniqueTracks;

        let html = '';
        data.slice(0, 20).forEach(detection => {
            const time = new Date(detection.timestamp).toLocaleTimeString();
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

        tbody.innerHTML = html;

    } catch (error) {
        console.error('Error loading detections:', error);
        document.getElementById('detections-tbody').innerHTML =
            '<tr><td colspan="4" class="text-center text-sm text-danger">Failed to load</td></tr>';
    }
}

/**
 * Load recent entry/exit events (fixed path)
 */
async function loadRecentEvents() {
    try {
        const response = await fetch(`${API_BASE}/api/stats/events?limit=50`);
        if (!response.ok) throw new Error('Failed to fetch events');

        const data = await response.json();
        const tbody = document.getElementById('events-tbody');

        if (!data || data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center text-sm">No events yet</td></tr>';
            return;
        }

        let html = '';
        data.slice(0, 20).forEach(event => {
            const time = new Date(event.timestamp).toLocaleString();
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

        tbody.innerHTML = html;

    } catch (error) {
        console.error('Error loading events:', error);
        document.getElementById('events-tbody').innerHTML =
            '<tr><td colspan="3" class="text-center text-sm text-danger">Failed to load</td></tr>';
    }
}

/**
 * Load polygon (optional)
 */
async function loadPolygon() {
    try {
        const response = await fetch('http://localhost:8000/api/config/areas');
        if (!response.ok) throw new Error('Failed to fetch polygon');

        const data = await response.json();
        console.log('Polygon API response:', data);

        if (data.length > 0 && data[0].coordinates) {
            if (typeof polygonEditor !== 'undefined' && polygonEditor !== null) {
                // FE sekarang pakai method baru yang ada di PolygonEditor
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

// panggil loadPolygon di DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(loadPolygon, 1000);
});

/**
 * Generate forecast
 */
async function generateForecast() {
    const btn = document.getElementById('btn-forecast');
    const originalText = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="ni ni-settings-gear-65 me-2"></i>Generating...';

        const response = await fetch(`${API_BASE}/api/stats/forecast`, { method: 'POST' });
        if (!response.ok) throw new Error('Failed to generate forecast');

        const data = await response.json();

        const forecastInfo = document.getElementById('forecast-info');
        forecastInfo.textContent = `Forecast generated: ${data.predictions.length} hours ahead`;

        if (data.predictions && data.predictions.length > 0 && typeof chartManager !== 'undefined') {
            chartManager.createForecastChart('chart-forecast', data.predictions);
        }

        btn.innerHTML = '<i class="ni ni-check-bold me-2"></i>Forecast Generated';
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }, 2000);

    } catch (error) {
        console.error('Error generating forecast:', error);
        btn.innerHTML = '<i class="ni ni-fat-remove me-2"></i>Failed';
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }, 2000);
    }
}

/**
 * Update timestamp display
 */
function updateTimestamp() {
    const now = new Date();
    const timeString = now.toLocaleTimeString();
    const timestampEl = document.getElementById('last-updated');
    if (timestampEl) timestampEl.textContent = timeString;
}
